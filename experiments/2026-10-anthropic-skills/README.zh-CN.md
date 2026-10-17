# 实验：agent 在 holon 树里能不能找到对的 skill？（anthropics/skills，2026 年 10 月）

[English](README.md)

这个文件夹完整保存了一次实验：脚本、标注好的请求、每一轮的 description、结果和日志。这里的东西不会被安装，`holon/` 也不依赖它。

## 要回答的问题

工具能检查一棵树格式对不对、它自己的例句会不会落到该去的地方（`validate`、`lint`、`replay`）。但用户真正关心的它查不了：一个人真实打出来的请求，agent 读这棵树时，会不会加载这个请求需要的 skill？这个实验在一个真实的库上测这件事，读树的是模型，然后根据测出来的问题去改工具。

## 实验设置

- **库。** [anthropics/skills](https://github.com/anthropics/skills) 在 `dbd4588f`（2026-10-09）这个提交的 19 个 skill，放进一棵 24 个 skill 的 holon 树：顶层 16 个；`office-docs/` 下面是 `docx`、`pdf`、`pptx`、`xlsx`；`web/` 下面是 `frontend-design`、`web-artifacts-builder`、`webapp-testing`；另外是树自带的 `editing` 和 `organizer`。原作者的每条 description（最长 1,068 字符）都改写成 holon 格式，不超过 200 字符、最多 5 个 cover 词，每个 skill 配 2 条正例句、1 条反例句。skill 正文不在这个文件夹里，`scripts/prep.py` 会从上游仓库的检出重建这棵树。
- **模型。** 所有模型调用都用 `deepseek-v4.1-flash`，走一个 OpenAI 兼容接口，包括写请求、标注、提 description 修改方案和读树。标注用的模型和读树的模型是同一家族，这是已知的弱点，见「局限」。
- **请求。** 40 个写手各分到 30 种身份之一（后端工程师、HR 经理、博士生……）和 6 种语气之一（简短英文、客气英文、非母语英文、三种中文），每人写 25 条请求，不告诉他们 skill 的名字：大约 14 条正好一个 skill 适用，4 条需要两个，7 条哪个都不适用。去重后共 976 条（`data/pool.json`）。
- **标注。** 三个标注器各自读原作者的 description（不是我们改写的版本），列出每条请求需要的 skill。769 条三个答案完全一致，193 条有两个一致，14 条没有任何两个一致，丢弃。留下的 962 条随机分成 `data/dev.json`（476 条，调优用）和 `data/test.json`（486 条，留到最后才用）。标签是一个 skill 集合，空集表示不该加载任何 skill。
- **三种路由方式，都和标签比对。**
  - `tree`：模型从根 `SKILL.md` 开始，读它的路由表，说下一步读哪些子文件夹，一层层往下（最多读 8 个文件）。最后到达的 skill 就是它的答案。
  - `flat`：模型在一张列表里看到所有 skill 的名字和 description，直接挑。`flat_old` 用原作者的 description，`flat_new` 用我们改写的。
  - `lex`：`organizer_cli.py route`，工具自己的词匹配，完全不用模型。
- **计分。** 加载的集合和标签完全相同才算对。`logs/` 里表格括号中的数字，是总共比标签多加载了几个 skill。

## 按顺序做了什么

| 步骤 | 做了什么 | 结果 |
|---|---|---|
| 0 | 第一版树，用本项目自己写的 80 条请求（`data/sentences.json`）手工调过 | flat_old 70/80，flat_new 77/80，tree 75/80，lex 39/80；replay 69/69 |
| 1 | 在 476 条 dev 请求上跑基线 | tree 335/476，lex 209/476 |
| 2 | 第 1 轮：每个 skill 配一个负责代理，读自己在 dev 上的错例，再派 3 个攻击代理（易混淆的请求、少见说法、中文边界句），提出新的 description、例句和同义词；每个同义词由三个审核代理投票 | tree 386/476，lex 262/476，但 **replay 掉到 54/69** |
| 3 | 第 2 轮：同样再来一遍 | tree 380/476，lex 241/476，replay 54/69，没有提升 |
| 4 | 修 replay，第一次尝试：一个代理拿到整棵树和全部 15 个失败 | 每次调用都撞上接口两分钟的上限（prompt 23,494 字符），一个结果都没拿到 |
| 5 | 修 replay，第二次尝试（`scripts/fixer2.py`）：每个失败一个小代理，只给它涉及的那几张卡片，每个失败出 3 个方案；每个方案在树的副本上单独测，能提升的按顺序叠加，只要还在提升就继续 | 两轮内 replay 从 54 到 68/69；最后一个手工修好 → **69/69** |
| 6 | 最终分数 | dev tree 390/476，test tree **389/486**；test lex 225/486 |
| 7 | 把根的阅读规则从「有一行匹配就往下」改成「每一行匹配都往下」，两种写法，在 test 上跑 | 377/486 和 389/486，见下文；没有采用 |

### 留出的验证集：第一版树对最终版树

| | 全部 | 一个 skill | 两个 skill | 中文 | 不该加载 |
|---|---|---|---|---|---|
| tree，第 0 轮 | 343/486 (70.6%) | 111/126 | 27/67 | 167/243 | 38/50 |
| tree，最终 | 389/486 (80.0%) | 120/126 | 28/67 | 195/243 | 46/50 |
| lex，第 0 轮 | 213/486 | 61/126 | 6/67 | 103/243 | 43/50 |
| lex，最终 | 225/486 | 74/126 | 4/67 | 103/243 | 44/50 |

同一批最终 description，改成平铺读，在同一个 test 集上另跑了一次：

| | 全部 | 一个 skill | 两个 skill | 中文 | 不该加载 |
|---|---|---|---|---|---|
| flat_old（原作者的 description） | 412/486 (84.8%) | 110/126 | 47/67 | 207/243 | 48/50 |
| flat_new（最终 description） | 398/486 (81.9%) | 114/126 | 38/67 | 198/243 | 48/50 |
| tree，最终（第二次运行） | 384/486 (79.0%) | 119/126 | 30/67 | 190/243 | 45/50 |

**在这个库上，平铺列表比树更准。** description 相同的情况下，平铺完全选对的次数比树多 14 次，差距几乎都在需要两个 skill 的请求（38 对 30）和中文请求上。只需要一个 skill 的请求，树略好一点（119 对 114）。`flat_old` 更高，但它的标签就是读同一批 description 标出来的。树第一次跑是 389，第二次是 384，所以五条上下的差别是噪声。

调优过程中没有看过 test 集。它在第 0 轮跑过一次，最终版树跑过一次，第 7 步的两种写法各跑一次。「实验说明了什么」第 3 条的错例分析，是在最终版跑完之后对 test 做的。

### 试过但没采用的阅读规则

需要两个 skill 的请求是最弱的一类（67 条对 28 条）。根规则第 1 条写的是「Go down only when a line matches ... When one matches, read the `SKILL.md` in that subfolder」，读起来像是只选一个。在 test 集上试了两种改写：

| 第 1 条的写法 | 全部 | 一个 skill | 两个 skill |
|---|---|---|---|
| 现有版本（「when one matches」） | 389 | 120 | 28 |
| 「每一行匹配都往下……一个任务经常匹配不止一行」 | 377 | 105 | 36 |
| 「每一行匹配都往下……只有任务确实需要那个 skill 做的事才算匹配；两行都确实匹配时，两个都读」 | 389 | 115 | 33 |

第一种多对了 8 条两个 skill 的请求，却丢了 15 条一个 skill 的请求，因为模型开始在不需要的地方多加载一个 skill。第二种多对 5 条、丢 5 条。两种总体都不更好，所以规则保持原样。如果对你来说少加载比多加载更糟，可以试第三种写法。

## 它让工具改了什么

- `lint` 会提示 `synonyms.md` 里到达不了任何 skill 的那一行（提交 `13ae9f9`）。第 1 轮生成的同义词组里有 `training, 培训, ...` 和 `email, 邮件`，它们的首词没有任何 skill 列出，折叠到这些词不改变任何路由，之前也没有任何提示。
- 第一次导入这个库时（提交 `4cc412e`）：`move` 会列出其他正文里还写着旧路径的地方；`lint` 区分三种情况：文件其实在某个祖先 skill 下（正文搬下来了，路径没跟着改）、资源文件确实缺失、路径多半是这一步要生成的输出；吸收一张卡片时，旧的长 description 里路由词以外的内容会移进正文第一步，不再直接丢掉。
- 文档里写进了这次实验说明的事：见 `holon/README.md`（现状和局限）、`holon/organizer/README.md`（检查通过不保证什么）和 `holon/organizer/references/design-notes.md` §21。

## 实验说明了什么

0. **24 个 skill 的规模下，树没有换来准确率。** 模型读一张 24 条短 description 的平铺列表，能同时看到所有选项，也能一次挑两个；读树的模型每一层都要先选定一个分支。树的价值在于库大到列不下时，每次要读的内容更少，而这个库没有那么大。这次实验没有测那种情况。
1. **为模型改写 description，和保持 replay 通过，方向是相反的。** 第 1 轮把 dev 从 335 提到 386，同时弄坏了 69 条例句里的 15 条。坏的几乎都是例句，而不是 description：父节点的正例只用了一个子 skill 的词；反例里还留着这个 skill 自己的 cover 词；某个子 skill 的例句里一个它自己的词都没有。改的是例句而不是 description，replay 就恢复了，dev 上的提升也没丢。
2. **词匹配只是粗筛。** test 请求里 `lex` 完全命中 46%（225/486），树是 80%；中文请求上 `lex` 只有 42%。加同义词开始有一点用，再加下去就会把无关请求送到错的 skill，这也是第 2 轮没有提升的原因。词模型的用途是检查树里已经做过的决定是否还成立，不是用来预测 agent 会怎么走。
3. **剩下的错，大多是一个要和别的 skill 一起用的 skill。** test 里有 29 条请求漏了 `discernment-nudge`，其中 25 条，标签要的其他 skill 树都加载了，只缺它一个。它讲的是怎么回答（起草、给建议、做推荐），几乎任何任务都可能用上，而一个每层只选一个分支的阅读者不会回头去拿它。`claude-api` 漏了 15 次，大多是 MCP 请求，标注器认为除了 `mcp-builder` 还要 `claude-api`。这两类有一部分取决于边界划在哪，而标注器划得比较宽。
4. **很多小代理做成了一个大代理做不成的事。** 整棵树一起修的 prompt 一次都没返回。每个失败一个代理、只给相关卡片、每个方案先用真实工具检查过再保留，两轮修好了 15 个里的 14 个。

## 局限

- 标签来自和读树模型同一家族的模型。三票一致能去掉一些噪声，但去不掉共同的习惯。标签是对原作者 description 含义的一种判断，不是真值。
- `flat_old` 的标签正是读同一批 description 标出来的，所以它占便宜。
- 只有一个模型、一个 24 个 skill 的库，每种配置只跑了一次。486 条里五条上下的差别，换一次运行就可能变。
- 完全匹配的计分方式，多加载一个 skill 算错（可能无害），少加载一个需要的 skill 也算错（可能有害）。日志里两种数都保留了。

## 重新运行

```bash
git clone https://github.com/anthropics/skills /tmp/anthropics-skills
git -C /tmp/anthropics-skills checkout dbd4588f
EXP=$PWD/experiments/2026-10-anthropic-skills
python3 $EXP/scripts/prep.py /tmp/anthropics-skills/skills /tmp/work final   # 或 round0、round2
cd /tmp/work && $EXP/cycle.sh                                                # validate、lint、replay：69/69

export LLM_BASE_URL=https://your-endpoint/v1   # 任何 OpenAI 兼容接口
export LLM_API_KEY=...                          # 如果代理会自动加 key，就不要设
SENTS=test.json python3 $EXP/scripts/evalrun.py test.json.out   # 加 FLAT=1 会同时跑平铺对照
python3 $EXP/scripts/score.py test.json.out
```

调用模型需要 `LLM_BASE_URL`；`LLM_MODEL` 默认是 `deepseek-v4.1-flash`。流水线的其余部分，按当时运行的顺序：`gen.py N`（写出 `pool.json`）、`label.py pool.json labeled.json`、随机切分成 `dev.json` 和 `test.json`、每一轮负责代理调优跑一次 `round.sh N 上一轮结果`（依次是 `owners.py`、`merge.py`、`cycle.sh`、`evalrun.py`、`score.py`），最后用 `fixer2.py 轮数 每个失败的方案数` 修 replay。`fixer.py` 是那个超时的整树修复，留着是因为 `fixer2.py` 复用它的辅助函数。

## 文件

| 路径 | 是什么 |
|---|---|
| `scripts/` | 流水线；所有路径和接口地址都在 `paths.py` 和 `llm.py` 里 |
| `cycle.sh`、`round.sh` | 把卡片写进树再检查；跑一轮负责代理调优 |
| `data/pool.json` | 写出来的 976 条请求原文 |
| `data/labeled.json` | 同样的请求加上三个标注器的投票 |
| `data/dev.json`、`data/test.json` | 留下的 962 条，切成 476 / 486 |
| `data/sentences.json` | 第 0 步的 80 条请求 |
| `data/upstream_descs.json` | 标注器读的原作者 description |
| `cards/round0.py`、`round2.py`、`final.py` | 第 0、3、6 步之后每个 skill 的 description 和例句 |
| `cards/synonyms_*.md` | 同样几个时间点树里的 `synonyms.md` |
| `results/` | 每次运行一个 JSON：每条请求的标签、各种方式加载了什么，以及树里走的路径 |
| `logs/` | 每一步的控制台输出，包括负责代理给出的理由和审核代理对同义词的投票 |
