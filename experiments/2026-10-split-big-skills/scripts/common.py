import json,os,re,sys,subprocess
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from llm import chat
HERE=os.environ.get('SPLIT_WORK',os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),'work'))
os.makedirs(HERE,exist_ok=True)
SRC=os.environ.get('GOS_DATA',os.path.join(os.path.dirname(HERE),'data'))+'/skills_1000'
HOLON=os.environ.get('HOLON',os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','..','holon'))
SKILLS=['citation-management','rdkit','pymatgen','senior-data-engineer']
def numbered(text): return '\n'.join('%5d  %s'%(i+1,l) for i,l in enumerate(text.splitlines()))
def jparse(s):
    s=s.strip()
    m=re.search(r'```(?:json)?\s*(.*?)```',s,re.S)
    if m: s=m.group(1)
    i=min([x for x in (s.find('{'),s.find('[')) if x>=0])
    return json.loads(s[i:s.rfind('}' if s[i]=='{' else ']')+1])
def ask_json(msgs,tries=3,**kw):
    last=None
    for _ in range(tries):
        r=chat(msgs,**kw)
        try: return jparse(r)
        except Exception as e: last=r
    raise RuntimeError('bad json: '+str(last)[:300])
