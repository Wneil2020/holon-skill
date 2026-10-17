"""Write task questions from the ORIGINAL SKILL.md, before any split exists."""
from common import *
import concurrent.futures as cf
P="""Below is a SKILL.md for an AI agent, with line numbers.
Write {n} questions an agent might face while doing real work where this skill applies, whose answer is stated in this file.
Rules:
- This is one part of a longer file; spread the questions over this whole part.
- Phrase each as a user's task or a concrete question ("I have a DOI list and need BibTeX in one file; which command and flag?"), never by quoting a heading or saying "according to section X".
- The answer must be short and checkable: a command, a function name, a parameter, a number, a rule.
- Give the smallest line range that contains the answer.
Return JSON only: {{"questions":[{{"q":"...","answer":"...","lines":"A-B"}}]}}

FILE:
{text}"""
W=4; PER=6
def window(args):
    s,w=args
    lines=open(f'{SRC}/{s}/SKILL.md').read().splitlines()
    n=len(lines); a=w*n//W; b=(w+1)*n//W
    part='\n'.join('%5d  %s'%(i+1,lines[i]) for i in range(a,b))
    out=ask_json([{"role":"user","content":P.format(n=PER,text=part)}],timeout=240)['questions'][:PER]
    return [dict(q,skill=s,window=w) for q in out]
def run(s):
    with cf.ThreadPoolExecutor(W) as ex: parts=list(ex.map(window,[(s,w) for w in range(W)]))
    out=[q for p in parts for q in p]
    for i,q in enumerate(out): q['id']=f'{s}#{i}'
    return out
qs=[]
with cf.ThreadPoolExecutor(4) as ex:
    for r in ex.map(run,SKILLS): qs+=r; print(r[0]['skill'],len(r),flush=True)
json.dump(qs,open(f'{HERE}/questions.json','w'),indent=1,ensure_ascii=False)
