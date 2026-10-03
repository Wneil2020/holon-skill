# holon skill

这个文件夹 `holon/` 就是主体包。安装后它是一个名叫 `holon` 的 skill 文件夹，两个工具是 `holon.py` 和 `organizer_cli.py`。

> **项目处于早期阶段。** holon skill 能用，也有完整的测试，但目前只在两个小型 skill 库上用过（合计约三十个 skill）。规则、描述格式和命令参数在后续版本里仍可能调整。每一处改动都会写进 [CHANGELOG.md](CHANGELOG.md)；能自动迁移的旧文件，用 `holon.py migrate` 改写。

agent 把所有 skill 放在同一个文件夹里时，每接一个任务都要把全部描述读一遍；skill 越多，选错的次数越多。holon 改成把 skill 排成一棵树：一个 skill 的文件夹里可以再放 skill（叫子 skill）。agent 先读最上一层，进入和任务对得上的那一枝，只读这条路上的文件。

holon 就是一些普通文件夹，加两个 Python 脚本。脚本只用标准库，需要 Python 3.8 或更高版本。它们负责让树保持一致，并检查每个 skill 能不能被它该接的句子找到。

[English](README.md)

## 安装

在这个仓库的目录里运行：

```bash
python3 holon/scripts/holon.py install
```

