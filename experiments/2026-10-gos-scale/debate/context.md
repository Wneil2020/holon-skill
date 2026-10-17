# Context (all technical, no personal data)

## holon (the project)
Zero-dependency Python tool + rules for organizing Agent Skills (SKILL.md folders) into a TREE. Each parent SKILL.md has an auto-generated routing table listing children with descriptions of the form "Use when ...: covers a, b; excludes c". Agents descend one level at a time, only into matching lines; "Read only what is on the path". Tools: sync, validate, lint, replay (example sentences in metadata.holon-triggers must route correctly via word matching), route, move, split (verbatim line-range split of a long SKILL.md into references/ and sub-skills by a JSON plan). Frontmatter is a strict YAML subset; extra data lives in the spec's `metadata` string map. Everything is offline, file-based, auditable; no embeddings, no servers.

## Measured so far
- Routing experiment, 24 skills (anthropics/skills), 486 held-out requests, model reads the tree: 80.0% exact skill set; same descriptions as flat list: 81.9%; word matching `route`: 46%. Gap is almost all requests needing two skills (tree picks one branch per level). A cross-cutting skill (`discernment-nudge`, advice style, applies alongside many tasks) accounts for many misses: in 25 of 29 misses the tree loaded every other needed skill. Rewording rule 1 to "go down every line that matches" gained multi-skill requests and lost single ones; not adopted.
- Split experiment, 4 long skills (600-1100 lines), 96 lookup questions: holon-rule split reads 27% less with 52/54 vs 54/54 correct on hard questions; mechanical heading split reads 44% MORE (pointer lines said only "details here"). Self-repeating grab-bag not helped.

## Graph of Skills (GoS, EMNLP 2026)
Offline: LLM builds a graph over SKILL.md files with typed edges (dependency, workflow, semantic). Runtime: hybrid vector+lexical seeds, then REVERSE personalized PageRank along dependency edges so prerequisites come along, return a capped bundle via MCP. Results on SkillsBench (87 tasks, avg 2.63 oracle skills per task): at 200 skills GoS ~= flat list (32.1 vs 32.5); at 500-2000 GoS +5-7 points while flat prompt tokens grow 1.85M->5.84M. Ablations: reverse traversal -> forward propagation costs 9.1 points (worse than removing graph, 5.1); halving description quality drops recall 0.146, halving I/O fields 0.024.
Local data available: GoS libraries of 200/500/1000 SKILL.md, the 87 SkillsBench tasks with oracle skill lists. A model endpoint (deepseek-v4.1-flash, 32 parallel) is available for experiments.

## Candidate additions (debate these; you may propose others)
A. Dependency edges: `metadata.holon-needs: "path/a, path/b"` on a skill = "when you load me, also load these" (prerequisites / cross-cutting). Reading rule: after reaching a skill, also read its needs (one hop, or transitive with a cap). sync renders "Also load: ..." in routing table lines; lint checks targets exist, no cycles, cap; route/replay follow edges.
B. Cross-cutting skills: a root-level "always consider" list (like discernment-nudge) separate from the tree.
C. Offline edge suggestion: `holon.py suggest-needs` proposes edges deterministically (a skill's body names another skill's path or name; co-occurrence in example sentences), agent decides. No embeddings.
D. Scale experiment: build trees for GoS 500/1000 and compare tree vs flat on the 87 SkillsBench tasks (recall of oracle set, tokens read).
E. Embedding/PPR retrieval, MCP server. (Presumed out of scope.)
