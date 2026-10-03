# Measuring whether the tree helps

[中文](evaluation.zh-CN.md)

`replay` shows that a tree agrees with its own word model. It does not show that an agent routes the same way, picks the right skill more often than with a flat folder, or finishes the task with less context. This page says how to measure that, so that a result can be compared with another. No result has been published yet.

## What to compare

Three arrangements of the same skills, so that the effect of the tree is separated from the effect of shorter bodies:

| Arrangement | What it is |
|---|---|
| A. flat, original | every skill as it arrived, side by side in one skills folder |
| B. flat, trimmed | the same bodies as in the tree (background moved to `references/`), still side by side |
| C. holon tree | the same skills, placed by the organizer rules, installed as one root |

B minus A is the effect of rule 2 (moving knowledge out of the body). C minus B is the effect of the tree. Design notes §17 suggests most of the saving measured so far is B minus A.

## The sentences

- At least 50 task sentences per library, written by people who did not place the skills. Sentences from `_feedback.md`, from issue trackers or from chat logs count; sentences written while placing the skills do not.
- Freeze them before any change to cover words or `synonyms.md`. A sentence used to tune the tree is moved to the tuning set and not counted.
- Include on purpose: paraphrases with none of the cover words, a second language, negation ("do not ..."), sentences that need two skills, and sentences that two independent tasks share.
- For each sentence, record the skill or skills a person expects before running anything.

## What to record per run

| Field | Meaning |
|---|---|
| `host`, `model` | for example Claude Code with a given model, Codex, Cursor |
| `arrangement` | A, B or C |
| `files_read` | every `SKILL.md` and reference file the agent opened, in order |
| `chosen` | the skill whose steps it followed |
| `route_ok` | `chosen` is one of the expected skills |
| `task_ok` | the task's result meets a check written beforehand |
| `input_tokens` | as the host reports them, for the whole task, not only routing |
| `wall_time`, `retries` | as observed |
| `word_model` | what `organizer_cli.py route` says for the same sentence on C |

Run each sentence at least three times per arrangement and model; agents are not deterministic.

## What to report

- `route_ok` and `task_ok` rates per arrangement, with the number of runs.
- Tokens per task, median and spread, per arrangement.
- On C: how often the agent's path equals `word_model`. When they differ, which one was right. This is the number that says whether `replay` passing means anything for that host.
- The sentences that failed, verbatim.

A tool built for running agents on tasks and grading the outcome, such as [skillgrade](https://github.com/mgechev/skillgrade), can do the runs; this page only fixes what is compared and counted.

## Contributing a result

Open an issue with the table above as a CSV, the sentence file, the library (or a description, if it cannot be shared), the host and model versions, and the date. A result that shows the tree does not help is as useful as one that shows it does.
