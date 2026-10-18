# A coding agent building a real feature with a split skill (2026-10-18)

[中文](README.zh-CN.md)

## Question

The earlier experiments measure lookup: can an agent find a fact in a skill, and how much does it read. This one measures the work itself. A coding agent gets a long team handbook and a real task. Does the skill make the feature correct and does it run in a browser? Does splitting the handbook (mechanically, or with holon's rules) keep that, and what does it cost? And where the agent still fails, is the cause the layout or the text?

## Setup

- **Platform and skill.** `tessel-frontend` is a fictional front-end platform invented for this run, so no model knows it. Its handbook (`skill/v1/full/tessel-frontend/SKILL.md`, 833 lines, 42,836 characters) was generated to read like a real team wiki: quick start, monorepo, parts, tokens, localization, accessibility, state, testing, CI and release, migration, FAQ. Ten conventions are buried in it (F1 to F10): where a part lives, the `tessel.part` wrapper, design tokens only, the CSS layer, every visible string through `t()`, string files under `locales/<lang>/<name>.strings`, a dismiss control with `data-ts-dismiss` and a translated label, dismissal kept in `tessel.store` with session scope, a spec using `@tessel/testkit`, and a change note under `changes/next/`.
- **Task.** "Add a dismissible announcement banner part. Provide English and Simplified Chinese text. Follow the team's conventions, include a test, and record the change for the release notes." The repository is a small scaffold (`scaffold/`); the agent has `read`, `list`, `write` and `shell` tools and at most 25 turns.
- **Four ways to give the skill.** `none`; `full` (the whole file in the system prompt); `heading` (every `##` section over 25 lines moved to `references/`, 12 of them, entry file in the prompt); `holon` (split from holon's rules with `holon.py split`: a short core, one `build-parts` sub-skill and ten `references/` files, entry file in the prompt). The agent opens further files itself.
- **Grading.** Static: the ten conventions (`grade.py`). Real: the agent's own spec run under vitest with a stand-in `@tessel/testkit`; a hidden jsdom behaviour test (renders in both languages, Chinese text present, the close button has a label and hides the banner, a re-mount stays hidden, a new session shows it again); an esbuild bundle opened in Chromium with screenshots, checking the same things across a click, a reload and a fresh browser context (`verify.py`).
- **Models.** `deepseek-v4.1-flash` and `glm-5.3-flash`, temperature 0.3, through an OpenAI-compatible hub, streamed with a stall watchdog; every call, retry and token count is logged. Runs cut short by revoked keys or rate limits are excluded and counted.
- **Skill versions.** v1 is the original. Each later version changes one thing (`skill/patches/`): v2 adds one testing rule (drive interactions with the `user` that `renderPart` returns and `await user.click(...)`); v3 also fixes two stale sentences that said strings live in `strings.en.json` inside the part folder; v4 adds to holon's `build-parts` sub-skill a "read next" list of four references with "skip the rest"; v5 lists six.

## Results

`own` = the agent's own spec passes; `hidden` = hidden behaviour test passes in both languages; `browser` = click, reload and new-context checks all pass in Chromium. Prompt tokens are the mean over valid runs.

### deepseek-v4.1-flash

| skill | way | n | score /10 | perfect | own | hidden | browser | prompt tokens |
|---|---|---|---|---|---|---|---|---|
| v1 | none | 10 | 0.10 | 0 | 0/10 | 1/10 | 1/10 | 95,813 |
| v1 | full | 9 | 9.78 | 7 | 1/9 | 8/9 | 8/9 | 233,227 |
| v1 | heading | 8 | 9.88 | 7 | 1/8 | 8/8 | 8/8 | 168,582 |
| v1 | holon | 8 | 10.00 | 8 | 5/8 | 8/8 | 8/8 | 157,537 |
| v3 | full | 5 | 9.40 | 3 | 5/5 | 5/5 | 5/5 | 141,917 |
| v3 | heading | 5 | 10.00 | 5 | 5/5 | 5/5 | 5/5 | 153,303 |
| v3 | holon | 5 | 10.00 | 5 | 5/5 | 5/5 | 5/5 | 143,580 |

### glm-5.3-flash

| skill | way | n | score /10 | perfect | own | hidden | browser | prompt tokens |
|---|---|---|---|---|---|---|---|---|
| v1 | none | 5 | 0.20 | 0 | 2/5 | 0/5 | 2/5 | 43,592 |
| v1 | full | 4 | 8.00 | 1 | 1/4 | 1/4 | 1/4 | 127,833 |
| v1 | heading | 5 | 8.40 | 0 | 1/5 | 1/5 | 1/5 | 101,843 |
| v1 | holon | 4 | 7.50 | 0 | 1/4 | 1/4 | 1/4 | 85,271 |
| v2 | full | 4 | 8.75 | 2 | 3/4 | 2/4 | 3/4 | 136,396 |
| v2 | heading | 4 | 5.75 | 0 | 1/4 | 1/4 | 2/4 | 81,332 |
| v2 | holon | 5 | 5.60 | 1 | 1/5 | 1/5 | 1/5 | 109,650 |
| v3 | full | 5 | 10.00 | 5 | 4/5 | 1/5 | 4/5 | 142,080 |
| v3 | heading | 5 | 9.60 | 3 | 2/5 | 2/5 | 3/5 | 104,064 |
| v3 | holon | 5 | 7.00 | 1 | 1/5 | 2/5 | 3/5 | 177,793 |

The holon routing runs used a second hub channel for the same model (`cline-pass/glm-5.3-flash`) after the first key could not be re-bound. Token counts differ between channels, so they have their own control:

| skill | way | n | score /10 | perfect | own | hidden | browser | prompt tokens | turns |
|---|---|---|---|---|---|---|---|---|---|
| v3 (control) | holon | 6 | 8.50 | 3 | 3/6 | 4/6 | 4/6 | 47,804 | 9.5 |
| v4: 4 refs listed | holon | 8 | 7.00 | 0 | 4/8 | 6/8 | 7/8 | 31,167 | 6.6 |
| v5: 6 refs listed | holon | 8 | 10.00 | 8 | 3/8 | 8/8 | 8/8 | 37,800 | 6.8 |

Per-convention passes, logs of every run and the scripts that produced the tables are in `results/` (`summary.json`, `*_report.txt`, `runs/<set>/<way>-<n>/result.json`). Transcripts, built pages and screenshots are in the full archive, not in the repository.

## What it showed

1. **The skill carries the task.** Without it both models build something that often works in the browser but follows almost none of the ten conventions (0.1 and 0.2 of 10). With any of the three layouts they reach 9.4 to 10.
2. **On a strong navigator, holon is the best and cheapest layout.** deepseek with holon: 10/10 on 8 of 8 runs and the most passing own specs, at 32% fewer prompt tokens on average than the whole file (mean 157,537 against 233,227; median 129,343 against 164,722). The whole file had the worst cost tail: some runs passed 400,000 prompt tokens because the 43 KB prompt is re-sent every turn.
3. **Most failures came from the text, not the layout.** Two stale sentences put the string files in the wrong place. deepseek ignored them; glm followed them in 11 of 13 skill runs, and its pages rendered no text. Separately, no step said how to drive a click in a test, so most agents' own specs clicked a raw element and failed on React's `act` warning. Fixing both (v3) made deepseek's own specs pass 5/5 in all three layouts, and lifted glm's whole-file score from 8.0 to 10.0.
4. **A weaker navigator does what the step lists, and only that.** With v3, glm on holon wandered through as many as all ten reference files and averaged 21 turns. v4 listed four references and said to skip the rest: every run read exactly those, cost dropped by a third, and every run lost the same three conventions, which live in the two files the list left out (8 of 8 runs at exactly 7/10). v5 listed all six: 8 of 8 runs at 10/10, every browser check passing, at the lowest cost of any condition with this model on that channel.
5. **Still open.** Own-spec pass rates for glm stay low even when the rule is read (3/8 in v5); the specs fail on the stand-in testkit, not on the feature. A few pages with a perfect convention score showed no Chinese message because the banner text came from a prop with no default; the task did not say who supplies the message.

## What changed in holon

organizer step 1 now says: a step names every `references/` file it needs, each with what is inside, and asks for no other; and passages that contradict each other are reconciled before a split, because after it they sit in different files.

## Limits

One synthetic skill and one task. Five to ten runs per cell, so differences of one or two runs are noise. Two models, both "flash" tiers. The stand-in `@tessel/testkit` and runtime are ours. The v4/v5 runs are on a different hub channel from the other glm runs.

## Reproducing

The scripts were run from one flat working directory: copy `scripts/*`, `scaffold/` and `runtime/` into it, put `skill/v1/full/tessel-frontend` under `data/skills_1000/` and the two splits (`skill/v1/{heading,holon}/tessel-frontend`) under `splitwork/trees/{heading,holon}/`, and build `data<V>`/`splitwork<V>` for later versions with the patches in `skill/patches/`. `npm install` in `runtime/`. Set `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, and optionally `CHROMIUM` and `PLAYWRIGHT_PY`. Then `SKILLSET=<V> python3 run.py <tag> none,full,heading,holon <reps>` and `python3 report.py runs/<tag>.json`. `ensure_env.sh` is specific to our sandbox.
