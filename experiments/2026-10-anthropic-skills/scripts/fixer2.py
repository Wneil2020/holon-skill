# Copyright (c) 2026 Wneil2020 and the holon skill contributors. Released under the MIT License.
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403  REPO, H, HOLON_PY, ORG, WORK, TREE
# One small agent per replay failure; evaluate each edit alone; greedily combine improving edits.
import json, sys, os, re, pprint, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from llm import chat
exec(open(os.path.join(HERE, 'fixer.py')).read().split("def propose(")[0])  # write_cards/run/evaluate/path_of/UP/T/H
import cards; C = dict(cards.CARDS); syn = open(f"{T}/synonyms.md", encoding="utf-8").read().rstrip("\n").split("\n")
HOLON = "editing covers: create skill, sync, routing table, validate, dry-run; excludes absorb, duplicate. organizer covers: absorb, duplicate, boundary, place; excludes sync, validate (both fixed, not editable)."
def involved(line):
    ns = {n for n in C if re.search(r'(?<![\w-])' + re.escape(n) + r'(?![\w-])', line)}
    for n in list(ns):
        if C[n][0] != '.': ns.add(C[n][0])
    return sorted(ns)
def fix_one(args):
    k, line, C, syn = args
    ns = involved(line)
    sub = {n: C[n] for n in ns}
    q = f"""Lexical replay failure in a hierarchical skill tree:
{line}
Rules: routing folds synonyms.md, then matches cover words as case-insensitive substrings (latin words need word boundaries), level by level from the root; at the root two skills taking a sentence = ambiguity; a parent's positive example must contain cover words of 2+ children; 'excludes' words block a skill. Each card = (parent, description, [2 positive trigger sentences, 1 negative 'X should go to <path>']). Description: <=200 chars, "Use when <situation>: covers w1, w2; excludes w3", <=5 cover words, English, faithful to the author's intent.
{HOLON}
Authors' intent: {json.dumps({n: UP.get(n, 'parent grouping') for n in ns}, ensure_ascii=False)}
Involved cards: {json.dumps(sub, ensure_ascii=False)}
synonyms.md: {json.dumps(syn, ensure_ascii=False)}
Make the smallest faithful fix. Often the trigger sentence itself is the problem (rewrite it to read like a real request that uses this skill's cover words), or an excludes word is missing. Reply JSON: {{"cards": {{"name": {{"description":..., "triggers":[3]}}}}, "add_synonyms": ["canon, alias"], "why": "..."}} with only changed cards."""
    try:
        o = chat([{"role":"user","content":q}], temperature=0.7, retries=2, timeout=110)
        return json.loads(o[o.index('{'):o.rindex('}')+1])
    except Exception as e:
        return None
def apply(C, syn, d):
    C2 = dict(C); syn2 = list(syn)
    for n, v in (d.get("cards") or {}).items():
        if n in C2 and isinstance(v, dict) and len(v.get("description","")) <= 200 and len(v.get("triggers",[])) == 3:
            C2[n] = (C2[n][0], v["description"].replace('"', "'"), v["triggers"])
    for g in d.get("add_synonyms") or []:
        if isinstance(g, str) and ',' in g and g not in syn2: syn2.append(g)
    return C2, syn2
def sc(s): return (s['valid'] and s['err'] == 0, s['passed'], -s['warn'])
best = evaluate(98, C, syn); print("start", best['passed'], best['total'], flush=True)
ROUNDS = int(sys.argv[1]) if len(sys.argv) > 1 else 3; PER = int(sys.argv[2]) if len(sys.argv) > 2 else 3
for rd in range(ROUNDS):
    jobs = [(i, line, C, syn) for i, line in enumerate(best['fails']) for _ in range(PER)]
    props = [p for p in cf.ThreadPoolExecutor(60).map(fix_one, jobs) if p]
    cand = [apply(C, syn, p) for p in props]
    evs = list(cf.ThreadPoolExecutor(16).map(lambda a: evaluate(a[0], *a[1]), enumerate(cand)))
    good = sorted([(sc(e), i) for i, e in enumerate(evs) if sc(e) > sc(best)], reverse=True)
    print("round", rd, "proposals", len(props), "improving", len(good), flush=True)
    for _, i in good:  # greedy combine
        C2, syn2 = apply(C, syn, props[i]); e = evaluate(97, C2, syn2)
        if sc(e) > sc(best):
            C, syn, best = C2, syn2, e; print("  accept", props[i].get('why','')[:120], "->", best['passed'], flush=True)
    if best['passed'] == best['total']: break
open('cards.py','w').write('# name: (parent, description, [pos1,pos2,neg])\nCARDS = ' + pprint.pformat(C, width=200) + '\n')
open(f"{T}/synonyms.md", "w", encoding="utf-8").write("\n".join(syn) + "\n")
print("final", best['passed'], best['total'], best['err'], best['warn']); print("\n".join(best['fails']))