它会把树拷到 `~/.agents/skills/holon/`。这是 [Agent Skills](https://agentskills.io) 标准的公共位置，Codex、Cursor、GitHub Copilot、Gemini CLI、OpenCode 等工具都读这个文件夹。接着 `install` 查找这台机器上从别处读 skill 的工具，比如 Claude Code（`~/.claude/skills/`）、Windsurf（`~/.codeium/windsurf/skills/`），在那里也放一份。它会检查拷过去的内容，并打印出哪个工具读哪个文件夹。每个工具下次启动时就能读到。

有的工具不止读一个文件夹。比如 Cursor 和 OpenCode 既读 `~/.claude/skills/` 也读 `~/.agents/skills/`，两处都放的话，它们会看到两棵一样的树。`install` 选文件夹时保证不会让任何一个工具看到两份。

`python3 holon/scripts/holon.py hosts` 列出 `install` 认识的 32 个工具、这台机器上装了哪些、每个工具读哪些文件夹。想自己指定装到哪里：

| 选项 | 作用 |
|---|---|
| `--host 名字` | 只装给这个工具；可以写多个（`--host windsurf --host codex`）。`--host agents` 表示只写公共文件夹 |
| `--project` | 用当前目录下的项目级文件夹（`.agents/skills/`、`.claude/skills/` 等），而不是用户主目录下的 |
| `--to DIR`、`--as NAME` | 任意文件夹、任意名字 |
| `--force` | 覆盖之前装过的同名文件夹 |
| `--link` | 其余位置用链接指向第一份，而不是拷贝；有的工具不跟随链接，所以默认是拷贝 |

列表里没有的工具，只要遵循这个标准，就会读 `~/.agents/skills/`，照样能用。读别的文件夹的工具，用 `--to` 指定那个文件夹。

`install` 也可以从别处安装：本地路径、git 地址、GitHub 上的 `owner/repo`，或者 `.zip`/`.tar.gz` 的下载地址。在一台没有下载过仓库的机器上，用[仓库首页 README](../README.zh-CN.md#快速开始) 里的一行安装命令即可，它不需要 git 和 curl，在 Windows 上也一样。有 git 和 curl 的机器上，下面这行也可以：

```bash
curl -sSL https://raw.githubusercontent.com/Wneil2020/holon-skill/main/holon/scripts/holon.py | python3 - install Wneil2020/holon-skill
```

agent 工具只读 skills 文件夹下第一层文件夹的描述。它看得见 `holon/`，看不见 `holon/office-docs/pdf/`。所以整个库都应该放在 `holon/` 里面：工具只需要选中这一个文件夹，往下的路由交给树。Cursor 是例外，它会递归扫描，把每个子 skill 也单独列出来；`install` 给 Cursor 安装时会提示这一点，在 Cursor 里从根往下路由同样有效。

## 五分钟建一棵树

下面的命令都在 `holon/` 文件夹里运行。显示的输出都是真实输出：有一个测试会把这一页上的每条命令都跑一遍并逐字比对。

先在顶层建一个办公文档的 skill，再在它下面建两个子 skill。`init` 会建出文件夹，并更新父级的子 skill 列表：

```
$ python3 scripts/holon.py init office-docs --parent . --desc "Use when producing or reading office documents: covers Word, PDF, spreadsheet, docx"
created: ./office-docs/SKILL.md
synced ./SKILL.md (3 sub-skills)
done: 1 file(s) updated
```

```
$ python3 scripts/holon.py init docx --parent office-docs --desc "Use when writing or editing Word documents: covers Word, docx, report; excludes spreadsheet"
created: office-docs/docx/SKILL.md
synced office-docs/SKILL.md (1 sub-skills)
done: 1 file(s) updated
also synced ./SKILL.md (it lists the words of the skills below it)
```

```
$ python3 scripts/holon.py init pdf --parent office-docs --desc "Use when the input or output is a PDF: covers PDF, form, fill in, merge pages"
created: office-docs/pdf/SKILL.md
synced office-docs/SKILL.md (2 sub-skills)
done: 1 file(s) updated
also synced ./SKILL.md (it lists the words of the skills below it)
```

描述分三段。`Use when ...` 说明什么场合用。`covers` 列最多五个词，任务句里出现其中任何一个，就路由到这里。`excludes` 列出属于别的 skill 的相近词。比对是逐字的、不分大小写；比对之前，句子先经过 `synonyms.md`，把用户平时说的词换成 skill 里用的词。

现在这棵树是这样的：

```
$ python3 scripts/holon.py tree office-docs
office-docs — Use when producing or reading office documents: covers Word, PDF, spreadsheet, docx
├── docx — Use when writing or editing Word documents: covers Word, docx, report; excludes spreadsheet
└── pdf — Use when the input or output is a PDF: covers PDF, form, fill in, merge pages
```

`route` 显示一句任务是怎么一层层往下走的：

```
$ python3 organizer/scripts/organizer_cli.py route . "fill in this PDF form"
sentence: "fill in this PDF form"
root -> taken by: office-docs (via 'PDF')
office-docs -> taken by: office-docs/pdf (via 'PDF','form','fill in')
office-docs/pdf -> no sub-skills
lands on: office-docs/pdf
read: 3 file(s), 3,828 bytes of 26,821 in the library (14%)
```

agent 只读了三个文件。最后一行就是这次的开销：路径上的字节数，和整棵树所有 `SKILL.md` 的字节数相比。树存在的意义，就是把这个数字压低。

一句话同时对上两个子 skill 时，说明这个任务横跨两者，把两者串起来是父级的事，所以路由停在父级：

```
$ python3 organizer/scripts/organizer_cli.py route . "convert the Word report to a PDF"
sentence: "convert the Word report to a PDF"
root -> taken by: office-docs (via 'Word','PDF')
office-docs -> taken by: office-docs/docx (via 'Word','report'), office-docs/pdf (via 'PDF') -> two or more children take it; a sentence spanning children is the parent's job, stop at office-docs
lands on: office-docs
read: 2 file(s), 3,372 bytes of 26,821 in the library (12%)
```

什么都对不上的句子停在根上，agent 按根的说明做事：

```
$ python3 organizer/scripts/organizer_cli.py route . "draw a poster for the launch"
sentence: "draw a poster for the launch"
root -> taken by: (none)
lands on: root (nobody took it)
read: 1 file(s), 2,374 bytes of 26,821 in the library (8%)
```

## 检查这棵树

新建的 skill 里还是占位文字，占位文字被换掉之前，两个检查工具都不放行：

```
$ python3 scripts/holon.py validate .
Found 6 problem(s):
  ✗ ./office-docs: example sentences (metadata.holon-triggers) are still TODO placeholders
  ✗ ./office-docs: body still contains TODO placeholders (body line 4)
  ✗ ./office-docs/docx: example sentences (metadata.holon-triggers) are still TODO placeholders
  ✗ ./office-docs/docx: body still contains TODO placeholders (body line 4)
  ✗ ./office-docs/pdf: example sentences (metadata.holon-triggers) are still TODO placeholders
  ✗ ./office-docs/pdf: body still contains TODO placeholders (body line 4)
```

```
$ python3 organizer/scripts/organizer_cli.py lint .
[E] office-docs: triggers are still the TODO placeholders from init; write 2 sentences it should take + 1 it should not
[E] office-docs/docx: triggers are still the TODO placeholders from init; write 2 sentences it should take + 1 it should not
[E] office-docs/pdf: triggers are still the TODO placeholders from init; write 2 sentences it should take + 1 it should not

lint: 3 errors, 0 warnings, 6 skills
bodies: 5 skills, 4 to 85 non-blank lines, median 9, 0 over 150
```

`lint` 的最后一行显示活分得匀不匀：最短和最长的正文、中位数、有几个超过 150 行。它只是参考信息，不算错误。

写好的 skill 是这样的：

```markdown
---
name: docx
description: "Use when writing or editing Word documents: covers Word, docx, report; excludes spreadsheet"
metadata:
  holon-triggers: |
    write the quarterly report in Word
    fix the heading styles in this docx
    draw a poster for the launch should go to /
---

# docx

1. Open or create the document with python-docx.
2. Apply the house styles from `references/styles.md` before adding content.
3. Write content section by section; never paste raw text into a heading.
4. Save and re-open once to confirm the file is not corrupt.
```

`holon-triggers` 下面三行就是这个 skill 的测试：两句它应该接的，一句它不该接的，并写明那句该去哪里。父级也要写三句，写的是没有哪个子 skill 能单独接住的句子，比如 "convert the Word report to a PDF"。`pdf` 和 `office-docs` 也写好例句和步骤之后，`replay` 把所有例句都走一遍：

```
$ python3 organizer/scripts/organizer_cli.py replay .
replay: 15/15 passed
```

以后某次改动让其中一句走到了别处，`replay` 会指出是哪句话、落在了哪里、被哪个词接走。每次改树，最后都要跑 `validate`、`lint`、`replay`，三个都通过才算完成。

## 从一棵空树开始

如果不想在仓库自带的这棵树上加，而是从零开始：

```bash
python3 holon/scripts/holon.py init mylib --root ~/.agents/skills
```

它会写出一个根，带上阅读规则和三个记录文件，并把工具一起拷过去，维护这棵树的 agent 手边就有工具可用：

| 文件 | 记什么 |
|---|---|
| `synonyms.md` | 用户平时说的词，对应到 skill 里用的词 |
| `_feedback.md` | 路由没走对的情况，一行一条，由 agent 在干活时记下 |
| `ABSORB.md` | 每一次放置决定，同一个问题不决定两次 |

真正开始用之前，先拿树的主人平时说过的十句话，逐句用 `route` 跑一遍。大多数会落空，因为 skill 里用的是作者的词，主人用的是自己的词。`synonyms.md` 就根据这些落空的句子来写。

## 规则

一个 skill 放在哪，只由一个问题决定：把它拿掉，agent 还能不能把事做成？

做不成，它就是 **skill**，有自己的文件夹和 `SKILL.md`。做得成、只是做得差一些，它就是 **知识**，放进用到它的那个 skill 的 `references/` 文件夹里。知识从来不单独占一个文件夹，所以树里永远不会长出"杂项"文件夹。

其余的规则都是在别的层级上问同一个问题。某个 skill 里的一步，如果单拿出来也能通过这个问题，就成为子 skill，放在那个 skill 的文件夹里面；`pdf` 就是 `office-docs` 的一步。两个 skill 接同样的请求、给出同样的结果，就是同一个 skill，应该合并。几个父级都要用的 skill，比如办公文档和网页都要用的主题工具，不归其中任何一个，而是留在顶层，由各个父级指向它。skill 从不按主题、大小或文件类型分组，因为这些都说明不了 agent 能不能把事做成。

完整的规则和加 skill 的步骤写在 `organizer/SKILL.md` 里，agent 维护这棵树时会读它。

## 加一个别人写的 skill

`organizer/SKILL.md` 里写了五步，agent 照着做：

1. 把新 skill 的每一部分都过一遍"拿掉还能不能做成"。步骤留在 `SKILL.md`，背景材料移到 `references/`。
2. 查树里是不是已经有 skill 做这件事。请求相同、结果也相同，就合并，并把新 skill 的说法加进 `synonyms.md`。主题相同但结果不同，不算重复。
3. 问"这是谁的一步"，找到它的父级。不是任何 skill 的一步，就放在顶层。
4. 把两个 skill 的例句互相走一遍。谁接走了对方的句子，就给谁加 `excludes`。
5. 运行 `counter --bump`，再运行 `validate`、`lint`、`replay`，然后在 `ABSORB.md` 里加一节，写下这次定了什么。

什么都不删。被合并或被替换的 skill 整个搬进 `.retired/`，定错了还能撤回。`organizer_cli.py ask .` 会把步骤清单和 `ABSORB.md` 里以前的所有决定一起打印出来。

## 命令

| 命令 | 作用 |
|---|---|
| `holon.py install [SRC]` | 把一棵树拷到这台机器上各个 agent 工具读 skill 的地方，并检查拷过去的内容 |
| `holon.py hosts` | 列出 `install` 认识的 agent 工具、这里装了哪些、每个读哪些文件夹 |
| `holon.py init NAME --parent DIR [--desc D]` | 建一个 skill，更新父级的列表 |
| `holon.py init NAME --root DIR [--bare]` | 建一个新的根，带阅读规则、记录文件，以及工具（`--bare` 时不带） |
| `holon.py move 源... --parent 目录`、`move --plan 文件` | 把 skill 文件夹移动或复制到位（计划的一行是 `源 -> 目标`），重新同步新旧两处；要么全做，要么全不做 |
| `holon.py sync [DIR]` | 按文件夹重新生成每个父级的子 skill 列表 |
| `holon.py tree [DIR]` | 打印树和每条描述 |
| `holon.py validate [DIR]` | 检查文件头、占位文字、过期的列表、循环、Agent Skills 规范；有错时退出码为 1 |
| `holon.py migrate [DIR]` | 把 1.0 之前的 `triggers:`、`archive_count:` 字段移到 `metadata:` 下 |
| `organizer_cli.py lint ROOT` | 检查每条描述、它的覆盖词、例句，以及 `ABSORB.md` |
| `organizer_cli.py replay ROOT` | 走一遍所有例句，报告走错的 |
| `organizer_cli.py route ROOT "句子"` | 显示一句话一层一层的走法 |
| `organizer_cli.py overlap ROOT` | 列出覆盖词重叠超过 0.4 的同级 skill |
| `organizer_cli.py retire ROOT PATH --reason R` | 把一个 skill 搬进 `.retired/` |
| `organizer_cli.py feedback ROOT` | 列出 `_feedback.md` 里记下、还没处理的路由错误 |
| `organizer_cli.py counter --bump ROOT` | 每次加入别人写的 skill 之前，把计数加一 |
| `organizer_cli.py ask ROOT` | 打印放置步骤和以前的所有决定 |

会写文件的命令都支持 `--dry-run`。

## 现状和局限

这是 1.0.0，第一个公开版本，项目处于早期阶段。

已经验证过的：测试在 Linux、macOS、Windows 上用 Python 3.8 到 3.13 运行；这一页上的每一段命令输出，都由 `tests/test_readme_outputs.py` 和真实输出逐字比对；仓库里每个 `SKILL.md` 都通过了 Agent Skills 规范的官方验证器。

还没有验证过的：这些规则只用在过两个库上，一个是二十个 skill 的公开库，一个是为这个项目自己的工作写的三个 skill。用的过程中规则改过两处。还没有在几百个 skill 的库上试过。规则里的数字（五个覆盖词、每个父级九个子 skill、0.4 的重叠）是让这两个库能被检查的取值，不是测出来的最优值。它们是可以调的设置：怎么为你自己的库修改，见 [organizer/README.zh-CN.md](organizer/README.zh-CN.md#为你自己的库调整参数)。

路由比对的是词，不是意思。一句话里一个 skill 的词都没出现，就到不了那个 skill。办法是在 `synonyms.md` 里加一行；agent 遇到这种情况时会记到 `_feedback.md` 里，等人来补。同样的比对不懂否定（"什么都不要 absorb"里仍然有 `absorb`）；一句话同时要两件不相干的事时，可能被两个分支的 `excludes` 同时挡住，停在根上。

`replay` 和 `route` 检查的是词的模型，不是 agent。读路由表的 agent 按意思判断，可能去到词的模型不会去的地方，两个方向都有可能。路由表的每一行都列出工具用来匹配的词，包括父级通过下面的 skill 接住的词（`also takes, through its sub-skills: ...`），所以两者至少读的是同一批词；某个模型会不会照着走，还没有测过。仓库根目录的 [`eval/`](../eval/README.zh-CN.md) 是测这个的工具，拿同一批 skill 的平铺文件夹做对照；目前还没有发布过真实 agent 的结果。

根的描述写的是"Use for every task"，这样只列顶层文件夹的工具会选中这棵树。如果同一个 skills 文件夹里还有别的顶层 skill，这一句会和它们抢；这时给根写一个说明这棵树管什么的描述（`init 名字 --desc ...`）。

`organizer/references/design-notes.md`（§17）里的上下文测量，数的是路径上 `SKILL.md` 的字节，不是 token，也不包括路由之后做任务时读的内容。那里的数字也显示，大部分节省来自把背景材料移进 `references/`，而这一点平铺的库同样能做。

skill 的正文，也就是文件头以下那部分该怎么写，是另一个问题，还没有定论。目前的规则只有两条：正文写成编号的步骤，背景材料放进 `references/`。

这个项目由一个人业余维护。只改一件事、并且带测试的 pull request 合得最快；改动需要保住什么，见 [CONTRIBUTING.md](../CONTRIBUTING.md)。

## 为什么这样设计

`pdf/` 本身是一个完整的 skill：把这一个文件夹拷到别的 agent 的 skills 文件夹里，不用改就能用。它同时又是 `office-docs/` 的一步，两种身份下文件夹里的内容完全一样。Arthur Koestler 在 1967 年造了 *holon* 这个词，指的正是这种东西：自己是一个整体，同时又是更大整体的一部分。也因为这样，挪动一个 skill 从来不需要改写它：挪文件夹，`sync` 会重新生成父级的列表。

工具从不做判断。`holon.py` 保证每个父级的子 skill 列表和磁盘上的文件夹一致。`organizer_cli.py` 检查能机械检查的部分：描述的格式、例句是否落在该落的地方、同级 skill 有没有抢同一个词、有没有东西被删掉。一个 skill 该放在哪，是 agent 读了 `organizer/SKILL.md` 之后做的决定；工具检查的是这个决定写下来之后是否一直成立。把 `organizer/` 整个删掉，树照样能路由。

```
holon/
├── SKILL.md              agent 怎么读这棵树，以及顶层的路由列表
├── scripts/holon.py      install、hosts、init、sync、tree、validate、migrate
├── editing/SKILL.md      agent 怎么通过工具改这棵树
├── organizer/
│   ├── SKILL.md          规则：skill 放在哪、什么算重复
│   ├── scripts/organizer_cli.py   lint、replay、route、overlap、retire、feedback、counter、ask
│   └── references/design-notes.md 每条规则的理由，以及应用规则时学到的东西
├── synonyms.md, _feedback.md, ABSORB.md   三个记录文件
└── tests/
```

每条规则背后的理由，以及每次应用规则学到了什么，写在 `organizer/references/design-notes.md` 里。

## 许可

MIT，见 [LICENSE](LICENSE)。
