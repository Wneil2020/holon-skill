"""Run one real task with a coding agent under several ways of giving it the skill; grade and log tokens."""
import os,sys,json,shutil,concurrent.futures as cf
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
from agent import run
from grade import grade
from verify import verify
TAG=sys.argv[1]; MODES=sys.argv[2].split(','); REPS=int(sys.argv[3])
TASK=("Add a dismissible announcement banner to the Tessel web app, as a new part named `announcement-banner`. "
      "It shows a short info message across the top of the page with a close button; once closed it stays hidden for the rest of the browser session. "
      "Provide English and Simplified Chinese text. Follow the team's conventions, include a test, and record the change for the release notes. "
      "You do not need to wire it into App.tsx.")
V=os.environ.get('SKILLSET','')  # '' original; '2' + test-interaction rule; '3' = 2 + stale strings.en.json/__tests__ line fixed; '4' = 3 + holon build-parts routes to 4 refs; '5' = 6 refs
TREES={'heading':f'{HERE}/splitwork{V}/trees/heading','holon':f'{HERE}/splitwork{V}/trees/holon'}
def system(mode,skills):
    s="You are a coding agent working in a repository. Use the tools to inspect and write files; paths are relative to the repository root. Call finish when done."
    if mode=='none': return s
    root=open(f'{skills}/tessel-frontend/SKILL.md',encoding='utf-8').read()
    if mode=='full':
        return s+"\n\nThis skill is installed for this codebase:\n\n"+root
    return (s+"\n\nThis skill is installed for this codebase. Its entry file `skills/tessel-frontend/SKILL.md` is below; "
            "the files it points to are under `skills/tessel-frontend/` and can be read with read_file.\n\n"+root)
def one(job):
    mode,rep=job
    out=f'{HERE}/runs/{TAG}/{mode}-{rep}'
    if os.path.exists(f'{out}/result.json'):
        return json.load(open(f'{out}/result.json'))
    shutil.rmtree(out,ignore_errors=True)
    repo=f'{out}/repo'; shutil.copytree(f'{HERE}/scaffold',repo)
    skills=f'{out}/skills'; os.makedirs(skills)
    if mode=='full': shutil.copytree(f'{HERE}/data{V}/skills_1000/tessel-frontend',f'{skills}/tessel-frontend')
    elif mode in TREES: shutil.copytree(f'{TREES[mode]}/tessel-frontend',f'{skills}/tessel-frontend')
    st,msgs=run(repo,skills,system(mode,skills),TASK)
    g=grade(repo); st.update(mode=mode,rep=rep,checks=g,score=sum(g.values()))
    try: st['verify']=verify(repo,f'{out}/page')
    except Exception as e: st['verify']={'error':str(e)[:300]}
    json.dump(msgs,open(f'{out}/transcript.json','w'),ensure_ascii=False,indent=1)
    json.dump(st,open(f'{out}/result.json','w'),ensure_ascii=False,indent=1)
    print(mode,rep,'score',st['score'],'turns',st['turns'],'prompt',st['prompt'],'compl',st['completion'],'skill_reads',len(st['skill_reads']),flush=True)
    return st
jobs=[(m,r) for r in range(REPS) for m in MODES]
with cf.ThreadPoolExecutor(int(os.environ.get('JOBS','12'))) as ex: res=list(ex.map(one,jobs))
json.dump(res,open(f'{HERE}/runs/{TAG}.json','w'),indent=1)
