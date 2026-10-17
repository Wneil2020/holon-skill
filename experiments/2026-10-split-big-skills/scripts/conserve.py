"""Every non-blank line of the source body still exists somewhere in the split skill (multiset check)."""
from common import *
import glob,collections,plan
for v in ('heading','holon'):
    for s in SKILLS:
        src=plan.src_text(s).split('---',2)[2]
        need=collections.Counter(l for l in src.splitlines() if l.strip())
        have=collections.Counter()
        t=f'{HERE}/trees/{v}/{s}'; old=set(os.listdir(f'{SRC}/{s}/references')) if os.path.isdir(f'{SRC}/{s}/references') else set()
        for p in glob.glob(f'{t}/**/*.md',recursive=True):
            if os.path.dirname(p)==f'{t}/references' and os.path.basename(p) in old: continue
            have.update(l for l in open(p).read().splitlines() if l.strip())
        miss=need-have
        print(v,s,'lines',sum(need.values()),'missing',sum(miss.values()),'files',len(glob.glob(f'{t}/**/*.md',recursive=True)),'subskills',len(glob.glob(f'{t}/*/SKILL.md')),'root_lines',len(open(f'{t}/SKILL.md').read().splitlines()))
