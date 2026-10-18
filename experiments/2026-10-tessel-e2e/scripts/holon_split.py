import sys,os
os.environ.setdefault('GOS_DATA',os.path.join(os.path.dirname(os.path.abspath(__file__)),'data')); os.environ.setdefault('SPLIT_WORK',os.path.join(os.path.dirname(os.path.abspath(__file__)),'splitwork'))
sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','2026-10-split-big-skills','scripts')); sys.argv=['x']
import llm_stream, common, plan
model=os.environ.get('SPLIT_MODEL')
f=lambda m,**k: llm_stream.chat(m,model=model,retries=3,stall=100,total=300,extra={'reasoning_effort':'none','enable_thinking':False,'thinking':{'type':'disabled'}})
common.chat=f; plan.chat=f
s,a,log=plan.run_holon('tessel-frontend'); print('attempts',a,log[-1]['error'] and log[-1]['error'][:800])
