# eval：测量这棵树到底有没有用

[English](README.md)

`replay` 只能说明一棵树和它自己的词模型一致。它说明不了：agent 是否按同样的路径走，是否比平铺的文件夹更常选对 skill，是否读得更少。这个文件夹里是测这些的工具 `harness.py`，和仓库其他部分一样只用标准库。它不属于安装的包。

目前还没有发布过真实 agent 的结果。下面的数字来自词模型，不花钱，也是 CI 跑的那部分；它们说明工具能用，不说明树有用。

## 比什么

同一批 skill 的三种摆法，用来把"树"的作用和"正文变短"的作用分开：

| 摆法 | 是什么 | 怎么得到 |
|---|---|---|
| A. 平铺，原样 | 每个 skill 保持拿来时的样子，平放 | 你手里原来的文件夹 |
| B. 平铺，精简 | 树里的 skill，正文和树里一样，平放 | `harness.py flatten 树 输出目录` |
| C. holon 树 | 同一批 skill，按 organizer 的规则放好，作为一个根 | `holon.py init`，再 `holon.py move --plan` |

B 减 A 是规则 2（把知识移出正文）的作用；C 减 B 才是树本身的作用。设计记录 §17 显示，目前测到的节省大部分属于 B 减 A。

## 从平铺文件夹到结果

```bash
# 1. 建根，以及计划里要用到的父级（由 organizer/SKILL.md 决定要哪些）
python3 holon/scripts/holon.py init mylib --root build
python3 build/mylib/scripts/holon.py init office-docs --parent build/mylib --desc "Use when ...: covers ..."

# 2. 写放置计划：每个 skill 一行，`源 -> 目标`（目标是 父级/名字；写成 `父级/` 则保留原名）
#      flat/word-docs -> build/mylib/office-docs/docx
#      flat/poster    -> build/mylib/
python3 build/mylib/scripts/holon.py move --plan plan.txt --copy     # 先加 --dry-run 看；要么全做，要么全不做
python3 build/mylib/scripts/holon.py validate build/mylib

# 3. 摆法 B
python3 eval/harness.py flatten build/mylib build/trimmed

# 4. 测试句子：在改覆盖词或 synonyms.md 之前先冻结
python3 eval/harness.py freeze sentences.tsv

# 5. 运行，再出报告
python3 eval/harness.py run sentences.tsv --tree build/mylib --flat flat --trimmed build/trimmed \
    --names plan.txt --runner claude-code --runs 3 --out results.csv
python3 eval/harness.py report results.csv
```

`move` 只做放置里机械的那一半。每个 skill 放哪、要建哪些父级，仍然由人或按 `organizer/SKILL.md` 工作的 agent 决定；计划文件就是把这个决定写下来的地方，可以审查，也可以重新执行。

## 句子文件

制表符分隔，带表头：`id  split  sentence  expected`。

- `split` 是 `test` 或 `tune`。只有 `test` 的行会运行并计入结果。用来调整树的句子放进 `tune`。
- `expected` 是一个或多个 skill 文件夹名，用 `|` 分隔；不该由任何 skill 接的写 `none`。在运行之前写好。
- `freeze` 记下 test 行的哈希。test 部分没冻结或冻结后改过，`run` 会拒绝；加 `--unfrozen` 可以照样跑，报告里会注明这些运行不能算证据。
- 尽量有至少 50 句 test，由没参与放置 skill 的人写：`_feedback.md` 里的行、issue、聊天记录。有意包含：不含任何覆盖词的改写、第二种语言、否定句、需要两个 skill 的句子。

## 执行方式

| `--runner` | 跑的是什么 | 花费 |
|---|---|---|
| `word-model`（默认） | organizer 的词法路由 | 不花钱；CI 跑的就是这个 |
| `claude-code` | 在临时项目里运行 `claude -p`，`.claude/skills/` 里放这种摆法，`HOME` 是空目录，工具只开放 `Read, Glob, Grep, Skill` | 每次运行一个 agent 会话 |
| `command` | 任何 agent：`--runner-cmd` 会收到 `{skills}`、`{prompt_file}`、`{workdir}`，最后输出一行 JSON：`{"chosen": ..., "files_read": [...], "input_tokens": N}` | 看你用什么 |

`--mode route`（默认）告诉 agent 不要做任务，只决定会照哪个 skill 的说明做，最后输出 `SKILL: <名字>`。这样测路由很便宜。`--mode task --check 命令` 让 agent 真的做任务，之后在项目文件夹里运行那条命令，退出码 0 记为 `task_ok`。

`claude-code` 默认给每次运行一个空的 `HOME`，这样你自己的 skill 和 `CLAUDE.md` 不会混进来；但这也会让订阅登录失效，所以要么设置 `ANTHROPIC_API_KEY`，要么加 `--keep-home` 并在结果里注明。`--raw-dir 目录` 会保存每次运行的 stream-json；`skills_seen` 一列记录工具启动时报告的 skill，用来找出看到了别处 skill 的运行。

没有真正调用到模型的运行（key 被拒、额度用完、代理返回提示而不是回答）会记下错误，并从所有比例中排除，不算作"选错"。

## 报告里有什么

- 每种摆法：完成的运行数、`route_ok`、`task_ok`、读取字节的中位数（工具顶层列表加上打开过的每个文件）、工具报告的输入 token 中位数；
- 在 C 上：agent 和词模型选得一样的比例；不一样时，哪一边是对的。这个数字说明在那个工具和模型上，`replay` 通过到底有没有意义；
- 每一次选错，按句子列出。

## 示例

`example/` 里是一个五个 skill 的平铺库、一份放置计划、十二句测试句子和两句调参句子。`example/build.py` 用这些输入建出树和精简副本；CI 会建一次并用词模型跑。当前工具的输出：

```
| arrangement | runs | sentences | route_ok | task_ok | median bytes read | median input tokens |
|---|---|---|---|---|---|---|
| A | 12 | 12 | 7/12 (58%) | - | 686 | - |
| B | 12 | 12 | 7/12 (58%) | - | 762 | - |
| C | 12 | 12 | 9/12 (75%) | - | 3873 | - |
```

要照它本来的分量看：十二句话和 skill 是同一个人写的，用的是词模型。C 接住了 A 和 B 都没接住的两句跨格式句子，因为父级 `office-docs` 就是为接这种句子建的。三种摆法都没接住 "fill out this Acrobat document" 和 "make a presentation about our Q3 numbers"（没有覆盖词），也都把 "do not touch the PDF" 送到了 `pdf`（不懂否定）。C 读的字节更多，因为树要经过根的说明和路由表；在五十个或五百个 skill 时，这是否比工具的平铺列表花更多 token，要靠真实运行来回答。

要接着做，先读 [HANDOFF.md](HANDOFF.md)：做了什么、没做什么，以及第一次真实 agent 运行的逐步做法。

## 提交结果

开一个 issue，附上 `results.csv`、句子文件、放置计划、技能库（不能公开就写一段说明）、工具和模型的版本、日期。证明树没有用的结果，和证明它有用的结果一样有价值。

## 测试

```bash
python3 eval/tests/test_harness.py
```

覆盖 `holon.py move`、`flatten`、冻结、三种执行方式（`claude-code` 用一个输出录制好的 stream-json 的假 `claude` 来测），以及没有调用到模型的运行。不会调用任何模型。
