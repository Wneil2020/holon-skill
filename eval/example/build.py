#!/usr/bin/env python3
# Copyright (c) 2026 Wneil2020 and the holon skill contributors. Released under the MIT License.
"""Build the worked example from its inputs: flat/ (arrangement A), plan.txt, sentences.tsv.

    python3 eval/example/build.py      # writes eval/example/tree/ (C) and eval/example/trimmed/ (B)

The tree and the trimmed copy are generated, not kept in the repository, so the example
always shows what the current tools do. Then run, from eval/:

    python3 harness.py run example/sentences.tsv --tree example/tree/library --flat example/flat \\
        --trimmed example/trimmed --names example/plan.txt --runs 1 --out example/results.csv
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOLON = HERE.parents[1] / "holon" / "scripts" / "holon.py"
PY = sys.executable
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")

# The one parent the plan needs. Its body says what only the parent does: the cross-format step.
OFFICE = ("office-docs", "Use when producing or converting office documents: covers office document, convert",
          ["turn this Word report into a PDF", "merge pages of the PDF and put the result in a Word file",
           "design a poster for the launch should go to poster"],
          "1. When the task needs two formats, do the first format's step with its sub-skill, "
          "then hand the file to the second one.")


def run(*args):
    p = subprocess.run([PY] + [str(a) for a in args], env=ENV, capture_output=True, text=True, encoding="utf-8")
    if p.returncode:
        sys.exit("failed: %s\n%s" % (" ".join(map(str, args)), p.stdout + p.stderr))
    return p.stdout


def fill(skill_dir, triggers, body):
    md = skill_dir / "SKILL.md"
    text = md.read_text(encoding="utf-8")
    lines = "\n".join("    " + t for t in triggers)
    head, sep, rest = text.partition("  holon-triggers: |\n")
    rest = rest.split("\n---\n", 1)[1]
    text = head + sep + lines + "\n---\n" + rest
    text = "\n".join(body if l.strip().startswith("1. TODO") else l for l in text.split("\n"))
    md.write_text(text, encoding="utf-8")


def main():
    for d in ("tree", "trimmed"):
        shutil.rmtree(HERE / d, ignore_errors=True)
    run(HOLON, "init", "library", "--root", HERE / "tree")
    root = HERE / "tree" / "library"
    tool = root / "scripts" / "holon.py"
    name, desc, triggers, body = OFFICE
    run(tool, "init", name, "--parent", root, "--desc", desc)
    fill(root / name, triggers, body)
    print(run(tool, "move", "--plan", HERE / "plan.txt", "--copy").strip())
    run(tool, "sync", root)
    print(run(tool, "validate", root).strip())
    run(HERE.parent / "harness.py", "flatten", root, HERE / "trimmed")
    print("built %s and %s" % (root, HERE / "trimmed"))


if __name__ == "__main__":
    main()
