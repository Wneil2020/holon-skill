---
name: organizer
description: "Use when absorbing a new skill or knowledge into this library, or when two skills look like duplicates: covers absorb, duplicate, boundary, place; excludes sync, validate"
metadata:
  holon-triggers: |
    absorb this new skill into the library
    is this skill a duplicate of an existing one, should they be merged
    just create a sub-skill directory and sync the parent routing table should go to editing
---

# organizer: how the library grows

This library is a list of jobs the agent can do. It is not an encyclopedia. The five rules below are the only basis for every decision. Everything after them is procedure.

In this document a *card* is one skill directory with its `SKILL.md`, treated as a unit that is moved, merged or retired whole.

## The five rules

1. **A skill is the ability to do one job and produce one result.** Test: if you removed it, could the agent still do the job? If not, it is a skill. Each skill is one directory with one `SKILL.md`.

2. **Knowledge is what you need to know to do a job well.** Test: if you removed it, the agent could still do the job, only worse. Knowledge is never a node of the tree. It goes into the `references/` folder of the skill that uses it. If several skills use it, it goes under their common parent. If no skill in the library uses it, there is no folder for it: either a skill is missing (add the skill, and the knowledge goes with it), or the knowledge is not needed (retire it). Knowledge is never kept for its own sake.

3. **A level is a step of a skill.** A skill produces its result in steps. A step that can be named on its own and has its own output is a sub-skill. To place anything, ask three questions: *Whose step is it? Does it have its own output? Is it a step of one of its siblings?* The three answers leave exactly one place. Keep splitting until a step has no output of its own. When a parent's step becomes a sub-skill, the parent keeps its own text for that step and adds one line pointing to the child. Levels have no names. A skill that is nobody's step is top-level. A skill that cannot be split further is a leaf. Everything between is "a sub-skill of X".

   Three consequences of this rule:

   - **Siblings get a parent when they deliver the same kind of thing.** Ask: is what these cards finally hand over the same kind of thing? Four cards that deliver Word, Excel, PowerPoint and PDF files all deliver an office document. Create an `office-docs` parent and move them in. The parent handles the cross-format steps, such as putting an Excel chart into a Word file. Do not ask "what extra does the parent do by itself"; that question never justifies any parent, because a parent's work can always be divided among its children. "The same kind of thing" has a second form: several cards that are successive stages of one product (see question 1 in the checklist below). Cards that deliver different things — a poster, an animation, a page layout — do not get a parent.
   - **A step that several parents need belongs to none of them.** Driving a browser to collect data is used by web work, by research and by reverse engineering. If it were filed under web work, every other task would have to mention "web" to find it. Such a card stays top-level, and each parent's text points to it. The same applies to **ways of working**, such as "interrogate a plan until it can be built" or "write the test before the code". They apply to every domain and are no domain's step. Keep them top-level. If the table gets long, open a "Ways of working" section in `groups.md`.
   - **Levels are not categories, but the table may be sectioned.** When siblings really deliver different things and the table is merely long, put a `groups.md` next to the parent's `SKILL.md`. Each line is one group: `Title: dir, dir`. The routing table is then written in sections, and children in no group fall into a final "Other" section. This only changes the layout. Nothing moves, nothing joins routing, and a section heading is not a node. A card that fits two sections is written on two lines and appears twice; the directory exists once. Creating a parent and moving directories is the first choice. `groups.md` is the fallback when no parent can be justified.

4. **A duplicate is the same task sentence with the same result.** The same topic with a different result is not a duplicate.

5. **A conflict is settled by comparing results.** If both skills can run, run them. If not, put both results in front of the library owner. Seniority and order of arrival do not count.

## Every skill carries three things

**A description in three parts:** `Use when ...: covers w, w; excludes w`.

