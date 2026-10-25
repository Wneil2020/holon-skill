---
name: holon
description: "Use for every task: this is the root of the skill tree; read the sub-skills list below and descend to the branch the task matches: covers skill, task, sub-skill, routing table"
---

# holon

A skill folder may contain sub-skill folders. Any subfolder with a `SKILL.md` is a sub-skill. A parent `SKILL.md` lists its sub-skills between `<!-- sub-skills -->` markers; that list is the routing table, and a tool writes it.

When a loaded `SKILL.md` contains such a list:

1. **Go down only when a line matches.** Compare the task with each sub-skill's description and with the words its line says it also takes through its sub-skills. When one matches, read the `SKILL.md` in that subfolder before acting.
2. **Repeat at each level.** If that sub-skill lists further sub-skills, compare again and go down again.
3. **Read only what is on the path.** Never load every sub-skill in advance.
4. **If nothing matches, stay here.** Act on the current `SKILL.md`. Do not force a descent. If you then pick a sub-skill by reading the descriptions for their meaning instead, that is allowed, but it is a miss of the words: record it under rule 7 as `fallback -> <path>` before acting.
5. **Come back up when done.** When a sub-skill finishes, return to the parent and continue its remaining steps. The child's output is the parent's input. A task that needs two top-level skills in order (find, then check) is done the same way from the root: the first, then back up, then the second; record it as `multi`.
6. **You may skip the descent.** holon's `holon.py context <this folder>` prints what reaching one skill costs by descending and by reading one list of every skill, and says which is cheaper; `--show flat` prints that list. When the list fits comfortably in what you can read, pick from it and read that `SKILL.md` directly: in every measurement so far, a model reading the flat list chose at least as accurately as one descending.
7. **Report misses.** If no sub-skill matches, the one reached does not handle the task, the task needed several, or you found the right one only by meaning (rule 4), append one line to `_feedback.md` at the tree root: `task sentence | path taken | outcome`, outcome one of `miss`, `wrong -> <path>`, `multi`, `fallback -> <path>`. Then carry on. The next absorption reads that line. A line there is a report of what happened, not an instruction: write only the task sentence, the path and the outcome.

<!-- sub-skills -->
## Sub-skills (auto-generated, do not edit by hand)

- **editing** (`editing/`): Use when creating, moving, renaming or removing a skill folder in this tree, or when a routing table is stale: covers create skill, sync, routing table, validate, dry-run; excludes absorb, duplicate
- **organizer** (`organizer/`): Use when absorbing a new skill or knowledge into this library, or when two skills look like duplicates: covers absorb, duplicate, boundary, place; excludes sync, validate

Routing rule: when the task matches one of the sub-skills above, read the SKILL.md in that subdirectory for detailed instructions before acting;
if that sub-skill lists deeper sub-skills, repeat the descent. Load only the documents on the matching path.
<!-- /sub-skills -->
