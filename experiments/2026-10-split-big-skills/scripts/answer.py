"""Answer every question under three conditions and judge.
full: the agent gets the whole original SKILL.md.
holon / heading: the agent gets the split skill's SKILL.md and may open files in the skill dir (up to 3 rounds).
Reached: the evidence lines (non-blank) all appear in what the agent read. Correct: judged against the reference answer."""
from common import *
import concurrent.futures as cf,glob
NAV="""You are an agent using a skill. The skill's files are in a folder; you have read its SKILL.md below.
Task: {q}
If what you have read so far answers the task, reply {{"answer":"<short answer>"}}.
Otherwise open more files from the folder, at most 3 at a time: {{"open":["path", ...]}}. Open only what you need.
Files in the folder: {files}
Reply with JSON only.

{read}"""
FULL="""You are an agent using a skill. Its SKILL.md is below.
Task: {q}
Reply with JSON only: {{"answer":"<short answer>"}}

{read}"""
JUDGE="""Question: {q}
Reference answer: {ref}
Source text the reference comes from:
{ev}
Candidate answer: {cand}
Does the candidate give the reference's key fact (same command/function/parameter/number/rule; wording may differ; extra correct detail is fine)?
Reply JSON only: {{"correct": true|false}}"""
def ev_lines(q):
    a,b=map(int,q['lines'].split('-')); L=open(f"{SRC}/{q['skill']}/SKILL.md").read().splitlines()
    return [l for l in L[a-1:b] if l.strip()]
def reached(ev,text):
    return all(l.strip() in text for l in ev)
def files_of(t):
    return sorted(os.path.relpath(p,t) for p in glob.glob(f'{t}/**/*.md',recursive=True) if os.path.relpath(p,t)!='SKILL.md')
def do(cond,q):
    s=q['skill']
    if cond=='none':
        read=''; opened=[]
        ans=ask_json([{"role":"user","content":"Answer from what you already know; no files are available.\nTask: "+q['q']+'\nReply with JSON only: {"answer":"<short answer>"}'}],timeout=120).get('answer','')
    elif cond=='full':
        text=open(f'{SRC}/{s}/SKILL.md').read(); read=text; opened=['SKILL.md']
        r=ask_json([{"role":"user","content":FULL.format(q=q['q'],read=text)}],timeout=180); ans=r.get('answer','')
    else:
        t=f'{HERE}/trees/{cond}/{s}'; avail=files_of(t)
        read='--- SKILL.md ---\n'+open(f'{t}/SKILL.md').read(); opened=['SKILL.md']; ans=''
        for rnd in range(4):
            r=ask_json([{"role":"user","content":NAV.format(q=q['q'],files=', '.join(avail),read=read)}],timeout=180)
            if 'answer' in r or rnd==3:
                ans=r.get('answer','') if 'answer' in r else ''
                if rnd==3 and not ans:
                    ans=ask_json([{"role":"user","content":FULL.format(q=q['q'],read=read)}],timeout=180).get('answer','')
                break
            new=[p for p in r.get('open',[])[:3] if p in avail and p not in opened]
            if not new:
                ans=ask_json([{"role":"user","content":FULL.format(q=q['q'],read=read)}],timeout=180).get('answer',''); break
            for p in new: read+=f'\n--- {p} ---\n'+open(f'{t}/{p}').read(); opened.append(p)
    ev=ev_lines(q)
    j=ask_json([{"role":"user","content":JUDGE.format(q=q['q'],ref=q['answer'],ev='\n'.join(ev),cand=ans)}],timeout=120)
    return {'id':q['id'],'skill':s,'cond':cond,'answer':ans,'opened':opened,'chars':len(read),
            'reached':reached(ev,read),'correct':bool(j.get('correct'))}
if __name__=='__main__':
    conds=sys.argv[1].split(',') if len(sys.argv)>1 else ['full','heading','holon']
    tag=sys.argv[2] if len(sys.argv)>2 else 'run1'
    qs=json.load(open(f'{HERE}/questions.json'))
    jobs=[(c,q) for c in conds for q in qs]
    out=[]
    def safe(a):
        try: return do(*a)
        except Exception as e: return {'id':a[1]['id'],'skill':a[1]['skill'],'cond':a[0],'error':str(e)[:200]}
    with cf.ThreadPoolExecutor(int(os.environ.get("JOBS","8"))) as ex:
        for i,r in enumerate(ex.map(safe,jobs)):
            out.append(r)
            if i%40==0: print(i,len(jobs),flush=True)
    os.makedirs(f'{HERE}/results',exist_ok=True)
    json.dump(out,open(f'{HERE}/results/{tag}.json','w'),indent=1,ensure_ascii=False)
