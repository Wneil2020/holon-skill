# Design notes for organizer

This document explains why each rule in `../SKILL.md` is what it is. The rules themselves only say what to do. This document is not needed while adding skills. It is for changing a number, questioning a rule, or writing a different set of rules on top of the tree.

## 1. The problem

A skill library keeps receiving new skills, and every arrival raises the same question: which folder does this go into? When the question is answered without a rule, three things happen.

- **The skill is lost.** It is filed under a parent whose keywords no task for it will contain.
- **The tree keeps changing.** Each misfiling is corrected by moving folders, and skills that were in one place last month are somewhere else this month.
- **A "misc" folder appears.** Skills with no obvious parent go into one catch-all folder, which grows until routing to it is no better than reading every skill.

The tree tool (`holon`) makes the tree readable, writable and checkable. It deliberately does not answer "which folder does this go into". `organizer` is the part that does.

## 2. Start from the meaning of the word

Most schemes for organising skills sort them by topic, by task type, by size or by stage. All four sort by a property of the *text*. A skill library does not hold text for its own sake; it holds abilities to do jobs. A skill is the ability to do one job. Every rule below follows from that one definition, and none of them needs a number.

## 3. How the five rules follow

**A skill is the ability to do one job and produce one result.** The test is one question: if you removed it, could the agent still do the job? If not, it is a skill. Length, topic and count do not enter into it.

**Knowledge is what you need to know to do a job well.** Same test: remove it, and the agent can still do the job, only worse. Knowledge is not a node, because a node must be able to take a task. If a task were routed to a reference document, the agent would have a document and no instructions. So knowledge lives in the `references/` folder of the skill that uses it. This one rule removes the "misc" folder: everything that used to go there is either some skill's knowledge or a skill whose parent has not yet been found.

**A level is a step of a skill.** A skill produces its result in steps. A step that can be named on its own and has its own output is a sub-skill. "Adapt to dark mode" is a step of "build a front-end interface". It can be named alone ("adapt the whole site to dark mode") and has its own output (a dark colour scheme), so it is a sub-skill. "Choose colours" is also a step, but if you remove it the interface is still built, just with worse colours. That is knowledge. Depth limits itself: splitting continues until a step has no output of its own, and in the libraries this has been applied to, that happens at two or three levels.

The three placement questions (whose step is it, does it have its own output, is it a step of a sibling) are the definition turned into questions. Three answers leave exactly one place, so there is no ambiguity to resolve.

Levels have no names, no "domain / object / phase". Any naming scheme makes the same content appear under several names. "A sub-skill of X" needs no scheme.

Applying rule 3 to real libraries produced three consequences:

- *Siblings get a parent when they deliver the same kind of thing.* Four cards for Word, Excel, PowerPoint and PDF all deliver an office document. That is one parent with four children, and the parent handles the cross-format steps. Asking instead "what does the parent do by itself" never justifies any parent, because a parent's work can always be divided among its children. "The same kind of thing" has a second form that is easy to miss: successive stages of one product. Set the visual direction, build the page, test it, check the copy: all four deliver a web product.
- *A step that several parents need belongs to none of them.* Driving a browser is used by web work, research and reverse engineering. Filed under any one of them, the others must say that parent's word to reach it. Such a card stays top-level and each parent points to it. Ways of working (test first, interrogate the plan) are the same case in general form.
- *Levels are not categories, but the table may be sectioned* with `groups.md`. See section 11.

**A duplicate is the same task sentence with the same result.** The same topic with a different result is not a duplicate. Counting how often two skills match the same sentence does not identify duplicates: siblings under one parent match the same sentences by design. Compare the results first, then use the replayed examples as evidence.

**A conflict is settled by comparing results.** Run both if both can run. Otherwise put both results in front of the library owner. "Not by seniority, not by order of arrival" closes two shortcuts: first-come-first-served means a newer and better skill always loses, and any fixed ordering becomes a rule of its own.

## 4. Why every skill carries exactly three things

- **The three-part description** (`Use when ...: covers w, w; excludes w`) makes routing a literal comparison. The cover words are the skill's positive edge. The `excludes` words are its negative edge. Both are visible in the parent's table. Because the comparison is literal, a program can repeat it.
- **The example sentences** turn the intended routing into a test. Whenever a description or the synonym file changes, `replay` shows whether some other skill's routing broke.
- **`synonyms.md`** separates wording from structure. The most common cause of a routing miss in a new library is not a missing skill but a missing synonym. Keeping synonyms in one file means fixing a miss never touches the tree.

