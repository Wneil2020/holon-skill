# 用 `holon.py split` 拆分四个长 skill（2026-10-17）

[English](README.md)

## 问题

除了路由之外，holon 的另一个主张是：一个又长又杂的 `SKILL.md` 可以重新规划成一个短的核心、若干子 skill 和若干 `references/` 文件，agent 只读任务用得上的那部分。路由实验（`../2026-10-anthropic-skills/`）和 Graph of Skills 测的都是「在已经干净的 skill 之间选哪个」，都没测这一点。这次查三件事：

1. 拆分会不会丢文字、改文字？
2. 拆完以后 agent 还能不能找到答案，读了多少？
3. holon 规划出来的拆法，是否比机械拆法好？

## 设置

- **skill**：取自 Graph of Skills 的 `skills_1000` 库（[数据集](https://huggingface.co/datasets/davidliuk/graph-of-skills-data)），是其中最长的四个相关文件：`citation-management`（1115 行）、`rdkit`（769 行）、`pymatgen`（691 行）、`senior-data-engineer`（608 行）。最后一个是大杂烩，Quick Start 的内容在 Workflows 里又重复了一遍。前三个是 SkillsBench 任务的标准答案 skill。
- **问题**：共 96 个，在任何拆分之前、对着**原始**文件写出。做法是把每个文件均分成四段，每段出 6 个问题，每题附一个简短的参考答案和出处行号（`qgen.py`、`questions.json`）。
- **把 skill 交给 agent 的三种方式**：
  - `full`：给整个原始 `SKILL.md`。
  - `heading`：机械拆分。凡是超过 25 行的 `##` 段，整段移到 `references/<slug>.md`，原处只留一行 `Details for this section: references/x.md`。
  - `holon`：让一个 agent 读 holon 自己的规则（organizer 规则 1–3、description 格式、organizer 第 1 步、editing 第 4 步）和带行号的原文件，写出 `split --plan`，再由 `holon.py split` 执行。它看不到问题。dry-run 拒绝时，把报错交还给它重写，最多试 5 次；实际只有 `citation-management` 需要重试一次。
  
  在 `heading` 和 `holon` 两种方式下，agent 从拆剩的 `SKILL.md` 读起，每轮最多打开 3 个文件，最多 3 轮，然后作答。
- **指标**：*答对*，由评判模型对照参考答案和出处行判断。*读到*，出处的每个非空行都出现在 agent 读过的文本里；这个指标很严，同一事实在别处出现不算。*读取量*，agent 读过的全部字符数。
- **难题集**：同一个模型完全不看文件，96 题能答对 42 题，因为 rdkit 和 pymatgen 它本来就熟。答错的 54 题组成难题集，只有在这些题上，读不读 skill 才决定答案。
- 出题、写拆分计划、作答、评判都用 `deepseek-v4.1-flash`，只跑了一轮。

## 结果

**一行没丢。** 两种拆法下，把每个源文件正文的非空行当作多重集合计数（`conserve.py`），全都还在拆分后的树里：853、544、504、401 行，缺失 0 行。

两种拆法的产物：

| skill | holon：子 skill／新 reference 文件／SKILL.md 剩余行数 | heading：reference 文件／剩余行数 |
|---|---|---|
| citation-management | 4／10／81 | 9／90 |
| rdkit | 12／2／88 | 3／53 |
| pymatgen | 9／5／166 | 5／104 |
| senior-data-engineer | 0／11／31 | 7／93 |

难题集（54 题）：

| 方式 | 答对 | 读到 | 读取字符 | 打开文件数 |
|---|---:|---:|---:|---:|
| full | 54/54 | 1.000 | 27,168 | 1.00 |
| heading | 52/54 | 0.574 | 39,014 | 3.37 |
| holon | 52/54 | 0.741 | 19,856 | 3.00 |

全部 96 题：full 答对 96/96，读 24,679 字符；heading 93/95（有一次调用失败），读 33,386；holon 94/96，读 16,396。

各 skill 的读取量，holon 对比 full：rdkit 10,583 对 20,789，pymatgen 13,108 对 20,841，citation-management 14,726 对 33,411，senior-data-engineer **27,165 对 23,678**。

## 说明了什么

- **holon 的拆分保住了答案，读取量少了约三分之一**：难题集上少 27%，全部题目上少 34%。代价是 54 题里错 2 题，而 full 一题没错。错的一题是一个命令示例，拆分计划把它放进了「示例工作流」，agent 却去「格式化」里找；另一题是一个参数，两种拆法都没找到。
- **机械拆分比不拆还差。** 同样是原样搬移，用的是同一个工具，区别只在指引行只写了「详情在这里」。结果 agent 打开了更多文件，读的比整个原文件还**多** 44%。两种拆法的差距，就出在指引行写了什么。
- **自我重复的大杂烩，拆分解决不了。** 在 `senior-data-engineer` 上，规划者没拆出任何子 skill，只拆出了 references。agent 读的反而比原文件多，因为同一批命令散落在好几块被移走的内容里。原样搬移会把两份副本都带走，所以得先合并副本，再拆。
- **真实世界的文件头。** `senior-data-engineer` 的文件头（嵌套映射、`related-agents: []`）超出了 holon 支持的 YAML 子集，`split` 拒绝处理。实验把这个文件头削减成只剩 `name` 和 `description`，这是本实验对源文本的唯一改动。现在 holon 已经能读 `[]` 这样的单行流式列表，嵌套映射仍然拒绝。

## holon 因此改了什么

- `holon.py` 能读单行流式列表（`key: []`、`key: [a, "b, c"]`），嵌套的流式集合仍然拒绝。对应测试是 `test_one_line_flow_lists`。
- editing 第 4 步：指引行要说明被移走的内容是干什么用的、什么时候该打开，不能只写它在哪。
- organizer 第 1 步：文件内容自我重复时，先合并副本再拆。

## 局限

- 只有 4 个 skill、96 个问题、跑了一轮，出题、拆分、作答、评判全是同一家族的模型。问题都是查找型的（一个命令、一个参数、一个函数），需要同时用到多个部分的任务没测。
- 2.5 万字符对现在的模型来说很便宜。这点节省要在同时加载很多 skill 或上下文很小的时候才显得重要。这次也没测端到端的任务成功率。
- 「读到」指标很严，同一事实出现两次时会少算；「答对」依赖评判模型。

## 复现

```bash
export LLM_BASE_URL=https://your-endpoint/v1 LLM_API_KEY=... LLM_MODEL=deepseek-v4.1-flash
cd experiments/2026-10-split-big-skills/scripts
./fetch.sh                                   # 把 GoS skills_1000 下载到 ../data/
export SPLIT_WORK=$PWD/..                    # trees/ 和 results/ 放在本 README 旁边
python3 apply_saved.py                       # 用 ../plans/ 里保存的计划重建两种拆分（不调模型）
python3 conserve.py                          # 缺失 0 行
python3 answer.py full,heading,holon run1    # 作答并评判
python3 answer.py none none1                 # 不给文件的基线
python3 report.py run1
python3 hard.py ../results/run1.json ../results/none1.json
# 想重新规划拆分而不用保存的计划：python3 plan.py；想重新出题：python3 qgen.py
```
