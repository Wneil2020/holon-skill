"""Author holon-needs edges offline: per skill, a model picks 0-3 prerequisites from 25 lexical candidates. No task data is used."""
import sys,json,os,re,math,collections,concurrent.futures as cf
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); from llm import chat; from data import library
OUT=os.environ.get('OUT',os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','results'))
SIZE=int(sys.argv[1]); lib=library(SIZE); names=sorted(lib)
tok=lambda s:[w for w in re.findall(r'[a-z0-9]+',s.lower()) if len(w)>2]
docs={n:tok(n.replace('-',' ')+' '+lib[n]['desc']) for n in names}
N=len(docs);avg=sum(map(len,docs.values()))/N;df=collections.Counter(w for d in docs.values() for w in set(d))
TF={n:collections.Counter(d) for n,d in docs.items()}
def bm25(q,k=25):
    qs=collections.Counter(tok(q));sc={}
    for n,tf in TF.items():
        s=0
        for w in qs:
            if w in tf: s+=math.log(1+(N-df[w]+.5)/(df[w]+.5))*tf[w]*2.2/(tf[w]+1.2*(.25+.75*len(docs[n])/avg))
        sc[n]=s
    return [n for n in sorted(sc,key=lambda n:-sc[n]) if sc[n]>0][:k]
def body(n):
    t=lib[n]['body']; t=t.split('---',2)[2] if t.startswith('---') else t
    return t
def one(n):
    b=body(n)
    cands=[c for c in bm25(lib[n]['desc']+' '+b[:3000],30) if c!=n][:25]
    # skills named in the body are always candidates
    for m in names:
        if m!=n and len(m)>5 and m not in cands and re.search(r'(?<![\w-])'+re.escape(m)+r'(?![\w-])',b): cands.append(m)
    lst="\n".join("- %s: %s"%(c,lib[c]['desc'][:250]) for c in cands)
    q=("A skill library lets a skill declare `needs`: other skills an agent must also load whenever it uses this one, because this skill's own steps rely on them "
       "(a tool it calls, a format it reads or writes, a step it hands off to). Being related or similar is NOT a need. Most skills need nothing.\n\n"
       "This skill: %s\nDescription: %s\nBody (start):\n%s\n\nCandidates:\n%s\n\nPick 0 to 3 candidates this skill needs. Reply JSON only: {\"needs\":[names]}")%(n,lib[n]['desc'],b[:2500],lst)
    for _ in range(3):
        try:
            m=re.search(r'\{.*\}',chat([{"role":"user","content":q}],timeout=180),re.S)
            return n,[x for x in json.loads(m.group(0)).get('needs',[]) if x in cands][:3]
        except Exception as e: err=e
    return n,None
with cf.ThreadPoolExecutor(int(os.environ.get('JOBS','24'))) as ex:
    res=dict(ex.map(one,names))
json.dump(res,open(os.path.join(OUT,'needs_%d.json'%SIZE),'w'),indent=1)
v=[x for x in res.values() if x]
print('skills',len(res),'failed',sum(x is None for x in res.values()),'with needs',len(v),'edges',sum(map(len,v)))