Together these are everything a program needs to replay routing. Nothing else in a skill card affects routing, so nothing else is required.

Two consequences of literal routing must be known by whoever writes cover words. First, cover words are folded through `synonyms.md` before matching, so a cover word that is an alias matches everything its standard word matches. Second, there is no grammar, so "restyle this page with brand colours" matches every skill that covers "page". Both are stated in the rules rather than fixed in code, because fixing them would require a tokenizer and a parser, and this package has no dependencies.

## 5. Why two children matching stops at the parent

If two children of one parent both match a sentence ("Word to PDF" matches the Word child and the PDF child), the sentence spans two steps. That is the parent's own job. So routing stops at the parent, and the parent's positive examples are exactly such spanning sentences. Only at the root, which is not a skill and cannot take anything, does a double match mean a conflict.

This is also why `excludes` between siblings must be used sparingly. Every `excludes` a child adds removes one spanning sentence that the parent could have taken.

## 6. Why nothing is deleted

Anything merged, replaced or split away goes whole into `.retired/<original path>/` with a one-line header. A library maintained in spare time has no one checking each deletion at the time it happens, and a wrong deletion is noticed only when a task later fails. Moving instead of deleting makes every such mistake reversible without anyone having noticed it at the time. The tools ignore `.retired/`, so it costs nothing at routing time.

## 7. Why `ABSORB.md` is one append-only file

Every structural decision (what was learned, what was merged, what was ruled) goes into one file at the library root, one section per addition. It answers "why is this skill here" and it holds the owner's rulings, so that the owner is never asked the same question twice; `ask` prints every `ruled:` line before the agent acts. Recording decisions inside each skill instead would mean reading every file to learn the tree's history.

A batch of many cards still gets one section and one count. One section per card would put the few `ruled:` lines among dozens of routine `learned:` entries.

## 8. Why the counter is bumped first

The absorption counter (`metadata.holon-archive-count` in the root frontmatter) is increased before an addition begins. That number is then used in three places: the headers of retired cards, the `ABSORB.md` section heading, and the counter itself. Bumping first makes the three agree. Bumping last leaves the headers one behind. The count is in additions, not dates, because two libraries with the same date can be at very different stages, while two libraries at addition 12 are comparable.

## 9. Why hints are not rules

Body length, number of siblings, hollow parents and keyword overlap are frequent signs of a problem and never proof of one. A long body that serves one job, or twelve unrelated siblings, is correct. If these conditions were errors, a correct tree would fail `lint`, and the real errors would be lost among them. So all four are `[·]` hints: not counted in the summary, not blocking. Each asks for the five rules to be applied to that skill once more. If the skill passes, it stays as it is.

The one hard rule that no tool can check is: an intermediate skill must have an output of its own; without one it is a category, not a skill, and may not be created. That is a question of meaning, so it lives only in the rules. It forbids creating nodes to shorten a table. To shorten a table without a node, use `groups.md` (section 11).

## 10. The parameters

None of these values comes from measurement. They are the values that made the rules checkable in the libraries this has been applied to, not values shown to be best. Adjust them for another library one at a time, and record the reason in `ABSORB.md`. The first two are hard rules; the rest only produce hints.

| Parameter | Value | Hard or soft | Reason |
|---|---|---|---|
| COVER_MAX | 5 words | hard | The cover-word list is one line of the routing table. More than five words means the skill is taking more than one job. |
| COVER_MIN | 2 characters | hard (warning) | A one-character cover word matches almost every sentence. |
| DESC_MAX | 200 characters | hard | Above this a table line wraps in an 80-column terminal more than twice, and the table becomes hard to scan. English descriptions need about twice the characters of Chinese ones, hence the value. |
| MAX_BODY | 150 lines | soft | Matches the tree tool's advice to consider splitting around 150 lines. A long body that serves one job stays long; the hint only asks you to re-check rules 1 and 2. |
| FANOUT | 9 | soft | Beyond about nine entries per table, agents in the libraries this was applied to began choosing the wrong line more often. Twelve unrelated siblings are not wrong, so this is a hint. |
| OVERLAP | 0.4 | soft | `overlap` is a screen, so it should report every possible duplicate and let the replayed examples rule out the false ones. In the libraries this was applied to, sibling pairs below 40 percent overlap were never duplicates. |

