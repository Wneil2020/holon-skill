---
name: editing
description: "Use when creating, moving, renaming or removing a skill folder in this tree, or when a routing table is stale: covers create skill, sync, routing table, validate, dry-run; excludes absorb, duplicate"
metadata:
  holon-triggers: |
    create a sub-skill under office-docs and sync the parent routing table
    validate the tree, the routing table looks stale
    absorb this new skill into the library should go to organizer
---

# editing

Never write a sub-skills list by hand. `scripts/holon.py` at the tree root writes every list. It needs Python 3.8 or newer and nothing else. Every command that writes files accepts `--dry-run`, which shows the change and makes none.

1. Create the skill with `python3 scripts/holon.py init <name> --parent <parent-dir> --desc "<description>"`. The parent's list is updated in the same command. For a top-level skill the parent is the tree root: `--parent .`
2. Write the description in three parts, `Use when ...: covers w, w; excludes w`, and the body as numbered steps. What goes into the description is in `organizer/SKILL.md`; background the steps need goes into `references/`.
3. After editing any description by hand, or moving or deleting a folder, run `python3 scripts/holon.py sync .` so every parent's list matches the folders on disk.
4. Run `python3 scripts/holon.py validate .`; it exits 1 on a missing description, leftover `TODO`, stale list, or loop. Then run `python3 organizer/scripts/organizer_cli.py lint .` and `replay .`. The change is finished when all three pass.

To see the whole tree with descriptions: `python3 scripts/holon.py tree .`

To start a new tree elsewhere: `python3 scripts/holon.py init <name> --root <skills-dir>` writes a root with the reading rules, the three ledgers, and copies `scripts/`, `organizer/` and `editing/` in beside them. To put a finished tree where agent tools read it: `python3 scripts/holon.py install [<tree or URL>] [--project]` copies it to the shared `~/.agents/skills/` and to the directory of every tool on the machine that reads somewhere else, never so that one tool sees it twice, and runs `validate`, `lint` and `replay` on the copy. `--host NAME` (repeatable) limits it to named tools; `hosts` lists them.

A `SKILL.md` is a YAML header with `name` and `description`, then a Markdown body. A parent body holds its list between `<!-- sub-skills -->` and `<!-- /sub-skills -->`; `sync` rewrites only what is between the markers and adds them at the end if they are missing. Deciding whether new content is a sub-skill or a `references/` file is not an editing question; it is rule 2 and rule 3 of `organizer/SKILL.md`.