- At most COVER_MAX cover words. Each at least COVER_MIN characters. Whole description no longer than DESC_MAX characters.
- Routing is a literal comparison. There is no tokenizer and no grammar. It is **case-insensitive**: Word, word and WORD are the same word.
- Write each cover word in the **shortest form a user would actually say**. "scraping" does not catch "scrape this". Write "scrape", and put "pull the data" into `synonyms.md` as its alias. A one-character cover word matches almost everything; `lint` flags it.
- Do not use **generic verbs** as cover words. "merge", "draft", "migrate" appear in everyone's sentences. "merge two PDFs" and "migrate the database" would both collide. Attach the object: "merge skills".
- Cover words are **folded through `synonyms.md` before matching**. A cover word that is itself an alias is replaced by its standard word first, so it matches every sentence containing the standard word. If "landing page" is an alias of "page", the cover word "landing page" catches every sentence that says "page". To match that much, write the standard word. To match less, pick a word that is not in any synonym group. `lint` points these out.

**Three example sentences under `metadata.holon-triggers`**, one per line. Two tasks this skill should take. One it should not, ending in `should go to <path>`. The Agent Skills spec allows six frontmatter fields and a string map named `metadata`; the sentences live there so that every file passes the spec's validator and any host that reads the spec reads it. Routing starts at the root and goes down one level at a time. A parent answers to its own cover words and to every cover word below it: a sub-skill is a step of the parent's job, so "build a pitch deck" reaches `office-docs/pptx` through `office-docs` although `office-docs` lists neither word. The parent's own cover words are for the sentences that span its children. Only a skill's own `excludes` blocks it; a child's `excludes` separates that child from its siblings and says nothing about the parent.

**A `synonyms.md` at the library root.** One group per line, comma-separated. The first word is the standard form. If an alias ends with the letters a cover word begins with, folding replaces the alias first and takes those letters with it, so the cover word no longer matches in that sentence. `lint` reports this; change one of the two.

The first entries in `synonyms.md` come from the owner, not from the skills. Before the library takes its first task, collect ten sentences the owner has actually said and run `route` on each. Cover words are written in the skill author's language; the owner's is different, and in the one library where this was measured, six of seven sentences missed until the synonym file was built from them. Every miss is one line for `synonyms.md`, or, if the owner's word names a job no skill does, one line for `_feedback.md`.

## Absorbing a new skill: five steps

Absorbing means teaching the library a new skill.

**Step 1. Separate skill from knowledge** (rules 1 and 2). Run each section of the newcomer through the removal test. A section that mixes both is split: steps stay in `SKILL.md`, background moves to `references/`, and the step that needs it names the file. A step that names a file which is not there cannot be followed; `lint` warns. To carry out the split, do not retype the text: run `python3 scripts/holon.py split <dir> --show`, decide each cut by line number, and apply it with `split --plan`; the plan format is in `editing/SKILL.md`. You decide what is cut and where it goes; the tool only copies the lines you named. A newcomer whose whole text says "call skill X" is not a skill. It is another name for X. Add the name to `synonyms.md` and create no directory.

**Step 2. Does the library already have the skill?** (rule 4). Before acting, read the `ruled:` lines of the root `ABSORB.md`. Those are decisions the library owner has already made, and they are not decided again. Run `ask`; it prints the checklist below and every `ruled:` line together.

- The library already has it. Do not learn it twice. Merge the newcomer into the existing skill, keep whichever text does the job better, and add the newcomer's wording to `synonyms.md`.
- The library has part of it. Add the missing part.
- The library does not have it. Learn it. Find the parent with the three questions of rule 3. No parent means a new top-level skill. Sub-skills that the newcomer brings **with their own directory and `SKILL.md`** are attached as children exactly as they are. Do not flatten or reorder them; the original author has already answered the three questions. Sections or sub-commands that exist only inside the text are split only if rule 3 says so. Either way, keep the text whole. A `---` line inside a body is not a card boundary.

  When a batch arrives, **read the whole batch** before answering the four questions. Read one card at a time and the answer to question 1 ("do these cards deliver the same kind of thing") cannot be seen.