Two internal thresholds are not parameters, because they only decide when a hint appears: `SHORT_BODY` (fewer than 5 non-blank lines gives the "very short" hint) and `HOLLOW_BODY` (a parent body of at most 3 lines with exactly one child gives the "hollow" hint).

## 11. `groups.md`: sections without nodes

When siblings really deliver different things and the table is merely long, a `groups.md` next to the parent lays the table out in sections. It moves nothing, creates no node, and takes no part in routing. A section heading cannot take a task. A card that fits two sections is written on two lines. `groups.md` is the second choice. Creating a parent and moving folders is the first choice whenever the four questions justify it. That is why the `lint` hint for too many siblings points to `ask` first and to `groups.md` second.

## 12. What the tool does and what the rules do

`scripts/organizer_cli.py` compares words and checks structure: it parses frontmatter, routes sentences by cover words, checks that negative targets exist, and moves folders into `.retired/`. It makes no judgement about meaning. The table in `../README.md` lists rule by rule who checks what.

This split is deliberate. The five rules are all judgements. But once a judgement is made, it is written into a description, an example, a synonym line or an `ABSORB.md` entry, and from then on a program can check it. As the library grows, more of the questions that arise have a recorded answer and fewer need a new judgement. The tool does not make judgements; it checks that recorded ones still hold.

`ask` follows the same idea. It prints the four-question checklist from the rules file, keeping no copy of its own, so the rules file is the only source and editing it edits the tool's output.

## 13. What can be replaced and what cannot

The five rules are not one option among several. The tree routes by matching a task sentence against skill descriptions. That mechanism already assumes what a skill is: a thing that takes a task and hands over a result. A tree sorted by team, by tool, or by risk level would be a consistent filing system, but routing over it would fail, because a task sentence names a job, not a team. The five rules say out loud what the routing mechanism already assumes. Section 3 shows that all five follow from that one definition; a library that keeps the tree and rejects the rules has to replace the routing mechanism too.

What can be replaced is the procedure built on the rules: the three-part description format, the count of `triggers`, `synonyms.md`, `ABSORB.md`, `.retired/`, the counter, and every number in section 10. These are one way of making the rules checkable by a program. Another library may need another way. Any replacement has to answer the same three questions:

1. **Which folder does a new skill go into?** Here: the removal test and the three placement questions.
2. **When does the structure change?** Here: split by rule 3, merge by rule 4, create a parent after the four questions.
3. **How are decisions recorded so they are not made twice?** Here: `synonyms.md`, `triggers`, `ABSORB.md`, `_feedback.md`.

The tool reads only the three things every skill carries: the three-part description, the example sentences (`metadata.holon-triggers`) and `synonyms.md`. As long as those keep their form, the procedure can be rewritten and the tool works unchanged. Changing the description format means rewriting `parse_desc` and `tokenize` in `organizer_cli.py`; the file has no dependencies.

## 14. First application to a public library

anthropics/skills, 20 cards, absorbed 2026-09-21 into a fresh library with this rule set. Every card's body was left as it arrived; only descriptions, `triggers:` and the tree changed. The result passed `validate`, `lint` (0 errors, 9 body-length hints) and `replay` (66/66) after two rounds of fixes that `replay` named.

What the rules decided without difficulty: four office formats got a parent (question 1, first form); three web stages got a parent (question 1, second form); two styling cards that both parents need stayed top-level (question 2); four ways of working stayed top-level (question 3). The root table had 15 entries and was sectioned with `groups.md`.

What the rules did not cover, and were amended for:

- **Knowledge that no skill uses.** One card was a reference document. Rule 2 said knowledge goes with the skill that uses it, and no skill did. Rule 2 now says: add the missing skill, or retire the knowledge.
- **Sibling `excludes` written in advance.** The office children were given `excludes` against each other before `replay` was run. All four cross-format sentences then failed. The passage on `excludes` now says to write one only after `replay` shows the need, and gives this case.

