"""Streaming chat call with a stall watchdog: aborts when no bytes arrive for STALL seconds, retries, logs every attempt."""
import json,os,subprocess,time,select
BASE=os.environ.get('LLM_BASE_URL','https://hub.oaifree.com/v1').rstrip('/')
MODEL=os.environ.get('LLM_MODEL','deepseek-v4.1-flash')
LOG=os.environ.get('LLM_LOG',os.path.join(os.path.dirname(os.path.abspath(__file__)),'llm_calls.log'))
def log(**k):
    with open(LOG,'a') as f: f.write(json.dumps(k,ensure_ascii=False)+'\n')
def chat(msgs,model=None,temperature=0,retries=4,stall=90,total=900,extra=None,**_):
    body=json.dumps({"model":model or MODEL,"messages":msgs,"temperature":temperature,"stream":True,"stream_options":{"include_usage":True},**(extra or {})})
    for att in range(retries):
        t0=time.time(); last=t0; out=[]; usage=None; err=None
        p=subprocess.Popen(["curl","-sN","-H","User-Agent: curl/8.5.0","--max-time",str(total),BASE+"/chat/completions","-H","Content-Type: application/json","-d","@-"],
                           stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        p.stdin.write(body); p.stdin.close(); buf=''
        while True:
            r,_,_=select.select([p.stdout],[],[],5)
            if r:
                line=p.stdout.readline()
                if not line: break
                last=time.time(); line=line.strip()
                if not line.startswith('data:'):
                    if line: buf+=line
                    continue
                d=line[5:].strip()
                if d=='[DONE]': break
                try: j=json.loads(d)
                except Exception: continue
                if j.get('usage'): usage=j['usage']
                for c in j.get('choices') or []:
                    x=(c.get('delta') or {}).get('content')
                    if x: out.append(x)
            elif time.time()-last>stall:
                err='stall %ds'%stall; p.kill(); break
        p.wait()
        text=''.join(out)
        log(t=time.strftime('%H:%M:%S'),attempt=att,secs=round(time.time()-t0,1),chars=len(text),usage=usage,err=err or (buf[:200] if not text else None))
        if text and not err: return text
        time.sleep(5*(att+1))
    raise RuntimeError('chat failed after %d attempts'%retries)
