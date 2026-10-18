"""Minimal coding agent: list/read/write files, then finish. Logs token usage from the API."""
import os,json,time,sys,urllib.request
BASE=os.environ['LLM_BASE_URL'].rstrip('/'); KEY=os.environ.get('LLM_API_KEY'); MODEL=os.environ.get('LLM_MODEL','deepseek-v4.1-flash')
TOOLS=[{"type":"function","function":{"name":n,"description":d,"parameters":{"type":"object","properties":p,"required":list(p)}}} for n,d,p in [
 ("list_dir","List a directory. Paths are relative to the repository root; skill files are under skills/.",{"path":{"type":"string"}}),
 ("read_file","Read a text file (repository or skills/).",{"path":{"type":"string"}}),
 ("write_file","Create or overwrite a file in the repository.",{"path":{"type":"string"},"content":{"type":"string"}}),
 ("finish","Call when the task is done.",{"summary":{"type":"string"}})]]
def call(msgs,stall=int(os.environ.get('STALL','120')),tries=4):
    """Streaming call with a stall watchdog; rebuilds a non-streaming response. Each attempt is logged."""
    import subprocess,select
    body=json.dumps({"model":MODEL,"messages":msgs,"tools":TOOLS,"temperature":0.3,"reasoning_effort":os.environ.get("EFFORT","low"),"stream":True,"stream_options":{"include_usage":True}})
    for att in range(tries):
        t0=time.time(); last=t0; content=[]; calls={}; usage={}; err=None; raw=''
        p=subprocess.Popen(["curl","-sN","--max-time","900",BASE+"/chat/completions","-H","Content-Type: application/json","-d","@-"]+(["-H","Authorization: Bearer "+KEY] if KEY else []),stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
        p.stdin.write(body); p.stdin.close()
        while True:
            r,_,_=select.select([p.stdout],[],[],5)
            if not r:
                if time.time()-last>stall: err='stall'; p.kill(); break
                continue
            line=p.stdout.readline()
            if not line: break
            last=time.time(); line=line.strip()
            if not line.startswith('data:'): raw+=line; continue
            d=line[5:].strip()
            if d=='[DONE]': break
            try: j=json.loads(d)
            except Exception: continue
            if j.get('usage'): usage=j['usage']
            for c in j.get('choices') or []:
                dl=c.get('delta') or {}
                if dl.get('content'): content.append(dl['content'])
                for tc in dl.get('tool_calls') or []:
                    k=tc.get('index',0); e=calls.setdefault(k,{"id":"","type":"function","function":{"name":"","arguments":""}})
                    if tc.get('id'): e['id']=tc['id']
                    f=tc.get('function') or {}
                    if f.get('name'): e['function']['name']+=f['name']
                    if f.get('arguments'): e['function']['arguments']+=f['arguments']
        p.wait()
        ok=not err and (content or calls)
        with open(os.environ.get('LLM_LOG',os.path.join(os.path.dirname(os.path.abspath(__file__)),'llm_calls.log')),'a') as fh:
            fh.write(json.dumps({"t":time.strftime('%H:%M:%S'),"agent":True,"attempt":att,"secs":round(time.time()-t0,1),"ok":bool(ok),"err":err or (raw[:200] if not ok else None),"usage":usage})+"\n")
        if ok:
            m={"role":"assistant","content":"".join(content)}
            if calls: m["tool_calls"]=[calls[k] for k in sorted(calls)]
            return {"choices":[{"message":m}],"usage":usage}
        time.sleep(5*(att+1))
    raise RuntimeError('agent call failed after %d attempts'%tries)
def run(repo,skills,system,user,max_turns=25):
    msgs=[{"role":"system","content":system},{"role":"user","content":user}]
    st={'prompt':0,'completion':0,'cached':0,'turns':0,'skill_reads':[],'skill_chars':0,'writes':[],'finished':False,'error':None}
    def resolve(p,write=False):
        p=p.strip().lstrip('./')
        if p.startswith('skills/') or p=='skills':
            if write: raise PermissionError('skills/ is read-only')
            base,rel=skills,p[len('skills'):].lstrip('/')
        else: base,rel=repo,p
        full=os.path.realpath(os.path.join(base,rel))
        if not full.startswith(os.path.realpath(base)): raise PermissionError('outside')
        return full,(base==skills)
    while st['turns']<max_turns:
        st['turns']+=1
        try: d=call(msgs)
        except Exception as e: st['error']=str(e)[:200]; break
        u=d.get('usage',{}); st['prompt']+=u.get('prompt_tokens',0); st['completion']+=u.get('completion_tokens',0)
        st['cached']+=(u.get('prompt_tokens_details') or {}).get('cached_tokens',0) or 0
        m=d['choices'][0]['message']; tc=m.get('tool_calls') or []
        msgs.append({"role":"assistant","content":m.get('content') or "","tool_calls":tc} if tc else {"role":"assistant","content":m.get('content') or ""})
        if not tc:
            msgs.append({"role":"user","content":"Continue with the tools. Call finish when the task is done."}); continue
        done=False
        for c in tc:
            f=c['function']['name']
            try: a=json.loads(c['function']['arguments'] or '{}')
            except Exception: a={}
            try:
                if f=='list_dir':
                    full,_=resolve(a.get('path','.'))
                    out="\n".join(sorted(x+('/' if os.path.isdir(os.path.join(full,x)) else '') for x in os.listdir(full)))
                elif f=='read_file':
                    full,sk=resolve(a['path']); out=open(full,encoding='utf-8').read()
                    if sk: st['skill_reads'].append(os.path.relpath(full,skills)); st['skill_chars']+=len(out)
                elif f=='write_file':
                    full,_=resolve(a['path'],True); os.makedirs(os.path.dirname(full),exist_ok=True)
                    open(full,'w',encoding='utf-8').write(a.get('content','')); out='written'; st['writes'].append(os.path.relpath(full,repo))
                elif f=='finish': out='ok'; done=True
                else: out='unknown tool'
            except Exception as e: out='error: %s'%e
            msgs.append({"role":"tool","tool_call_id":c['id'],"content":out})
        if done: st['finished']=True; break
    return st,msgs
