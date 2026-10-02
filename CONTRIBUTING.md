# Contributing

Thank you for considering a contribution. This project is small on purpose: one Python file per tool, no dependencies, and a rules file that fits in one reading. Changes that keep it that size are accepted more readily than changes that grow it.

One person maintains this project in spare time. Every issue and pull request is read, but a reply may take days or weeks. A pull request that changes one thing and includes a test is the kind that gets merged fastest.

## Before you start

- For a bug fix or a small change, open a pull request directly.
- For a new command, a change to the rules in `holon/organizer/SKILL.md`, or anything that changes the file format, open an issue first. The project is at an early stage and the format is still settling, so it is better to agree on the change before writing it.

## Setting up

There is nothing to install. Clone the repository and run the checks:

```bash
python3 scripts/check.py      # Windows: py scripts\check.py
bash scripts/check.sh         # the same checks, where bash is available
```

Python 3.8 or newer is needed. To also run the Agent Skills validator that CI runs:

```bash
pip install "git+https://github.com/agentskills/agentskills.git#subdirectory=skills-ref"
```

## Rules for a change

1. **No dependencies.** Each tool stays a single file that uses only the Python 3.8 standard library. The README's promise that a folder works when copied into any skills directory depends on this.

2. **Tests come first.** To fix a bug, first write a test that fails because of the bug, then fix it. To add a feature, add a test for it. `python3 scripts/check.py` (or `bash scripts/check.sh`) must pass.

3. **`holon/organizer/SKILL.md` is the only source of the rules.** If you change it:
   - The five rules work together. Say in the pull request how a change to one affects the other four, and update the matching section of `holon/organizer/references/design-notes.md`.
   - If the rule you change is one the tool checks, change the tool and its test in the same pull request. If a rule and its check disagree, `lint` passes trees that break the rule, and nobody is told.
   - The parameter table and the constants in the tool must stay identical. A test enforces this.

4. **Existing trees must keep working.** If you change the routing rules in `holon/SKILL.md`, or the block that `holon.py` writes between the `<!-- sub-skills -->` markers, say in the pull request whether trees built with the previous version still route the same way.

5. **Documents and tools agree.** Every command output quoted in `holon/README.md` and `holon/README.zh-CN.md` is compared with the real output by `holon/tests/test_readme_outputs.py`. A change to a tool's output therefore needs a change to both READMEs in the same pull request. The two READMEs keep the same sections and the same commands.

6. **Messages say what happened and what to do.** A message from `lint` or `replay` names the skill, states the condition found, and names the fix, in that order. Follow the form of the existing messages.

7. **Plain prose.** Say what the thing does, with real examples, in plain sentences; no marketing adjectives.

## Submitting a change

1. Fork the repository and create a branch.
2. Make the change and run `python3 scripts/check.py`.
3. Add a line to the `[Unreleased]` section of the package's `CHANGELOG.md`.
4. Open a pull request against `main`. Keep it to one change. The description states the reason for the change; the diff shows the change itself.

By submitting a pull request, you agree that your contribution is released under the project's MIT License.

## Reporting a problem

Open an issue and include:

- the command you ran and its complete output;
- the smallest tree that reproduces the problem, as `SKILL.md` files pasted into the issue;
- your Python version and operating system.

## Code of conduct

Everyone taking part is expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
