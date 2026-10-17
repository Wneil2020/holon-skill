# Copyright (c) 2026 Wneil2020 and the holon skill contributors. Released under the MIT License.
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403  REPO, H, HOLON_PY, ORG, WORK, TREE
# Round of owner agents. Each owner = one skill. Owner spawns adversary sub-agents (boundary cases),
# then proposes a revised card + synonym groups from its failures. Output: proposals_rN.json, adv_rN.json
import json, sys, os, re, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from llm import chat
import importlib, cards; importlib.reload(cards)
CARDS = cards.CARDS
UP = {d['name']: d['description'] for d in json.load(open('upstream_descs.json'))}
rnd = sys.argv[1]; res = json.load(open(sys.argv[2]))
import subprocess
REPLAY = subprocess.run(['python3',ORG,'replay',TREE],capture_output=True,text=True).stdout.splitlines()
LINT = subprocess.run(['python3',ORG,'lint',TREE],capture_output=True,text=True).stdout.splitlines()
SYN = open(os.path.join(TREE, 'synonyms.md'), encoding='utf-8').read()
POOL = cf.ThreadPoolExecutor(60)
def J(out, kind='{'):
    a, b = ('{', '}') if kind == '{' else ('[', ']')
    return json.loads(out[out.index(a):out.rindex(b)+1])
def lexset(r):
    land = r['lex_land'].split('/')[-1]
    return {land} if land in CARDS else set()
def neighbors(n):
    p = CARDS[n][0]
    sib = [k for k, v in CARDS.items() if v[0] == p and k != n]
    return {k: CARDS[k][1] for k in sib + ([p] if p != '.' else [])}
def adversary(n, k):
    nb = neighbors(n)
    q = f"""You attack the boundary of skill "{n}". Its author's intent: {UP.get(n, CARDS[n][1])}
Neighbor skills: {json.dumps({x: UP.get(x, d) for x, d in nb.items()}, ensure_ascii=False)}
Write 8 realistic user requests (attack angle #{k}: {['near-misses that should NOT go to it','requests that SHOULD go to it but use unexpected everyday wording','Chinese requests (中文, natural workplace phrasing) on its boundary'][k]}). Never name skills. JSON list of strings only."""
    try: return [{"request": s, "lang": "zh" if k == 2 else "en", "persona": f"adv:{n}"} for s in J(chat([{"role":"user","content":q}], temperature=0.9), '[')]
    except Exception: return []
def owner(n):
    advf = [POOL.submit(adversary, n, k) for k in range(3)]
    fn = [r for r in res if n in r['label'] and n not in r['tree']]
    fp = [r for r in res if n in r['tree'] and n not in r['label']]
    lfn = [r for r in res if n in r['label'] and n not in lexset(r)]
    lfp = [r for r in res if n in lexset(r) and n not in r['label']]
    def ex(rs, m=12): return [{"request": r['request'], "should_load": r['label'], "tree_loaded": r['tree'], "lexical_landed": r['lex_land']} for r in rs[:m]]
    p, desc, trig = CARDS[n]
    q = f"""You own skill "{n}" in a hierarchical skill tree (parent: {p}). Agents choose skills by reading one-line descriptions in a routing table, level by level; a coarse lexical checker also matches cover words (after folding synonyms.md) as substrings.
Author's original intent: {UP.get(n, '(parent node grouping its children)')}
Current card: description="{desc}"  triggers={json.dumps(trig, ensure_ascii=False)}
Neighbors: {json.dumps(neighbors(n), ensure_ascii=False)}
Current synonyms.md:
{SYN}
Agent-routing misses (should load, didn't): {json.dumps(ex(fn), ensure_ascii=False)}
Agent-routing false loads: {json.dumps(ex(fp), ensure_ascii=False)}
Lexical misses: {json.dumps(ex(lfn, 15), ensure_ascii=False)}
Lexical false landings: {json.dumps(ex(lfp), ensure_ascii=False)}

Replay/lint lines that mention you (FAIL/[E]/[W] must be fixed; your triggers are replayed lexically: your 2 positive sentences must lexically reach you, the negative must not land on you and should reach its target):
{json.dumps([l for l in REPLAY+LINT if (n in l) and not l.strip().startswith('ok') and ('FAIL' in l or '[E]' in l or '[W]' in l or 'NOTE' in l)][:12], ensure_ascii=False)}

Propose the minimal change. Hard rules: description <= 200 chars, form "Use when <situation>: covers w1, w2; excludes w3" (excludes optional), at most 5 cover words, each cover word a phrase that really appears in requests for this skill and rarely elsewhere (substring match! avoid short or generic words like 'doc', 'file', 'app'), English only in description. triggers: exactly 3 lines: 2 sentences it should take, 1 sentence it should not, ending with ' should go to <path>' where path is the neighbor's tree path like office-docs/docx or web/frontend-design or a top-level name. Synonym groups: lines 'canonical, alias, alias' where canonical should be one of YOUR cover words; aliases may be Chinese or English everyday wordings seen in the misses; never alias a word that belongs to another skill; an alias must be specific: forbidden are words that also appear in many requests for other skills or for no skill (e.g. email, tool, connect, wrap, skill, 通知, 学习, 工具, 演示); a negative-example target must be an existing tree path; keep it to at most 2 groups, max 8 aliases each. If no change helps, return the current card.
Reply JSON: {{"description":..., "triggers":[...3], "synonyms":["canon, a, b"], "why": "one line"}}"""
    try: prop = J(chat([{"role":"user","content":q}], temperature=0.3))
    except Exception as e: prop = {"error": str(e)}
    adv = [x for f in advf for x in f.result()]
    return n, prop, adv, len(fn), len(fp), len(lfn), len(lfp)
names = [n for n in CARDS]
out = list(cf.ThreadPoolExecutor(30).map(owner, names))
json.dump({n: dict(prop=p, fn=a, fp=b, lfn=c, lfp=d) for n, p, _, a, b, c, d in out}, open(f'proposals_r{rnd}.json', 'w'), ensure_ascii=False, indent=1)
json.dump([x for o in out for x in o[2]], open(f'adv_r{rnd}.json', 'w'), ensure_ascii=False, indent=1)
for n, p, adv, a, b, c, d in out: print(n, f"fn={a} fp={b} lfn={c} lfp={d}", "|", p.get('why', p.get('error', ''))[:100])
