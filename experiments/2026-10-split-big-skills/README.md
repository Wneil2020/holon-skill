# Splitting four long skills with `holon.py split` (2026-10-17)

[中文](README.zh-CN.md)

## Question

holon's claim beyond routing is that one long, mixed `SKILL.md` can be re-planned into a short core, sub-skills and `references/` files, so an agent reads only the part a task needs. The routing experiment (`../2026-10-anthropic-skills/`) and Graph of Skills both measure *choosing among* skills that are already clean; neither measures this. Three things were checked here:

1. Does the split lose or change any text?
2. With the split, does the agent still find the answer, and how much does it read?
3. Is holon's planned split better than a mechanical one?

## Setup

- **Skills.** The four longest relevant files in the Graph of Skills `skills_1000` library ([dataset](https://huggingface.co/datasets/davidliuk/graph-of-skills-data)): `citation-management` (1,115 lines), `rdkit` (769), `pymatgen` (691), `senior-data-engineer` (608, a grab-bag that repeats its Quick Start inside its Workflows). The first three are oracle skills of SkillsBench tasks.
- **Questions.** 96, written from the *original* files before any split existed: each file cut into four equal windows, six questions per window, each with a short reference answer and the line range it comes from (`qgen.py`, `questions.json`).
- **Three ways to give the agent the skill.**
  - `full`: the whole original `SKILL.md`.
  - `heading`: a mechanical split; every `##` section longer than 25 lines moves to `references/<slug>.md`, leaving `Details for this section: references/x.md`.
  - `holon`: an agent reads holon's own rules (organizer rules 1–3, the description form, organizer step 1, editing step 4) and the numbered file, and writes a `split --plan`; `holon.py split` applies it. It never sees the questions. If the dry run refuses the plan, the error goes back to it (up to five tries; it needed one retry, for `citation-management`).
  
  In `heading` and `holon` the agent starts from the remaining `SKILL.md` and may open up to three files per round for up to three rounds, then answers.
- **Measures.** *Correct*: a judge compares the answer with the reference answer and its source lines. *Reached*: every non-blank source line appears in the text the agent read (strict; a fact repeated elsewhere is not counted). *Chars*: everything the agent read.
- **Hard set.** The same model answering with no file at all gets 42 of 96 right (rdkit and pymatgen are well known to it). The 54 it gets wrong are the hard set; only there does reading the skill decide the answer.
- Model `deepseek-v4.1-flash` for questions, plans, answers and judging. One run.

## Results

**Nothing was lost.** For both splits, every non-blank line of each source body exists in the split tree, counted as a multiset (`conserve.py`): 853, 544, 504 and 401 lines, 0 missing.

What the splits produced:

| skill | holon: sub-skills / new reference files / lines left in SKILL.md | heading: reference files / lines left |
|---|---|---|
| citation-management | 4 / 10 / 81 | 9 / 90 |
| rdkit | 12 / 2 / 88 | 3 / 53 |
| pymatgen | 9 / 5 / 166 | 5 / 104 |
| senior-data-engineer | 0 / 11 / 31 | 7 / 93 |

Hard set (54 questions):

| condition | correct | reached | chars read | files opened |
|---|---:|---:|---:|---:|
| full | 54/54 | 1.000 | 27,168 | 1.00 |
| heading | 52/54 | 0.574 | 39,014 | 3.37 |
| holon | 52/54 | 0.741 | 19,856 | 3.00 |

All 96 questions: full 96/96 at 24,679 chars; heading 93/95 (one call failed) at 33,386; holon 94/96 at 16,396.

Per skill, chars read with holon vs full: rdkit 10,583 vs 20,789, pymatgen 13,108 vs 20,841, citation-management 14,726 vs 33,411, senior-data-engineer **27,165 vs 23,678**.

## What it shows

- **holon's split kept the answers and cut reading by about a third** (−27% on the hard set, −34% on all questions), at a cost of 2 wrong out of 54 against 0. One miss was a command example that the plan had filed under example workflows while the agent looked under formatting; the other was a flag that both split conditions missed.
- **A mechanical split is worse than no split.** Same verbatim moves, same tool, but pointers that only say "details here": the agent opened more files and read 44% *more* than the whole file. What the pointer line says is the difference between the two splits.
- **A grab-bag that repeats itself is not fixed by splitting.** On `senior-data-engineer` the planner made no sub-skills, only references, and the agent read more than the original, because the same commands sit in several moved pieces. Verbatim moves carry both copies along; the copies have to be merged first.
- Real-world headers: `senior-data-engineer`'s header (nested maps, `related-agents: []`) was outside holon's YAML subset, so `split` refused the file. The experiment cut that header to `name` and `description` (its only edit to source text); holon now reads one-line flow lists such as `[]`, and still refuses nested maps.

## What changed in holon

- `holon.py` reads one-line flow lists (`key: []`, `key: [a, "b, c"]`); nested flow collections are still refused. Test: `test_one_line_flow_lists`.
- editing step 4: a pointer says what the moved text is for and when to open it, not only where it is.
- organizer step 1: if a file repeats itself, merge the copies before splitting.

## Limits

- Four skills, 96 questions, one run, one model family writing questions, plans, answers and judgments. The questions are lookups (a command, a flag, a function); a task that needs several parts at once was not tested.
- 25k characters is cheap for current models. The saving matters when many skills are loaded at once or the context is small; this run does not measure end-to-end task success.
- `reached` is strict and undercounts facts that appear twice; *correct* depends on the judge.

## Reproduce

```bash
export LLM_BASE_URL=https://your-endpoint/v1 LLM_API_KEY=... LLM_MODEL=deepseek-v4.1-flash
cd experiments/2026-10-split-big-skills/scripts
./fetch.sh                                   # GoS skills_1000 into ../data/
export SPLIT_WORK=$PWD/..                    # trees/ and results/ go next to this README
python3 apply_saved.py                       # rebuild both splits from ../plans/ (no model calls)
python3 conserve.py                          # 0 missing lines
python3 answer.py full,heading,holon run1    # answers + judge
python3 answer.py none none1                 # no-file baseline
python3 report.py run1
python3 hard.py ../results/run1.json ../results/none1.json
# to re-plan instead of using the saved plans: python3 plan.py ; to rewrite questions: python3 qgen.py
```
