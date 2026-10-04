# organizer

[English](README.md)

树工具 `../scripts/holon.py` 保证文件格式正确、每个父级的子 skill 列表和磁盘上的文件夹一致。它决定不了四件事：新 skill 该放在哪；两个 skill 是不是在做同一件事；两个 skill 指示相互冲突时听谁的；怎么移除一个 skill 又不把它弄丢。`organizer` 就是回答这四个问题的 skill。答案是 `SKILL.md` 里的规则，agent 加 skill 时照着做；`scripts/organizer_cli.py` 是检查这些规则有没有被遵守的工具。

这一页讲工具。规则本身在 `SKILL.md` 里，这里不重复。

## 文件

- `SKILL.md`：五条规则、每个 skill 必须带的三样东西、加入一个 skill 的五步、建父级之前要问的四个问题、`.retired/` 和 `ABSORB.md` 怎么用，以及参数表。
- `references/design-notes.md`：每条规则、每个数字为什么是现在这样。加 skill 时用不到。
- `scripts/organizer_cli.py`：工具。它比对词、检查结构，不对意思做任何判断。它用树工具自己的解析器读 skill 文件，所以两个工具看到的永远是同一个文件。
- `tests/test_organizer_cli.py`：测试，其中一组让这个包自己通过自己的检查。

## 命令

在树的根目录（放根 `SKILL.md` 的那个文件夹）里运行：

```bash
python3 organizer/scripts/organizer_cli.py lint     .                     # 格式检查；有 [E] 时退出码为 1
python3 organizer/scripts/organizer_cli.py replay   .                     # 走一遍所有例句；有失败时退出码为 1
python3 organizer/scripts/organizer_cli.py route    . "一句话"            # 一层一层显示一句话的走法
python3 organizer/scripts/organizer_cli.py overlap  . [--threshold 0.4]   # 覆盖词重叠的同级 skill
python3 organizer/scripts/organizer_cli.py retire   . <path> --reason R   # 把一个 skill 搬进 .retired/
python3 organizer/scripts/organizer_cli.py feedback .                     # _feedback.md 里还没处理的行
python3 organizer/scripts/organizer_cli.py counter  . [--bump]            # 查看或增加吸收计数
python3 organizer/scripts/organizer_cli.py ask      .                     # 步骤清单和以前的所有决定
```

每次改树，最后都要跑三条命令，三条都通过才算完成：

```bash
python3 scripts/holon.py validate .                  # 文件格式和路由列表
python3 organizer/scripts/organizer_cli.py lint .    # 每个 skill 都带齐了该带的东西
python3 organizer/scripts/organizer_cli.py replay .  # 例句仍然落在该落的地方
```

## 读懂 `lint`

`lint` 输出三种行，只有第一种算失败。

**`[E]`，错误，退出码 1。** 树缺了它就没法工作：没有描述、描述里没有覆盖词或覆盖词太多、例句少于三句、反例指向一个不存在的 skill、`groups.md` 格式不对。

**`[W]`，警告。** 很可能是失误，但树还能工作：旧格式留下的字段、短到几乎什么都能匹配的覆盖词、会被 `synonyms.md` 改写的覆盖词、只有一个成员的分组、缺少 `_feedback.md`、`ABSORB.md` 里编号超前于计数器或重复的小节、`.retired/` 里没有头行的文件、正文里提到却不存在的文件。

**`[·]`，提示。** 不计数，也不算错，就是 `SKILL.md` 里的“提示，不是规则”。正文超过 MAX_BODY 行或少于三行非空行、父级有超过 FANOUT 个子 skill 却没有 `groups.md`、只有一个子 skill 且正文是空的父级、一个没有任何同级覆盖的 `excludes` 词。

倒数第二行是计数，比如 `lint: 0 errors, 0 warnings, 5 skills`，最后一行汇总整棵树的正文长度。

`lint` 读的是描述和结构，不读正文的意思，所以它分辨不出一段正文是在描述一个 skill，还是混进了应该放进 `references/` 的知识。

## 工具检查什么，留给 agent 什么

