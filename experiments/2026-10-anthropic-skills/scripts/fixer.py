# Copyright (c) 2026 Wneil2020 and the holon skill contributors. Released under the MIT License.
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403  REPO, H, HOLON_PY, ORG, WORK, TREE
# Parallel replay fixer: K candidate edits per iteration, each evaluated in its own tree copy; keep best.
import json, sys, os, re, shutil, subprocess, pprint, importlib, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from llm import chat
from paths import H, TREE as T
UP = {d['name']: d['description'] for d in json.load(open('upstream_descs.json'))}
def path_of(C, n):
    p = C[n][0]; return n if p == "." else os.path.join(path_of(C, p), n)
def write_cards(root, C, syn):
    for n,(p,desc,trig) in C.items():
        f = os.path.join(root, path_of(C,n), "SKILL.md"); t = open(f, encoding="utf-8").read()
        end = t.index("\n---", 4); fm, body = t[4:end], t[end+4:]
        fm = re.sub(r'^description:.*$', 'description: "%s"' % desc.replace('"',"'"), fm, count=1, flags=re.M)
        fm = re.sub(r'(  holon-triggers: \|\n)(    .*\n?)+', lambda m: m.group(1) + "".join("    %s\n" % s for s in trig), fm + "\n").rstrip("\n")
        open(f, "w", encoding="utf-8").write("---\n" + fm + "\n---" + body)
    open(os.path.join(root, "synonyms.md"), "w", encoding="utf-8").write("\n".join(syn) + "\n")
def run(root):
    subprocess.run(["python3", f"{H}/scripts/holon.py", "sync", root], capture_output=True)
    v = subprocess.run(["python3", f"{H}/scripts/holon.py", "validate", root], capture_output=True, text=True).stdout
    l = subprocess.run(["python3", f"{H}/organizer/scripts/organizer_cli.py", "lint", root], capture_output=True, text=True).stdout
    r = subprocess.run(["python3", f"{H}/organizer/scripts/organizer_cli.py", "replay", root], capture_output=True, text=True).stdout
    m = re.search(r"replay: (\d+)/(\d+)", r); e = re.search(r"lint: (\d+) errors, (\d+) warnings", l)
    ok = "valid and in sync" in v
    return dict(passed=int(m.group(1)) if m else 0, total=int(m.group(2)) if m else 0, err=int(e.group(1)) if e else 99, warn=int(e.group(2)) if e else 99, valid=ok,
                fails=[x for x in r.splitlines() if "FAIL" in x], lint=[x for x in l.splitlines() if x.startswith("[E]") or x.startswith("[W]")])
def evaluate(k, C, syn):
    root = f"/tmp/cand{k}/lib"; shutil.rmtree(f"/tmp/cand{k}", ignore_errors=True)
    shutil.copytree(T, root, ignore=shutil.ignore_patterns("canvas-fonts", "*.ttf"))
    write_cards(root, C, syn); return run(root)
def propose(C, syn, state, k, protect):
    q = f"""You maintain a hierarchical skill tree. Each card: name -> (parent, description, [2 positive trigger sentences, 1 negative 'X should go to <path>']). A lexical replay checks triggers: cover words (after synonyms.md folding, substring match, case-insensitive) decide routing level by level; at the root, two skills taking one sentence is an ambiguity failure; a parent's positive sentence must contain cover words of two or more children. Skills 'editing' and 'organizer' (holon's own, not editable) cover: create skill, sync, routing table, validate, dry-run / absorb, duplicate, boundary, place.
Description rules: <= 200 chars, "Use when <situation>: covers w1, w2; excludes w3", <= 5 cover words, English. Description quality matters most: AI agents route by reading it; keep each skill's meaning faithful to its author's intent:
{json.dumps(UP, ensure_ascii=False)}
Cards: {json.dumps(C, ensure_ascii=False)}
synonyms.md lines: {json.dumps(syn, ensure_ascii=False)}
Replay failures: {json.dumps(state['fails'], ensure_ascii=False)}
Lint [E]/[W]: {json.dumps(state['lint'], ensure_ascii=False)}
Fix as many failures as possible with small, faithful edits (edit triggers that were badly chosen, add excludes, adjust cover words, add/remove a synonym line). Do not weaken descriptions of these skills unless needed: {protect}. Candidate #{k}.
Reply JSON: {{"cards": {{"name": {{"description":..., "triggers":[3]}}}}, "synonyms": [full new list of lines, first line is the comment header]}} -- include only changed cards."""
    try:
        o = chat([{"role":"user","content":q}], temperature=0.8, retries=1, timeout=420)
        d = json.loads(o[o.index('{'):o.rindex('}')+1])
        C2 = dict(C)
        for n, v in d.get("cards", {}).items():
            if n in C2 and len(v.get("description","")) <= 200 and len(v.get("triggers",[])) == 3:
                C2[n] = (C2[n][0], v["description"], v["triggers"])
        syn2 = d.get("synonyms") or syn
        return C2, syn2, list(d.get("cards", {}))
    except Exception as e:
        return None
def score(s): return (s['valid'] and s['err'] == 0, s['passed'], -s['warn'])
import cards; C = dict(cards.CARDS); syn = open(f"{T}/synonyms.md", encoding="utf-8").read().rstrip("\n").split("\n")
best = evaluate(99, C, syn); print("start", best['passed'], best['total'], best['err'], best['warn'], flush=True)
K = int(sys.argv[1]) if len(sys.argv) > 1 else 12; ITER = int(sys.argv[2]) if len(sys.argv) > 2 else 5
protect = sys.argv[3] if len(sys.argv) > 3 else ""
for it in range(ITER):
    props = [p for p in cf.ThreadPoolExecutor(K).map(lambda k: propose(C, syn, best, k, protect), range(K)) if p]
    evs = list(cf.ThreadPoolExecutor(K).map(lambda a: evaluate(a[0], a[1][0], a[1][1]), enumerate(props)))
    i = max(range(len(evs)), key=lambda i: score(evs[i])) if evs else None
    if i is None or score(evs[i]) <= score(best):
        print("iter", it, "no improvement", [ (e['passed'], e['err']) for e in evs], flush=True); continue
    C, syn, best = props[i][0], props[i][1], evs[i]
    print("iter", it, "->", best['passed'], best['total'], best['err'], best['warn'], "changed", props[i][2], flush=True)
    if best['passed'] == best['total'] and best['err'] == 0: break
open('cards.py','w').write('# name: (parent, description, [pos1,pos2,neg])\nCARDS = ' + pprint.pformat(C, width=200) + '\n')
open(f"{T}/synonyms.md", "w", encoding="utf-8").write("\n".join(syn) + "\n")
print("final", best['passed'], best['total'], best['err'], best['warn']); print("\n".join(best['fails']))
