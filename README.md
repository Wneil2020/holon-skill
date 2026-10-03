# holon skill

Rules and tools for keeping a large collection of AI agent skills in order: which folder each skill goes in, how the agent finds the right one, and how to check that it does.

> **Early stage.** Version 1.0.0 is the first public release. It is tested on Linux, macOS and Windows, but it has only been used on two small skill libraries, and the rules and command options may still change. Changes are recorded in [holon/CHANGELOG.md](holon/CHANGELOG.md).

[中文说明](README.zh-CN.md)

## Quick start

Python 3.8 or newer is the only requirement; git is not needed. Install with one command:

```bash
python3 -c "import urllib.request as u; exec(u.urlopen('https://raw.githubusercontent.com/Wneil2020/holon-skill/main/install.py').read())"
```

On Windows, type the same line with `py` in place of `python3` (cmd or PowerShell). The command downloads `install.py` from this repository and runs it; read [install.py](install.py) first if you want to know what it does. Options go at the end, for example `... .read())" --host claude-code` or `--force` to replace an earlier install.

That line always installs the latest `main`. To install a fixed release, name its tag twice, once in the address and once as `--ref`:

```bash
python3 -c "import urllib.request as u; exec(u.urlopen('https://raw.githubusercontent.com/Wneil2020/holon-skill/v1.0.0/install.py').read())" --ref v1.0.0
```

The tags are listed on the [Releases](https://github.com/Wneil2020/holon-skill/releases) page.

From a downloaded copy of the repository the same thing is:

```bash
git clone https://github.com/Wneil2020/holon-skill.git
cd holon-skill
python3 holon/scripts/holon.py install
```

For a fixed release, add `--branch v1.0.0` to `git clone`, or download the zip attached to that release.

Either way, this copies the skill tree to where the agent tools on this machine read skills (Claude Code, Codex, Cursor, GitHub Copilot, Gemini CLI and others), checks the copy, and prints what it did. [holon/README.md](holon/README.md) walks through building a first tree in five minutes.

## Building your own system

The tree, the rules and the checks are one package, `holon/`. The rules live in `holon/organizer/SKILL.md`, and six numbers in them (how many cover words a skill may have, how long a description may be, and so on) are settings, not laws. [holon/organizer/README.md](holon/organizer/README.md#changing-the-parameters-for-your-own-library) explains what each one does and how to change it. Change the table in `SKILL.md` and the constants in `holon/organizer/scripts/organizer_cli.py` together; a test fails when they disagree. Then run the checks below.
## What is in this repository

| Folder | What it is |
|---|---|
| [`holon/`](holon/README.md) | The package: the skill tree, the rules for placing skills in it (`organizer/`), and the tools that check both |
| [`eval/`](eval/README.md) | the harness that measures whether a tree helps an agent, against a flat folder of the same skills; not installed |
| `install.py` | the one-command installer that users run (see Quick start) |
| `scripts/` | `check.py` (any system) and `check.sh` (bash) run locally what CI runs |

## Checking a change

```bash
python3 scripts/check.py      # Windows: py scripts\check.py
bash scripts/check.sh         # the same checks, where bash is available
```

It runs every test suite, checks the package's own skill tree, builds a fresh tree with `init` and checks it, installs into an empty home folder, and, if `skills-ref` is installed, validates every `SKILL.md` against the [Agent Skills specification](https://agentskills.io/specification). CI (`.github/workflows/test.yml`) runs the same checks, plus the `holon` tests on Linux and Windows with Python 3.8 to 3.13. macOS has its own workflow (`.github/workflows/macos.yml`, Python 3.10 and 3.13), because GitHub's macOS runners are sometimes unavailable for a while; it also runs once a week, and can be started by hand from the Actions tab.

## Contributing

Issues and pull requests are welcome. One person maintains this in spare time, so replies may take a while. [CONTRIBUTING.md](CONTRIBUTING.md) says what a change has to keep true, and [SECURITY.md](SECURITY.md) how to report a security problem.

## License

MIT. See [LICENSE](LICENSE).