`replay` 从根开始，把每个 skill 的例句走一遍。正例必须落在它自己的 skill 上，反例必须不落在上面。一句话同时对上同一父级下的两个子 skill 时，停在父级，这算正确，因为横跨两步的活是父级的。两个顶层 skill 同时对上时，`replay` 报 `[FAIL ambiguous]`。每个失败都说明原因：被哪个同级用哪个词接走、被哪个 `excludes` 挡住、或者因为缺词停在哪一层。

`route` 走一句话，逐层打印：谁接走了、靠哪个词、哪个子 skill 被它自己的 `excludes` 挡住。如果 `synonyms.md` 改写了句子，会显示改写后的句子。改了覆盖词或同义词之后、跑 `replay` 之前，先用它看一看。

`overlap` 列出覆盖词重叠超过 OVERLAP 的同级对，这些就是可能要合并的对。`retire` 把文件夹搬到 `.retired/<原路径>/`，在里面每个 `SKILL.md` 的第一行写上 `retired @<计数> <原因>`，再跑 `sync`。`ask` 原样打印 `SKILL.md` 里的四个问题，再打印 `ABSORB.md` 里每一行 `ruled:`，让以前的决定在做新决定之前被读到。

留给 agent 的，是所有需要理解意思的事：五条规则、拿掉测试、放置问题，以及遇到提示时怎么办。工具的保证更窄：一个决定一旦写成描述、例句或同义词，每次都会被同样地检查。所以三项检查都通过，说明树的格式正确、以前的每个决定仍然成立；不说明每个 skill 都放对了地方，那方面的证据会出现在 `_feedback.md` 里。

### 检查通过不保证什么

反例可能只是避开了自己的 skill，却没有到达声明的目标，仍算通过。这时 `replay` 会打印 `NOTE negative did not reach its target`，该提示不改变退出码；不要只看 passed 计数。同样，引用文件缺失属于 lint 警告，不是执行验收。三个零退出码不保证依赖齐全、任务能运行，也不保证真实 agent 走同一条路。

非 ASCII 覆盖词按子串匹配，不做分词：`文件` 也会命中 `文件夹`。将 COVER_MIN 降为 1 会增加这个风险，不会获得中文分词能力。同义词是全局、无上下文的折叠；修好一次漏匹配的别名，也可能造成新的误匹配。每次修改后都要复测应当命中及不相关的请求。

如果 skill 引用了父级或根的资料、其他 skill，或树相对路径的反例目标，它就不是自包含目录。复制到另一棵树前，要带上依赖或调整引用与例句，再运行检查。organizer 脚本本身也依赖根目录的 `scripts/holon.py`。

## 退役一个 skill 之后

`retire` 搬文件夹时不读内容，`lint` 和 `replay` 也从不看 `.retired/` 里面。它不会更新那些反例指向被退役 skill 的其他 skill。退役 `web/chart` 之后，`lint` 会逐个点名：

```
[E] lib-org: negative-example target 'web/chart' is not a skill in this library
[E] web/dark-mode: negative-example target 'web/chart' is not a skill in this library

lint: 2 errors, 0 warnings, 4 skills, 1 retired
```

## 为你自己的库调整参数

`SKILL.md` 里的规则对每个库都一样，但其中六个数字不是规则，而是设置。它们是为了让最初用过的两个库能被检查而取的值；习惯不同的库可以取别的值。它们写在两个地方，两处必须一致：

- `SKILL.md` 末尾“Parameters”一节的表，agent 读这个；
- `scripts/organizer_cli.py` 开头的常量，`lint` 和 `overlap` 用这个。

有一个测试（`test_param_table_matches_cli_constants`）比对这两处，所以要一起改。改完在仓库根目录运行 `python3 scripts/check.py`。