What the tool reported that the author had missed: a multi-word cover word (`create skill`) that no sentence contains literally; a parent example that only one child took; two negatives that did not reach their targets because the sentence lacked the target's words. Each message named the fix.

**Second pass on one card.** `pdf` arrived with a 316-line body, a `forms.md`, a `reference.md` and eight scripts. Applying rules 2 and 3 to it:

- The body was a catalogue of code snippets by library (pypdf, pdfplumber, reportlab, qpdf). Removal test: the agent can merge a PDF without the catalogue, only slower. Knowledge, to `references/libraries.md`. `reference.md` likewise, to `references/advanced.md`.
- `forms.md` was a four-step procedure with its own scripts, its own trigger words ("form", "fillable fields") and its own output (a filled PDF). A step of `pdf` with its own result: rule 3 makes it a sub-skill, `pdf/form-fill`. Its scripts moved with it.
- What remained of `pdf` is 47 lines: the operation-to-tool table, three steps, and a check.

`replay` then caught three things in order. The sub-skill's example contained "spreadsheet", so `xlsx` took it too and the route stopped at `office-docs`; the message for this case was wrong (it said the parent's cover words were absent when they were present) and was fixed in the tool. The sub-skill's cover word "form fill" did not appear in "fill this PDF form"; the rule already said to write the shortest form a user says. The parent's example "fill this PDF form" now belonged to the child; a parent's example must span two children.

**Second pass on a second card.** `skill-creator`, 323 lines, was the opposite kind: no library catalogue, but one long procedure with several loops folded into it. Rule 3 found two steps with their own trigger words, scripts and output: the eval loop (`eval`, six scripts, three subagent briefs, a viewer) and description tuning (`describe`, one script). Rule 2 found three sections that fail the removal test: how to talk to the user, host-specific mechanics, the writing guide. What remained is 69 lines: the loop, the draft steps, and pointers. Two scripts that serve the whole loop stayed with the parent.

Both passes ended the same way: `replay` reported that a parent's example was now taken by only one child, because the sentence had become the child's job. A second pass moves examples as well as text.

Each pass took about the same effort as placing the other nineteen. That ratio is the cost of rule 2 in practice, and the reason the body-length check is a hint. A third pass, on `claude-api`, is in §17; the remaining six are in §19.

The resulting tree is not part of the open-source release. During development it was kept with its headers and structure and with stub bodies, because the passes on `pdf`, `pptx` and `doc-coauthoring` described in this section and in §19 are derivative works of text that upstream does not allow to be redistributed (`NOTICE.md` in that folder). The numbers quoted here were measured on the full bodies before they were withdrawn.

## 15. The host sees only the root

Every host that loads `SKILL.md` folders reads the description of each top-level folder and stops there. Nothing in this project changes that. The tree begins where the host's choice ends: after the host has opened `holon/`, the routing table in the root `SKILL.md` takes over.

This has one consequence for how the tree is used. If `holon/` is one folder among many in the host's directory, the host chooses between `holon/` and its neighbours by their descriptions alone, and `holon/`'s description says nothing about Word files. A task about Word files goes to a neighbour or nowhere. To make the host choose `holon/`, the root description would have to list what the branches cover, and that list would change every time a top-level branch is added. The tool does not write it, because a description written by a tool would be a second routing table, and the first one already exists one line below.

So the rules are written for the arrangement in which the tree is the whole library. Every skill is a branch of `holon/`; the host has one folder to choose and chooses it every time; from then on the tree routes. In that arrangement the root description does not need to name the branches, because the host is not choosing between `holon/` and anything else.

A library that must keep other top-level folders beside the tree can still use it, with the root description written by hand to name the branches. That is a maintenance cost the rules do not account for, and `lint` does not check that the root description and the branches agree.

The root `SKILL.md` itself is the one skill in the tree that does one job without a step list: its job is to be read on the way down, and its body is the six reading rules. Editing the tree is a different job with steps of its own, so it is a sub-skill, `editing/`. Before 1.0.0 the root carried both, and every route through the root paid for the editing instructions it did not need. An earlier fix moved the editing half to `references/editing.md`; that treated a job with steps and a result as knowledge, and the root still had to point to it. `editing/` is a sub-skill by rule 3.

## 16. The first real tree

On 2026-09-21 a tree of three working skills (review, writing, publish) was built for the work of preparing holon itself. Two things were learned that the example trees had not shown.

