# organizer

[中文说明](README.zh-CN.md)

The tree tool, `../scripts/holon.py`, keeps files well-formed and every parent's list of sub-skills equal to its folders. It cannot decide where a new skill belongs, whether two skills do the same job, which one wins when two give conflicting instructions, or how to remove a skill without losing it. `organizer` is the skill that answers those four questions. The answers are the rules in `SKILL.md`, which the agent follows when it adds a skill; `scripts/organizer_cli.py` is a tool that checks the rules were followed.

This page is about the tool. The rules themselves are in `SKILL.md` and are not repeated here.

## Files

- `SKILL.md`: the five rules, what every skill must carry, the five steps for adding a skill, the four questions to ask before creating a parent, how `.retired/` and `ABSORB.md` work, and the parameters.
- `references/design-notes.md`: why each rule and each number is what it is. Not needed while adding skills.
- `scripts/organizer_cli.py`: the tool. It compares words and checks structure, and makes no judgement about meaning. It reads skill files with the tree tool's own parser, so the two tools always see a file the same way.
- `tests/test_organizer_cli.py`: the tests, including a set that runs this package through its own checks.

## Commands

Run from the root of a tree, the folder that holds the root `SKILL.md`:

```bash
python3 organizer/scripts/organizer_cli.py lint     .                     # format checks; exit 1 on any [E]
python3 organizer/scripts/organizer_cli.py replay   .                     # route every example sentence; exit 1 on any failure
python3 organizer/scripts/organizer_cli.py route    . "a sentence"        # show where one sentence goes, level by level
python3 organizer/scripts/organizer_cli.py overlap  . [--threshold 0.4]   # sibling skills whose cover words overlap
python3 organizer/scripts/organizer_cli.py retire   . <path> --reason R   # move a skill into .retired/
python3 organizer/scripts/organizer_cli.py feedback .                     # unhandled lines in _feedback.md
python3 organizer/scripts/organizer_cli.py counter  . [--bump]            # show or increase the absorption counter
python3 organizer/scripts/organizer_cli.py ask      .                     # the checklist and every earlier ruling
```

Every change to a tree ends with three commands, and all three must pass:

```bash
python3 scripts/holon.py validate .                  # file format and routing lists
python3 organizer/scripts/organizer_cli.py lint .    # every skill has what it must carry
python3 organizer/scripts/organizer_cli.py replay .  # example sentences still land where they should
```

## Reading `lint`

`lint` prints three kinds of line, and only the first kind fails.

**`[E]`, error, exit code 1.** Something the tree cannot work without: a missing description, a description with no cover words or too many, fewer than three example sentences, a negative example pointing at a skill that does not exist, a malformed `groups.md`.

**`[W]`, warning.** Probably a mistake, but the tree still works: fields left over from an earlier format, a cover word so short it matches almost anything, a cover word that `synonyms.md` rewrites before matching, a group with one member, a missing `_feedback.md`, an `ABSORB.md` section numbered ahead of the counter or numbered twice, a file in `.retired/` without its header line, a file named in a body that does not exist.

**`[·]`, hint.** Not counted and not an error; these are the "Hints, not rules" of `SKILL.md`. A body longer than MAX_BODY or shorter than three non-blank lines, a parent with more than FANOUT children and no `groups.md`, a parent with one child and an empty body, an `excludes` word that no sibling covers.

The last line counts them, for example `lint: 0 errors, 0 warnings, 5 skills`, and the line after it summarizes body lengths across the tree.

`lint` reads descriptions and structure. It does not read a body for meaning, so it cannot tell whether a body describes a skill or contains knowledge that belongs in `references/`.

## What the tool checks, and what it leaves to the agent

`replay` routes each skill's example sentences from the root. A positive example must land on its own skill and a negative one must not. When a sentence matches two children of one parent, it stops at the parent, and that counts as correct, because a job spanning two steps is the parent's. When two top-level skills both match, `replay` reports `[FAIL ambiguous]`. Each failure says why: which sibling took the sentence and by which word, which `excludes` blocked it, or at which level it stopped for lack of a word.

`route` walks one sentence and prints each level: who took it, by which word, and which child was blocked by its own `excludes`. If `synonyms.md` rewrote the sentence, the rewritten sentence is shown. It is the command to run after changing cover words or synonyms, before `replay`.

`overlap` lists pairs of siblings whose cover words overlap by more than OVERLAP; those are the pairs to look at for a possible merge. `retire` moves a folder to `.retired/<original path>/`, writes `retired @<count> <reason>` as the first line of each `SKILL.md` inside, and runs `sync`. `ask` prints the four questions of `SKILL.md` exactly as they are written there, then every `ruled:` line in `ABSORB.md`, so that earlier decisions are read before a new one is made.

What stays with the agent is everything that needs meaning: the five rules, the removal test, the placement questions, and what to do about a hint. The tool's guarantee is narrower. Once a decision is written down as a description, an example sentence or a synonym, it is checked the same way every time. Three passing checks therefore show that the tree is well-formed and that every decision so far still holds. They do not show that every skill is in the right place; `_feedback.md` is where evidence of that arrives.

### What a passing result does not promise

A negative example can pass because it avoids its own skill without reaching the named target. `replay` then prints `NOTE negative did not reach its target`; this note does not change the exit code. Read notes as well as the passed count. Similarly, a missing referenced file is a lint warning, not an execution test. Three zero exit codes do not prove that every dependency exists, that a task can run, or that a real agent will follow the same path.

