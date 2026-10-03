# Handoff: the first real-agent run

For an agent (or a person) continuing this work on a machine where Claude Code can reach a model. Read `README.md` in this folder first; this page says what is done, what is not, and what to do next, in order.

## State

| Done | Where |
|---|---|
| `holon.py move` places existing skill folders into a tree from a plan | `holon/scripts/holon.py`, tests in `eval/tests/test_harness.py` |
| The harness: `flatten`, `freeze`, `run`, `report`; runners `word-model`, `claude-code`, `command` | `eval/harness.py` |
| A worked example (5 skills, 12 test sentences) and its word-model result | `eval/example/`, `README.md` |
| All checks pass | `python3 scripts/check.py` |

| Not done | Why |
|---|---|
| Any run with a real model | the machine that built this had no model access; `claude -p` returned a proxy message, which the harness correctly recorded as "no model call" and did not count |
| A library larger than the example | needs the owner's own skills |
| Sentences not written by the skills' author | needs other people's words (`_feedback.md`, issues, chat logs) |
| Automatic placement (deciding where a skill goes) | out of scope for the harness; `move --plan` only carries out a decision |

## Step 1: check the machine (no cost)

```bash
python3 --version                    # 3.8 or newer
claude --version                     # Claude Code installed
python3 scripts/check.py             # from the repository root: every test passes
python3 eval/example/build.py        # builds eval/example/tree and eval/example/trimmed
```

## Step 2: one real call, to see that the wiring works (about one session)

```bash
cd eval
printf 'id\tsplit\tsentence\texpected\nx1\ttest\tbuild a pitch deck for Friday\tpptx\n' > /tmp/one.tsv
python3 harness.py freeze /tmp/one.tsv
python3 harness.py run /tmp/one.tsv --tree example/tree/library --runner claude-code \
    --runs 1 --out /tmp/one.csv --raw-dir /tmp/raw
python3 harness.py report /tmp/one.csv
```

Check, in this order:

1. **The report says `runs: 1 completed`.** If it says `NOT COUNTED ... no model call`, the model was not reached. With the default empty `HOME`, Claude Code cannot see a subscription login: either export `ANTHROPIC_API_KEY`, or add `--keep-home` (then the user's own `~/.claude/skills` and `CLAUDE.md` are visible to the run, which contaminates it; note that in the result).
2. **`skills_seen` in `/tmp/one.csv` contains `library`.** That is the tree's root, the only top-level skill of arrangement C. If it lists other skills, they come from somewhere else (the user's home, a plugin) and must be removed before any number is trusted. Claude Code's own built-in skills may be listed too; they are the same in all three arrangements.
3. **`files_read` starts with `library/SKILL.md`.** Open the raw file in `/tmp/raw/` and look at the tool calls. If the agent chose a skill without opening anything, the choice came from the listing alone; that is allowed, but write it down.
4. **`chosen` is a folder name.** If it is wrong while the raw transcript shows the agent picked the right skill, the `SKILL:` line was missing or malformed; fix the parsing in `parse_claude_stream`, add a test with that transcript, and rerun.

If anything in 1 to 4 is off, fix the harness first. Do not spend sessions on step 3 with a harness you have not seen work.

## Step 3: the example, all three arrangements (12 sentences x 3 arrangements x 3 runs = 108 sessions)

```bash
python3 harness.py run example/sentences.tsv --tree example/tree/library --flat example/flat \
    --trimmed example/trimmed --names example/plan.txt --runner claude-code --runs 3 \
    --out example/real.csv --raw-dir example/raw
python3 harness.py report example/real.csv
```

`--model` pins a model; without it, write down which model the host used. The file is appended to, so an interrupted run can be continued by running the same command (it will add rows; remove the partial sentence's rows first, or accept extra runs for it).

What to write down, next to the report:

- host and model versions, date, whether `--keep-home` was used;
- the line `C, agent vs word model: same choice in N/M runs`. This is the number the project lacks: how far `replay` predicts this agent;
- for every sentence where the agent and the word model disagree, which one was right, and one line from the raw transcript showing why the agent went where it went;
- median input tokens per arrangement. Bytes are only a proxy.

## Step 4: a library that is not the example

The example cannot show whether the tree helps: its sentences were written by the author of its skills, and five skills fit in any flat listing. The result that counts needs:

1. The owner's own flat skills folder (arrangement A), copied, never moved: use `move --plan ... --copy`.
2. A plan, written by applying `holon/organizer/SKILL.md` to those skills, with the parents it calls for created by `init --parent`. Commit the plan file; it is part of the result.
3. `validate`, `lint` and `replay` passing on the tree.
4. At least 50 test sentences from people who did not place the skills, with `expected` filled in **before** any run, frozen with `freeze`. Sentences used afterwards to fix cover words or `synonyms.md` move to `tune`, and `freeze` is run again; the report keeps the earlier result.
5. `flatten` for arrangement B, then the same `run` as in step 3.

## Rules for reporting

- Report every run, including the ones that make the tree look bad. A result where C does not beat B is the most useful thing this project can learn.
- Do not tune cover words, `synonyms.md` or the plan on the test sentences and then report on the same sentences.
- Keep `results.csv`, the sentence file, its `.lock`, the plan and the raw transcripts together; anyone should be able to rerun `report` and get the same table.
- If a result goes into the repository, it goes into `eval/results/<date>-<host>-<model>/` with those files and a short `README.md`, and the root README's limits section is updated to say what it showed.

## If you change code

- `harness.py` and `holon.py` stay standard library only, Python 3.8+.
- Every change comes with a test in `eval/tests/test_harness.py` (or `holon/tests/` for `holon.py`). The `claude-code` runner is tested against a fake `claude` that prints recorded stream-json; add a real transcript from `--raw-dir` as a new fixture when parsing needs to change.
- `python3 scripts/check.py` must pass. If a change alters a command's output quoted in `holon/README.md`, update both READMEs in the same commit (`holon/tests/test_readme_outputs.py` compares them).
- Read `AGENTS.md` and `CONTRIBUTING.md` at the repository root.
