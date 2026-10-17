# Copyright (c) 2026 Wneil2020 and the holon skill contributors. Released under the MIT License.
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import *  # noqa: F401,F403  REPO, H, HOLON_PY, ORG, WORK, TREE
import sys, os, re, subprocess
sys.path.insert(0, os.path.dirname(__file__))
from cards import CARDS
root = sys.argv[1]
def path_of(n):
    p = CARDS[n][0]
    return n if p == "." else os.path.join(path_of(p), n)
for n,(p,desc,trig) in CARDS.items():
    f = os.path.join(root, path_of(n), "SKILL.md")
    t = open(f, encoding="utf-8").read()
    assert t.startswith("---\n")
    end = t.index("\n---", 4)
    fm, body = t[4:end], t[end+4:]
    lic = re.search(r"^license:.*$", fm, re.M)
    old = re.search(r"^description:(.*?)(?=^\S|\Z)", fm, re.M | re.S).group(1)
    new = "name: %s\ndescription: \"%s\"\n" % (n, desc)
    if lic: new += lic.group(0) + "\n"
    new += "metadata:\n  holon-triggers: |\n" + "".join("    %s\n" % s for s in trig)
    if p != "." or n in ("office-docs","web"):
        pass
    if n in ("office-docs","web"):
        kids = [k for k,v in CARDS.items() if v[0]==n]
        body = "\n\n# %s\n\n1. When a task touches one of the sub-skills below, read that sub-skill and follow it.\n2. When a task spans two of them, read both and do the cross-format step here: take the output of one as the input of the other.\n\n<!-- sub-skills -->\n<!-- /sub-skills -->\n" % n
    open(f, "w", encoding="utf-8").write("---\n" + new + "---" + body)
    print("rewrote", f, "old desc chars", len(" ".join(old.split())))
