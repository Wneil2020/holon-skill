# Copyright (c) 2026 Wneil2020 and the holon skill contributors. Released under the MIT License.
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403  REPO, H, HOLON_PY, ORG, WORK, TREE
import json, sys, os, random, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from llm import chat
UP = json.load(open('upstream_descs.json'))
PERSONAS = ["startup founder","product manager","backend engineer","frontend engineer","data analyst","finance controller","HR manager",
 "marketing lead","designer","teacher","PhD student","undergrad","lawyer","sales rep","customer support lead","devops engineer",
 "indie game dev","consultant","journalist","executive assistant","researcher at an AI lab","Slack community manager","QA engineer",
 "nonprofit coordinator","small shop owner","technical writer","ML engineer","solo developer learning AI","CTO","recruiter"]
STYLES = [("English, terse, lowercase, typos ok","en"),("English, polite and wordy","en"),("Simplified Chinese, casual chat style","zh"),
 ("Simplified Chinese mixed with English tech terms","zh"),("Simplified Chinese, workplace formal","zh"),("English, non-native speaker","en")]
def job(i):
    rnd = random.Random(i)
    p = PERSONAS[i % len(PERSONAS)]; st, lang = STYLES[i % len(STYLES)]
    focus = rnd.sample([d['name'] for d in UP], 6)
    prompt = f"""You are a {p}. You use an AI agent at work. Write 25 different requests you'd actually type to it this month.
Style: {st}.
The agent has the skills listed below, but you don't know their names: write naturally, never name a skill, avoid copying wording from descriptions.
Mix: about 14 requests that one of these skills clearly fits (lean toward: {', '.join(focus)}), 4 that need two of them, 7 ordinary requests none fits (coding bugs, questions, emails, Google Docs/Sheets, other vendors' APIs, near-misses).
Output ONLY a JSON list of strings.
SKILLS: {json.dumps(UP, ensure_ascii=False)}"""
    try:
        out = chat([{"role":"user","content":prompt}], temperature=0.9)
        arr = json.loads(out[out.index('['):out.rindex(']')+1])
        return [{"request": s, "lang": lang, "persona": p} for s in arr if isinstance(s, str)]
    except Exception as e:
        print("fail", i, e, file=sys.stderr); return []
N = int(sys.argv[1])
with cf.ThreadPoolExecutor(40) as ex:
    res = [r for rs in ex.map(job, range(N)) for r in rs]
seen=set(); out=[]
for r in res:
    k=r['request'].strip().lower()
    if k not in seen: seen.add(k); out.append(r)
json.dump(out, open('pool.json','w'), ensure_ascii=False, indent=1)
print(len(out))
