# holon skill

This folder, `holon/`, is the package. It installs as a skill folder named `holon`, and its two tools are `holon.py` and `organizer_cli.py`.

> **Early stage.** holon skill works and is tested, but it has been used on two small libraries only (about thirty skills in total). The rules, the description format and the command options may still change between versions. Anything that changes is listed in [CHANGELOG.md](CHANGELOG.md), and `holon.py migrate` rewrites older files where it can.

When an agent keeps all its skills in one folder, it reads every skill's description on every task, and the more skills there are, the more often it picks the wrong one. holon keeps skills in a tree instead. A skill's folder can hold other skills (its sub-skills), so the agent reads the top level, goes into the one branch that matches the task, and reads only the files on that path.

holon is a set of plain folders and two Python scripts. The scripts use only the standard library and need Python 3.8 or newer. They keep the tree consistent, and they check that each skill is reached by the sentences it is meant to be reached by.

[中文说明](README.zh-CN.md)

## Installing

From a checkout of this repository:

```bash
python3 holon/scripts/holon.py install
```

This copies the tree to `~/.agents/skills/holon/`, the shared location of the [Agent Skills](https://agentskills.io) standard. Codex, Cursor, GitHub Copilot, Gemini CLI, OpenCode and other tools read that folder. `install` then looks for tools on the machine that read skills from somewhere else, such as Claude Code (`~/.claude/skills/`) or Windsurf (`~/.codeium/windsurf/skills/`), and puts a copy there too. It checks the copy and prints which tool reads which folder. Each tool picks the tree up at its next session.

Some tools read more than one folder. Cursor and OpenCode, for example, read both `~/.claude/skills/` and `~/.agents/skills/`, so a copy in both places would show them the tree twice. `install` never writes a set of folders in which one tool sees two copies.

`python3 holon/scripts/holon.py hosts` lists the 32 tools `install` knows, which of them are on this machine, and every folder each one reads. To choose the target yourself:

| Option | What it does |
|---|---|
| `--host NAME` | install for that tool only; repeat for several (`--host windsurf --host codex`). `--host agents` means the shared folder alone |
| `--project` | use the project-level folders under the current directory (`.agents/skills/`, `.claude/skills/`, ...) instead of the home directory |
| `--to DIR`, `--as NAME` | any folder, any name |
| `--force` | replace an earlier install of the same name |
| `--link` | link the extra folders to the first copy instead of copying; some tools do not follow links, so copying is the default |

A tool that is not in the list still works if it follows the standard, because it reads `~/.agents/skills/`. For a tool that reads somewhere else, use `--to` with that folder.

`install` can also install from somewhere else: a local path, a git URL, `owner/repo` on GitHub, or a `.zip`/`.tar.gz` URL. On a machine with no checkout, the one-line installer in the [repository README](../README.md#quick-start) needs neither git nor curl and works the same on Windows. Where git and curl are available, this also works:

```bash
curl -sSL https://raw.githubusercontent.com/Wneil2020/holon-skill/main/holon/scripts/holon.py | python3 - install Wneil2020/holon-skill
```

An agent tool reads only the descriptions of the folders directly inside its skills folder. It sees `holon/`, not `holon/office-docs/pdf/`. That is why the whole library is meant to live inside `holon/`: the tool has one folder to choose, and the tree does the rest of the routing. Cursor is the exception. It scans folders recursively and lists every sub-skill on its own as well; `install` says so when it writes for Cursor, and routing through the root still works there.

## A first tree in five minutes

The commands below are run from inside the `holon/` folder. Each output shown is the real output; a test runs every command on this page and compares.

Create a skill for office documents at the top level, then two sub-skills under it. `init` writes the folder and updates the parent's list of sub-skills:

```
$ python3 scripts/holon.py init office-docs --parent . --desc "Use when producing or reading office documents: covers Word, PDF, spreadsheet, docx"
created: ./office-docs/SKILL.md
synced ./SKILL.md (3 sub-skills)
done: 1 file(s) updated
```

```
$ python3 scripts/holon.py init docx --parent office-docs --desc "Use when writing or editing Word documents: covers Word, docx, report; excludes spreadsheet"
created: office-docs/docx/SKILL.md
synced office-docs/SKILL.md (1 sub-skills)
done: 1 file(s) updated
also synced ./SKILL.md (it lists the words of the skills below it)
```

```
$ python3 scripts/holon.py init pdf --parent office-docs --desc "Use when the input or output is a PDF: covers PDF, form, fill in, merge pages"
created: office-docs/pdf/SKILL.md
synced office-docs/SKILL.md (2 sub-skills)
done: 1 file(s) updated
also synced ./SKILL.md (it lists the words of the skills below it)
```

A description has three parts. `Use when ...` names the situation. `covers` lists up to five words; a task sentence that contains one of them is routed here. `excludes` lists nearby words that belong to another skill. Words are compared literally and without regard to case, after the sentence has passed through `synonyms.md`, which maps the words users say to the words the skills use.

The tree now looks like this:

```
$ python3 scripts/holon.py tree office-docs
office-docs — Use when producing or reading office documents: covers Word, PDF, spreadsheet, docx
├── docx — Use when writing or editing Word documents: covers Word, docx, report; excludes spreadsheet
└── pdf — Use when the input or output is a PDF: covers PDF, form, fill in, merge pages
```

`route` shows how a task sentence travels down the tree:

```
$ python3 organizer/scripts/organizer_cli.py route . "fill in this PDF form"
sentence: "fill in this PDF form"
root -> taken by: office-docs (via 'PDF')
office-docs -> taken by: office-docs/pdf (via 'PDF','form','fill in')
office-docs/pdf -> no sub-skills
lands on: office-docs/pdf
read: 3 file(s), 3,828 bytes of 26,515 in the library (14%)
```

The agent read three files and nothing else. The last line is that cost: the bytes on the path, against every `SKILL.md` in the tree. Lowering that number is what the tree is for.

When a sentence matches two sub-skills, the task spans both, and combining the two is the parent's job, so the route stops at the parent:

```
$ python3 organizer/scripts/organizer_cli.py route . "convert the Word report to a PDF"
sentence: "convert the Word report to a PDF"
root -> taken by: office-docs (via 'Word','PDF')
office-docs -> taken by: office-docs/docx (via 'Word','report'), office-docs/pdf (via 'PDF') -> two or more children take it; a sentence spanning children is the parent's job, stop at office-docs
lands on: office-docs
read: 2 file(s), 3,372 bytes of 26,515 in the library (12%)
```

A sentence that matches nothing stays at the root, and the agent works from the root's instructions:

```
$ python3 organizer/scripts/organizer_cli.py route . "draw a poster for the launch"
sentence: "draw a poster for the launch"
root -> taken by: (none)
lands on: root (nobody took it)
read: 1 file(s), 2,374 bytes of 26,515 in the library (8%)
```

## Checking the tree

The new skills still contain placeholder text, and both checkers refuse them until it is replaced:

```
$ python3 scripts/holon.py validate .
Found 6 problem(s):
  ✗ ./office-docs: example sentences (metadata.holon-triggers) are still TODO placeholders
  ✗ ./office-docs: body still contains TODO placeholders (body line 4)
  ✗ ./office-docs/docx: example sentences (metadata.holon-triggers) are still TODO placeholders
  ✗ ./office-docs/docx: body still contains TODO placeholders (body line 4)
  ✗ ./office-docs/pdf: example sentences (metadata.holon-triggers) are still TODO placeholders
  ✗ ./office-docs/pdf: body still contains TODO placeholders (body line 4)
```

```
$ python3 organizer/scripts/organizer_cli.py lint .
[E] office-docs: triggers are still the TODO placeholders from init; write 2 sentences it should take + 1 it should not
[E] office-docs/docx: triggers are still the TODO placeholders from init; write 2 sentences it should take + 1 it should not
[E] office-docs/pdf: triggers are still the TODO placeholders from init; write 2 sentences it should take + 1 it should not

lint: 3 errors, 0 warnings, 6 skills
bodies: 5 skills, 4 to 85 non-blank lines, median 9, 0 over 150
```

The last line of `lint` shows how evenly the work is divided: the shortest and longest body, the median, and how many are over 150 lines. It is information, not an error.

A finished skill looks like this:

```markdown
---
name: docx
description: "Use when writing or editing Word documents: covers Word, docx, report; excludes spreadsheet"
metadata:
  holon-triggers: |
    write the quarterly report in Word
    fix the heading styles in this docx
    draw a poster for the launch should go to /
---

# docx

1. Open or create the document with python-docx.
2. Apply the house styles from `references/styles.md` before adding content.
3. Write content section by section; never paste raw text into a heading.
4. Save and re-open once to confirm the file is not corrupt.
```

The three `holon-triggers` lines are the test for this skill: two sentences it should take, and one it should not, with where that one should go instead. The parent gets three sentences as well, and its sentences are the ones that no single sub-skill can take alone, such as "convert the Word report to a PDF". Once `pdf` and `office-docs` have their sentences and steps too, `replay` routes all of them:

```
$ python3 organizer/scripts/organizer_cli.py replay .
replay: 15/15 passed
```

When a later change sends one of those sentences somewhere else, `replay` names the sentence, where it landed, and which word took it. Every change to a tree ends with `validate`, `lint` and `replay`, and all three must pass.

## Starting an empty tree

To start from nothing instead of adding to the tree this repository ships:

```bash
python3 holon/scripts/holon.py init mylib --root ~/.agents/skills
```

This writes a root with the reading rules and three ledger files, and copies the tools in beside them, so the agent maintaining the tree has them at hand:

| File | What goes in it |
|---|---|
| `synonyms.md` | words users say, mapped to the words the skills use |
| `_feedback.md` | routing misses, one line each, recorded by the agent while it works |
| `ABSORB.md` | every placement decision, so the same question is not decided twice |

Before the first real task, run `route` on ten sentences the tree's owner has actually said. Most will miss, because skills use their authors' words and the owner uses different ones. Those misses are what `synonyms.md` is written from.

## The rule

Where a skill goes is decided by one question: remove it, and can the agent still do the job?

If it cannot, the thing is a **skill**, and it gets its own folder with a `SKILL.md`. If it can, only less well, the thing is **knowledge**, and it goes into a file under the `references/` folder of the skill that uses it. Knowledge never gets a folder of its own, so the tree never grows a "misc" folder.

The other rules ask the same question at other levels. A step of a skill that would pass the question on its own becomes a sub-skill, a folder inside that skill's folder; `pdf` is a step of `office-docs`. Two skills that answer the same request with the same result are one skill, so they are merged. A skill that several parents need, such as a theme tool used by both office documents and web pages, belongs to none of them; it stays at the top level and each parent points to it. Skills are never grouped by topic, size or file type, because none of those says whether the agent can do the job.

The full rules, with the procedure for adding a skill, are in `organizer/SKILL.md`. The agent reads that file when it maintains the tree.

## Adding a skill someone else wrote

`organizer/SKILL.md` gives five steps, and the agent follows them:

1. Put each part of the new skill through the removal question. Steps stay in `SKILL.md`; background moves to `references/`.
2. Check whether the tree already does this job. Same request and same result means merge, and the newcomer's wording goes into `synonyms.md`. Same topic but a different result is not a duplicate.
3. Find the parent by asking whose step this is. If it is no one's step, it goes at the top level.
4. Replay both skills' example sentences against each other. Where one takes the other's sentence, add an `excludes`.
5. Run `counter --bump`, then `validate`, `lint` and `replay`, and add a section to `ABSORB.md` saying what was decided.

Nothing is deleted. A skill that was merged or replaced moves whole into `.retired/`, so a wrong decision can be undone. `organizer_cli.py ask .` prints the checklist together with every earlier decision in `ABSORB.md`.

## Commands

| Command | What it does |
|---|---|
| `holon.py install [SRC]` | copy a tree to where the agent tools on this machine read skills, and check the copy |
| `holon.py hosts` | list the agent tools `install` knows, which are installed here, and the folders each reads |
| `holon.py init NAME --parent DIR [--desc D]` | create a skill and update its parent's list |
| `holon.py init NAME --root DIR [--bare]` | create a new root with the reading rules, the ledgers and (unless `--bare`) the tools |
| `holon.py sync [DIR]` | regenerate every parent's list of sub-skills from the folders |
| `holon.py tree [DIR]` | print the tree with descriptions |
| `holon.py validate [DIR]` | check headers, placeholders, stale lists, loops and the Agent Skills spec; exit 1 on error |
| `holon.py migrate [DIR]` | move pre-1.0 `triggers:` and `archive_count:` fields under `metadata:` |
| `organizer_cli.py lint ROOT` | check each description, its cover words, its example sentences, and `ABSORB.md` |
| `organizer_cli.py replay ROOT` | route every example sentence and report the ones that land wrong |
| `organizer_cli.py route ROOT "sentence"` | show one sentence's path, level by level |
| `organizer_cli.py overlap ROOT` | list sibling skills whose cover words overlap by more than 0.4 |
| `organizer_cli.py retire ROOT PATH --reason R` | move a skill into `.retired/` |
| `organizer_cli.py feedback ROOT` | list routing misses recorded in `_feedback.md` and not yet handled |
| `organizer_cli.py counter --bump ROOT` | increase the counter before adding a skill someone else wrote |
| `organizer_cli.py ask ROOT` | print the placement checklist and every earlier decision |

Commands that write files accept `--dry-run`.

## Status and limits

This is version 1.0.0, the first public release, and the project is at an early stage.

What has been checked: the tests run on Linux, macOS and Windows with Python 3.8 to 3.13; every command output on this page is compared with the real output by `tests/test_readme_outputs.py`; every `SKILL.md` in the repository passes the reference validator of the Agent Skills specification.

What has not: the rules have been applied to two libraries, a public library of twenty skills and three skills written for this project's own work. Applying them changed two passages of the rules. They have not been tried on a library of hundreds of skills. The numbers in the rules (five cover words, nine sub-skills per parent, 0.4 overlap) are values that made those two libraries checkable, not measured best values. They are settings: [organizer/README.md](organizer/README.md#changing-the-parameters-for-your-own-library) says how to change them for your own library.

Routing compares words, not meaning. A sentence that uses none of a skill's words does not reach it. The fix is a line in `synonyms.md`, and `_feedback.md` is where the agent records such a miss so that someone adds the line. The same comparison does not understand negation ("do not absorb anything" still contains `absorb`), and a sentence that asks for two unrelated things can be blocked by both branches' `excludes` and stay at the root.

What `replay` and `route` check is the word model, not the agent. The agent that reads the routing table decides by meaning, and may go where the word model would not, in either direction. Each line of the table shows the words the tools match on, including the ones a parent takes through the skills below it (`also takes, through its sub-skills: ...`), so the two at least read the same words; whether a given model then follows them is not measured yet. [references/evaluation.md](references/evaluation.md) describes the measurement that would answer it, and what it would take to count as evidence.

The root's description says "Use for every task", so that a tool which lists only top-level folders picks the tree. In a skills folder that also holds other top-level skills, that line competes with them; give the root a description naming what the tree covers instead (`init NAME --desc ...`).

The context measurements in `organizer/references/design-notes.md` (§17) count bytes of `SKILL.md` files on the path, not tokens, and not what the task reads after routing. They also show that most of the saving came from moving background into `references/`, which a flat library can do as well.

How to write the body of a skill, below its header, is a separate question with no settled answer yet. For now the rule is only that a body is numbered steps and that background goes into `references/`.

One person maintains this in spare time. A pull request that changes one thing and comes with a test is the quickest to be merged; [CONTRIBUTING.md](../CONTRIBUTING.md) says what a change has to keep true.

## Why it is built this way

`pdf/` is a complete skill: copy that one folder into another agent's skills folder and it works there unchanged. It is also one step of `office-docs/`, and nothing in the folder differs between the two roles. Arthur Koestler coined the word *holon* in 1967 for exactly this: a unit that is whole on its own and at the same time part of something larger. Because of this, moving a skill never means rewriting it. The folder is moved, and `sync` regenerates the parents' lists.

The tools never make a judgement. `holon.py` keeps every parent's list of sub-skills equal to the folders on disk. `organizer_cli.py` checks what can be checked mechanically: the shape of each description, that example sentences land where they should, that sibling skills do not claim the same words, that nothing was deleted. Where a skill belongs is decided by the agent reading `organizer/SKILL.md`; the tools check that the decision, once written down, keeps holding. The tree still routes with `organizer/` removed.

```
holon/
├── SKILL.md              how the agent reads a tree, and the top-level routing list
├── scripts/holon.py      install, hosts, init, sync, tree, validate, migrate
├── editing/SKILL.md      how the agent edits a tree through the tool
├── organizer/
│   ├── SKILL.md          the rules: where a skill goes, what counts as a duplicate
│   ├── scripts/organizer_cli.py   lint, replay, route, overlap, retire, feedback, counter, ask
│   └── references/design-notes.md why each rule is what it is, and what applying them taught
├── synonyms.md, _feedback.md, ABSORB.md   the three ledgers
└── tests/
```

The reasoning behind each rule, and what was learned each time the rules were applied, is in `organizer/references/design-notes.md`.

## License

MIT. See [LICENSE](LICENSE).