Seven sentences the owner had actually typed were routed. Six landed nowhere. The cover words were English; the owner writes Chinese. `synonyms.md` was the answer the rules already had, and it worked: after one synonym file built from those seven sentences, six of seven routed. But nothing in the rules says to build `synonyms.md` from the owner's real sentences first, before the first task. It should be step 0 of using a tree: collect ten sentences the owner has said, route them, and write the synonym file from the misses. The seventh sentence is in `_feedback.md`.

The routing table with five entries was already two kinds of thing: three skills the owner's tasks reach, two that only the tree's maintainer reaches. `groups.md` sectioned it. This is the case §11 describes, met in practice at five entries rather than at the nine the FANOUT hint waits for. The hint's number is not wrong; the split into "work" and "maintenance" is visible before any number is reached, and the rules could say so.

## 17. Measuring the context cost

The tree exists to make an agent read less per task. Until 2026-09-21 that had not been measured; the numbers below are the first, taken on the §14 library with the upstream bodies copied back in. The table is as of the end of the day, after the passes in §19: 31 skills, 123,569 bytes of `SKILL.md`; before those passes the library was 183,995 bytes and the `mcp-builder` and `slack-gif-creator` rows read 0.91 and 0.90.

**Method.** Tree cost is what `route` now prints on its last line: the bytes of every `SKILL.md` on the path from the root to where the sentence lands. Flat cost is what a host without a tree makes the agent read: the descriptions of all 20 upstream cards (6,356 bytes) plus the upstream card it picks. Both counts leave out `references/` and `shared/` files, which either arrangement opens only when a step needs them. Ten sentences, chosen to land in different parts of the tree:

| Sentence | Lands on | Tree | Flat | Tree/flat |
|---|---|---|---|---|
| fill in this PDF form | office-docs/pdf/form-fill | 11,057 | 14,428 | 0.77 |
| convert the Word report to a PDF | office-docs | 6,397 | 21,339 | 0.30 |
| write the quarterly report in Word | office-docs/docx | 12,770 | 13,267 | 0.96 |
| stream a response from the Claude API in Python | claude-api | 9,535 | 92,554 | 0.10 |
| migrate this to the newest model | claude-api/maintain | 11,829 | 92,554 | 0.13 |
| run a managed agent every night | managed-agents | 7,565 | 92,554 | 0.08 |
| build an MCP server for our ticket system | mcp-builder | 7,686 | 15,448 | 0.50 |
| make a GIF for Slack | slack-gif-creator | 6,867 | 14,197 | 0.48 |
| how do I get started with Claude | academy-guide | 12,052 | 14,111 | 0.85 |
| draw a poster for the launch | canvas-design | 16,939 | 18,295 | 0.93 |

