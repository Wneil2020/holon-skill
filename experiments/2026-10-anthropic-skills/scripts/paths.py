# Copyright (c) 2026 Wneil2020 and the holon skill contributors. Released under the MIT License.
"""Where things are. Every script runs with the work directory as its current directory."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get("HOLON_REPO", os.path.normpath(os.path.join(HERE, "..", "..", "..")))
H = os.path.join(REPO, "holon")
HOLON_PY = os.path.join(H, "scripts", "holon.py")
ORG = os.path.join(H, "organizer", "scripts", "organizer_cli.py")
WORK = os.environ.get("WORK", os.getcwd())
TREE = os.environ.get("TREE", os.path.join(WORK, "tree", "lib"))
sys.path.insert(0, WORK)  # cards.py lives in the work directory
