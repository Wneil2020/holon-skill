import json,glob,statistics as st,sys
SETS=[('main','deepseek','v1 original','none,full,heading,holon'),
      ('dsfix','deepseek','v3 test rule + contradiction fixed','full,heading,holon'),
      ('glm','glm','v1 original','none,full,heading,holon'),
      ('glmrule','glm','v2 + test rule','full,heading,holon'),
      ('glmfix','glm','v3 test rule + contradiction fixed','full,heading,holon'),
      ('glmctl','glm*','v3 (channel control)','holon'),
      ('glmroute','glm*','v4 build-parts routes to 4 refs','holon'),
      ('glmroute6','glm*','v5 build-parts routes to 6 refs','holon')]
rows=[]
for tag,model,ver,modes in SETS:
  res=[json.load(open(f)) for f in sorted(glob.glob(f'runs/{tag}/*/result.json'))]
  bad=[r for r in res if r.get('error') or r['turns']<=2]
  res=[r for r in res if r not in bad]
  for m in modes.split(','):
    x=[r for r in res if r['mode']==m]
    if not x: continue
    V=lambda r,k:(r.get('verify') or {})
    own=sum(1 for r in x if (V(r,0).get('own_tests') or [0,0])[1] and V(r,0)['own_tests'][0]==V(r,0)['own_tests'][1])
    beh=sum(1 for r in x if V(r,0).get('behavior')==[2,2])
    pg=lambda r:(V(r,0).get('page') or {})
    br=sum(1 for r in x if pg(r).get('hidden_after_click') and pg(r).get('hidden_after_reload') and pg(r).get('back_in_new_session'))
    rows.append(dict(set=tag,model=model,skill=ver,mode=m,n=len(x),excluded=sum(1 for r in bad if r['mode']==m),
      score=round(st.mean(r['score'] for r in x),2),perfect=sum(1 for r in x if r['score']==10),
      own_tests=own,behavior=beh,browser=br,prompt_mean=int(st.mean(r['prompt'] for r in x)),
      prompt_median=int(st.median(r['prompt'] for r in x)),compl_mean=int(st.mean(r['completion'] for r in x)) if 'completion' in x[0] else int(st.mean(r.get('compl',0) for r in x)),
      turns=round(st.mean(r['turns'] for r in x),1),reads=round(st.mean(len(r.get('skill_reads') or []) for r in x),1),skill_chars=int(st.mean(r.get('skill_chars',0) for r in x))))
json.dump(rows,open('runs/summary.json','w'),indent=1)
for r in rows: print(r)
