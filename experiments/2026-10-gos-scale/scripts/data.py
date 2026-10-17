import glob,os,re,json
ROOT=os.environ.get('GOS_DATA',os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','data'))
norm=lambda s:re.sub(r'[^a-z0-9]+','',s.lower())
def desc_of(text):
    if not text.startswith('---'): return ''
    fm=text.split('---',2)[1]
    m=re.search(r'^description:\s*(.*?)(?=^\w[\w-]*:|\Z)',fm,re.M|re.S)
    d=m.group(1).strip() if m else ''
    d=re.sub(r'^[>|][-+]?\s*','',d); d=' '.join(d.split())
    return d.strip('"\'')
def library(size):
    out={}
    for p in sorted(glob.glob(f'{ROOT}/skills_{size}/**/SKILL.md',recursive=True)):
        name=os.path.basename(os.path.dirname(p))
        t=open(p,errors='ignore').read()
        out[name]={'desc':desc_of(t),'path':p,'body':t}
    return out
def tasks(lib_names):
    idx={norm(n):n for n in lib_names}
    rows=[]
    for t in sorted(os.listdir(f'{ROOT}/tasks')):
        o=sorted(os.path.basename(os.path.dirname(p)) for p in glob.glob(f'{ROOT}/tasks/{t}/environment/skills/*/SKILL.md'))
        ins=open(f'{ROOT}/tasks/{t}/instruction.md').read()
        rows.append({'id':t,'instruction':ins,'gold':sorted(idx[norm(x)] for x in o)})
    return rows
def score(rows,preds,cap=None):
    rec=comp=0;n=len(rows);sizes=0
    for r in rows:
        p=preds.get(r['id'],[])
        if cap: p=p[:cap]
        g=set(r['gold']);h=len(g&set(p))
        rec+=h/len(g);comp+=(h==len(g));sizes+=len(p)
    return {'recall':round(rec/n,3),'complete':round(comp/n,3),'avg_k':round(sizes/n,2)}
