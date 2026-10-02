# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.0.0] - 2026-10-02

First public release, under the project name **holon skill**. One package, `holon/`, with the rules in `organizer/`; it installs as a skill folder named `holon`.

### Open-source release
- Project renamed to *holon skill*. The package folder, the installed folder name, the tool names (`holon.py`, `organizer_cli.py`) and the `holon-` metadata keys are unchanged, so trees built during development keep working.
- The repository is the package alone. The draft packages used while preparing it (the body rule, the writing rules, the three work skills and the evaluation folder) are not part of the release.
- `install.py` at the repository root: the one-command install for users, `python3 -c "import urllib.request as u; exec(u.urlopen('https://raw.githubusercontent.com/Wneil2020/holon-skill/main/install.py').read())"`. It needs neither git nor curl, so the same line works on Windows.
- `organizer/README.md` and the new `organizer/README.zh-CN.md`: "Changing the parameters for your own library": what each parameter controls, when to change it, the range the tests accept, and how to record the change in `ABSORB.md`. `organizer/SKILL.md` says the six values are settings of the library.
- Tests no longer depend on the parameter values: the organizer tests compute their inputs from the constants, and `tests/test_readme_outputs.py` runs the README walkthrough on a copy with the shipped values put back.
- The repository no longer ships `examples/`. The example library was built from a third-party skill collection whose licences do not all allow redistribution. The README walkthrough builds a three-skill tree from scratch, and `tests/test_readme_outputs.py` runs every quoted command of both the English and the Chinese README against that tree.
- The design notes keep the measurements taken on that library (§14, §17 to §19) as a record; they describe the library, not files in this repository.
- Added at the repository root: `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, issue and pull request templates, `scripts/check.py` and `scripts/check.sh` (run locally what CI runs; `check.py` also on Windows).

### Tree tool (`scripts/holon.py`)
- `init`, `sync`, `tree`, `validate` commands; every writing command supports `--dry-run`.
- Routing table injected between `<!-- sub-skills -->` markers; markers inside code fences and inline code are ignored.
- `groups.md` sections the routing table without moving directories.
- `validate` rejects TODO placeholders in descriptions and bodies, stale routing tables, cycles, and malformed `groups.md`.
- Frontmatter parser supports scalars, quoted scalars with escapes, lists, `|` and `>` block scalars, and a leading BOM.

### Rules (`organizer/`)
- Rules file `organizer/SKILL.md`: five rules, the three things every skill carries, the five steps for adding a skill, the four-question checklist, the no-deletion policy, the `ABSORB.md` format, hints and parameters.
- `organizer_cli.py`: `lint`, `replay`, `route`, `overlap`, `retire`, `feedback`, `counter`, `ask`.
- Routing: when two children of one parent match, the route stops at the parent; when two top-level skills match, it is reported as a conflict.
- `replay` explains each failure: which sibling took the sentence and by which keyword, whose `excludes` blocked it, or at which ancestor it was stopped.
- `lint` warns on alias cover words and alias/cover-word collisions in `synonyms.md`.

### Development before release (from the first draft of 2026-09-16)

*Changed*
- One repository. `holon` and `holon-organizer` were the same tree tool published twice, once with rules and once without; the rules follow from what the tree already assumes (`design-notes.md` §13), so there is one package, `holon`, with `organizer/` inside it. Deleting `organizer/` and running `sync` leaves the bare tree.
- Root `SKILL.md` is the six reading rules and the routing table, 27 lines. Editing the tree is a job with steps and a result, so it is a sub-skill, `editing/`, by rule 3; an intermediate fix had put it in `references/editing.md`. The root is read on every task; before, every route paid for 52 lines of editing instructions.
- Root description is in the three-part form and says the tree is the entry point for every task. `design-notes.md` §15: the host sees only top-level folders, so the tree is meant to be the whole library.
- `init` scaffold body is one numbered `TODO` step, not two prose sections. `validate` catches `TODO` inside numbered-list items, which it missed.
- `organizer` description: `excludes domain knowledge itself` replaced by `excludes sync, validate`; routing is literal and no user sentence contains the former.
- `lint` does not report a body as "very short" while it still carries the scaffold's `TODO`; `validate` already reports that.

- (Not in the open-source release; see "Open-source release" above.) `examples/anthropics-skills/` shipped structure and headers only. The bodies of the upstream skills that forbid redistribution (`docx`, `pdf`, `pptx`, `xlsx`) or carry no licence (`doc-coauthoring`), including the second-pass rewrites of `pdf`, `pptx` and `doc-coauthoring`, are stubs. Modified Apache-2.0 bodies carry a notice, and the folder has `NOTICE.md` and the Apache licence text.

- `install` has no default tool. It writes to the shared `~/.agents/skills/` of the Agent Skills standard and to the directory of every agent tool found on the machine that reads somewhere else, choosing directories so that no tool sees the tree twice (Cursor and OpenCode read both the Claude and the shared directories). Every directory gets a real copy; `--link` links instead, since some tools do not follow links to skill folders. The table covers 32 tools; `holon.py hosts` lists them, which were found, and what each reads. `--host` is repeatable, `--force` replaces an earlier install.
- The Claude Code plugin marketplace file is removed. It served one tool, and it installed the rules without the tree.

*Fixed*
- `validate`, `tree` and `lint` no longer crash with `UnicodeEncodeError` when stdout cannot encode `✓`, `✗`, `·` or box-drawing characters (Windows consoles and redirected output default to cp1252). Such characters now print as `?`; exit codes are unchanged. Regression test added.

*Added*
- `lint` warns when two `ABSORB.md` sections carry the same `@n`; each absorption has its own number.
- `organizer/SKILL.md` names the two things an `excludes` word can do: a redirect (some skill covers the word) or a refusal (none does). `lint` lists refusals as hints. On the example library: 28 redirects, 15 refusals, all 15 intended.
- `organizer/SKILL.md`: the first entries in `synonyms.md` come from routing ten of the owner's own sentences before the first task.
- `tests/test_readme_outputs.py`: every command output quoted in the README is produced by running the command and compared; CI runs it.
- `design-notes.md` §16: what the first tree built for real work showed (owner's sentences miss until `synonyms.md` is built from them; a five-entry table is already two kinds of thing).
- `examples/anthropics-skills/`: the tree, headers and ledgers from absorbing a public 20-skill library; upstream bodies replaced by pointers. CI runs `validate`, `lint` and `replay` on it, so a rule or tool change that breaks a real tree fails the build.
- `route` ends with the cost of the route: how many `SKILL.md` files were read on the path, their bytes, and the bytes of every `SKILL.md` in the library. This is the number the tree exists to lower; it is now printed rather than computed by hand.
- `design-notes.md` §17: the first measurement of that cost, ten sentences on the example library with upstream bodies, tree against a flat host. Where a card has had its second pass the tree reads 0.08 to 0.62 of the flat cost; where it has not, about 0.9.
- Routing: a parent answers to every cover word below it. A sub-skill is a step of its parent, so "build a pitch deck" reaches `office-docs/pptx` through `office-docs` although `office-docs` lists neither word; before, the route stopped at the root unless the parent repeated the child's words, and COVER_MAX left no room to. Only a skill's own `excludes` blocks it. `route` names the child whose word took the sentence. Rule text and `replay` messages changed to match.
- Frontmatter follows the Agent Skills specification. holon's two fields moved under `metadata:` as `holon-triggers` (one sentence per line) and `holon-archive-count`; the top-level `triggers:` and `archive_count:` of earlier drafts are read but reported by `validate`, and `holon.py migrate` rewrites them. `validate` also checks the spec's `name` rules and that `name` equals the directory. Every `SKILL.md` in the repository passes `skills-ref validate`, and CI runs it (`design-notes.md` §20).
- `init` without `--parent` writes a root: the six reading rules as its body, the standard root description, `metadata.holon-archive-count: "0"`, and the three ledgers `_feedback.md`, `synonyms.md`, `ABSORB.md`. From the command line it also copies `scripts/`, `organizer/` and `editing/` in beside them and syncs the root's table, so the tree can be maintained where it is; `--bare` leaves the three out. A tree started this way passes `validate`, `lint`, `replay` and `skills-ref` before its first skill is added.
- `holon.py install [SRC] [--path P] [--host H ... [--project] | --to DIR] [--as NAME]`: one command puts a tree where a host reads it. SRC is a path, a git URL, GitHub `owner/repo` or a `.zip`/`.tar.gz` URL (shallow clone or stdlib unpack into a temporary folder; the tree inside is the child carrying `scripts/holon.py`, else the command lists the skill folders and asks for `--path`); default is the tree this script is in. The script runs from stdin too, so `curl ... | python3 - install owner/repo` is an install with no checkout. Copies the tree into the host's skills directory without `examples/`, `tests/`, caches and the repository's `.claude-plugin/`; fills in `scripts/holon.py`, `organizer/` and `editing/` when the copied tree kept only their headers; runs `validate`, `lint` and `replay` on the copy and prints the three verdict lines. Replaces the sequence clone, choose folder, copy, rename, check, each of which an agent had to get right on its own. Verified against Claude Code 2.1.267: the copy is a plain skills-directory folder, loaded at the next session.
- `init` with `--parent` writes three `TODO` example sentences; `validate` and `lint` refuse them until written.
- `synonyms.md` lines beginning with `#` are comments.
- `lint` ends with one line on how evenly the work is cut: body lines of every skill, smallest to largest, median, and how many are over MAX_BODY. Printed, not judged.
- `lint` warns when a body names a file in backticks that is not under the skill or at the tree root. On the example library this found 20 pointers to upstream files the example does not carry, and two `references/` files the `pdf` second pass named but never wrote; stubs added for all 22, each saying where the upstream file is; the six passes of §19 added 13 more.
- `examples/anthropics-skills/_sentences.md`: twenty sentences quoted by the upstream authors as what their users say, with where each lands; the test suite routes them. 6 of 20 landed before this release's changes, 15 after; the five misses are in `_feedback.md` with reasons (`design-notes.md` §18).
- Example library: second pass on `claude-api` (377 lines to 27; 19 reference summaries to one `references/` file; four maintenance subcommands to `claude-api/maintain/`; Managed Agents to top-level `managed-agents/`).
- Example library: second pass on the six remaining bodies over 150 lines (`algorithmic-art`, `doc-coauthoring`, `slack-gif-creator`, `pptx`, `discernment-nudge`, `mcp-builder`), giving `doc-coauthoring/reader-test` and `mcp-builder/evals`. With upstream bodies the library is 120,980 bytes of `SKILL.md`, from 183,995; no body over 150 lines. 31 skills, 90 sentences replayed (`design-notes.md` §19).

*Fixed*
- `replay`: when a grandchild's example is taken by both its parent and its parent's sibling, the explanation now names the sibling. It used to say the parent's cover words were absent when they were present. Test added.

*Changed*
- `replay`: the message for a parent example taken by only one child now says what to do when that child is new (move the sentence to the child, give the parent a spanning one). Both second passes in design-notes §14 ended on this message.
- Rule 2 now says what to do with knowledge that no skill in the library uses: add the missing skill, or retire it.
- The passage on sibling `excludes` now says to add one only after `replay` shows a sibling taking the example, and records the case where writing them in advance failed every cross-child sentence.
- `design-notes.md` §14: the first application of the rules to a public library (anthropics/skills, 20 cards), what held, what was amended, what was not done.
- README: the `route` example now states which tree it was run on and shows a second sentence that descends to a leaf. Its output is the real output of the tool.
