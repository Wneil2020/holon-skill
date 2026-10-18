import sys,json,os,concurrent.futures as cf
sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','2026-10-split-big-skills','scripts')); from llm import chat
F={f['id']:f['text'] for f in json.load(open('facts.json'))}
S=[("Quick Start","F1","clone, install with `pnpm i`, `tessel dev`, where things are; restate briefly that parts live in their folders"),
("Monorepo layout and local development","","@tessel/cli commands (tessel dev, tessel build, tessel lint, tessel gen), env vars, ports, proxies"),
("Building parts","F2 F5","how a part is structured, props, hooks, composition, a code example of a simple read-only part (not a banner, nothing dismissible)"),
("Design tokens and styling","F3 F4","token families (color, space, radius, type), dark mode, CSS modules vs inline style, a token table"),
("Localization","F6","pluralization, interpolation `{count}`, RTL notes, translation workflow with the vendor"),
("Accessibility","F7","focus management, keyboard support, contrast, screen reader testing"),
("State and data","F8","data fetching with tessel.query, caching, error states, URL state"),
("Testing","F9","unit vs e2e, snapshot policy, flaky test policy, coverage thresholds"),
("Git, PRs, CI and release","F10","branch names, PR template, CI stages, release train, feature flags, deploy"),
("Analytics, performance and browser support","","event naming, perf budgets, bundle size, browser matrix"),
("Migration from Tessel 2","","old APIs vs new, codemods, deprecated components folder"),
("FAQ and troubleshooting","","10 Q&As and common errors; may restate a couple of rules loosely")]
def one(s):
    title,ids,hint=s
    must="\n".join("- "+F[i] for i in ids.split())
    q=("Write ONE section of the internal SKILL.md of a fictional company frontend platform \"Tessel\" (@tessel/core, @tessel/testkit, @tessel/cli). Section: \"## %s\". 45-70 lines of Markdown, realistic and a bit messy, like several teams appended to it over years; ### subsections and at least one fenced code example. Content: %s.\n"%(title,hint)+
       ("These conventions must appear inside the section, worded EXACTLY as given (copy backticked code verbatim), embedded in prose among other material, not as the first lines:\n"+must+"\n" if must else "")+
       "Do not show a complete banner or any dismissible part. Output only the section, starting with the ## heading.")
    for _ in range(5):
        try:
            t=chat([{"role":"user","content":q}],timeout=240,temperature=0.7).strip()
            if t.startswith('```'): t=t.split('\n',1)[1].rsplit('```',1)[0].strip()
            if all(F[i] in t for i in ids.split()): return t
            print('missing facts, retry',title,flush=True)
        except Exception as e: print('err',title,e,flush=True)
    raise RuntimeError(title)
with cf.ThreadPoolExecutor(12) as ex: parts=list(ex.map(one,S))
head='---\nname: tessel-frontend\ndescription: "Use when building or changing UI in the Tessel web app: parts, tokens, strings, tests, release notes, CLI, CI and deploy."\n---\n\n# Tessel frontend handbook\n\nEverything a web engineer at Tessel needs, collected by the platform team and every team that hit a problem. Read the section you need.\n\n'
os.makedirs('skill',exist_ok=True)
t=head+"\n\n".join(parts)+"\n"
open('skill/SKILL.md','w').write(t)
print(len(t.splitlines()),'lines',len(t),'chars',[i for i in F if F[i] not in t])