- The newcomer **cannot perform a single step outside its original repository**. Its first step runs that repository's private command or reads its state file. Do not learn it. Move the whole card to `.retired/` with the reason "bound to its original repository".

  A retired card **need not be a valid card**; missing frontmatter is fine, because the tools never read `.retired/`.

  Judge by the first step. If the first step is independent and only later text carries the repository's path conventions, those conventions are knowledge (rule 2): learn the card and move the conventions to `references/`. **If the first step is bound** and later steps merely look generic, retire the whole card. Those later steps consume the first step's result and have no input anywhere else.

**Step 3. Put the knowledge part into `references/`** of the skill it serves. If the library already has the same document, keep the more complete one.

**Step 4. Settle conflicts** (rule 5).

*Routing conflicts*: two skills take the same sentence. Replay both skills' example sentences against each other. The skill whose positive example is taken by the other adds an `excludes`. If neither can take the other's, they are a real duplicate: go back to step 2 and merge.

First establish at which level they collide. **Two children of the same parent taking one sentence is not a conflict.** A sentence that spans two children is the parent's own step, and the route stops at the parent. "Word to PDF" stops at the office-docs parent, not in the Word or PDF child. Only **two top-level skills** taking one sentence is a suspected duplicate, because the root is not a skill and nobody can take it. When a child's positive example is also taken by a sibling and therefore stops at the parent, `replay` names the sibling. That is the moment to add an `excludes`.

**Every `excludes` between siblings** removes one cross-child sentence that the parent could have taken. If the Word child says "excludes PDF", the parent's "Word to PDF" has only the PDF child left, the route descends into it, and the parent never sees it. So a child's `excludes` lists only the sibling words that actually take its positive examples. Siblings whose cover words are disjoint, such as Word, PDF, slides and spreadsheet, never take each other's examples and need no `excludes` against each other at all; every such `excludes` only blocks a cross-format sentence from reaching the parent.

The first time this rule set was applied to a public library, every one of the four office children had been given `excludes` against its siblings, and `replay` failed every cross-format sentence until they were removed. Write an `excludes` only after `replay` shows a sibling taking your example.

An `excludes` word does one of two things, and the writer should know which. If some other skill covers the word, the `excludes` is a **redirect**: the sentence leaves this skill and reaches that one. If no skill covers it, the `excludes` is a **refusal**: this skill will not take the sentence, and nothing else will either, so it lands on the nearest ancestor or on the root. Redirects are the common case and are what step 4 produces. Refusals are for sentences the library should not handle at all; `lint` lists them as hints so that a refusal that was meant to be a redirect, whose target was renamed or never written, is seen.

Literal routing **ignores subject and object**. In "restyle this web page with brand colours", the page is the object, yet the word "web" matches the web parent. For sentences of the form "apply Y to X", put Y's word into the X parent's `excludes`, one at a time. What cannot be blocked goes into `_feedback.md`. Do not rewrite the example sentence to avoid the problem; users will not avoid it.

*Content conflicts*: two skills give opposite instructions for the same step. Verify what can be verified. Stop and ask the library owner about the rest. Record the decision in `ABSORB.md` so the same question is never asked twice.

**Step 5. Count and close.** Before changing the library, **run `counter --bump`**. This adds one to `metadata.holon-archive-count` in the root frontmatter, and that number is this absorption's id. `retire` writes it into the header of each retired card as `@<count>`. The new `ABSORB.md` section heading is `## @<count>`. All three use the same number. If you retire before you bump, the header is one behind the heading, and `lint` says so. To close: run `validate`, `lint` and `replay`; then append one section to `ABSORB.md`.

## Before creating a parent: four questions

Answer these in order before moving anything.

1. **Do these cards deliver the same kind of thing?** If yes, create a parent and move the directories in. This is the first choice. "The same kind of thing" has two forms. Several cards each deliver one format of the same product, such as several kinds of office document. Or several cards are **successive stages of one product**: set the visual direction, build the page, run the tests, check the copy. All of those deliver one web product. The second form is easy to miss, because the stages do not look alike and do not share names. (Common mistake: asking "what does the parent do by itself". With that question no parent is ever justified.)

2. **Is this card needed by several parents?** If yes, it belongs to none of them. Keep it top-level, and let each parent's text point to it. (Common mistake: filing it under the nearest domain, after which every other domain must say that domain's word to find it.)

