# For an agent working on this repository

1. Read the README of the package you are changing, and `CONTRIBUTING.md`.
2. Prose says what the thing does, with real examples, in plain sentences, and no marketing adjectives. After writing a document, read it from the top as someone who has never seen the project, and fix the line where that reader would stop.
3. Before committing, run `bash scripts/check.sh` (or `python scripts/check.py`, which also works on Windows); both run what CI runs. Every command output quoted in `holon/README.md` is checked against the real output, so a change to a tool's output means a change to the README in the same commit.
4. A tree's decisions are in its `ABSORB.md`. Read the `ruled:` lines before making a new one; do not decide the same question twice.
