#!/usr/bin/env python3
# Copyright (c) 2026 Wneil2020 and the holon skill contributors. Released under the MIT License.
"""Tests for organizer_cli (unittest, zero dependencies). Run directly or collect with pytest:
    python3 organizer/tests/test_organizer_cli.py

Four groups:
  unit         parsing / three-part descriptions / synonym folding / lexical matching / routing
  rules        one test per item organizer/SKILL.md says lint checks; hints must not count as warnings
  integration  real files produced by the mechanism layer's `init --desc`, then validate / lint / replay;
               retire and restore
  dogfood      this package itself must pass validate / lint / replay; the parameter table and the CLI
               constants must agree name by name and value by value
"""
import re
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORG_DIR = HERE.parent                 # organizer/
PKG_ROOT = ORG_DIR.parent             # library root (contains scripts/holon.py)
CLI = ORG_DIR / "scripts" / "organizer_cli.py"
NS_CLI = PKG_ROOT / "scripts" / "holon.py"

sys.path.insert(0, str(ORG_DIR / "scripts"))
import organizer_cli as oc  # noqa: E402
ns = oc.ns

BODY_FILL = "\n".join(f"Body line {i}." for i in range(14))


def write(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def run(*argv, cwd=None):
    """Run one CLI command; return (returncode, stdout+stderr)."""
    r = subprocess.run([sys.executable, *map(str, argv)], capture_output=True, text=True, cwd=cwd)
    return r.returncode, r.stdout + r.stderr


def skill(name, desc, triggers, extra="", body=None):
    """A SKILL.md in the Agent Skills spec form: holon's sentences live under metadata."""
    trig = "\n".join(f"    {t}" for t in triggers)
    body = BODY_FILL if body is None else body
    return (f"---\nname: {name}\nmetadata:\n  holon-triggers: |\n{trig}\n"
            f"description: {json.dumps(desc, ensure_ascii=False)}\n{extra}---\n# {name}\nBody.\n{body}\n")


ROOT_BODY = "# root\n\nWhen routing misses or goes wrong, append a line to `_feedback.md` and carry on.\n"

# Sample tree: root -> web(dark-mode, chart) / lib-org
# web "builds front-end interfaces"; dark-mode and chart are two of its steps; lib-org is another top-level skill.
WEB_DESC = "Use when building a front-end interface: covers front-end, page, dark mode, chart; excludes library organization"
DARK_DESC = "Use when doing dark mode: covers dark mode, dark theme; excludes light palette"
DARK_TRIG = ["adapt the whole site to dark mode", "how to layer cards in a dark theme",
             "choose a chart for the report page should go to web/chart"]
CHART_DESC = "Use when building charts or dashboards: covers chart, dashboard; excludes page layout"
CHART_TRIG = ["build a data dashboard", "choose a chart for the report page",
              "adapt the whole site to dark mode should go to web/dark-mode"]
ORG_DESC = "Use when absorbing skills into the library: covers library organization, absorb, duplicate; excludes page"
ORG_TRIG = ["absorb this new skill into the library", "is this skill a duplicate",
            "build a data dashboard should go to web/chart"]


def make_tree(root):
    write(root / "SKILL.md", "---\nname: brain\nmetadata:\n  holon-archive-count: \"12\"\n"
          'description: "Use when archiving or retrieving: covers library routing"\n---\n' + ROOT_BODY)
    write(root / "synonyms.md", "dark mode,night mode,dark theme\nchart,data visualization,dashboard\npage,front-end,landing page\n")
    write(root / "_feedback.md", "# _feedback.md\n")
    write(root / "ABSORB.md", "# ABSORB.md\n\n## @12 the web family\nlearned: web, web/dark-mode, web/chart\n")
    write(root / "web" / "SKILL.md", skill("web", WEB_DESC,
          ["write a landing page", "review the visual design of the page",
           "absorb this new skill into the library should go to lib-org"]))
    write(root / "web" / "dark-mode" / "SKILL.md", skill("dark-mode", DARK_DESC, DARK_TRIG))
    write(root / "web" / "chart" / "SKILL.md", skill("chart", CHART_DESC, CHART_TRIG))
    write(root / "lib-org" / "SKILL.md", skill("lib-org", ORG_DESC, ORG_TRIG))


class TempTree(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "demo"
        make_tree(self.root)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def skills(self):
        return oc.find_skills(self.root)[0]

    def write_dark(self, desc=DARK_DESC, triggers=DARK_TRIG, extra="", body=None):
        write(self.root / "web" / "dark-mode" / "SKILL.md", skill("dark-mode", desc, triggers, extra, body))

    def lint(self):
        return run(CLI, "lint", self.root)


# ---------------------------------------------------------------- unit

class TestParsing(TempTree):
    def test_frontmatter_via_core_parser(self):
        meta, body, err = oc.parse_frontmatter((self.root / "web/dark-mode/SKILL.md").read_text(encoding="utf-8"))
        self.assertIsNone(err)
        self.assertEqual(meta["name"], "dark-mode")
        self.assertEqual(len(meta["triggers"]), 3)
        self.assertIn("Body.", body)

    def test_parse_unquotes_like_core(self):
        meta, _, _ = oc.parse_frontmatter('---\nname: a\ndescription: "Use when x: covers nginx; excludes dns"\n---\n')
        self.assertEqual(oc.parse_desc(meta["description"]), ({"nginx"}, {"dns"}))

    def test_parse_desc(self):
        self.assertEqual(oc.parse_desc(DARK_DESC), ({"dark mode", "dark theme"}, {"light palette"}))

    def test_parse_desc_is_case_insensitive_on_keywords(self):
        self.assertEqual(oc.parse_desc("Use when x: Covers a, b; Excludes c"), ({"a", "b"}, {"c"}))

    def test_prose_covers_and_excludes_are_not_routing_clauses(self):
        cases = [
            ("Use when a document covers several topics: covers summary, outline, digest",
             {"summary", "outline", "digest"}, set()),
            ("Use when the policy excludes contractors from payroll: covers payroll; excludes invoice",
             {"payroll"}, {"invoice"}),
            ("Use when comparing book covers", set(), set()),
            ("当文档涉及多项时：covers 摘要、提纲；excludes 发票", {"摘要", "提纲"}, {"发票"}),
        ]
        for desc, covers, excludes in cases:
            with self.subTest(desc=desc):
                self.assertEqual(oc.parse_desc(desc), (covers, excludes))
                self.assertEqual(set(ns.description_covers(desc)), covers)
                self.assertEqual(set(oc.covers_text({"description": desc}).split(",")) - {""}, covers)

    def test_duplicate_routing_clauses_are_reported_by_lint(self):
        self.write_dark(desc="Use for dark work: covers dark mode; covers chart")
        rc, out = self.lint()
        self.assertEqual(rc, 1, out)
        self.assertIn("duplicate covers clause", out)

    def test_synonyms_first_word_is_canonical(self):
        syn = oc.load_synonyms(self.root)
        self.assertEqual(oc.normalize("night mode", syn), "dark mode")
        self.assertIn("dark mode", oc.canonicalize("switch the site to night mode", syn))

    def test_canonicalize_does_not_rewrite_inside_canonical_form(self):
        """Synonym word -> word document: a sentence already containing the canonical form must not
        have the `word` inside it replaced again into `word document document`."""
        syn = {"wdoc": "word document", "word": "word document"}
        self.assertEqual(oc.canonicalize("write a word document", syn), "write a word document")
        self.assertEqual(oc.canonicalize("write a word summary", syn), "write a word document summary")
        self.assertEqual(oc.canonicalize("export wdoc", syn), "export word document")

    def test_canonicalize_chain_of_aliases_is_single_pass(self):
        """A -> B where B is an alias on another line is still replaced once; a canonical form in the sentence stays."""
        syn = {"acme sdk": "acme api", "vendor sdk": "acme api", "sdk-upgrade": "sdk-upgrade"}
        self.assertEqual(oc.canonicalize("vendor sdk-upgrade", syn), "acme api-upgrade")
        self.assertEqual(oc.canonicalize("acme api pricing", syn), "acme api pricing")

    def test_split_anti_only_accepts_trailing_keyword(self):
        self.assertEqual(oc.split_anti("choose a chart for the report page should go to web/chart"),
                         ("choose a chart for the report page", "web/chart"))
        self.assertEqual(oc.split_anti("x should go to a/b#section"), ("x", "a/b"))
        self.assertIsNone(oc.split_anti("migrate the config from v1 -> v2"))
        self.assertIsNone(oc.split_anti("upgrade A → B"))
        self.assertIsNone(oc.split_anti("should go to anywhere is fine"))

    def test_ascii_words_use_word_boundary(self):
        self.assertEqual(oc.canonicalize("fix the mongodb connection", {"db": "database"}), "fix the mongodb connection")
        self.assertEqual(oc.canonicalize("fix the db connection", {"db": "database"}), "fix the database connection")
        self.assertFalse(oc.contains("fix the mongodb connection", "db"))
        self.assertTrue(oc.contains("debug the deadlock flow", "deadlock"))

    def test_non_ascii_words_match_as_substrings(self):
        self.assertTrue(oc.contains("修复死锁流程", "死锁"))
        self.assertEqual(oc.parse_desc("当排查时使用: covers 死锁, 超时; excludes 网络"), ({"死锁", "超时"}, {"网络"}))


class TestRouting(TempTree):
    def test_route_after_synonym(self):
        path = oc.route("switch the site to night mode", self.root, self.skills(), oc.load_synonyms(self.root))
        self.assertEqual(path[-1], self.root / "web/dark-mode")

    def test_route_exclusion_blocks(self):
        path = oc.route("absorb this new skill into the library", self.root, self.skills(), oc.load_synonyms(self.root))
        self.assertEqual(path[-1], self.root / "lib-org")

    def test_route_stops_at_parent_when_no_child_matches(self):
        path = oc.route("write a landing page", self.root, self.skills(), oc.load_synonyms(self.root))
        self.assertEqual(path[-1], self.root / "web")

    def test_two_hits_at_root_is_ambiguity(self):
        """The root is an index, not a skill: two top-level skills taking one sentence -> ambiguity, suspected duplicate."""
        write(self.root / "lib-org" / "SKILL.md",
              skill("lib-org", "Use when absorbing skills: covers library organization, absorb, page; excludes domain knowledge", ORG_TRIG))
        path = oc.route("write a landing page", self.root, self.skills(), oc.load_synonyms(self.root))
        self.assertIsInstance(path[-1], tuple)
        self.assertEqual(sorted(path[-1][1]), [self.root / "lib-org", self.root / "web"])
        self.assertTrue(oc.still_reachable(self.root / "web", path))

    def test_two_hits_under_a_parent_stop_at_parent(self):
        """Two children of one parent taking one sentence -> the sentence spans two steps, i.e. the parent's own job:
        stop at the parent, not an ambiguity."""
        path = oc.route("add dark mode to the chart page", self.root, self.skills(), oc.load_synonyms(self.root))
        self.assertEqual(path[-1], self.root / "web")
        self.assertFalse(oc.still_reachable(self.root / "web/dark-mode", path))

    def test_retired_dir_is_not_a_skill(self):
        """Both CLIs share one definition of "what is a skill": .retired/ is not."""
        write(self.root / ".retired" / "old" / "SKILL.md", "---\nname: old\ndescription: covers chart\n---\n")
        self.assertEqual(len(self.skills()), 5)
        run(NS_CLI, "sync", self.root)   # complete the parent routing tables first
        rc, out = run(NS_CLI, "validate", self.root)
        self.assertEqual(rc, 0, out)
        self.assertIn("5 skill(s)", out)


# ---------------------------------------------------------------- rules: every skill carries three things

class TestLintThreeThings(TempTree):
    def test_compliant_tree_is_clean(self):
        rc, out = self.lint()
        self.assertEqual(rc, 0, out)
        # dark-mode's `excludes light palette` is a refusal (no skill covers it): one hint, by design.
        self.assertIn("lint: 0 errors, 0 warnings, 1 hints, 5 skills", out)

    def test_description_three_parts(self):
        self.write_dark(desc="how to do dark mode")
        rc, out = self.lint()
        self.assertEqual(rc, 1)
        self.assertIn("[E] web/dark-mode: description has no 'covers' word list", out)

    def test_cover_word_count_capped(self):
        n = oc.COVER_MAX + 1
        self.write_dark(desc="Use when doing dark mode: covers " + ",".join(f"a{i}" for i in range(n)) + "; excludes light")
        rc, out = self.lint()
        self.assertIn(f"{n} cover words > {oc.COVER_MAX}", out)

    def test_description_length_capped(self):
        self.write_dark(desc="Use when doing dark mode: covers dark mode; excludes " + "long " * (oc.DESC_MAX // 5 + 1))
        rc, out = self.lint()
        self.assertIn(f"characters > {oc.DESC_MAX}", out)

    def test_tiny_cover_word_warned(self):
        if oc.COVER_MIN < 2:
            self.skipTest("COVER_MIN is 1: no cover word is too short")
        short = "x" * (oc.COVER_MIN - 1)
        self.write_dark(desc=f"Use when doing dark mode: covers dark mode, {short}; excludes light palette")
        rc, out = self.lint()
        self.assertIn(f"word '{short}' is only {len(short)} character(s) long", out)

    def test_triggers_two_positive_one_anti(self):
        self.write_dark(triggers=["adapt the whole site to dark mode", "choose a chart for the report page should go to web/chart"])
        rc, out = self.lint()
        self.assertEqual(rc, 1)
        self.assertIn("triggers needs 2 sentences it should take + 1 it should not", out)
        self.write_dark(triggers=["a", "b", "c"])
        rc, out = self.lint()
        self.assertIn("triggers has no negative example", out)

    def test_anti_target_must_exist(self):
        self.write_dark(triggers=["adapt the whole site to dark mode", "cards in a dark theme", "x should go to nowhere"])
        rc, out = self.lint()
        self.assertEqual(rc, 1)
        self.assertIn("negative-example target 'nowhere' is not a skill in this library", out)

    def test_intermediate_skill_also_needs_triggers(self):
        """An intermediate skill is a skill too and carries the same three sentences."""
        write(self.root / "web" / "SKILL.md", f"---\nname: web\ndescription: {json.dumps(WEB_DESC)}\n---\n# web\n{BODY_FILL}\n")
        rc, out = self.lint()
        self.assertEqual(rc, 1)
        self.assertIn("[E] web: triggers", out)

    def test_root_exempt_from_three_parts_and_triggers(self):
        rc, out = self.lint()
        self.assertNotIn("[E] .:", out)

    def test_no_legacy_fields(self):
        """Fields from an earlier design (ledger / last-verified / axis) are flagged for removal."""
        self.write_dark(extra='ledger: |\n  [DEFERRED] @3 x\nlast-verified: "3"\naxis: activity\n')
        rc, out = self.lint()
        self.assertEqual(rc, 0, out)
        self.assertIn("[W] web/dark-mode: legacy field(s) axis, last-verified, ledger", out)


# ---------------------------------------------------------------- rules: root files

class TestLintRootFiles(TempTree):
    def test_missing_feedback_file(self):
        (self.root / "_feedback.md").unlink()
        rc, out = self.lint()
        self.assertIn("[W] .: library root has no _feedback.md", out)

    def test_root_must_mention_feedback(self):
        write(self.root / "SKILL.md", '---\nname: brain\narchive_count: 12\ndescription: "Use when archiving: covers library routing"\n---\n# root\n')
        rc, out = self.lint()
        self.assertIn("[W] .: root SKILL.md does not tell the AI to report routing misses to _feedback.md", out)

    def test_lint_warns_when_alias_swallows_a_cover_word(self):
        """Alias 'vendor sdk' folds to 'acme api' while a skill's cover word is 'sdk-upgrade':
        the sentence 'vendor sdk-upgrade' is eaten by the longer alias first and the cover word can never match."""
        write(self.root / "synonyms.md", "dark mode,night mode\nacme api,vendor sdk\n")
        self.write_dark(desc="Use when upgrading the SDK: covers sdk-upgrade, major version; excludes light palette")
        rc, out = self.lint()
        self.assertIn("[W] synonyms.md: alias 'vendor sdk' (folds to acme api) overlaps web/dark-mode's cover word 'sdk-upgrade' "
                      "in a sentence: \"vendor sdk-upgrade\" folds to \"acme api-upgrade\" and cover word 'sdk-upgrade' is gone", out)

    def test_lint_silent_when_aliases_do_not_collide(self):
        write(self.root / "synonyms.md", "dark mode,night mode\nacme api,vendor sdk\n")
        rc, out = self.lint()
        self.assertNotIn("overlaps", out)

    def test_absorb_entries_format(self):
        write(self.root / "ABSORB.md", "# ABSORB.md\n\n## @12 the web family\nlearned: web\n\n## heading without count\nlearned: x\n\n## @13 fine\nsome free text\n")
        rc, out = self.lint()
        self.assertIn("[W] ABSORB.md: section heading should be '## @<count> <source name>', got: ## heading without count", out)
        self.assertIn("[W] ABSORB.md: '## @13 fine' should contain at least one learned:/merged:/ruled: line", out)

    def test_absorb_count_not_ahead_of_counter(self):
        write(self.root / "ABSORB.md", "# ABSORB.md\n\n## @13 future\nlearned: x\n")
        rc, out = self.lint()
        self.assertIn("[W] ABSORB.md: @13 is ahead of the root archive_count 12", out)

    def test_retired_entries_need_header(self):
        write(self.root / ".retired" / "web" / "old" / "SKILL.md", "---\nname: old\n---\nno retired header\n")
        write(self.root / ".retired" / "web" / "old2" / "SKILL.md", "retired @12 merged into web/dark-mode\n---\nname: old2\n---\n")
        rc, out = self.lint()
        self.assertIn("[W] .retired/web/old: first line should be 'retired @<count> <reason>'", out)
        self.assertNotIn("old2", out)


# ---------------------------------------------------------------- rules: hints, not rules (never a warning)

class TestLintFileRefs(TempTree):
    """A body that names a file in backticks tells the agent to open it; lint checks the file is there."""

    def test_missing_relative_file_is_a_warning(self):
        self.write_dark(body="1. Read `references/palette.md` first.\n2. Apply it.\n3. Check contrast.\n4. Done.\n5. Report.")
        rc, out = self.lint()
        self.assertEqual(rc, 0, out)   # a warning, not an error
        self.assertIn("[W] web/dark-mode: body points at `references/palette.md` and there is no such file under web/dark-mode/ or at the tree root", out)

    def test_present_file_root_relative_file_and_bare_output_name_pass(self):
        (self.root / "web" / "dark-mode" / "references").mkdir(parents=True)
        write(self.root / "web" / "dark-mode" / "references" / "palette.md", "# palette\n")
        write(self.root / "tools.md", "# tools\n")
        self.write_dark(body="1. Read `references/palette.md`.\n2. Run `tools.md` at the tree root.\n3. Write `out.json`.\n4. Match `*.css`.\n5. Done.")
        rc, out = self.lint()
        self.assertNotIn("points at", out)


class TestLintBodySummary(TempTree):
    def test_last_line_is_body_distribution(self):
        rc, out = self.lint()
        last = out.rstrip().splitlines()[-1]
        self.assertRegex(last, r"^bodies: \d+ skills, \d+ to \d+ non-blank lines, median \d+, \d+ over " + str(oc.MAX_BODY) + "$")
        self.write_dark(body="\n".join(f"line {i}" for i in range(oc.MAX_BODY + 5)))
        rc, out = self.lint()
        self.assertTrue(out.rstrip().splitlines()[-1].endswith(f"1 over {oc.MAX_BODY}"), out)


class TestLintHints(TempTree):
    def _hint_count(self, out):
        return len(re.findall(r"^\[·\]", out, re.M))

    def test_long_body_is_hint_not_warning(self):
        self.write_dark(body="\n".join(f"line {i}" for i in range(oc.MAX_BODY + 5)))
        rc, out = self.lint()
        self.assertEqual(rc, 0, out)
        self.assertIn(f"[·] web/dark-mode: body has {oc.MAX_BODY + 7} non-blank lines > {oc.MAX_BODY}", out)
        self.assertIn("is knowledge mixed in", out)
        self.assertIn("0 errors, 0 warnings, 2 hints", out)  # long body + the fixture's refusal hint

    def test_fanout_hint_points_to_ask_then_groups_file(self):
        for i in range(oc.FANOUT):
            write(self.root / "web" / f"s{i}" / "SKILL.md",
                  skill(f"s{i}", f"Use when doing s{i}: covers term{i}; excludes none", [f"term{i} alpha", f"term{i} beta", "build a data dashboard should go to web/chart"]))
        rc, out = self.lint()
        self.assertIn(f"[·] web: {oc.FANOUT + 2} sub-skills at one level > {oc.FANOUT}; run `organizer_cli.py ask <root>` "
                      "and answer the four questions first -- if several deliver the same kind of thing, create a "
                      f"parent and move them in; only if none do, write a {ns.GROUPS_FILE} to section the table", out)

    def test_fanout_silent_once_grouped(self):
        """Once the table is sectioned the hint disappears -- it is no longer one long list."""
        for i in range(oc.FANOUT):
            write(self.root / "web" / f"s{i}" / "SKILL.md",
                  skill(f"s{i}", f"Use when doing s{i}: covers term{i}; excludes none", [f"term{i} alpha", f"term{i} beta", "build a data dashboard should go to web/chart"]))
        write(self.root / "web" / ns.GROUPS_FILE, "Style: dark-mode, chart\nParts: " + ", ".join(f"s{i}" for i in range(oc.FANOUT)) + "\n")
        run(NS_CLI, "sync", self.root)
        rc, out = self.lint()
        self.assertEqual(rc, 0, out)
        self.assertNotIn("at one level", out)

    def test_group_with_one_member_is_warning(self):
        write(self.root / "web" / ns.GROUPS_FILE, "Style: dark-mode\n")
        run(NS_CLI, "sync", self.root)
        rc, out = self.lint()
        self.assertEqual(rc, 0, out)
        self.assertIn(f"[W] web: group 'Style' in {ns.GROUPS_FILE} has only 1 member; one card is not a section "
                      f"-- delete the line and it falls into the trailing '{ns.OTHER_SECTION}' section", out)

    def test_groups_file_errors_surface_in_lint(self):
        write(self.root / "web" / ns.GROUPS_FILE, "Style: dark-mode, nope\n")
        rc, out = self.lint()
        self.assertEqual(rc, 1, out)
        self.assertIn("[E] web: groups.md line 1: 'nope' in group 'Style' is not a sub-skill here", out)

    def test_child_in_two_groups_routes_once(self):
        """A card listed in two sections is still one routing candidate; no ambiguity."""
        write(self.root / "web" / ns.GROUPS_FILE, "Style: dark-mode, chart\nData: chart\n")
        run(NS_CLI, "sync", self.root)
        path = oc.route("choose a chart for the report page", self.root, *oc.find_skills(self.root)[:1], oc.load_synonyms(self.root))
        self.assertEqual(path[-1], self.root / "web" / "chart")

    def test_hollow_parent_is_hint(self):
        """A parent with one child whose body only points at the child -> hollow."""
        shutil.rmtree(self.root / "web" / "chart")
        write(self.root / "web" / "SKILL.md",
              skill("web", WEB_DESC, ["write a landing page", "review the page", "absorb a skill should go to lib-org"], body="see dark-mode."))
        write(self.root / "web" / "dark-mode" / "SKILL.md",
              skill("dark-mode", DARK_DESC, ["adapt the whole site to dark mode", "how to layer cards in a dark theme", "absorb a skill should go to lib-org"]))
        rc, out = self.lint()
        self.assertIn("[·] web: exactly one sub-skill and a 3-line body -- looks hollow", out)

    def test_parent_with_real_body_is_not_hollow(self):
        shutil.rmtree(self.root / "web" / "chart")
        write(self.root / "web" / "dark-mode" / "SKILL.md",
              skill("dark-mode", DARK_DESC, ["adapt the whole site to dark mode", "how to layer cards in a dark theme", "absorb a skill should go to lib-org"]))
        rc, out = self.lint()
        self.assertNotIn("hollow", out)

    def test_short_body_is_hint(self):
        self.write_dark(body="one line.")
        rc, out = self.lint()
        self.assertEqual(rc, 0, out)
        self.assertIn("[·] web/dark-mode: body has 3 non-blank lines, very short", out)

    def test_hints_not_counted_as_warnings(self):
        self.write_dark(body="one line.")
        rc, out = self.lint()
        self.assertIn("0 warnings, 2 hints", out)  # very-short body + the refusal hint the fixture always has


# ---------------------------------------------------------------- ask

class TestExcludesKinds(TempTree):
    def test_refusal_is_hint(self):
        rc, out = self.lint()  # fixture's dark-mode excludes 'light palette', which no skill covers
        self.assertEqual(rc, 0, out)
        self.assertIn("[·] web/dark-mode: excludes 'light palette' is a refusal", out)

    def test_redirect_is_silent(self):
        self.write_dark(desc="Use when doing dark mode: covers dark mode, dark theme; excludes chart")
        rc, out = self.lint()
        self.assertNotIn("excludes 'chart'", out)

    def test_redirect_through_synonym_is_silent(self):
        # dashboard is an alias of chart in synonyms.md; web/chart covers chart.
        self.write_dark(desc="Use when doing dark mode: covers dark mode, dark theme; excludes dashboard")
        rc, out = self.lint()
        self.assertNotIn("excludes 'dashboard'", out)


class TestAbsorbNumbers(TempTree):
    def test_duplicate_section_number_is_warning(self):
        write(self.root / "ABSORB.md", "# ABSORB.md\n\n## @12 first\nlearned: web\n\n## @12 second\nlearned: lib-org\n")
        rc, out = self.lint()
        self.assertIn("[W] ABSORB.md: @12 is used twice", out)
        self.assertIn("counter --bump", out)


class TestAsk(TempTree):
    """`ask` prints the checklist from the rulebook and the library's rulings. The checklist is not copied into
    code; it is read from SKILL.md, so the rulebook is the single source."""

    def section_lines(self):
        text = (ORG_DIR / "SKILL.md").read_text(encoding="utf-8")
        start = text.index(oc.CHECKLIST_HEAD)
        end = text.find("\n## ", start + 1)
        return [l for l in text[start:end].splitlines() if l.strip()]

    def test_ask_prints_checklist_verbatim_from_rules_doc(self):
        rc, out = run(CLI, "ask", self.root)
        self.assertEqual(rc, 0, out)
        lines = self.section_lines()
        self.assertGreaterEqual(len(lines), 6)
        for l in lines:
            self.assertIn(l, out, f"rulebook line not printed: {l}")

    def test_ask_lists_ruling_lines_with_their_section(self):
        write(self.root / "ABSORB.md", "# ABSORB.md\n\n## @12 the web family\nlearned: web, web/dark-mode, web/chart\n"
              "ruled: chart and dark mode both deliver a page -> under web\n\n## @12 addendum\nruled: library organization belongs to no domain, stays top-level\n")
        rc, out = run(CLI, "ask", self.root)
        self.assertEqual(rc, 0, out)
        self.assertIn("This library has 2 ruling(s)", out)
        self.assertIn("@12 the web family", out)
        self.assertIn("ruled: chart and dark mode both deliver a page -> under web", out)
        self.assertIn("@12 addendum", out)
        self.assertIn("ruled: library organization belongs to no domain, stays top-level", out)
        self.assertNotIn("learned: web", out, "learned: lines are not rulings and must not be printed")

    def test_ask_without_rulings_says_so(self):
        rc, out = run(CLI, "ask", self.root)
        self.assertEqual(rc, 0, out)
        self.assertIn("no ruled: lines yet", out)

    def test_ask_prints_checklist_before_rulings(self):
        write(self.root / "ABSORB.md", "# ABSORB.md\n\n## @12 x\nruled: alpha\n")
        rc, out = run(CLI, "ask", self.root)
        self.assertLess(out.index(oc.CHECKLIST_HEAD), out.index("ruled: alpha"))


# ---------------------------------------------------------------- overlap / replay

class TestOverlapReplay(TempTree):
    def test_overlap_reports_intersection(self):
        write(self.root / "web" / "chart" / "SKILL.md",
              skill("chart", "Use when building charts: covers chart, dashboard, dark mode", CHART_TRIG))
        rc, out = run(CLI, "overlap", self.root, "--threshold", "0.1")
        self.assertIn("[OVERLAP", out)
        self.assertIn("dark mode", out)
        self.assertIn("cross-replay", out)

    def test_overlap_default_threshold_is_rule_parameter(self):
        rc, out = run(CLI, "overlap", self.root)
        self.assertIn(f"threshold {oc.OVERLAP}", out)

    def test_replay_all_pass(self):
        rc, out = run(CLI, "replay", self.root)
        self.assertEqual(rc, 0, out)
        self.assertIn("12/12 passed", out)

    def test_intermediate_anti_pointing_to_own_child_passes(self):
        """An intermediate skill's negative pointing at its own child: the route necessarily passes through the parent.
        Passing through is not a hit; stopping there is."""
        write(self.root / "web" / "SKILL.md",
              skill("web", WEB_DESC, ["write a landing page", "review the visual design of the page",
                                      "choose a chart for the report page should go to web/chart"]))
        rc, out = run(CLI, "replay", self.root)
        self.assertEqual(rc, 0, out)
        self.assertIn("12/12 passed", out)

    def test_intermediate_anti_stopping_at_itself_fails(self):
        """The same negative, but no child takes it and the route stops at the parent -> a real hit."""
        write(self.root / "web" / "SKILL.md",
              skill("web", WEB_DESC, ["write a landing page", "review the visual design of the page",
                                      "write a landing page should go to web/chart"]))
        rc, out = run(CLI, "replay", self.root)
        self.assertEqual(rc, 1)
        self.assertIn("[FAIL negative hit] web: \"write a landing page\" -- this skill is the route's end point", out)

    def test_replay_covers_intermediate_skills(self):
        """web is an intermediate skill; its examples are replayed too and its positives must stop at web itself.
        Taken by its own child -> the sentence was the child's job; the message says how a parent positive must be written."""
        write(self.root / "web" / "SKILL.md",
              skill("web", WEB_DESC, ["write a landing page", "build a data dashboard", "absorb a skill should go to lib-org"]))
        rc, out = run(CLI, "replay", self.root)
        self.assertEqual(rc, 1)
        self.assertIn("[FAIL not reached] web: \"build a data dashboard\" lands on web/chart (only child web/chart took this sentence, "
                      "so routing descended into it -> a parent's positive example must contain cover words of two or more children; "
                      "this one only has web/chart's -- if the child is new, this sentence is now its job: "
                      "move it to the child's triggers and give the parent one that spans two children)", out)

    def test_replay_parent_positive_blocked_by_sibling_exclusion(self):
        """A parent positive that should span two children, but one child's `excludes` blocks it, so only the other child
        hits and routing descends. The message must name the sibling and the blocking word."""
        self.write_dark(desc="Use when doing dark mode: covers dark mode, dark theme; excludes chart")
        write(self.root / "web" / "SKILL.md",
              skill("web", WEB_DESC, ["write a landing page", "chart colours in dark mode", "absorb a skill should go to lib-org"]))
        rc, out = run(CLI, "replay", self.root)
        self.assertEqual(rc, 1)
        self.assertIn("[FAIL not reached] web: \"chart colours in dark mode\" lands on web/chart"
                      " (sibling web/dark-mode's cover words also take this sentence, but its own 'excludes chart' blocks it"
                      " -> this sentence should span two children and stop at the parent; 'excludes' is for separating siblings "
                      "that compete for the same sentence, not for blocking sentences that span children)", out)

    def test_replay_parent_positive_truly_child_work_keeps_plain_message(self):
        """No sibling blocked by `excludes` -> the sentence really is the child's job; plain message."""
        write(self.root / "web" / "SKILL.md",
              skill("web", WEB_DESC, ["write a landing page", "build a data dashboard", "absorb a skill should go to lib-org"]))
        rc, out = run(CLI, "replay", self.root)
        self.assertIn("(only child web/chart took this sentence", out)
        self.assertNotIn("blocks it", out)

    def test_replay_landing_elsewhere_has_plain_message(self):
        """Landing somewhere else (neither own child nor ancestor) -> just the landing point."""
        self.write_dark(triggers=["absorb this new skill into the library", "how to layer cards in a dark theme",
                                  "choose a chart for the report page should go to web/chart"])
        rc, out = run(CLI, "replay", self.root)
        self.assertEqual(rc, 1)
        self.assertIn("[FAIL not reached] web/dark-mode: \"absorb this new skill into the library\" lands on lib-org\n", out + "\n")

    def test_replay_sibling_stealing_a_childs_sentence_is_failure(self):
        """A sibling also takes a child's own positive -> stops at the parent; the message names the sibling."""
        write(self.root / "web" / "chart" / "SKILL.md",
              skill("chart", "Use when building charts: covers chart, dashboard, dark mode", CHART_TRIG))
        rc, out = run(CLI, "replay", self.root)
        self.assertEqual(rc, 1)
        self.assertIn("[FAIL not reached] web/dark-mode: \"adapt the whole site to dark mode\" lands on web "
                      "(sibling web/chart also takes this sentence, via its cover word 'dark mode' -> either a real duplicate, "
                      "or add an 'excludes' to web/chart)", out)

    def test_replay_parent_sentence_spanning_two_children_passes(self):
        """A parent positive spanning two children stops at the parent -- exactly the parent's job."""
        write(self.root / "web" / "SKILL.md",
              skill("web", WEB_DESC, ["write a landing page", "add dark mode to the chart page", "absorb a skill should go to lib-org"]))
        rc, out = run(CLI, "replay", self.root)
        self.assertEqual(rc, 0, out)

    def test_replay_root_ambiguity_is_failure(self):
        write(self.root / "lib-org" / "SKILL.md",
              skill("lib-org", "Use when absorbing skills: covers library organization, absorb, page; excludes domain knowledge", ORG_TRIG))
        rc, out = run(CLI, "replay", self.root)
        self.assertEqual(rc, 1)
        self.assertIn("[FAIL ambiguous] web: \"write a landing page\" is taken by 2 top-level skills at once [lib-org, web]", out)

    def test_replay_anti_note_names_target_not_self(self):
        """The diagnosis of a negative that misses its target talks about the declared target, not the skill on the line."""
        self.write_dark(triggers=["adapt the whole site to dark mode", "cards in a dark theme",
                                  "add a night toggle to the page should go to web/chart"])
        rc, out = run(CLI, "replay", self.root)
        self.assertEqual(rc, 0, out)
        self.assertIn("[NOTE negative did not reach its target] web/dark-mode: \"add a night toggle to the page\" is declared to go to web/chart, "
                      "but lexical routing lands on web -- most likely synonyms.md or the target's cover words lack the wording used in this sentence"
                      " (target web/chart did not take it: the sentence contains none of its cover words chart,dashboard)", out)
        self.assertNotIn("this skill did not take it", out)

    def test_replay_anti_not_reaching_target_is_noted(self):
        self.write_dark(triggers=["adapt the whole site to dark mode", "cards in a dark theme",
                                  "a completely unrelated sentence should go to web/chart"])
        rc, out = run(CLI, "replay", self.root)
        self.assertEqual(rc, 0, out)
        self.assertIn("[NOTE negative did not reach its target]", out)
        self.assertIn("synonyms.md", out)
        self.assertIn("the sentence was stopped at ancestor web: it contains none of web's cover words front-end,page,dark mode,chart", out)
        self.assertIn(f"lands on {oc.ROOT_LABEL}", out)

    def test_replay_positive_stopped_at_ancestor_names_the_gate(self):
        """A child positive that does not even pass the parent lands on the root; the message names the parent and its cover words."""
        self.write_dark(triggers=["make the whole site black with white text", "how to layer cards in a dark theme",
                                  "choose a chart for the report page should go to web/chart"])
        rc, out = run(CLI, "replay", self.root)
        self.assertEqual(rc, 1)
        self.assertIn(f"[FAIL not reached] web/dark-mode: \"make the whole site black with white text\" lands on {oc.ROOT_LABEL}"
                      " (the sentence was stopped at ancestor web: it contains none of web's cover words front-end,page,dark mode,chart"
                      " and none of the cover words below it, so none of this skill's either -- write the sentence with one of "
                      "this skill's words, or fold its wording to one in synonyms.md)", out)

    def test_parent_answers_to_a_child_cover_word_it_does_not_list(self):
        """A sub-skill is a step of its parent, so the parent takes a sentence that names only the
        child's word. web lists neither 'toggle' nor 'switch'; web/dark-mode/toggle does."""
        write(self.root / "web" / "dark-mode" / "toggle" / "SKILL.md",
              skill("toggle", "Use when adding a dark mode switch: covers toggle, switch; excludes palette",
                    ["add a toggle for the theme", "put a switch in the header", "choose a chart should go to web/chart"]))
        run(NS_CLI, "sync", self.root)
        rc, out = run(CLI, "route", self.root, "put a switch in the header")
        self.assertEqual(rc, 0, out)
        self.assertIn("lands on: web/dark-mode/toggle", out)
        # the child's own excludes does not block the parent: web still takes a sentence with 'palette' and 'switch'
        rc, out = run(CLI, "route", self.root, "a switch for the palette")
        self.assertIn("lands on: web/dark-mode", out)
        rc, out = run(CLI, "replay", self.root)
        self.assertEqual(rc, 0, out)

    def test_replay_grandchild_stopped_because_sibling_of_parent_also_took_it(self):
        """A grandchild's positive that both its parent and its parent's sibling take stops at the
        grandparent. The message must name the sibling, not claim the parent's cover words were absent."""
        write(self.root / "web" / "dark-mode" / "toggle" / "SKILL.md",
              skill("toggle", "Use when adding a dark mode switch: covers toggle, switch; excludes palette",
                    ["add a dark mode toggle to the chart", "put a dark theme switch in the header",
                     "choose a chart for the report page should go to web/chart"]))
        run(NS_CLI, "sync", self.root)
        rc, out = run(CLI, "replay", self.root)
        self.assertEqual(rc, 1)
        self.assertIn("[FAIL not reached] web/dark-mode/toggle: \"add a dark mode toggle to the chart\" lands on web "
                      "(the sentence was stopped at web: web/dark-mode took it, but so did its sibling(s) web/chart, "
                      "and a sentence two children take stays with their parent -- drop the sibling's word from this example, "
                      "or accept that this sentence is web's job)", out)
        self.assertNotIn("contains none of web/dark-mode's cover words", out)

    def test_replay_positive_missing_own_cover_says_so(self):
        """Passed the parent, but none of its own cover words match -> lands on the parent; message lists its cover words."""
        self.write_dark(triggers=["add a night toggle to the page", "how to layer cards in a dark theme",
                                  "choose a chart for the report page should go to web/chart"])
        rc, out = run(CLI, "replay", self.root)
        self.assertEqual(rc, 1)
        self.assertIn("[FAIL not reached] web/dark-mode: \"add a night toggle to the page\" lands on web"
                      " (this skill did not take it: the sentence contains none of its cover words dark mode,dark theme)", out)

    def test_replay_positive_blocked_by_own_exclusion_says_so(self):
        """Own cover word matches but own `excludes` blocks -> message names the exclude word."""
        self.write_dark(triggers=["which light palette to use in dark mode", "how to layer cards in a dark theme",
                                  "choose a chart for the report page should go to web/chart"])
        rc, out = run(CLI, "replay", self.root)
        self.assertEqual(rc, 1)
        self.assertIn("[FAIL not reached] web/dark-mode: \"which light palette to use in dark mode\" lands on web"
                      " (this skill is blocked by its own 'excludes light palette')", out)

    def test_replay_top_level_positive_nobody_takes_names_own_covers(self):
        """A top-level positive nobody takes -> lists the skill's own cover words (word-form mismatches are visible at a glance)."""
        write(self.root / "lib-org" / "SKILL.md",
              skill("lib-org", ORG_DESC, ["absorbing this new skill", "is this skill a duplicate", "build a data dashboard should go to web/chart"]))
        rc, out = run(CLI, "replay", self.root)
        self.assertEqual(rc, 1)
        self.assertIn(f"[FAIL not reached] lib-org: \"absorbing this new skill\" lands on {oc.ROOT_LABEL}"
                      " (this skill did not take it: the sentence contains none of its cover words library organization,absorb,duplicate)", out)

    def test_positive_with_arrow_is_not_anti(self):
        self.write_dark(triggers=["adapt the whole site to dark mode", "move the theme from v1 -> v2 to dark mode",
                                  "choose a chart for the report page should go to web/chart"])
        rc, out = run(CLI, "replay", self.root)
        self.assertEqual(rc, 0, out)


class TestAliasAmplification(TempTree):
    """A cover word that is itself an alias of a frequent canonical word is folded into that word before matching
    and therefore takes every sentence containing it. lint must flag it; replay must name the alias when a sibling steals."""

    def _chart_with_alias_cover(self):
        # synonyms: page,front-end,landing page -> chart uses "landing page" as a cover word; folded it is "page",
        # so every sentence containing "page" hits chart
        write(self.root / "web" / "chart" / "SKILL.md",
              skill("chart", "Use when building charts: covers chart, dashboard, landing page; excludes page layout", CHART_TRIG))

    def test_lint_warns_cover_word_that_is_an_alias(self):
        self._chart_with_alias_cover()
        rc, out = self.lint()
        self.assertIn("[W] web/chart: cover word 'landing page' is an alias of 'page' in synonyms.md and becomes 'page' before matching"
                      " -- every sentence containing 'page' will hit this skill. To take that much, write 'page' directly; "
                      "otherwise pick a word that is not in a synonym group", out)

    def test_lint_allows_cover_word_that_is_canonical(self):
        """A cover word that is the first (canonical) word of its group is normal usage; no warning."""
        rc, out = self.lint()
        self.assertNotIn("is an alias of", out)

    def test_replay_names_alias_when_sibling_steals(self):
        """When a sibling steals via an alias cover word, replay says which word and what it folds to."""
        self._chart_with_alias_cover()
        write(self.root / "web" / "dark-mode" / "SKILL.md",
              skill("dark-mode", DARK_DESC, ["adapt this page to dark mode", "how to layer cards in a dark theme",
                                             "choose a chart for the report page should go to web/chart"]))
        rc, out = run(CLI, "replay", self.root)
        self.assertEqual(rc, 1)
        self.assertIn("[FAIL not reached] web/dark-mode: \"adapt this page to dark mode\" lands on web"
                      " (sibling web/chart also takes this sentence, via its cover word 'landing page' (an alias of 'page' in synonyms.md, "
                      "so it takes every sentence containing 'page')"
                      " -> either a real duplicate, or add an 'excludes' to web/chart)", out)


# ---------------------------------------------------------------- retire: nothing is really deleted

class TestRetire(TempTree):
    def test_retire_moves_whole_dir_and_writes_header(self):
        rc, out = run(CLI, "retire", self.root, "web/chart", "--reason", "merged into web/dark-mode")
        self.assertEqual(rc, 0, out)
        self.assertFalse((self.root / "web" / "chart").exists())
        moved = self.root / ".retired" / "web" / "chart" / "SKILL.md"
        self.assertTrue(moved.is_file())
        self.assertEqual(moved.read_text(encoding="utf-8").splitlines()[0], "retired @12 merged into web/dark-mode")
        self.assertIn("moved to .retired/web/chart", out)

    def test_lint_summary_counts_retired(self):
        """Retired cards are outside the tree and easy to overlook; the lint summary counts them. Nothing shown when none."""
        rc, out = self.lint()
        self.assertNotIn("retired", out)
        run(CLI, "retire", self.root, "lib-org", "--reason", "test")
        rc, out = self.lint()
        self.assertRegex(out, r"lint: \d+ errors, \d+ warnings(, \d+ hints)?, 4 skills, 1 retired")

    def test_retire_syncs_parent_routing_table(self):
        run(NS_CLI, "sync", self.root)
        self.assertIn("chart", (self.root / "web" / "SKILL.md").read_text(encoding="utf-8"))
        run(CLI, "retire", self.root, "web/chart", "--reason", "x")
        self.assertNotIn("**chart**", (self.root / "web" / "SKILL.md").read_text(encoding="utf-8"))
        rc, out = run(NS_CLI, "validate", self.root)
        self.assertEqual(rc, 0, out)

    def test_retire_refuses_root_and_missing(self):
        rc, out = run(CLI, "retire", self.root, ".", "--reason", "x")
        self.assertEqual(rc, 1)
        rc, out = run(CLI, "retire", self.root, "nope", "--reason", "x")
        self.assertEqual(rc, 1)
        self.assertIn("is not a skill in this library", out)

    def test_retire_twice_keeps_both_copies(self):
        run(CLI, "retire", self.root, "web/chart", "--reason", "one")
        write(self.root / "web" / "chart" / "SKILL.md", skill("chart", CHART_DESC, CHART_TRIG))
        rc, out = run(CLI, "retire", self.root, "web/chart", "--reason", "two")
        self.assertEqual(rc, 0, out)
        kept = sorted(p.name for p in (self.root / ".retired" / "web").iterdir())
        self.assertEqual(len(kept), 2)
        self.assertIn("chart", kept)

    def test_retired_is_invisible_to_lint_and_replay(self):
        run(CLI, "retire", self.root, "web/chart", "--reason", "x")
        # other skills' negatives still point at web/chart -> error (it is no longer in the library)
        rc, out = self.lint()
        self.assertEqual(rc, 1)
        self.assertIn("negative-example target 'web/chart' is not a skill in this library", out)


# ---------------------------------------------------------------- feedback / counter / relative paths

class TestFeedbackCounter(TempTree):
    def test_feedback_lists_pending(self):
        write(self.root / "_feedback.md", "# header\n> note\ntask a | web | miss\ntask b | web/chart | wrong done\n")
        rc, out = run(CLI, "feedback", self.root)
        self.assertIn("task a", out)
        self.assertNotIn("task b", out)
        self.assertIn("1 line(s) pending", out)

    def test_counter_refuses_dir_without_root_skill(self):
        rc, out = run(CLI, "counter", self.tmp, "--bump")
        self.assertEqual(rc, 1)
        self.assertFalse((self.tmp / "SKILL.md").exists())

    def test_counter_bumps(self):
        rc, out = run(CLI, "counter", self.root, "--bump")
        self.assertEqual((rc, out.strip()), (0, "archive_count: 12 -> 13"))
        rc, out = run(CLI, "counter", self.root)
        self.assertEqual((rc, out.strip()), (0, "archive_count: 13"))

    def test_same_result_for_dot_and_absolute(self):
        _, a = run(CLI, "lint", self.root)
        _, b = run(CLI, "lint", ".", cwd=self.root)
        self.assertEqual(a, b)
        _, a = run(CLI, "replay", self.root)
        _, b = run(CLI, "replay", ".", cwd=self.root)
        self.assertEqual(a, b)


# ---------------------------------------------------------------- route command / counter alignment

class TestRouteCommand(TempTree):
    """`route` answers "where does this sentence land and how did each gate go" without building probe cards."""

    def test_route_prints_each_gate_and_landing(self):
        rc, out = run(CLI, "route", self.root, "adapt the whole site to dark mode")
        self.assertEqual(rc, 0, out)
        self.assertIn("sentence: \"adapt the whole site to dark mode\"", out)
        self.assertIn("root -> taken by: web (via 'dark mode')", out)
        # 'dark theme' folds to 'dark mode' in synonyms.md: one word, listed once with the other spelling attached
        self.assertIn("web -> taken by: web/dark-mode (via 'dark mode' ('dark theme' fold to the same word))", out)
        self.assertIn("web/dark-mode -> no sub-skills", out)
        self.assertIn("lands on: web/dark-mode", out)

    def test_route_shows_canonical_form_when_synonyms_apply(self):
        rc, out = run(CLI, "route", self.root, "switch the whole site to night mode")
        self.assertEqual(rc, 0, out)
        self.assertIn("folded: \"switch the whole site to dark mode\"", out)
        self.assertIn("lands on: web/dark-mode", out)

    def test_route_two_children_stop_at_parent(self):
        rc, out = run(CLI, "route", self.root, "chart colours in dark mode")
        self.assertEqual(rc, 0, out)
        self.assertIn("web -> taken by: web/chart (via 'chart' ('dashboard' fold to the same word)), "
                      "web/dark-mode (via 'dark mode' ('dark theme' fold to the same word))"
                      " -> two or more children take it; a sentence spanning children is the parent's job, stop at web", out)
        self.assertIn("lands on: web", out)

    def test_route_nobody_and_root_ambiguity(self):
        rc, out = run(CLI, "route", self.root, "a completely unrelated sentence")
        self.assertEqual(rc, 0, out)
        self.assertIn("root -> taken by: (none)", out)
        self.assertIn(f"lands on: {oc.ROOT_LABEL}", out)
        write(self.root / "lib-org" / "SKILL.md",
              skill("lib-org", "Use when absorbing skills: covers library organization, absorb, page; excludes domain knowledge", ORG_TRIG))
        rc, out = run(CLI, "route", self.root, "write a landing page")
        self.assertEqual(rc, 0, out)
        self.assertIn("lands on: ambiguous, 2 top-level skills take it at once [lib-org, web]", out)

    def test_route_names_child_blocked_by_its_own_exclusion(self):
        rc, out = run(CLI, "route", self.root, "which light palette to use in dark mode")
        self.assertEqual(rc, 0, out)
        self.assertIn("web -> taken by: (none); web/dark-mode would take it but is blocked by its own 'excludes light palette'", out)
        self.assertIn("lands on: web", out)

    def test_route_folds_covers_that_are_one_word_after_synonyms(self):
        """Several spellings that synonyms.md folds to one word (Word/docx/dotx) count once, not three times."""
        write(self.root / "synonyms.md", "dark mode,night mode,dark theme\nword,docx,dotx\n")
        self.write_dark(desc="Use when handling Word documents: covers Word, docx, dotx; excludes light palette")
        rc, out = run(CLI, "route", self.root, "a dark mode docx template")
        self.assertEqual(rc, 0, out)
        self.assertIn("web -> taken by: web/dark-mode (via 'Word' ('docx','dotx' fold to the same word))", out)

    def test_route_requires_sentence(self):
        rc, out = run(CLI, "route", self.root)
        self.assertEqual(rc, 2)
        self.assertIn("route needs a sentence", out)

    def test_route_last_line_is_bytes_read_on_the_path(self):
        """The tree exists to lower what an agent reads per task; route prints that number.
        Path bytes are the SKILL.md sizes of root, web, web/dark-mode; the total is every SKILL.md in the tree."""
        rc, out = run(CLI, "route", self.root, "adapt the whole site to dark mode")
        self.assertEqual(rc, 0, out)
        path = [self.root / "SKILL.md", self.root / "web" / "SKILL.md", self.root / "web" / "dark-mode" / "SKILL.md"]
        read = sum(p.stat().st_size for p in path)
        total = sum(p.stat().st_size for p in self.root.rglob("SKILL.md") if ".retired" not in p.parts)
        self.assertLess(read, total)
        self.assertEqual(out.rstrip().splitlines()[-1],
                         f"read: 3 file(s), {read:,} bytes of {total:,} in the library ({100 * read // total}%)")

    def test_route_nobody_reads_only_the_root(self):
        rc, out = run(CLI, "route", self.root, "a completely unrelated sentence")
        self.assertEqual(rc, 0, out)
        self.assertRegex(out.rstrip().splitlines()[-1], r"^read: 1 file\(s\), [\d,]+ bytes of [\d,]+ in the library \(\d+%\)$")


class TestPortableOutput(TempTree):
    def test_relative_labels_use_slashes_on_windows_and_posix(self):
        from pathlib import PurePosixPath, PureWindowsPath
        for root in (PureWindowsPath(r"C:\Users\reader\skill tree"),
                     PureWindowsPath(r"\\server\share\skills"), PurePosixPath("/tmp/skill tree")):
            with self.subTest(root=str(root)):
                self.assertEqual(oc.rel(root, root / "web" / "dark-mode"), "web/dark-mode")
                self.assertEqual(oc.rel(root, root), ".")
                self.assertEqual(oc.where(root, root / "web" / "chart"), "web/chart")

    def test_counter_writes_lf_even_with_windows_default_newlines(self):
        import io
        from unittest import mock
        real_open = io.open

        def windows_open(file, mode="r", buffering=-1, encoding=None, errors=None,
                         newline=None, closefd=True, opener=None):
            if "w" in mode and "b" not in mode and newline is None:
                newline = "\r\n"
            return real_open(file, mode, buffering, encoding, errors, newline, closefd, opener)

        with mock.patch("io.open", side_effect=windows_open):
            self.assertEqual(oc.cmd_counter(self.root, bump=True), 0)
        self.assertNotIn(b"\r\n", (self.root / "SKILL.md").read_bytes())

    def test_route_counts_actual_bytes_in_crlf_input(self):
        for file in self.root.rglob("SKILL.md"):
            data = file.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            file.write_bytes(data)
        rc, out = run(CLI, "route", self.root, "adapt the whole site to dark mode")
        files = [self.root / part / "SKILL.md" for part in (".", "web", "web/dark-mode")]
        used = sum(file.stat().st_size for file in files)
        total = sum(file.stat().st_size for file in self.root.rglob("SKILL.md"))
        self.assertEqual(rc, 0, out)
        self.assertIn(f"read: 3 file(s), {used:,} bytes of {total:,}", out)


class TestFunctionalRegressions(TempTree):
    def test_counter_updates_only_frontmatter_not_body_examples(self):
        body = '\nExample:\nmetadata:\n  holon-archive-count: "99"\n'
        for field in ('  holon-archive-count: "12"\n', "  holon-archive-count: '12'\n"):
            with self.subTest(field=field):
                text = '---\nname: demo\ndescription: task\nmetadata:\n' + field + '---\n' + body
                write(self.root / "SKILL.md", text)
                rc, out = run(CLI, "counter", self.root, "--bump")
                self.assertEqual((rc, out.strip()), (0, "archive_count: 12 -> 13"))
                updated = (self.root / "SKILL.md").read_text(encoding="utf-8")
                self.assertTrue(updated.endswith(body))
                self.assertEqual(oc.read_counter(self.root), 13)

    def test_counter_ignores_counter_example_when_header_has_none(self):
        body = '\nmetadata:\n  holon-archive-count: "99"\n'
        write(self.root / "SKILL.md", '---\nname: demo\ndescription: task\n---\n' + body)
        rc, out = run(CLI, "counter", self.root, "--bump")
        self.assertEqual((rc, out.strip()), (0, "archive_count: 0 -> 1"))
        self.assertEqual(oc.read_counter(self.root), 1)
        self.assertTrue((self.root / "SKILL.md").read_text(encoding="utf-8").endswith(body))

    def test_invalid_counter_is_not_silently_reset(self):
        f = self.root / "SKILL.md"
        text = f.read_text(encoding="utf-8").replace('"12"', '"invalid"')
        f.write_text(text, encoding="utf-8")
        rc, out = run(CLI, "counter", self.root, "--bump")
        self.assertEqual(rc, 1, out)
        self.assertEqual(f.read_text(encoding="utf-8"), text)

    def test_feedback_word_undone_is_still_pending(self):
        write(self.root / "_feedback.md", "task a | web | undone\ntask b | web | miss done\n")
        rc, out = run(CLI, "feedback", self.root)
        self.assertEqual(rc, 0)
        self.assertIn("task a", out)
        self.assertNotIn("task b", out)
        self.assertIn("1 line(s) pending", out)

    def test_retire_rejects_external_destination_link(self):
        outside = self.tmp / "outside"
        outside.mkdir()
        try:
            (self.root / ".retired").symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links are unavailable")
        rc, out = run(CLI, "retire", self.root, "web/chart", "--reason", "test")
        self.assertEqual(rc, 1, out)
        self.assertTrue((self.root / "web/chart/SKILL.md").is_file())
        self.assertEqual(list(outside.iterdir()), [])

    def test_broken_frontmatter_fails_every_routing_check_cleanly(self):
        write(self.root / "web/chart/SKILL.md", '---\nname: chart\ndescription:\n  - bad type\n---\n')
        for command, args in (("lint", []), ("replay", []), ("route", ["build a chart"]), ("overlap", [])):
            with self.subTest(command=command):
                rc, out = run(CLI, command, self.root, *args)
                self.assertEqual(rc, 1, out)
                self.assertNotIn("Traceback", out)

    def test_routing_checks_reject_empty_libraries(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        for command in ("lint", "replay", "overlap"):
            rc, out = run(CLI, command, empty)
            self.assertEqual(rc, 1, out)

    def test_chinese_alias_routes_to_leaf(self):
        with (self.root / "synonyms.md").open("a", encoding="utf-8") as f:
            f.write("dark mode,夜间模式\n")
        rc, out = run(CLI, "route", self.root, "请把页面改为夜间模式")
        self.assertEqual(rc, 0, out)
        self.assertIn("lands on: web/dark-mode", out)

    def test_invalid_overlap_threshold_is_rejected(self):
        for value in ("nan", "inf", "-0.1", "1.1"):
            rc, out = run(CLI, "overlap", self.root, "--threshold", value)
            self.assertEqual(rc, 2, out)


class TestCounterAlignment(TempTree):
    """archive_count, retired headers and ABSORB.md section headings must carry one number; bump first, then act."""

    def test_retire_tells_which_absorb_section_it_belongs_to(self):
        rc, out = run(CLI, "retire", self.root, "web/chart", "--reason", "merged into web/dark-mode")
        self.assertEqual(rc, 0, out)
        self.assertIn("first line 'retired @12 merged into web/dark-mode' (this absorption's section heading in ABSORB.md should also be @12; "
                      "if you have not bumped yet, run counter --bump before retire)", out)

    def test_lint_hints_retired_head_without_absorb_section(self):
        write(self.root / ".retired" / "web" / "old" / "SKILL.md", "retired @11 merged into web/dark-mode\n---\nname: old\n---\n")
        rc, out = self.lint()
        self.assertEqual(rc, 0, out)
        self.assertIn("[·] .retired/web/old: header says @11 but ABSORB.md has no '## @11' section", out)
        write(self.root / ".retired" / "web" / "old" / "SKILL.md", "retired @12 merged into web/dark-mode\n---\nname: old\n---\n")
        rc, out = self.lint()
        self.assertNotIn("has no '## @", out)


# ---------------------------------------------------------------- integration: mechanism-layer output -> judgement-layer checks

class TestInitDescToLintReplay(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "brain"
        # --bare: this fixture tests two hand-made skills, not the tools a root normally carries.
        rc, out = run(NS_CLI, "init", "brain", "--root", self.tmp, "--bare", "--desc",
                      "Use when archiving or retrieving: covers library routing; excludes domain content")
        self.assertEqual(rc, 0, out)
        for name, desc in [("my-domain", "Use when handling nginx 502: covers nginx, 502, upstream; excludes dns"),
                           ("dns-domain", "Use when debugging name resolution: covers dns, resolution, domain name; excludes 502")]:
            rc, out = run(NS_CLI, "init", name, "--parent", self.root, "--desc", desc)
            self.assertEqual(rc, 0, out)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _fill_todo(self, p, steps):
        text = p.read_text(encoding="utf-8")
        text = re.sub(r"^1\. TODO:.*$", steps, text, count=1, flags=re.M)
        p.write_text(text, encoding="utf-8")

    def _finish(self, name, triggers):
        p = self.root / name / "SKILL.md"
        self._fill_todo(p, BODY_FILL)
        meta, body, err = oc.parse_frontmatter(p.read_text(encoding="utf-8"))
        self.assertIsNone(err)
        trig = "\n".join(f"    {t}" for t in triggers)
        p.write_text(f'---\nname: {meta["name"]}\ndescription: "{meta["description"]}"\nmetadata:\n  holon-triggers: |\n{trig}\n---{body}', encoding="utf-8")

    def test_fresh_init_reports_missing_triggers(self):
        rc, out = run(CLI, "lint", self.root)
        self.assertEqual(rc, 1)
        self.assertIn("[E] my-domain: triggers", out)

    def test_full_pipeline(self):
        self._finish("my-domain", ["nginx returns 502", "how to debug an upstream timeout", "nginx dns resolution fails should go to dns-domain"])
        self._finish("dns-domain", ["domain name does not resolve", "how to flush the dns cache", "nginx 502 should go to my-domain"])
        self._fill_todo(self.root / "SKILL.md", "1. Descend by the routing table. On a miss, append a line to _feedback.md.")
        write(self.root / "_feedback.md", "# _feedback.md\n")
        rc, out = run(NS_CLI, "validate", self.root)
        self.assertEqual(rc, 0, out)
        rc, out = run(CLI, "lint", self.root)
        self.assertEqual(rc, 0, out)
        # 'dns' and '502' are three characters; a library that raised COVER_MIN above 3 is warned.
        self.assertIn("0 errors, 0 warnings" if oc.COVER_MIN <= 3 else "0 errors,", out)
        rc, out = run(CLI, "replay", self.root)
        self.assertEqual(rc, 0, out)
        self.assertIn("6/6", out)

    def test_quoted_desc_exclusion_still_works(self):
        self._finish("my-domain", ["nginx returns 502", "how to debug an upstream timeout", "nginx dns resolution fails should go to dns-domain"])
        self._finish("dns-domain", ["domain name does not resolve", "how to flush the dns cache", "nginx 502 should go to my-domain"])
        p = self.root / "my-domain" / "SKILL.md"
        p.write_text(p.read_text(encoding="utf-8").replace("; excludes dns", ""), encoding="utf-8")
        rc, out = run(CLI, "replay", self.root)
        self.assertEqual(rc, 1)
        self.assertIn("[FAIL negative hit] my-domain", out)


# ---------------------------------------------------------------- dogfood: this package itself

class TestDogfood(unittest.TestCase):
    def test_repo_passes_validate(self):
        rc, out = run(NS_CLI, "validate", PKG_ROOT)
        self.assertEqual(rc, 0, out)

    def test_repo_passes_lint_clean(self):
        rc, out = run(CLI, "lint", PKG_ROOT)
        self.assertEqual(rc, 0, out)
        self.assertIn("0 errors, 0 warnings", out)

    def test_repo_passes_replay(self):
        rc, out = run(CLI, "replay", PKG_ROOT)
        self.assertEqual(rc, 0, out)
        self.assertNotIn("FAIL", out)

    def test_param_table_matches_cli_constants(self):
        text = (ORG_DIR / "SKILL.md").read_text(encoding="utf-8")
        table = dict(re.findall(r"^\| (\S+) \| ([^|]+?) \|", text, re.M))
        self.assertEqual(table["COVER_MAX"], f"{oc.COVER_MAX} words")
        self.assertEqual(table["DESC_MAX"], f"{oc.DESC_MAX} characters")
        self.assertEqual(table["MAX_BODY"], f"{oc.MAX_BODY} lines")
        self.assertEqual(table["FANOUT"], str(oc.FANOUT))
        self.assertEqual(table["OVERLAP"], str(oc.OVERLAP))
        self.assertEqual(table["COVER_MIN"], f"{oc.COVER_MIN} characters")
        self.assertEqual(set(table) - {"Parameter"}, {"COVER_MAX", "COVER_MIN", "DESC_MAX", "MAX_BODY", "FANOUT", "OVERLAP"})

    def test_rule_text_has_no_legacy_machinery(self):
        """Machinery from the earlier design must not reappear in the rulebook."""
        text = (ORG_DIR / "SKILL.md").read_text(encoding="utf-8")
        for bad in ("ledger", "_inbox", ".lock", "_volatile", "misc/", "axis:", "last-verified",
                    "[DEFERRED]", "[STUB]", "DEPTH(", "M1", "M6"):
            self.assertNotIn(bad, text, f"rulebook still mentions legacy machinery '{bad}'")

    def test_rules_doc_keeps_checklist(self):
        """The four-question checklist is read by `ask`; its heading and key phrases are load-bearing."""
        text = (ORG_DIR / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn(oc.CHECKLIST_HEAD, text)
        self.assertTrue(oc.CHECKLIST_HEAD.startswith("## "))
        for q in ("deliver the same kind of thing", "needed by several parents", "way of working", "Which sentences does the parent itself take"):
            self.assertIn(q, text, f"checklist is missing '{q}'")
        self.assertIn("read the `ruled:` lines of the root `ABSORB.md`", text)
        self.assertIn("`ask`", text)
        self.assertIn("successive stages of one product", text)
        self.assertIn("When a batch arrives", text)

    def test_rules_doc_keeps_routing_facts(self):
        """Facts about lexical routing the AI needs in order to write cover words and examples correctly."""
        text = (ORG_DIR / "SKILL.md").read_text(encoding="utf-8")
        for phrase in ("Every `excludes` between siblings", "generic verbs", "ignores subject and object",
                       "outside its original repository", "shortest form a user would actually say",
                       "cover words of two or more children", "folded through `synonyms.md` before matching",
                       "read the whole batch", "need not be a valid card", "with their own directory and `SKILL.md`",
                       "case-insensitive", "run `counter --bump`", "If the first step is bound",
                       "The tools only recognise `learned:`, `merged:` and `ruled:`"):
            self.assertIn(phrase, text, f"rulebook is missing '{phrase}'")

    def test_organizer_card_has_no_generic_verb_as_cover(self):
        """organizer is the only skill card shipped with the package; its cover words must not be generic verbs
        like 'merge' (which would collide with 'merge two PDFs', 'merge the branch')."""
        meta, _, _ = oc.parse_frontmatter((ORG_DIR / "SKILL.md").read_text(encoding="utf-8"))
        covers, _ = oc.parse_desc(meta["description"])
        self.assertNotIn("merge", covers)
        self.assertIn("duplicate", covers)

    def test_rules_body_within_max_body(self):
        meta, body, err = oc.parse_frontmatter((ORG_DIR / "SKILL.md").read_text(encoding="utf-8"))
        self.assertIsNone(err)
        lines = len([l for l in body.splitlines() if l.strip()])
        # MAX_BODY only produces a hint; an owner who lowers it below the rulebook's own
        # length gets that hint, not a failing package. 150 is the shipped value.
        self.assertLessEqual(lines, max(oc.MAX_BODY, 150))


if __name__ == "__main__":
    unittest.main(verbosity=1)
