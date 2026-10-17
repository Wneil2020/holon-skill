# Copyright (c) 2026 Wneil2020 and the holon skill contributors. Released under the MIT License.
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403  REPO, H, HOLON_PY, ORG, WORK, TREE
import json,sys
from collections import defaultdict
res=json.load(open(sys.argv[1]))
conds=[c for c in ['flat_old','flat_new','tree','lex'] if c in res[0]]
import os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from cards import CARDS
def lexset(r):
    land=r['lex_land'].split('/')[-1]
    if land in CARDS and land in ('office-docs','web'):
        kids={k for k,v in CARDS.items() if v[0]==land}
        lab=set(r['label'])
        return lab if lab and lab<=kids else {land}
    return set(r['lex'])
def sc(r,c):
    got=lexset(r) if c=='lex' else set(r[c]); lab=set(r['label'])
    return dict(exact=got==lab, hit=lab<=got and (bool(lab) or not got), miss=len(lab-got), extra=len(got-lab))
tab=defaultdict(lambda: defaultdict(int))
for r in res:
    for c in conds:
        s=sc(r,c)
        for k in ('all',r['kind']):
            tab[(c,k)]['n']+=1; tab[(c,k)]['exact']+=s['exact']; tab[(c,k)]['hit']+=s['hit']; tab[(c,k)]['extra']+=s['extra']
kinds=['all','single','multi','zh','none']
print("cond      "+"  ".join("%-12s"%k for k in kinds))
for c in conds:
    print("%-9s "%c+"  ".join("%2d/%2d (+%d)  "%(tab[(c,k)]['exact'],tab[(c,k)]['n'],tab[(c,k)]['extra']) for k in kinds))
