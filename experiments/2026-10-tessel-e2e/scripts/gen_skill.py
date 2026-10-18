import sys,json,os
sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','2026-10-split-big-skills','scripts')); from llm import chat
F=json.load(open('facts.json'))
facts="\n".join("- [%s] %s"%(f['id'],f['text']) for f in F)
q="""Write the internal SKILL.md of a fictional company's frontend platform called "Tessel" (packages @tessel/core, @tessel/testkit, @tessel/cli). It must read like a real, messy, grown-over-years monolith skill that several teams appended to: about 550-700 lines of Markdown.

Required content: these 10 conventions must each appear, worded EXACTLY as given (copy the backticked code verbatim), each placed inside a relevant section, scattered across the whole file (some early, some in the middle, some near the end), not in one list. Do not include the [F#] tags.
%s

Also include, as realistic filler that a part author does NOT need for building a part: local dev setup and @tessel/cli commands, monorepo layout, git branch and PR rules, CI pipeline stages, deploy and feature flags, analytics event naming, performance budgets, a design-review checklist, browser support matrix, an FAQ, a troubleshooting section, and an old "Migration from Tessel 2" section. Some of it should repeat or slightly overlap (e.g. a Quick Start that restates a few things). Include several code examples in fenced blocks. Do not include a complete example of a banner or of any dismissible part.

Start with this exact header:
---
name: tessel-frontend
description: "Use when building or changing UI in the Tessel web app: parts, tokens, strings, tests, release notes, CLI, CI and deploy."
---
Output only the file."""%facts
t=chat([{"role":"user","content":q}],timeout=900,temperature=0.7)
t=t.strip()
if t.startswith('```'): t=t.split('\n',1)[1].rsplit('```',1)[0]
os.makedirs('data/skills_1000/tessel-frontend',exist_ok=True)
open('data/skills_1000/tessel-frontend/SKILL.md','w').write(t.strip()+'\n')
print(len(t.splitlines()))
