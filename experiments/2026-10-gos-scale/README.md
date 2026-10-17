# A tree of 500 skills, and dependency edges (2026-10-17)

[中文](README.zh-CN.md)

## Question

[Graph of Skills](https://github.com/davidliuk/graph-of-skills) (GoS) reports that past about 500 skills, listing every description flat costs too much and loses to structured retrieval, and that bringing a skill's prerequisites along (reverse traversal of dependency edges) matters more than the graph itself. holon had never been tried above 24 skills. Two questions:

1. At 500 skills, does a model reading a holon-style tree find the skills a task needs as well as a model reading the flat list, and how much less does it read?
2. Do one-hop `needs` edges ("when you load this, also load these"), written offline without looking at any task, close the gap?

Before running anything, three model agents argued what to borrow from GoS (a proponent, a skeptic, a maintainer; `debate/`). All three rejected embeddings, PageRank and an MCP server as against holon's offline, file-based design, and agreed on one-hop capped `needs` edges, with cross-cutting skills as `needs` of the root, gated by this experiment. The maintainer's adoption threshold: recall +5 points over the tree without edges.

## Setup

- **Library**: GoS `skills_500`. **Tasks**: the 87 SkillsBench tasks, each with its oracle skills (2.63 on average; 61 tasks need two or more). All 229 oracle references are in the library.
- **Tree** (`build_tree.py`): a model grouped the 500 skills into a routing tree, at most 12 lines per table, group lines in holon's `Use when ...: covers ...; excludes ...` form, leaves keeping their original descriptions. 104 tables, depth up to 4. It is one model pass, not a library tuned with `replay` and feedback as holon's rules intend.
- **Needs** (`needs.py`): for each skill, a model saw its body and 25 lexically similar skills and picked 0 to 3 that it *must* load with (a tool it calls, a format it reads); no task text was used. 40 skills got 61 edges. Edges found only by a skill's body naming another skill cover 15 of the 574 ordered oracle pairs, so name-matching alone would not have helped.
- **Routing** (`evalscale.py`): `flat`, the task and all 500 descriptions, choose skills. `tree`, start at the root table, choose lines to go down (several allowed), repeat, collect the leaves reached. `+needs`, add the chosen skills' needs, one hop. Same model (`deepseek-v4.1-flash`) for everything, one run. Retrieval only; tasks were not executed.

## Results

| | recall | all oracle skills found | precision | skills loaded | characters read |
|---|---:|---:|---:|---:|---:|
| flat | 0.900 | 67/87 | 0.842 | 3.02 | 95,188 |
| flat + needs | 0.913 | 69/87 | 0.837 | 3.11 | 95,188 |
| tree | 0.700 | 45/87 | 0.752 | 2.44 | 8,228 |
| tree + needs | 0.719 | 46/87 | 0.752 | 2.55 | 8,228 |

All oracle skills found, by how many the task needs: one skill, flat 26/26 and tree 21/26; two, 15/20 and 7/20; three or more, 26/41 and 17/41.

## What it shows

- **The tree reads about a twelfth as much and finds clearly less.** 20 points of recall lost against the flat list. Of the 73 oracle skills the tree missed, the flat list found 43, so most misses are routing, not skills that are hard to find either way.
- **Losses are spread over the domain branches, not one bad group.** Misses by top-level branch: documents 15, media 14, data science 13, software 13, science 10, others 8. A model choosing among 9 group lines at the root and again a level down can drop a needed skill at either step, and more often when the task needs several.
- **95k characters (about 24k tokens) was not too much for this model.** GoS's flat baseline degrades with size; this one, retrieval only, did not at 500. Flat listing stays the better choice while the whole list fits the model comfortably. What would change that is a model with a small context, or a library several times larger; neither was tested.
- **`needs` helped a little and cheaply**: +1.3 recall on the flat list, +1.9 on the tree, adding 7 oracle skills and 3 others on the tree. That is below the +5 that would justify a new header field, rule and tool support, so holon does **not** add `needs` now. The edges and the script are kept here for the next try.

## Limits

- One library, one model pass to build the tree, one model, one run. A tree tuned on its own misses (as in `../2026-10-anthropic-skills/`, where tuning raised tree routing by 9 points) might close part of the gap.
- Recall of the oracle set, not task success; GoS's numbers are task success.
- `needs` were chosen by a model in one pass; hand-written edges could be better or worse.

## Reproduce

```bash
export LLM_BASE_URL=https://your-endpoint/v1 LLM_API_KEY=... LLM_MODEL=deepseek-v4.1-flash
cd experiments/2026-10-gos-scale/scripts
./fetch.sh                 # skills_500 into ../data/; put the SkillsBench tasks in ../data/tasks/
python3 build_tree.py 500  # ../results/tree_500.json
python3 needs.py 500       # ../results/needs_500.json
python3 evalscale.py 500 run1
```
