"""Build a holon-style tree over a GoS library with a model. Leaves keep their original descriptions."""
import sys,json,os,re,concurrent.futures as cf
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); from llm import chat; from data import library
OUT=os.environ.get('OUT',os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','results'))
SIZE=int(sys.argv[1]); MAXLEAF=int(os.environ.get('MAXLEAF','12'))
lib=library(SIZE)
def J(s):
    m=re.search(r'\{.*\}',s,re.S); return json.loads(m.group(0))
RULES=("You are organizing an Agent Skills library into a tree. A parent's routing table lists its children; an agent reading the table descends only into lines that match its task. "
"Group by the job a user brings (a domain or a kind of task), so that a task needing a skill can tell from the group line alone that it should go down. Each group description has the form "
"'Use when <situations>: covers <3-6 routing words>; excludes <what belongs elsewhere>' and must name the kinds of tasks of every skill in it.")
def split(path,names):
    if len(names)>80: return split_big(path,names)
    return split_small(path,names)
def split_big(path,names):
    listing="\n".join("- %s: %s"%(n,lib[n]['desc'][:90]) for n in names)
    q=(RULES+"\n\nPropose 6 to 9 groups for these %d skills. Do not list members yet.\n\n%s\n\nReply JSON only: {\"groups\":[{\"name\":\"...\",\"description\":\"Use when ...: covers ...; excludes ...\"}]}")%(len(names),listing)
    for attempt in range(4):
        try: g=J(chat([{"role":"user","content":q}],timeout=600))['groups']; break
        except Exception as e: print('retry big',path,e,flush=True)
    else: raise RuntimeError('big split failed')
    gl="\n".join("- %s: %s"%(x['name'],x['description']) for x in g); gi={x['name']:i for i,x in enumerate(g)}
    def assign(batch):
        q2="Groups:\n%s\n\nPut each skill below in the one group whose line an agent would follow for that skill's tasks.\n%s\nReply JSON only {\"skill-name\":\"group-name\",...}"%(gl,"\n".join("- %s: %s"%(n,lib[n]['desc'][:300]) for n in batch))
        for _ in range(4):
            try: return J(chat([{"role":"user","content":q2}],timeout=300))
            except Exception as e: pass
        return {}
    seen={}
    with cf.ThreadPoolExecutor(12) as ex:
        for a in ex.map(assign,[names[i:i+40] for i in range(0,len(names),40)]):
            for k,v in a.items():
                if k in names and v in gi: seen[k]=gi[v]
    miss=sum(1 for n in names if n not in seen)
    for n in names: seen.setdefault(n,0)
    groups=[{'name':re.sub(r'[^a-z0-9-]','',x['name'].lower())[:40] or 'g%d'%i,'description':x['description'],'skills':[n for n in names if seen[n]==i]} for i,x in enumerate(g)]
    groups=[x for x in groups if x['skills']]
    print('big',path,[len(x['skills']) for x in groups],'defaulted',miss,flush=True)
    return groups
def split_small(path,names):
    listing="\n".join("- %s: %s"%(n,lib[n]['desc'][:160]) for n in names)
    k=min(9,max(3,round(len(names)/MAXLEAF)))
    q=(RULES+"\n\nGroup these %d skills into %d to 9 groups (aim for about %d). Every skill goes in exactly one group. Folder names are short lowercase-hyphen words.\n\n%s\n\n"
       "Reply with JSON only: {\"groups\":[{\"name\":\"...\",\"description\":\"Use when ...: covers ...; excludes ...\",\"skills\":[\"skill-name\",...]}]}")%(len(names),3,k,listing)
    for attempt in range(4):
        try:
            g=J(chat([{"role":"user","content":q}],timeout=600,temperature=0))['groups']
        except Exception as e:
            print('retry',path,e,flush=True); continue
        seen={}
        for gi,x in enumerate(g):
            for s in x['skills']:
                if s in names and s not in seen: seen[s]=gi
        miss=[n for n in names if n not in seen]
        if len(miss)>len(names)*0.1: print('too many missing',path,len(miss),flush=True); continue
        if miss:  # place the rest by asking once
            gl="\n".join("- %s: %s"%(x['name'],x['description']) for x in g)
            q2="Groups:\n%s\n\nPut each of these skills in one group.\n%s\nReply JSON {\"skill-name\":\"group-name\",...}"%(gl,"\n".join("- %s: %s"%(n,lib[n]['desc'][:300]) for n in miss))
            try: a=J(chat([{"role":"user","content":q2}],timeout=300))
            except Exception: a={}
            gi={x['name']:i for i,x in enumerate(g)}
            for n in miss: seen[n]=gi.get(a.get(n),0)
        groups=[{'name':re.sub(r'[^a-z0-9-]','',x['name'].lower())[:40] or 'g%d'%i,'description':x['description'],'skills':[n for n in names if seen[n]==i]} for i,x in enumerate(g)]
        groups=[x for x in groups if x['skills']]
        # dedupe names
        used=set()
        for x in groups:
            b=x['name'];i=2
            while x['name'] in used: x['name']='%s-%d'%(b,i);i+=1
            used.add(x['name'])
        if len(groups)<2: continue
        return groups
    raise RuntimeError('split failed '+path)
def build(path,names):
    if len(names)<=MAXLEAF: return {'path':path,'leaves':names,'groups':[]}
    gs=split(path,names)
    node={'path':path,'leaves':[],'groups':[]}
    with cf.ThreadPoolExecutor(9) as ex:
        subs=list(ex.map(lambda x: build(path+'/'+x['name'] if path!='.' else x['name'],x['skills']),gs))
    for x,s in zip(gs,subs):
        # a group of one skill: keep the skill as a leaf here
        if len(x['skills'])==1: node['leaves'].append(x['skills'][0]); continue
        s['description']=x['description']; s['name']=x['name']; node['groups'].append(s)
    print('built',path,len(names),'->',len(node['groups']),'groups',len(node['leaves']),'leaves',flush=True)
    return node
tree=build('.',sorted(lib))
json.dump(tree,open(os.path.join(OUT,'tree_%d.json'%SIZE),'w'),indent=1)
def stats(n,d=0):
    yield d,len(n['groups'])+len(n['leaves'])
    for g in n['groups']: yield from stats(g,d+1)
s=list(stats(tree)); print('nodes',len(s),'max depth',max(d for d,_ in s),'max table',max(w for _,w in s))