| 参数 | 出厂值 | 管什么 | 类型 | 什么时候改 | 测试接受的范围 |
|---|---|---|---|---|---|
| COVER_MAX | 5 个词 | 一条描述最多几个覆盖词 | 错误 `[E]` | 你的 skill 要靠很多短词来命名时调高（比如中文库里一个 skill 有好几个近义说法）；想逼 skill 分得更细时调低 | 5 及以上。低于 5 时，包自带的 `editing` skill（5 个覆盖词）过不了 `lint`，要先缩短它的描述 |
| COVER_MIN | 2 个字符 | 覆盖词最短几个字符 | 警告 `[W]` | 中文、日文库设为 1，因为一个字常常就是一个词；两个字母的词老是误匹配时调到 3 | 1 到 4。设为 5 时，包自带的四字母覆盖词（`task`、`sync`）会被警告 |
| DESC_MAX | 200 个字符 | 描述最长多少字符 | 错误 `[E]` | 需要更多字符的语言，或者想写更长的 `Use when` 时调高；中文库可以调低 | 198 及以上（包里最长的描述是 198 个字符） |
| MAX_BODY | 150 行 | 正文超过多少行给提示 | 提示 `[·]` | 想更早被提醒“知识该放进 `references/`”时调低；skill 本来就是长流程时调高 | 任意；低于 85 时 `organizer` 自己会收到提示 |
| FANOUT | 9 | 一个父级下超过几个子 skill 时，提示建一个中间父级或写 `groups.md` | 提示 `[·]` | agent 在长列表里常选错行时调低；能接受长而平的列表时调高 | 任意正整数 |
| OVERLAP | 0.4 | 两个同级 skill 的覆盖词重叠比例超过多少时被 `overlap` 列出 | 筛查 | 想看到更多可能的重复时调低，想看到更少时调高 | 0 到 1 之间 |

“类型”说的是一个 skill 超过这个值会怎样。只有错误会让 `lint` 退出码为 1；警告会打印并计数；提示只打印、不计数。`OVERLAP` 只影响 `overlap` 列出什么。

手工修改一个参数：

1. 改 `SKILL.md` 表里那一行。单位词（`words`、`characters`、`lines`）要保留，测试会读它们。
2. 改 `scripts/organizer_cli.py` 里同名的常量。
3. 运行 `python3 organizer/tests/test_organizer_cli.py`（在仓库根目录还可以运行 `bash scripts/check.sh`），然后对你的树跑 `validate`、`lint`、`replay`。把上限调低，可能会让现有的 skill 变成错误；`lint` 会逐个点名。
4. 在你的树的 `ABSORB.md` 里加一行 `ruled:`，写明改了哪个值、为什么，例如 `ruled: COVER_MIN 2 -> 1 -> 这个库是中文的，单个汉字就是一个词`。改规则也是一个决定，`ask` 会在下一个决定之前把它给 agent 看。

一次只改一个值，这样之后 `lint` 报出的任何问题都能追到它。出厂值的理由见 `references/design-notes.md` 第 10 节。

`holon/README.md` 里的演示引用的是用出厂值跑出来的输出。它的测试会在一份把出厂值放回去的副本上跑演示，所以改参数不会让这个测试失败。

### 哪些不是参数

`SKILL.md` 里其余的内容都是规则，不是设置：描述格式 `Use when ...: covers ...; excludes ...`、每个 skill 三句例句、两个子 skill 同时对上时停在父级、用 `.retired/` 代替删除、`ABSORB.md` 里的 `learned:` / `merged:` / `ruled:` 行。工具依赖这些，改它们就要改工具和测试（见 `CONTRIBUTING.md`）。

库里由你来填的部分也不是参数，而是文件：

| 文件 | 写什么 |
|---|---|
| 根 `SKILL.md` | 树的名字和下面的 skill（`holon.py init 名字 --root 目录` 会写好） |
| `synonyms.md` | 你自己的说法，对应到 skill 用的覆盖词。按 `SKILL.md` 说的，从你真正说过的十句话开始 |
| `groups.md`（可选，放在某个父级旁边） | 长路由表的分节标题 |
| `ABSORB.md` | 你做的决定，包括参数的修改 |

## 测试

```bash
python3 tests/test_organizer_cli.py
```

改了 `SKILL.md` 或工具之后都要跑。这个包自己必须通过 `validate`、`lint`、`replay`，`SKILL.md` 也必须保留工具和 `ask` 依赖的那些语句。

## 许可

MIT，见包根目录的 `LICENSE` 文件。