**What the numbers say.** Where a card has had its second pass, the tree reads a tenth to two thirds of what the flat host reads. Where it has not (`docx`, `academy-guide`, `canvas-design` in the table), the tree reads about nine tenths: the root table (4,513 bytes of the root's 4,936) costs less than the flat host's 6,356 bytes of descriptions, and the rest of the cost is the card itself, which is the same file in both arrangements. So most of the saving comes from rule 2, and a flat card could apply rule 2 as well. What only the tree gives is in the rows that land on a parent or a sub-skill: "convert the Word report to a PDF" reads 6,397 bytes because the parent takes the sentence that spans two children, where a flat host would have the agent open both cards; "fill in this PDF form" reads a four-line sub-skill and not the rest of `pdf`.

Before the `claude-api` pass, rebuilt for comparison: "stream a response" read 90,082 bytes in the tree against 92,554 flat, ratio 0.97, because the 85,420-byte card sat on the path. The other two Claude sentences landed nowhere; "migrate" and "managed agent" were words inside that card, not cover words of any skill, so the tree read the root and stopped. The pass did two things at once: it cut the bytes on one path by nine tenths and gave two kinds of sentence a place to land. One card that has not had its pass sets the cost for every sentence that touches it, and hides the jobs inside it from the routing table.

**The third body type.** `pdf` was a directory of scripts, `skill-creator` a long loop. `claude-api` was a hub: 377 lines that already pointed at 68 files and carried a summary of each. Rules 2 and 3 applied without amendment. The summaries fail the removal test (each restates a file the step already names) and went to one `references/quick-reference.md`, 63,858 bytes, opened by the step that needs a parameter. Four subcommands on existing code (migrate, prompt audit, SDK upgrade, cost) each have a guide, a scope step and a result, so they are a sub-skill, `maintain/`. The Managed Agents section describes a hosted agent that is used without the SDK path. It was first made a child of `claude-api`, and under the routing rule of the time its sentences ("run this agent every night") could not get through the parent; it became top-level, `managed-agents/`, reading the parent's `shared/` files. §18 changed that rule, so the routing reason is gone; the placement stands on rule 3 alone: a hosted agent is a different result from SDK code, not a step of writing it. What remained is 27 lines, six steps. The pass took about the effort of the `pdf` pass.

**What changed in the tool.** `route` prints the path's byte count and the library's total on its last line, so the measurement is made on every route rather than by hand. `lint` gained nothing; the 150-line hint had named all three cards before their passes.

## 18. Twenty sentences nobody in this project wrote

Every sentence replayed so far was written by the person who placed the skills, and it landed because they wrote it to land. §16 found the first outside sentences, seven of them, in the owner's own words. The example library had none: its 84 sentences are all the author's. On 2026-09-21 twenty were found in the upstream cards themselves: phrases the skill authors quote as what their users say ("how do I", "teach me", "make me a GIF of X doing Y for Slack", "Keep 1,4,7,9"), the sample request in the upstream README, and the document names `docx` lists (memo, letter, report). During development they were kept, with where each lands, in a file the test suite routed; that file left the repository with the example library.

Six of twenty landed. The fourteen misses had four causes, and the count of each decided what to do.

**Five were words the tree already had, one level down.** "build a pitch deck" contains `deck`, which `pptx` covers, and stopped at the root because `office-docs` does not list `deck`. "a landing page in React with Tailwind" likewise: `web` does not list `React`. The rule at the time said a child's sentences must contain the parent's cover words; the parent had five words for four children and no room. This was the rule contradicting rule 3. A sub-skill is a step of its parent's job, so a sentence that names the step names the job; the parent should answer to it without being told. Routing now does that: a skill takes a sentence by its own cover words or by any cover word below it, and only its own `excludes` blocks it. The parent's own words are for the sentences that span children. `route` says when the word that took a sentence was a child's. The first draft of the fix was a `lint` warning listing every child word the parent lacked; it found 29 in this library, which is the number of words that would have had to be copied upward, and was deleted in favour of changing routing.

The change had one cost, which `replay` found: "apply the ocean theme to these slides" became ambiguous between `theme-factory` and `office-docs`, because `slides` was now `office-docs`'s through `pptx`. A parent that answers to more words needs redirects its children did not; `office-docs` excludes `theme, brand`.

**Six were the author's word for the owner's word.** `how do I` for "how can I", "what can Claude do", "teach me"; `eval` for "evaluations"; `Word` for "memo", "letter"; `spreadsheet` for "csv". Six `synonyms.md` lines. This is §16 again, on a library whose author and owner are the same person: the words still differ, because the author wrote cover words looking at the skill and the users spoke looking at their task.

**One was a generic cover word.** "Use the PDF skill to extract the form fields" was taken by `skill-creator` through `skill`. The rule already forbade generic verbs; in a skill library `skill` is a generic noun. `new skill, make a skill`.

**Five remain**, in `_feedback.md` with a reason each. Two have no object ("Create a chart", "Format this data"); two are replies inside a conversation the skill is already running ("Keep 1,4,7,9"), which routing does not see; one is "how can I" doing double duty for a question about Claude and a request for work, and the fix would cost `academy-guide` its own sentences. Fifteen of twenty, from six.

What this changes in practice: `replay` on the author's sentences is a check that the tree agrees with itself. Whether it agrees with anyone else is a separate number, and a library should carry a file of sentences it did not write and the count of them that land.

## 19. The remaining six, in one sitting

After §17 six cards were still over MAX_BODY: `algorithmic-art` 297 lines, `doc-coauthoring` 232, `slack-gif-creator` 187, `pptx` 176, `discernment-nudge` 162, `mcp-builder` 160. §14 had put the cost of a pass at about the cost of placing nineteen cards, and stopped. §17 showed what a pass buys: a card at 0.9 of flat cost goes to 0.1-0.6. That made the six worth doing, and they were done on 2026-09-21, each by the same two questions.

What came out, card by card:

- `algorithmic-art`: the five example philosophies and the seeding/parameter code went to two `references/` files; 23 lines of steps remain. The `templates/` were already separate and are now named by the step that reads them.
- `doc-coauthoring`: stage 3, reader testing, has its own trigger words ("reader test", "blind spots"), its own output (a list of what a fresh reader got wrong) and is invoked on a finished document, so it is a sub-skill, `reader-test/`. Host mechanics (connectors, artifacts vs files) and guidance on tone went to `references/`. 7 steps remain.
- `slack-gif-creator`: drawing advice, the utility catalogue and the eight animation concepts went to three `references/` files; 5 steps remain, each naming the `core/` module it uses.
- `pptx`: four `references/` files (pptxgenjs gotchas, template editing, design, QA). The five faults that corrupt the file stayed in the body, because a step that says "see the gotchas" will be skipped and the file will be corrupt. 5 steps.
- `discernment-nudge`: the reasoning behind each "when" and "when not" case went to `references/when.md`; the cases themselves stayed as two lists. 4 steps.
- `mcp-builder`: phase 4, evaluations, has its own guide, script and output (an XML of ten questions) and is done after the server exists, so it is a sub-skill, `evals/`. 6 steps remain.

Two things the tools caught during the passes. The `evals/` body named `reference/evaluation.md` and `scripts/evaluation.py` as if it were the parent; the file-pointer check that `lint` gained the same day (a body that names a file with a path must have the file) warned before `replay` ran. And `evals/` first covered `eval set`, which `skill-creator` also covers through `eval`; `replay` reported the collision on the first run. `question set`.

The library is 123,569 bytes of `SKILL.md`, from 183,995 (the figure first recorded was 120,980; the `metadata:` wrapper of §20 and a body for `form-fill`, which had been a stub, account for the rest); `lint` reports 0 over 150, median 14 lines. The time for the six was about the time for two of the earlier passes: the same two questions asked six more times, with the answers coming faster.

What this says about §14's stopping decision: the cost estimate was right, the value estimate was missing. A body-length hint on a card the routing table will send many sentences to is worth acting on; one on a leaf that takes one sentence in fifty is not. `route`'s last line now gives the number that decides.

## 20. The spec's validator rejected every file

On 2026-09-21 the Agent Skills specification (agentskills.io/specification) and its reference validator, `skills-ref`, were read for the first time. The spec allows six frontmatter fields: `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools`. `metadata` is a map from string to string. Anything else is an error. holon wrote two fields of its own at the top level, `triggers:` and `archive_count:`, and the validator rejected all 38 `SKILL.md` files in this repository, the two tools' own included.

That is a failure of the requirement the whole project is for: a tree a host can load. A host that checks the spec before loading a skill would have loaded none of these.

The fix keeps the two things and moves them. `triggers:` becomes `metadata.holon-triggers`, a block scalar with one sentence per line; `archive_count:` becomes `metadata.holon-archive-count`, a string. The keys carry the `holon-` prefix the spec recommends for a tool's own metadata. The parser reads both forms and lifts the metadata keys to the names the rest of the two tools already use, so nothing above the parser changed. `validate` reports the old form; `holon.py migrate` rewrites it, once, byte for byte except for the two fields. `init` writes the new form, with three `TODO` sentences that `validate` and `lint` refuse until they are written; before, `init` wrote no sentences and `lint` reported "needs 3 entries", which told the writer less. `counter --bump` writes the new location.

Two more things the validator required and holon had not checked: `name` must be lowercase letters, digits and hyphens with no leading, trailing or doubled hyphen, and must equal the directory name. `validate` now checks both. The example library's root is named `holon` in a directory called `anthropics-skills`, because it is a root that installs as `holon/`; CI copied it under that name before validating.

CI now installs `skills-ref` and validates every skill folder in the repository. The check that matters is not this project's own; it is the one a host would run.

What this says about the earlier sessions: nine sessions of tests, replay counts and byte measurements, and no one had run the one external check that decides whether the output is usable at all. The rule taken from this: when a format has a published validator, run it before anything else.