3. **Is this card a way of working rather than a job in some domain?** If yes, keep it top-level and open a "Ways of working" section in `groups.md`. (Common mistake: forcing it under a domain, or treating it as unplaceable because it belongs to no domain.)

4. **Which sentences does the parent itself take?** Only sentences that span two or more of its steps. A sentence that touches one step belongs to the child. "Span" is literal: the sentence must contain **cover words of two or more children**, not merely be about the parent's topic. (Common mistake: writing a child's job as the parent's positive example. `replay` reports "only child X took this sentence".)

Only when all four are answered, no parent can be justified, and the table is still too long, write `groups.md` to section it.

## Nothing is deleted

Anything merged, superseded or split away is not destroyed. The whole directory moves to `.retired/<original path>/` at the library root, with a first line `retired @<count> <reason>`. If feedback later says "the old one was better", it can be restored whole. Routing and every check ignore `.retired/`.

## ABSORB.md

`ABSORB.md` sits at the library root and is append-only. One section per absorption:

```
## @3 <newcomer name>
learned: path/a, path/b
merged: newcomer's X merged into path/c, original moved to .retired/...
ruled: <one line stating the conflict> -> <how it was settled: evidence, or "owner's ruling">
```

A batch of many cards still gets one section and one count. The heading names the batch. `learned:` lists every path. `merged:` lists what was retired or merged. `ruled:` has one line per structural decision: which parents were created, which cards stay top-level, which were sectioned, and why. **The tools only recognise `learned:`, `merged:` and `ruled:`** lines. `lint` checks that each section has at least one; `ask` prints every `ruled:`. Other lines are not errors; they are simply not read. One section per card would put the `ruled:` lines among dozens of routine `learned:` entries, where they are hard to find.

## Hints, not rules

`lint` prints the following as hints (`[·]`), which do not count as errors or warnings; the missing-file case is a warning (`[W]`), because a step that names a missing file cannot be followed. Each asks for one more look at the skill, and none by itself requires a change.

- Body over MAX_BODY lines. Look at rules 1 and 2 again. Is knowledge mixed in? Are several separately nameable jobs mixed in? A long body that serves one job stays long.
- More than FANOUT siblings under one parent and no `groups.md`. Run `ask` and answer the four questions. If some siblings deliver the same kind of thing, create that thing as an intermediate skill and move them in (rule 3). Only if none do, write `groups.md`. Sectioning creates no node and needs no output. A one-member group is not a section; `lint` says so.
- A parent with exactly one child whose body says nothing but "see the child". This is a hollow parent. Promote the child and retire the parent.
- Two siblings' cover words overlap above OVERLAP. Suspected duplicate. Go to step 4.
- An `excludes` word that no skill covers. It is a refusal, not a redirect. Correct if the library has no skill for that word; otherwise name the sibling's cover word.
- A body that names a file in backticks, with a directory in the path, and no such file exists under the skill or at the tree root. The step cannot be followed. Add the file or fix the path. A bare name with no directory is not checked; it may be an output the step writes.

## Parameters

These six values are settings for this library, not rules. Its owner may change them; `organizer/README.md` says how, and the change is recorded as a `ruled:` line in `ABSORB.md`.

| Parameter | Value |
|---|---|
| COVER_MAX | 5 words |
| COVER_MIN | 2 characters |
| DESC_MAX | 200 characters |
| MAX_BODY | 150 lines |
| FANOUT | 9 |
| OVERLAP | 0.4 |

## Feedback

When the agent carrying out a task is routed to the wrong skill or finds no matching skill, it appends one line to `_feedback.md` at the library root: `task sentence | path taken | outcome`. Before the next absorption, handle each line:

- Routed wrongly: add a negative example to the skill that wrongly took it.
- Nothing found: first ask whether some skill already does this job. If yes, only the wording was missing; add the sentence's phrasing to `synonyms.md`. If no, a skill is genuinely missing; place it with rule 3.

Append ` done` to a handled line, and the `feedback` command stops listing it.
