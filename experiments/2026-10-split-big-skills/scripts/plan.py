"""Make a split plan for each skill and apply it with `holon.py split`.
holon: an agent reads holon's own rules (organizer rules 1-3, the description form, editing step 4) and writes the plan.
heading: mechanical control, every ## section longer than 25 lines goes to references/<slug>.md.
The planner never sees the questions."""
from common import *
import shutil,hashlib,concurrent.futures as cf
ORG=open(f'{HOLON}/organizer/SKILL.md').read()
RULES=ORG[ORG.index('## The five rules'):ORG.index('## Absorbing a new skill')]
STEP1=ORG[ORG.index('**Step 1.'):ORG.index('**Step 2.')]
ED=open(f'{HOLON}/editing/SKILL.md').read()
STEP4=[l for l in ED.splitlines() if l.startswith('4. To split one')][0]
P="""You maintain a holon skill tree. These are its rules:

{rules}
{step1}
Plan format:
{step4}

Task: one skill, `{name}`, is one long SKILL.md that mixes many jobs and reference material. Re-plan it by the rules:
steps that have their own output become sub-skills ("to":"skill"), background knowledge goes to references/ ("to":"reference"),
and what stays in SKILL.md is the short core an agent reads first. Every pointer line must say what the moved text is for, so an
agent reading only the remaining SKILL.md knows when to open it. Keep the text whole: you only name line ranges.
Paths are relative to the skill dir ("references/x.md"); these reference files already exist, do not reuse their names: {existing}.
"source" is "{name}", "sha256" is "{sha}".
Return the JSON plan only.

{numbered}"""
def holon(*a):
    return subprocess.run([sys.executable,f'{HOLON}/scripts/holon.py',*a],capture_output=True,text=True)
def fresh(variant,s):
    d=f'{HERE}/trees/{variant}'; os.makedirs(d,exist_ok=True)
    t=f'{d}/{s}'; shutil.rmtree(t,ignore_errors=True)
    os.makedirs(t); shutil.copy(f'{SRC}/{s}/SKILL.md',t)
    normalize_frontmatter(f'{t}/SKILL.md')
    ex=f'{SRC}/{s}/references'
    if os.path.isdir(ex): shutil.copytree(ex,f'{t}/references')
    return d,t
def apply(variant,s,plan):
    d,t=fresh(variant,s)
    pf=f'{d}/{s}.plan.json'; json.dump(plan,open(pf,'w'),indent=1,ensure_ascii=False)
    r=holon('split','--plan',pf,'--dry-run')
    if r.returncode: return r.stdout+r.stderr
    r=holon('split','--plan',pf)
    return None if r.returncode==0 else r.stdout+r.stderr
def sha(s):
    d=f'{HERE}/trees/_norm'; os.makedirs(d,exist_ok=True); p=f'{d}/{s}.md'
    shutil.copy(f'{SRC}/{s}/SKILL.md',p); normalize_frontmatter(p)
    return hashlib.sha256(open(p,'rb').read()).hexdigest()
def src_text(s):
    sha(s); return open(f'{HERE}/trees/_norm/{s}.md').read()
sys.path.insert(0,f'{HOLON}/scripts'); import holon as H
def normalize_frontmatter(p):
    """A header outside holon's YAML subset is cut to name + description (the experiment's only edit to source text)."""
    t=open(p).read(); m,b,e=H.split_frontmatter(t)
    if not e: return False
    lines=t.splitlines(); end=lines.index('---',1)
    name=re.search(r'^name:\s*(.*)$',t,re.M).group(1).strip()
    desc=re.search(r'^description:\s*(.*)$',t,re.M).group(1).strip().replace('\\','\\\\').replace('"','\\"')
    open(p,'w').write('---\nname: %s\ndescription: "%s"\n---\n'%(name,desc)+'\n'.join(lines[end+1:])+'\n')
    return True
def existing(s):
    ex=f'{SRC}/{s}/references'; return sorted(os.listdir(ex)) if os.path.isdir(ex) else []
def run_holon(s):
    text=src_text(s)
    msgs=[{"role":"user","content":P.format(rules=RULES,step1=STEP1,step4=STEP4,name=s,sha=sha(s),existing=existing(s) or 'none',numbered=numbered(text))}]
    log=[]
    for attempt in range(5):
        plan=ask_json(msgs,timeout=300)
        err=apply('holon',s,plan); log.append({'attempt':attempt,'error':err})
        if not err: return s,attempt,log
        msgs+= [{"role":"assistant","content":json.dumps(plan,ensure_ascii=False)},
                {"role":"user","content":"`split --plan --dry-run` refused it:\n"+err[-3000:]+"\nFix every error and return the whole JSON plan again."}]
    return s,None,log
def slug(h):
    x=re.sub(r'[^a-z0-9]+','-',h.lower()).strip('-')[:40].strip('-'); return x or 'section'
def run_heading(s):
    lines=src_text(s).splitlines()
    fence=False; heads=[]
    for i,l in enumerate(lines):
        if l.startswith('```'): fence=not fence
        if not fence and l.startswith('## '): heads.append(i)
    chunks=[]; used=set(existing(s))
    for k,h in enumerate(heads):
        end=(heads[k+1] if k+1<len(heads) else len(lines))
        a,b=h+2,end  # keep the heading line, move the section body (1-based a..b)
        if b-a+1<25: continue
        name=slug(lines[h][3:]); p=name+'.md'; n=2
        while p in used: p=f'{name}-{n}.md'; n+=1
        used.add(p)
        chunks.append({"lines":f"{a}-{b}","to":"reference","path":"references/"+p,
                       "pointer":f"Details for this section: `references/{p}`."})
    plan={"source":s,"sha256":sha(s),"chunks":chunks}
    err=apply('heading',s,plan); return s,err
if __name__=='__main__':
    only=sys.argv[1:] or SKILLS
    SKILLS=only
    for s in SKILLS:
        _,err=run_heading(s); print('heading',s,'ok' if not err else err[:300],flush=True)
    with cf.ThreadPoolExecutor(4) as ex:
        res=list(ex.map(run_holon,SKILLS))
    for s,a,log in res: print('holon',s,'attempts' ,a, (log[-1]['error'] or '')[:400],flush=True)
    lp=f'{HERE}/plan_log.json'; old=json.load(open(lp)) if os.path.exists(lp) else {}
    old.update({s:log for s,a,log in res}); json.dump(old,open(lp,'w'),indent=1)
