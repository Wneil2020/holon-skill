"""Score only the questions the model gets wrong with no file at all (results/none1.json)."""
from common import *
R=json.load(open(sys.argv[1])); N={r['id']:r for r in json.load(open(sys.argv[2]))}
hard={i for i,r in N.items() if not r.get('correct') and 'error' not in r}
print('no-file correct', sum(bool(r.get('correct')) for r in N.values()), '/', len(N), '-> hard set', len(hard))
for c in ('full','heading','holon'):
    x=[r for r in R if r['cond']==c and r['id'] in hard and 'error' not in r]
    if x: print('%-8s n=%d correct=%.3f reached=%.3f chars=%d files=%.2f'%(c,len(x),sum(r['correct'] for r in x)/len(x),sum(r['reached'] for r in x)/len(x),sum(r['chars'] for r in x)/len(x),sum(len(r['opened']) for r in x)/len(x)))
