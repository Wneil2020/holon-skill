# Copyright (c) 2026 Wneil2020 and the holon skill contributors. Released under the MIT License.
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403  REPO, H, HOLON_PY, ORG, WORK, TREE
import json, sys, os, re, subprocess, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(__file__))
from llm import chat
from paths import TREE, ORG as O
UP = json.load(open('upstream_descs.json'))
NAMES = {d['name'] for d in UP}
sents = json.load(open(os.environ.get("SENTS","sentences.json")))
import cards; CARDS=cards.CARDS
SYS = "You are an AI agent with a skills folder. Decide which skill files to read before doing the task. Reply with JSON only."

def parse(out):
    m = re.search(r'\{.*\}', out, re.S)
    return json.loads(m.group(0))

def flat(task, descs):
    listing = "\n".join("- %s: %s" % (n, d) for n, d in descs)
    q = ("Available skills (name: description):\n%s\n\nUser task: %s\n\nWhich skills, if any, would you load before doing this task? "
         "Load a skill only if its description says it applies. Reply {\"load\": [names]} (empty list if none).") % (listing, task)
    return [n for n in parse(chat([{"role":"system","content":SYS},{"role":"user","content":q}]))["load"] if n in NAMES]

def tree(task):
    visited, leaves, frontier, files = [], set(), ["."], 0
    while frontier and len(visited) < 8:
        node = frontier.pop(0)
        txt = open(os.path.join(TREE, node, "SKILL.md"), encoding="utf-8").read()
        files += 1
        visited.append(node)
        if node != ".":
            n = node.split("/")[-1]
            if n in NAMES: leaves.add(n)
        if "<!-- sub-skills -->" not in txt or "## Sub-skills" not in txt:
            continue
        q = ("You have just loaded this SKILL.md (path: %s):\n\n%s\n\nUser task: %s\n\nFollowing the reading rules, which sub-skill folders listed in its routing table do you read next? "
             "Reply {\"read\": [folder names exactly as listed, e.g. \"pdf\"]} or {\"read\": []} to stay here.") % (node, txt, task)
        try:
            nxt = parse(chat([{"role":"system","content":SYS},{"role":"user","content":q}]))["read"]
        except Exception as e:
            nxt = []
        for c in nxt:
            c = c.strip().strip('/').split('/')[-1]
            p = c if node == "." else node + "/" + c
            if os.path.isfile(os.path.join(TREE, p, "SKILL.md")) and p not in visited and p not in frontier:
                frontier.append(p)
    return sorted(leaves), visited, files

def lexical(task):
    out = subprocess.run(["python3", O, "route", TREE, task], capture_output=True, text=True).stdout
    m = re.search(r"lands on: (\S+)", out)
    land = m.group(1) if m else "?"
    n = land.split("/")[-1]
    return land, ([n] if n in NAMES else [])

new_descs = []
for n in sorted(NAMES):
    new_descs.append((n, CARDS[n][1]))
old_descs = [(d['name'], d['description']) for d in UP]

def one(s):
    t = s['request']
    r = {"id": s['id'], "kind": s['kind'], "label": sorted(s['label']), "request": t}
    if os.environ.get('FLAT'):
        try: r['flat_old'] = sorted(flat(t, old_descs))
        except Exception as e: r['flat_old'] = ["ERR"]
        try: r['flat_new'] = sorted(flat(t, new_descs))
        except Exception as e: r['flat_new'] = ["ERR"]
    try:
        r['tree'], r['tree_path'], r['tree_files'] = tree(t)
    except Exception as e: r['tree'] = ["ERR"]
    r['lex_land'], r['lex'] = lexical(t)
    return r

with cf.ThreadPoolExecutor(50) as ex:
    res = list(ex.map(one, sents))
json.dump(res, open(sys.argv[1] if len(sys.argv) > 1 else 'results.json', 'w'), ensure_ascii=False, indent=1)
print("done", len(res))
