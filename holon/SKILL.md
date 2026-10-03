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
4. **If nothing matches, stay here.** Act on the current `SKILL.md`. Do not force a descent.
5. **Come back up when done.** When a sub-skill finishes, return to the parent and continue its remaining steps. The child's output is the parent's input.
6. **Report misses.** If no sub-skill matches, or the one reached does not handle the task, append one line to `_feedback.md` at the tree root: `task sentence | path taken | outcome`. Then carry on. The next absorption reads that line.

<!-- sub-skills -->
## Sub-skills (auto-generated, do not edit by hand)

- **editing** (`editing/`): Use when creating, moving, renaming or removing a skill folder in this tree, or when a routing table is stale: covers create skill, sync, routing table, validate, dry-run; excludes absorb, duplicate
- **organizer** (`organizer/`): Use when absorbing a new skill or knowledge into this library, or when two skills look like duplicates: covers absorb, duplicate, boundary, place; excludes sync, validate

Routing rule: when the task matches one of the sub-skills above, read the SKILL.md in that subdirectory for detailed instructions before acting;
if that sub-skill lists deeper sub-skills, repeat the descent. Load only the documents on the matching path.
<!-- /sub-skills -->
