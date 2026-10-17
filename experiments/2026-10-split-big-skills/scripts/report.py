from common import *
import collections
tag=sys.argv[1] if len(sys.argv)>1 else 'run1'
R=json.load(open(f'{HERE}/results/{tag}.json'))
g=collections.defaultdict(list)
for r in R: g[(r['cond'],r['skill'])].append(r); g[(r['cond'],'ALL')].append(r)
print('%-8s %-22s %4s %8s %8s %9s %6s'%('cond','skill','n','correct','reached','avg_chars','err'))
for k in sorted(g):
    x=[r for r in g[k] if 'error' not in r]; e=len(g[k])-len(x)
    if not x: continue
    print('%-8s %-22s %4d %8.3f %8.3f %9d %6d'%(k[0],k[1],len(x),sum(r['correct'] for r in x)/len(x),sum(r['reached'] for r in x)/len(x),sum(r['chars'] for r in x)/len(x),e))
