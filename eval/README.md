# eval: measuring whether the tree helps

[中文](README.zh-CN.md)

`replay` shows that a tree agrees with its own word model. It does not show that an agent routes the same way, picks the right skill more often than with a flat folder, or reads less to get there. This folder holds the tool that measures that: `harness.py`, standard library only, like the rest of the repository. It is not part of the installed package.

No result with a real agent has been published yet. The numbers below come from the word model, which costs nothing and is what CI runs; they show the harness works, not that the tree helps.

## What is compared

Three arrangements of the same skills, so that the effect of the tree is separated from the effect of shorter bodies:

| Arrangement | What it is | How you get it |
|---|---|---|
| A. flat, original | every skill as it arrived, side by side | the folder you start from |
| B. flat, trimmed | the tree's skills, bodies as in the tree, side by side | `harness.py flatten TREE OUT` |
| C. holon tree | the same skills, placed by the organizer rules, as one root | `holon.py init`, then `holon.py move --plan` |

B minus A is the effect of rule 2 (moving knowledge out of the body). C minus B is the effect of the tree. Design notes §17 suggests most of the saving measured so far is B minus A.

## From a flat folder to a result

```bash
# 1. a root, and the parents your plan needs (organizer/SKILL.md decides which)
python3 holon/scripts/holon.py init mylib --root build
python3 build/mylib/scripts/holon.py init office-docs --parent build/mylib --desc "Use when ...: covers ..."

# 2. a plan: one line per skill, `SRC -> DEST` (DEST is parent/name; `parent/` keeps the name)
#      flat/word-docs -> build/mylib/office-docs/docx
#      flat/poster    -> build/mylib/
python3 build/mylib/scripts/holon.py move --plan plan.txt --copy     # --dry-run first; all or nothing
python3 build/mylib/scripts/holon.py validate build/mylib

# 3. arrangement B
python3 eval/harness.py flatten build/mylib build/trimmed

# 4. sentences, frozen before you touch cover words or synonyms.md
python3 eval/harness.py freeze sentences.tsv

# 5. runs, then the report
python3 eval/harness.py run sentences.tsv --tree build/mylib --flat flat --trimmed build/trimmed \
    --names plan.txt --runner claude-code --runs 3 --out results.csv
python3 eval/harness.py report results.csv
```

`move` is the mechanical half of placement. Where each skill goes, and which parents exist, is still decided by a person or an agent following `organizer/SKILL.md`; the plan file is where that decision is written down, so it can be reviewed and re-applied.

## The sentence file

Tab-separated, with a header: `id  split  sentence  expected`.

- `split` is `test` or `tune`. Only `test` lines are run and counted. A sentence you used to adjust the tree goes in `tune`.
- `expected` is one or more skill folder names, `|`-separated, or `none` when no skill should take the sentence. Write it before running anything.
- `freeze` stores a hash of the test lines. `run` refuses a test split that is not frozen or has changed since; `--unfrozen` runs anyway and the report says those runs are not evidence.
- Aim for at least 50 test sentences, written by people who did not place the skills: lines from `_feedback.md`, issues, chat logs. Include on purpose paraphrases with none of the cover words, a second language, negation, and sentences that need two skills.

## Runners

| `--runner` | What runs | Cost |
|---|---|---|
| `word-model` (default) | the organizer's lexical routing | none; this is what CI runs |
| `claude-code` | `claude -p` in a scratch project whose `.claude/skills/` holds the arrangement, with an empty `HOME`, tools limited to `Read, Glob, Grep, Skill` | one agent session per run |
| `command` | any agent: `--runner-cmd` gets `{skills}`, `{prompt_file}`, `{workdir}` and prints one JSON line `{"chosen": ..., "files_read": [...], "input_tokens": N}` | yours |

`--mode route` (default) tells the agent not to do the task, only to decide whose instructions it would follow and end with `SKILL: <name>`. That measures routing cheaply. `--mode task --check CMD` lets the agent do the task and runs `CMD` in the project folder afterwards; exit 0 counts as `task_ok`.

By default the `claude-code` runner gives each run an empty `HOME`, so the user's own skills and `CLAUDE.md` stay out of it; that also hides a subscription login, so export `ANTHROPIC_API_KEY`, or pass `--keep-home` and say so in the result. `--raw-dir DIR` keeps every run's stream-json, and the `skills_seen` column lists the skills the host reported at start-up, so a run that saw skills from elsewhere can be found.

A run that never reached a model (a refused key, an exhausted quota, a proxy message instead of an answer) is recorded with its error and left out of every rate. It is not counted as a wrong choice.

## What the report shows

- per arrangement: completed runs, `route_ok`, `task_ok`, median bytes read (the host's top-level listing plus every file opened), median input tokens as the host reports them;
- on C: how often the agent chose what the word model chose, and when they differ, which one was right. This is the number that says whether `replay` passing means anything for that host and model;
- every wrong choice, by sentence.

## The worked example

`example/` is a five-skill flat library, a plan, and twelve test sentences, two of them tuning. `example/build.py` builds the tree and the trimmed copy from those inputs; CI builds it and runs the word model on it. Output on the current tools:

```
| arrangement | runs | sentences | route_ok | task_ok | median bytes read | median input tokens |
|---|---|---|---|---|---|---|
| A | 12 | 12 | 7/12 (58%) | - | 686 | - |
| B | 12 | 12 | 7/12 (58%) | - | 762 | - |
| C | 12 | 12 | 9/12 (75%) | - | 3873 | - |
```

Read it for what it is: twelve sentences written by the same person who wrote the skills, and a lexical model. C takes the two cross-format sentences that A and B leave unrouted, because the parent `office-docs` exists to take them. All three miss "fill out this Acrobat document" and "make a presentation about our Q3 numbers" (no cover word), and all three send "do not touch the PDF" to `pdf` (no negation). C reads more bytes, because a tree routes through its root's instructions and tables; whether that costs more tokens than a host's flat listing at fifty or five hundred skills is the question a real run answers.

To continue this work, start with [HANDOFF.md](HANDOFF.md): what is done, what is not, and the first real-agent run step by step.

## Contributing a result

Open an issue with `results.csv`, the sentence file, the plan, the library (or a description, if it cannot be shared), the host and model versions, and the date. A result that shows the tree does not help is as useful as one that shows it does.

## Tests

```bash
python3 eval/tests/test_harness.py
```

They cover `holon.py move`, `flatten`, freezing, all three runners (the `claude-code` runner against a fake `claude` that prints recorded stream-json), and a run that reached no model. No model is called.
