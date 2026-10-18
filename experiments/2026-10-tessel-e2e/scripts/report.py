import json,sys,statistics as S
res=json.load(open(sys.argv[1]))
modes=[]; [modes.append(r['mode']) for r in res if r['mode'] not in modes]
print('%-8s %3s %6s %6s %9s %8s %6s %6s'%('mode','n','score','sd','prompt','compl','turns','reads'))
for m in modes:
    x=[r for r in res if r['mode']==m]
    sc=[r['score'] for r in x]
    print('%-8s %3d %6.2f %6.2f %9d %8d %6.1f %6.1f'%(m,len(x),S.mean(sc),S.pstdev(sc),S.mean(r['prompt'] for r in x),S.mean(r['completion'] for r in x),S.mean(r['turns'] for r in x),S.mean(len(r['skill_reads']) for r in x)))
keys=list(res[0]['checks'])
print('\nper check (passes / runs)')
print('%-18s'%'check'+''.join('%9s'%m for m in modes))
for k in keys:
    print('%-18s'%k+''.join('%9s'%('%d/%d'%(sum(r['checks'][k] for r in res if r['mode']==m),sum(1 for r in res if r['mode']==m))) for m in modes))

def V(r):
    v=r.get('verify') or {}; pg=v.get('page') or {}
    b=v.get('behavior') or [0,0]; o=v.get('own_tests') or [0,0]
    return {'part_exists':v.get('exists',True) and 'behavior' in v,'behavior_all':b[1]>0 and b[0]==b[1],'own_tests_pass':o[1]>0 and o[0]==o[1],
            'page_builds':bool(pg.get('build')),'page_no_errors':bool(pg.get('build')) and not pg.get('errors'),
            'browser_dismiss':bool(pg.get('hidden_after_click')),'browser_persist':bool(pg.get('hidden_after_reload')),'browser_new_session':bool(pg.get('back_in_new_session'))}
print('\nreal run (passes / runs)')
print('%-20s'%'check'+''.join('%9s'%m for m in modes))
for k in V(res[0]):
    print('%-20s'%k+''.join('%9s'%('%d/%d'%(sum(V(r)[k] for r in res if r['mode']==m),sum(1 for r in res if r['mode']==m))) for m in modes))
print('\nfinished / errors:',{m:(sum(r['finished'] for r in res if r['mode']==m),sum(bool(r['error']) for r in res if r['mode']==m)) for m in modes})
