#!/usr/bin/env python3
# Copyright (c) 2026 Wneil2020 and the holon skill contributors. Released under the MIT License.
"""Run locally what CI runs, on any operating system (the same steps as scripts/check.sh).

    python scripts/check.py          (Windows: py scripts\\check.py)

Exit 0 means all passed. The Agent Skills validator runs only if `skills-ref` is installed.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")


def step(title):
    print("\n== " + title, flush=True)


def run(args, cwd, env=None):
    p = subprocess.run([PY] + args, cwd=cwd, env=env or ENV)
    if p.returncode != 0:
        print("FAILED: %s (in %s)" % (" ".join(args), cwd))
        sys.exit(1)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def main():
    holon = os.path.join(REPO, "holon")
    step("holon: tests")
    for args in (["tests/test_holon.py"], ["organizer/tests/test_organizer_cli.py"], ["tests/test_readme_outputs.py"],
                 ["scripts/holon.py", "validate", "."], ["organizer/scripts/organizer_cli.py", "lint", "."],
                 ["organizer/scripts/organizer_cli.py", "replay", "."]):
        run(args, holon)

    step("copyright: every LICENSE and source header names the same holder")
    holders = set()
    for d, dirs, files in os.walk(REPO):
        dirs[:] = [x for x in dirs if x not in (".git", "__pycache__", ".pytest_cache", ".venv", "venv", "node_modules", ".ruff_cache")]
        for f in files:
            if f == "LICENSE" or f.endswith(".py"):
                for m in re.finditer(r"^(?:# )?(Copyright \(c\) .*?)(?:\. Released under the MIT License\.)?$",
                                     read(os.path.join(d, f)), re.M):
                    holders.add(m.group(1))
    print("\n".join(sorted(holders)))
    if len(holders) != 1:
        print("copyright lines differ; make every LICENSE and .py header name the same holder")
        sys.exit(1)
    if read(os.path.join(REPO, "LICENSE")) != read(os.path.join(holon, "LICENSE")):
        print("holon/LICENSE differs from LICENSE")
        sys.exit(1)

    tmp = tempfile.mkdtemp()
    try:
        step("a fresh root built by init passes all three checks")
        skills = os.path.join(tmp, "skills")
        subprocess.run([PY, os.path.join(holon, "scripts", "holon.py"), "init", "mylib", "--root", skills],
                       env=ENV, stdout=subprocess.DEVNULL, check=True)
        tree = os.path.join(skills, "mylib")
        for args in (["scripts/holon.py", "validate", "."], ["organizer/scripts/organizer_cli.py", "lint", "."],
                     ["organizer/scripts/organizer_cli.py", "replay", "."]):
            run(args, tree)

        step("install into an empty home")
        home = os.path.join(tmp, "home")
        os.makedirs(home)
        env = dict(ENV, HOME=home, USERPROFILE=home)
        for key in ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "VIBE_HOME", "XDG_CONFIG_HOME"):
            env.pop(key, None)
        subprocess.run([PY, os.path.join(holon, "scripts", "holon.py"), "install"], env=env,
                       stdout=subprocess.DEVNULL, check=True)
        dest = os.path.join(home, ".agents", "skills", "holon")
        if not os.path.isfile(os.path.join(dest, "scripts", "holon.py")) or os.path.exists(os.path.join(dest, "tests")):
            print("install did not produce the expected tree in " + dest)
            sys.exit(1)
        print("installed and checked: " + dest)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if shutil.which("skills-ref"):
        step("Agent Skills spec: skills-ref validate")
        for d, dirs, files in os.walk(REPO):
            dirs[:] = [x for x in dirs if x not in (".git", "__pycache__", ".retired", "tests", ".venv", "venv", "node_modules", ".ruff_cache")]
            if "SKILL.md" in files and subprocess.run(["skills-ref", "validate", d], stdout=subprocess.DEVNULL).returncode:
                print("FAILED: skills-ref validate " + d)
                sys.exit(1)
        print("all SKILL.md files pass")
    else:
        step("skipped: skills-ref not installed")
        print('pip install "git+https://github.com/agentskills/agentskills.git#subdirectory=skills-ref"')

    print("\nall checks passed")


if __name__ == "__main__":
    main()
