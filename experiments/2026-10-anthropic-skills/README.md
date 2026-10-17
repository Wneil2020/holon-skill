# Experiment: does an agent find the right skill in a holon tree? (anthropics/skills, October 2026)

[中文](README.zh-CN.md)

This folder keeps one experiment whole: the scripts, the labeled requests, every round's descriptions, the results and the logs. Nothing here is installed; `holon/` does not depend on it.

## The question

The tools can check that a tree is well formed and that its own example sentences land where they should (`validate`, `lint`, `replay`). They cannot check what matters to a user: given a request a person actually types, does an agent reading the tree load the skill that request needs? This experiment measures that on a real library, with a model reading the tree, and uses what it finds to change the tools.

## Setup

- **Library.** The 19 skills of [anthropics/skills](https://github.com/anthropics/skills) at commit `dbd4588f` (2026-10-09), in a holon tree of 24 skills: 16 at the top, `office-docs/` over `docx`, `pdf`, `pptx`, `xlsx`, and `web/` over `frontend-design`, `web-artifacts-builder`, `webapp-testing`, plus the tree's own `editing` and `organizer`. Each upstream description (up to 1,068 characters) was rewritten as a holon description of at most 200 characters with at most 5 cover words, and each skill got 2 positive and 1 negative example sentence. The skill bodies are not part of this folder; `scripts/prep.py` rebuilds the tree from an upstream checkout.
- **Model.** Every model call used `deepseek-v4.1-flash` through an OpenAI-compatible endpoint: writing requests, labeling them, proposing descriptions, and reading the tree. A model labeling the requests and a model of the same family reading the tree is a known weakness; see Limits.
- **Requests.** 40 writers, each given one of 30 roles (backend engineer, HR manager, PhD student ...) and one of 6 styles (terse English, polite English, non-native English, three kinds of Chinese), wrote 25 requests each, without the skill names: about 14 that one skill fits, 4 that need two, 7 that none fits. After removing duplicates: 976 requests (`data/pool.json`).
- **Labels.** Three labelers each read the authors' original descriptions, not ours, and listed the skills a request needs. 769 requests had three identical answers, 193 had two, 14 had none in common and were dropped. The 962 kept were split at random into `data/dev.json` (476, used for tuning) and `data/test.json` (486, held out until the end). A label is a set of skills; an empty set means no skill should load.
- **Ways of routing, scored against the label.**
  - `tree`: the model starts at the root `SKILL.md`, reads its routing table, says which sub-skill folders to read next, and so on down (at most 8 files). The skills it reaches are its answer.
  - `flat`: the model sees every skill's name and description in one list and picks. `flat_old` uses the authors' descriptions, `flat_new` ours.
  - `lex`: `organizer_cli.py route`, the tool's word matching, with no model at all.
- **Score.** Exact match of the set loaded and the label. The number in brackets in the tables of `logs/` is how many skills were loaded beyond the label in total.

## What was done, in order

| Step | What | Result |
|---|---|---|
| 0 | First tree, tuned by hand on 80 requests written in this project (`data/sentences.json`) | flat_old 70/80, flat_new 77/80, tree 75/80, lex 39/80; replay 69/69 |
| 1 | Baseline on the 476 dev requests | tree 335/476, lex 209/476 |
| 2 | Round 1: one owner agent per skill read its own misses on dev, ran 3 attackers (confusable requests, unusual wording, Chinese boundary cases), proposed a new description, examples and synonyms; three reviewers voted on each synonym | tree 386/476, lex 262/476, but **replay fell to 54/69** |
| 3 | Round 2: the same again | tree 380/476, lex 241/476, replay 54/69: no gain |
| 4 | Repair replay, first try: one agent given the whole tree and all 15 failures | every call ran into the endpoint's two-minute deadline (23,494-character prompts); nothing came back |
| 5 | Repair replay, second try (`scripts/fixer2.py`): one small agent per failure, given only the cards involved, 3 proposals each; every proposal tested alone on a copy of the tree, the improving ones applied one after another while they still improved | replay 54 → 68/69 in two rounds; the last failure fixed by hand → **69/69** |
| 6 | Final scores | dev tree 390/476, test tree **389/486**; test lex 225/486 |
| 7 | Change the root's reading rule from "go down when a line matches" to "go down every line that matches", two wordings, on test | 377/486 and 389/486, see below; not adopted |

### Held-out test set, first tree against final tree

| | all | one skill | two skills | Chinese | none |
|---|---|---|---|---|---|
| tree, round 0 | 343/486 (70.6%) | 111/126 | 27/67 | 167/243 | 38/50 |
| tree, final | 389/486 (80.0%) | 120/126 | 28/67 | 195/243 | 46/50 |
| lex, round 0 | 213/486 | 61/126 | 6/67 | 103/243 | 43/50 |
| lex, final | 225/486 | 74/126 | 4/67 | 103/243 | 44/50 |

The same final descriptions, read flat, in a separate run on the same test set:

| | all | one skill | two skills | Chinese | none |
|---|---|---|---|---|---|
| flat_old (authors' descriptions) | 412/486 (84.8%) | 110/126 | 47/67 | 207/243 | 48/50 |
| flat_new (final descriptions) | 398/486 (81.9%) | 114/126 | 38/67 | 198/243 | 48/50 |
| tree, final (second run) | 384/486 (79.0%) | 119/126 | 30/67 | 190/243 | 45/50 |

**On this library the flat list was more accurate than the tree.** With the same descriptions, flat chose the exact set 14 times more often than the tree, almost all of it on requests that need two skills (38 against 30) and on Chinese ones. On requests that need one skill the tree was a little better (119 against 114). `flat_old` is higher still, but it is scored against labels made from the same descriptions it reads. The tree run gave 389 the first time and 384 the second, so differences of about five are noise.

The test set was not looked at while tuning; it was run once for round 0 and once for the final tree, and once for each reading-rule wording in step 7. The error analysis in point 3 of "What it showed" was done on the test set after the final run.

### The reading rule that was tried and not kept

Requests that need two skills are the weakest group (28 of 67). The root's rule 1 says "Go down only when a line matches ... When one matches, read the `SKILL.md` in that subfolder", which reads as one. Two rewrites were run on the test set:

| Rule 1 wording | all | one skill | two skills |
|---|---|---|---|
| as released ("when one matches") | 389 | 120 | 28 |
| "go down every line that matches ... one task often matches more than one line" | 377 | 105 | 36 |
| "go down every line that matches ... a line matches only when the task needs what that skill does; when two lines truly match, read both" | 389 | 115 | 33 |

The first gains eight two-skill requests and loses fifteen one-skill requests, because the model starts loading a second skill where none is needed. The second gains five and loses five. Neither is better overall, so the rule was left as it is. If loading too little is worse for you than loading too much, the third wording is the one to try.

## What it changed in the tools

- `lint` hints at a line of `synonyms.md` that reaches no skill (commit `13ae9f9`). In round 1 the generated synonym groups included `training, 培训, ...` and `email, 邮件`, whose first words no skill listed; folding to them changed no route, and nothing said so.
- From the first import of this library (commit `4cc412e`): `move` lists the pointers in other bodies that still name the old path; `lint` tells apart a file that exists under an ancestor skill (text moved down without its paths), a missing resource file, and a path that is probably an output the step writes; absorbing a card moves what its long old description said beyond routing words into the first step instead of dropping it.
- The documents now say what the experiment showed: see `holon/README.md` (Status and limits), `holon/organizer/README.md` (What a passing result does not promise) and `holon/organizer/references/design-notes.md` §21.

## What it showed

0. **At 24 skills the tree buys no accuracy.** A model reading one flat list of 24 short descriptions sees every option at once and can take two; a model reading the tree commits to one branch per level. The tree's case is the size of what is read when a library is too large to list, which this library is not. This experiment does not test that case.
1. **Rewriting descriptions for a model and keeping replay passing pull in different directions.** Round 1 raised dev from 335 to 386 and broke 15 of 69 example sentences. Nearly all the breaks were in the example sentences, not the descriptions: a parent's positive example that used only one child's words, a negative example that still contained the skill's own cover word, a sentence about a child that used none of the child's words. Fixing the sentences, not the descriptions, brought replay back without losing the dev gain.
2. **Word matching is a coarse screen.** `lex` exactly matched 46% of test requests (225/486) against the tree's 80%; on Chinese requests, 42%. Adding synonyms helps a little and then starts sending unrelated requests to the wrong skill, which is why round 2 added nothing. The word model is for checking that the tree's own decisions still hold, not for predicting what an agent does.
3. **Most of what is still wrong is a skill that applies alongside another.** 29 test requests miss `discernment-nudge`; in 25 of them the tree loaded every other skill the label wanted and only that one was missing. It is a skill about how to answer (draft, advise, recommend) that can apply to almost any task, and a reader who picks one branch per level does not go back for it. The 15 misses of `claude-api` are mostly MCP requests where the labelers wanted `claude-api` as well as `mcp-builder`. Both are partly a matter of where the line is, and the labelers drew it generously.
4. **Many small agents worked where one large one did not.** The whole-tree repair prompt never returned. One agent per failure with only the relevant cards, each proposal checked by the real tools before it was kept, fixed 14 of 15 in two rounds.

## Limits

- The labels come from a model of the same family as the one reading the tree. Three-way agreement removes some noise but not shared habits. A label is a judgment of what the authors' descriptions imply, not ground truth.
- `flat_old` is scored against labels that were made by reading those same descriptions, so it has an advantage.
- One model, one library of 24 skills, one run of each configuration. Differences of five or so requests out of 486 are within what a second run could change.
- Exact match counts a request as wrong when one extra skill is loaded, which may be harmless, and when one needed skill is missing, which may not be. The logs keep both counts.

## Running it again

```bash
git clone https://github.com/anthropics/skills /tmp/anthropics-skills
git -C /tmp/anthropics-skills checkout dbd4588f
EXP=$PWD/experiments/2026-10-anthropic-skills
python3 $EXP/scripts/prep.py /tmp/anthropics-skills/skills /tmp/work final   # or round0, round2
cd /tmp/work && $EXP/cycle.sh                                                # validate, lint, replay: 69/69

export LLM_BASE_URL=https://your-endpoint/v1   # any OpenAI-compatible endpoint
export LLM_API_KEY=...                          # leave unset if a proxy adds the key
SENTS=test.json python3 $EXP/scripts/evalrun.py test.json.out   # FLAT=1 adds the flat conditions
python3 $EXP/scripts/score.py test.json.out
```

Model calls need `LLM_BASE_URL`; `LLM_MODEL` defaults to `deepseek-v4.1-flash`. The rest of the pipeline, in the order it was run: `gen.py N` (writes `pool.json`), `label.py pool.json labeled.json`, a random split into `dev.json` and `test.json`, `round.sh N PREVIOUS_RESULTS` for each owner round (`owners.py`, `merge.py`, `cycle.sh`, `evalrun.py`, `score.py`), and `fixer2.py ROUNDS PROPOSALS_PER_FAILURE` to repair replay. `fixer.py` is the whole-tree repair that timed out; it is kept because `fixer2.py` reuses its helpers.

## Files

| Path | What |
|---|---|
| `scripts/` | the pipeline; `paths.py` and `llm.py` hold every location and the endpoint |
| `cycle.sh`, `round.sh` | write the cards into the tree and check it; one owner round |
| `data/pool.json` | the 976 requests as written |
| `data/labeled.json` | the same with the three labelers' votes |
| `data/dev.json`, `data/test.json` | the 962 kept, split 476 / 486 |
| `data/sentences.json` | the 80 requests of step 0 |
| `data/upstream_descs.json` | the authors' descriptions the labelers read |
| `cards/round0.py`, `round2.py`, `final.py` | every skill's description and example sentences after step 0, step 3 and step 6 |
| `cards/synonyms_*.md` | the tree's `synonyms.md` at the same points |
| `results/` | one JSON per run: for each request the label, what each condition loaded, and the tree's path |
| `logs/` | the console output of each step, including the owners' reasons and the reviewers' votes on synonyms |