Non-ASCII cover words are matched as substrings, not segmented words: `文件` also matches `文件夹`. Lowering COVER_MIN to 1 increases this risk; it does not add Chinese word segmentation. Synonyms are folded globally and without context, so an alias that fixes one miss can create another false match. Retest both intended and unrelated requests after each change.

A skill with references to its parent/root, other skills, or a tree-relative negative-example target is not self-contained. Copy those dependencies or adjust the references and examples before validating it in another tree. The organizer script itself depends on the root's `scripts/holon.py`.

## After retiring a skill

`retire` moves a folder without reading it, and `lint` and `replay` never look inside `.retired/`. It does not update other skills whose negative examples pointed at the retired one. After retiring `web/chart`, `lint` names each of them:

```
[E] lib-org: negative-example target 'web/chart' is not a skill in this library
[E] web/dark-mode: negative-example target 'web/chart' is not a skill in this library

lint: 2 errors, 0 warnings, 4 skills, 1 retired
```

## Changing the parameters for your own library

The rules in `SKILL.md` are the same for every library. Six numbers in them are not: they are settings, chosen so that the two libraries this was first applied to could be checked, and a library with other habits may want other values. They are in two places that must agree:

- the table at the end of `SKILL.md` (section "Parameters"), which the agent reads;
- the constants near the top of `scripts/organizer_cli.py`, which `lint` and `overlap` use.

A test (`test_param_table_matches_cli_constants`) compares the two, so change both together. After changing them, run `python3 scripts/check.py` at the repository root.

| Parameter | Shipped value | What it controls | Kind | When to change it | Range the tests accept |
|---|---|---|---|---|---|
| COVER_MAX | 5 words | most cover words in one description | error `[E]` | Raise it if your skills are named by many short words (for example a Chinese library with several near-synonyms per skill). Lower it to force narrower skills | 5 or more. Below 5 the package's own `editing` skill (5 cover words) fails `lint`; shorten its description first |
| COVER_MIN | 2 characters | shortest cover word | warning `[W]` | Set it to 1 for a Chinese or Japanese library, where one character is often a whole word. Raise it to 3 if two-letter words keep over-matching | 1 to 4. At 5 the package's own four-letter cover words (`task`, `sync`) are warned |
| DESC_MAX | 200 characters | longest description | error `[E]` | Raise it for languages that need more characters, or to allow longer `Use when` clauses. A Chinese library can go lower | 198 or more (the package's longest description is 198) |
| MAX_BODY | 150 lines | body length that produces a hint | hint `[·]` | Lower it to be reminded earlier that knowledge belongs in `references/`; raise it if your skills are long procedures | any; below 85 the `organizer` skill itself gets the hint |
| FANOUT | 9 | children under one parent before a hint suggests a parent or `groups.md` | hint `[·]` | Lower it if your agent picks the wrong line in long tables; raise it if you accept long flat tables | any positive integer |
| OVERLAP | 0.4 | share of cover words two siblings may have in common before `overlap` lists them | screen | Lower it to see more possible duplicates, raise it to see fewer | between 0 and 1 |

"Kind" says what happens when a skill goes past the value. Only an error makes `lint` exit 1; a warning is printed and counted; a hint is printed and not counted. `OVERLAP` only changes what `overlap` lists.

How to change one by hand:

1. Edit the row in the table in `SKILL.md`. Keep the unit words (`words`, `characters`, `lines`), because the test reads them.
2. Edit the constant of the same name in `scripts/organizer_cli.py`.
3. Run `python3 organizer/tests/test_organizer_cli.py` (and, from the repository root, `bash scripts/check.sh`), then `validate`, `lint` and `replay` on your tree. A lower limit may turn existing skills into errors; `lint` names each one.
4. Add a `ruled:` line to your tree's `ABSORB.md` saying which value changed and why, for example `ruled: COVER_MIN 2 -> 1 -> the library is in Chinese; one-character words are real words`. Rule changes are decisions, and `ask` shows them to the agent before the next one.

Change one value at a time, so that whatever `lint` reports afterwards can be traced to it. The reasons for the shipped values are in `references/design-notes.md`, section 10.

The README walkthrough (`holon/README.md`) quotes output produced with the shipped values. Its test runs the walkthrough on a copy with the shipped values put back, so changing a parameter does not break that test.

### What is not a parameter

Everything else in `SKILL.md` is a rule, not a setting: the description format `Use when ...: covers ...; excludes ...`, three example sentences per skill, the stop-at-parent behaviour, `.retired/` instead of deletion, and the `learned:` / `merged:` / `ruled:` lines of `ABSORB.md`. The tools depend on these, and changing them means changing the tools and their tests (see `CONTRIBUTING.md`).

The parts of a library that are yours to fill in are not parameters either; they are files:

| File | What you put in it |
|---|---|
| root `SKILL.md` | the tree's name and the skills below it (`holon.py init NAME --root DIR` writes it) |
| `synonyms.md` | your own words, mapped to the cover words your skills use. Start from ten sentences you have actually said, as `SKILL.md` describes |
| `groups.md` (optional, next to a parent) | section titles for a long routing table |
| `ABSORB.md` | your decisions, including parameter changes |

## Tests

```bash
python3 tests/test_organizer_cli.py
```

Run them after editing `SKILL.md` as well as after editing the tool. This package has to pass `validate`, `lint` and `replay` itself, and `SKILL.md` has to keep the phrases the tool and `ask` depend on.

## License

MIT. See the `LICENSE` file at the package root.
