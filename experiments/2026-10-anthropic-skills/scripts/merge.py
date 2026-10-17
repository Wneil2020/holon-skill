# Copyright (c) 2026 Wneil2020 and the holon skill contributors. Released under the MIT License.
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403  REPO, H, HOLON_PY, ORG, WORK, TREE
import json, sys, re, pprint, shutil, concurrent.futures as cf
from llm import chat
sys.path.insert(0, '.')
import cards
C = dict(cards.CARDS); P = json.load(open(sys.argv[1]))
from paths import TREE
SYNF = os.path.join(TREE, 'synonyms.md')
shutil.copy('cards.py', 'cards.bak.py'); shutil.copy(SYNF, 'synonyms.bak.md')
syn_lines = open(SYNF, encoding='utf-8').read().rstrip('\n').split('\n')
owned = {}  # alias -> owner, to drop conflicting groups
for l in syn_lines[1:]:
    for w in l.split(','): owned[w.strip().lower()] = 'existing'
skip = set(sys.argv[2:])
ALL = {k: v[1] for k, v in C.items()}
def vote(n, canon, ws, k):
    q = f"""A lexical router folds each alias to '{canon}' in every user request before matching skill cover words. Skill '{n}': {ALL[n]}
Other skills: {json.dumps({a:b for a,b in ALL.items() if a!=n})}
Aliases: {json.dumps(ws, ensure_ascii=False)}
Keep an alias only if a request containing it is almost always about '{n}' (it would rarely appear in requests for other skills or for unrelated work). Reviewer #{k}. Reply JSON {{"keep":[...]}}"""
    try:
        o = chat([{"role":"user","content":q}], temperature=0.5)
        return set(json.loads(re.search(r'\{.*\}', o, re.S).group(0))["keep"])
    except Exception: return set()
def review(n, canon, ws):
    if not ws: return ws
    vs = list(cf.ThreadPoolExecutor(3).map(lambda k: vote(n, canon, ws, k), range(3)))
    kept = [w for w in ws if sum(w in v for v in vs) >= 2]
    print('review', flush=True) if False else print('review', n, canon, 'kept', kept, 'dropped', [w for w in ws if w not in kept])
    return kept
cands = []
for n, v in P.items():
    p = v['prop']
    if n in skip or 'description' not in p: continue
    for g in p.get('synonyms', [])[:2]:
        ws = [w.strip() for w in re.split(r'[,，]', g) if w.strip()]
        if len(ws) >= 2: cands.append((n, ws[0], tuple(ws[1:])))
RV = dict(zip(cands, cf.ThreadPoolExecutor(40).map(lambda c: review(*c[:2], list(c[2])), cands)))
for n, v in P.items():
    p = v['prop']
    if n in skip or 'description' not in p: continue
    d = p['description'].replace('"', "'")
    t = p.get('triggers') or C[n][2]
    if len(d) <= 200 and len(t) == 3:
        C[n] = (C[n][0], d, t)
    for g in p.get('synonyms', [])[:2]:
        ws = [w.strip() for w in re.split(r'[,，]', g) if w.strip()]
        if len(ws) < 2: continue
        canon = ws[0].lower()
        if canon in owned and owned[canon] != n:
            # extend existing group only if it's ours
            continue
        new = [w for w in ws[1:] if w.lower() not in owned and len(w) >= 2]
        new = [w for w in new if w in RV.get((n, ws[0], tuple(ws[1:])), [])]
        if not new: continue
        for w in [canon] + new: owned[w.lower()] = n
        syn_lines.append(', '.join([ws[0]] + new))
open(SYNF, 'w', encoding='utf-8').write('\n'.join(syn_lines) + '\n')
open('cards.py', 'w').write('# name: (parent, description, [pos1,pos2,neg])\nCARDS = ' + pprint.pformat(C, width=200) + '\n')
print('merged; synonyms lines', len(syn_lines))
