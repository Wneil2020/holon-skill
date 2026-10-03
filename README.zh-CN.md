# holon skill

一套帮 AI agent 管理大量 skill 的规则和工具：每个 skill 放在哪个文件夹，agent 怎么找到对的那个，以及怎么检查它确实找得到。

> **项目处于早期阶段。** 1.0.0 是第一个公开版本。它在 Linux、macOS、Windows 上都有测试，但目前只在两个小型 skill 库上用过，规则和命令参数以后仍可能调整。每次改动都记在 [holon/CHANGELOG.md](holon/CHANGELOG.md)。

[English](README.md)

## 快速开始

只需要 Python 3.8 或更高版本，不需要 git。一条命令安装：

```bash
python3 -c "import urllib.request as u; exec(u.urlopen('https://raw.githubusercontent.com/Wneil2020/holon-skill/main/install.py').read())"
```

在 Windows 上把 `python3` 换成 `py`，在 cmd 或 PowerShell 里输入同样这一行。这条命令会从本仓库下载 `install.py` 并运行它；想先知道它做什么，可以读一下 [install.py](install.py)。选项写在最后，比如 `... .read())" --host claude-code`，或者用 `--force` 覆盖以前装过的。

这一行装的总是最新的 `main`。要装固定的版本，把版本的 tag 写两次，一次在地址里，一次作为 `--ref`：

```bash
python3 -c "import urllib.request as u; exec(u.urlopen('https://raw.githubusercontent.com/Wneil2020/holon-skill/v1.0.0/install.py').read())" --ref v1.0.0
```

所有 tag 列在 [Releases](https://github.com/Wneil2020/holon-skill/releases) 页面上。

如果已经下载了仓库，等价的做法是：

```bash
git clone https://github.com/Wneil2020/holon-skill.git
cd holon-skill
python3 holon/scripts/holon.py install
```

要固定版本，在 `git clone` 后面加 `--branch v1.0.0`，或者下载那个 release 附带的 zip。

两种方式都会把 skill 树拷到这台机器上各个 agent 工具读 skill 的位置（Claude Code、Codex、Cursor、GitHub Copilot、Gemini CLI 等），检查拷过去的内容，并打印做了什么。[holon/README.zh-CN.md](holon/README.zh-CN.md) 带你五分钟建出第一棵树。

## 构建你自己的体系

树、规则和检查工具是同一个包：`holon/`。规则写在 `holon/organizer/SKILL.md` 里，其中六个数字（一个 skill 最多几个覆盖词、描述最长多少字符等）是可以调的设置，不是定律。每个数字管什么、怎么改，见 [holon/organizer/README.zh-CN.md](holon/organizer/README.zh-CN.md#为你自己的库调整参数)。`SKILL.md` 里的表和 `holon/organizer/scripts/organizer_cli.py` 里的常量要一起改，两处不一致时有测试会失败；改完跑一遍下面的检查。
## 仓库里有什么

| 文件夹 | 是什么 |
|---|---|
| [`holon/`](holon/README.zh-CN.md) | 主体包：skill 树、把 skill 放进树的规则（`organizer/`），以及检查这两者的工具 |
| [`eval/`](eval/README.zh-CN.md) | 测量树对 agent 有没有帮助的工具，拿同一批 skill 的平铺文件夹做对照；不随包安装 |
| `install.py` | 用户运行的一条命令安装程序（见“快速开始”） |
| `scripts/` | `check.py`（任何系统）和 `check.sh`（bash）在本地跑一遍 CI 的检查 |

## 检查一次改动

```bash
python3 scripts/check.py      # Windows：py scripts\check.py
bash scripts/check.sh         # 同样的检查，有 bash 时可用
```

它会跑所有测试，检查包自带的 skill 树，用 `init` 新建一棵树并检查，往一个空的主目录里安装一次；如果装了 `skills-ref`，还会用 [Agent Skills 规范](https://agentskills.io/specification) 的验证器检查每个 `SKILL.md`。CI（`.github/workflows/test.yml`）跑的是同样的检查，另外在 Linux 和 Windows 上用 Python 3.8 到 3.13 跑 `holon` 的测试。macOS 单独一个 workflow（`.github/workflows/macos.yml`，Python 3.10 和 3.13），因为 GitHub 的 macOS 机器有时会一段时间排不上；它每周也会自动跑一次，也可以在 Actions 页面手动启动。

## 参与

欢迎提 issue 和 pull request。这个项目由一个人业余维护，回复可能会慢。改动需要保住什么，见 [CONTRIBUTING.md](CONTRIBUTING.md)；安全问题怎么报告，见 [SECURITY.md](SECURITY.md)。

## 许可

MIT，见 [LICENSE](LICENSE)。
