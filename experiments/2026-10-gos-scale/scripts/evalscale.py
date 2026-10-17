"""Route the 87 SkillsBench tasks: flat list vs tree, each with and without one-hop needs. Retrieval only."""
import sys,json,os,re,concurrent.futures as cf
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); from llm import chat; from data import library,tasks
OUT=os.environ.get('OUT',os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','results'))
SIZE=int(sys.argv[1]); TAG=sys.argv[2]
lib=library(SIZE); rows=tasks(lib)
tree=json.load(open(os.path.join(OUT,'tree_%d.json'%SIZE))); needs=json.load(open(os.path.join(OUT,'needs_%d.json'%SIZE)))
SYS="You are an AI agent with a skills folder. Decide which skill files to read before doing the task. Reply with JSON only."
def J(s): return json.loads(re.search(r'\{.*\}',s,re.S).group(0))
def ask(q):
    for _ in range(4):
        try: return J(chat([{"role":"system","content":SYS},{"role":"user","content":q}],timeout=300))
        except Exception as e: err=e
    raise err
FLAT="\n".join("- %s: %s"%(n,lib[n]['desc']) for n in sorted(lib))
def flat(task):
    q=("Available skills (name: description):\n%s\n\nUser task:\n%s\n\nWhich skills would you load before doing this task? Load every skill whose description says it applies, and only those. "
       "Reply {\"load\": [names]}.")%(FLAT,task)
    return [n for n in ask(q).get('load',[]) if n in lib], len(FLAT)
def table(node):
    lines=["- **%s** (`%s/`): %s"%(g['name'],g['name'],g['description']) for g in node['groups']]
    lines+=["- **%s** (`%s/`): %s"%(n,n,lib[n]['desc']) for n in node['leaves']]
    return "## Sub-skills\n\n"+"\n".join(lines)
RULE=("Reading rules: go down only into lines that match the task; repeat at each level; read only what is on the path; if nothing matches, stay. "
      "A line that is a single skill (no deeper table) is loaded when chosen.")
def treeroute(task):
    loaded=[];chars=0;frontier=[tree];visits=0
    while frontier and visits<20:
        node=frontier.pop(0); visits+=1
        t=table(node); chars+=len(t)
        q=("%s\n\nYou are at `%s` and have loaded its routing table:\n\n%s\n\nUser task:\n%s\n\nWhich lines do you go down into (or load)? Reply {\"read\": [folder names exactly as listed]} or {\"read\": []}.")%(RULE,node['path'],t,task)
        try: pick=[p.strip().strip('/').split('/')[-1] for p in ask(q).get('read',[])]
        except Exception: pick=[]
        for p in pick:
            g=[x for x in node['groups'] if x['name']==p]
            if g: frontier.append(g[0])
            elif p in node['leaves'] and p not in loaded: loaded.append(p)
    return loaded,chars
def close(ls):
    out=list(ls)
    for n in ls:
        for m in (needs.get(n) or []):
            if m not in out: out.append(m)
    return out
def one(r):
    o={'id':r['id'],'gold':r['gold']}
    try: o['flat'],o['flat_chars']=flat(r['instruction'])
    except Exception as e: o['flat']=None
    try: o['tree'],o['tree_chars']=treeroute(r['instruction'])
    except Exception as e: o['tree']=None
    for k in ('flat','tree'):
        if o[k] is not None: o[k+'_needs']=close(o[k])
    return o
with cf.ThreadPoolExecutor(int(os.environ.get('JOBS','24'))) as ex: res=list(ex.map(one,rows))
json.dump(res,open(os.path.join(OUT,'res_%d_%s.json'%(SIZE,TAG)),'w'),indent=1)
def sc(k):
    x=[r for r in res if r.get(k) is not None]
    rec=sum(len(set(r['gold'])&set(r[k]))/len(r['gold']) for r in x)/len(x)
    comp=sum(set(r['gold'])<=set(r[k]) for r in x)/len(x)
    prec=sum(len(set(r['gold'])&set(r[k]))/max(1,len(r[k])) for r in x)/len(x)
    return 'n=%d recall=%.3f complete=%.3f precision=%.3f avg_loaded=%.2f'%(len(x),rec,comp,prec,sum(len(r[k]) for r in x)/len(x))
for k in ('flat','flat_needs','tree','tree_needs'): print('%-11s'%k,sc(k))
x=[r for r in res if r.get('tree') is not None]; print('tree chars avg',sum(r['tree_chars'] for r in x)//len(x),'flat chars',len(FLAT))
