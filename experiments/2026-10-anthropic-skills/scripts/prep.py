# Copyright (c) 2026 Wneil2020 and the holon skill contributors. Released under the MIT License.
"""Build the work directory: a holon tree holding the anthropics/skills cards, laid out as in this experiment.

usage: python3 prep.py UPSTREAM_SKILLS_DIR WORK_DIR [round0|round2|final]
UPSTREAM_SKILLS_DIR is the skills/ folder of a checkout of github.com/anthropics/skills (commit dbd4588f was used).
"""
import os, sys, shutil, subprocess, glob
HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
REPO = os.environ.get("HOLON_REPO", os.path.normpath(os.path.join(EXP, "..", "..")))
up, work = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
which = sys.argv[3] if len(sys.argv) > 3 else "final"
if os.path.exists(work):
    sys.exit("refusing to overwrite " + work)
os.makedirs(work)
for f in glob.glob(os.path.join(EXP, "data", "*.json")):
    shutil.copy(f, work)
shutil.copy(os.path.join(EXP, "cards", which + ".py"), os.path.join(work, "cards.py"))
sys.path.insert(0, work)
from cards import CARDS  # noqa: E402
tree = os.path.join(work, "tree", "lib")
subprocess.run([sys.executable, os.path.join(REPO, "holon", "scripts", "holon.py"), "init", "lib",
                "--root", os.path.join(work, "tree")], check=True, stdout=subprocess.DEVNULL)
def path_of(n):
    p = CARDS[n][0]
    return n if p == "." else os.path.join(path_of(p), n)
for n in CARDS:
    dest = os.path.join(tree, path_of(n))
    src = os.path.join(up, n)
    if os.path.isdir(src):
        shutil.copytree(src, dest)
    else:  # a grouping parent this experiment added (office-docs, web)
        os.makedirs(dest, exist_ok=True)
        with open(os.path.join(dest, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write("---\nname: %s\ndescription: placeholder\n---\n" % n)
syn = os.path.join(EXP, "cards", "synonyms_%s.md" % which)
if os.path.exists(syn):
    shutil.copy(syn, os.path.join(tree, "synonyms.md"))
subprocess.run([sys.executable, os.path.join(HERE, "apply.py"), tree], check=True, stdout=subprocess.DEVNULL, cwd=work)
print("work directory ready: " + work)
print("next: cd %s && %s" % (work, os.path.join(EXP, "cycle.sh")))
