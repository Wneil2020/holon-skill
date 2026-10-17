# Copyright (c) 2026 Wneil2020 and the holon skill contributors. Released under the MIT License.
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403  REPO, H, HOLON_PY, ORG, WORK, TREE
# 3 independent labelers, majority vote, using upstream full descriptions (ground truth = authors' intent)
import json, sys, os, re, concurrent.futures as cf
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from llm import chat
UP = json.load(open('upstream_descs.json')); NAMES={d['name'] for d in UP}
listing="\n".join(f"- {d['name']}: {d['description']}" for d in UP)
def lab(req, seed):
    q=f"""Skill library (name: author's description):
{listing}

Request: {req}

Which skills must the agent read to do this request well? Follow each description's own scope and exclusions strictly. A skill that would only be tangentially useful does not count. Answer JSON {{"skills":[...]}} (empty if none). Labeler #{seed}."""
    out=chat([{"role":"user","content":q}],temperature=0.6)
    s=json.loads(re.search(r'\{.*\}',out,re.S).group(0))["skills"]
    return tuple(sorted(x for x in s if x in NAMES))
def one(r):
    try:
        votes=[lab(r['request'],k) for k in range(3)]
    except Exception as e:
        return None
    c=Counter(votes).most_common(1)[0]
    r=dict(r); r['votes']=[list(v) for v in votes]
    r['label']=list(c[0]); r['agree']=c[1]
    return r
pool=json.load(open(sys.argv[1]))
with cf.ThreadPoolExecutor(40) as ex:
    res=[x for x in ex.map(one,pool) if x]
json.dump(res,open(sys.argv[2],'w'),ensure_ascii=False,indent=1)
print(len(res),Counter(x['agree'] for x in res))
