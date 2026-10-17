"""Rebuild the split trees from the saved plans in ../plans/ (no model calls)."""
from common import *
import plan
for v in ('heading','holon'):
    for s in SKILLS:
        p=json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','plans',v,s+'.plan.json')))
        err=plan.apply(v,s,p); print(v,s,'ok' if not err else err[:300])
