#!/usr/bin/env python3
# Copyright (c) 2026 Wneil2020 and the holon skill contributors. Released under the MIT License.
"""Unit tests for holon. Runnable with pytest OR directly:
    python3 tests/test_holon.py
"""
import contextlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import holon as ns  # noqa: E402


def make_skill(path, name, description, body="", markers=True):
    os.makedirs(path, exist_ok=True)
    text = "---\nname: %s\ndescription: %s\n---\n\n# %s\n\n%s\n" % (
        name, json.dumps(description, ensure_ascii=False), name, body)
    if markers:
        text += "\n%s\n%s\n" % (ns.MARK_OPEN, ns.MARK_CLOSE)
    with open(os.path.join(path, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write(text)


class TestFrontmatter(unittest.TestCase):
    def test_parse_ok(self):
        meta, err = ns.parse_frontmatter(
            '---\nname: foo\ndescription: "bar baz"\n---\nbody')
        self.assertIsNone(err)
        self.assertEqual(meta["name"], "foo")
        self.assertEqual(meta["description"], "bar baz")

    def test_missing_frontmatter(self):
        meta, err = ns.parse_frontmatter("no frontmatter here")
        self.assertIsNotNone(err)

    def test_unterminated(self):
        meta, err = ns.parse_frontmatter("---\nname: x\nno closing")
        self.assertIn("unterminated", err)

    def test_unquoted_mapping_separator_is_rejected(self):
        _, err = ns.parse_frontmatter("---\ndescription: use when: always\n---\n")
        self.assertIsNotNone(err)

    def test_quoted_colon_is_preserved(self):
        meta, err = ns.parse_frontmatter('---\ndescription: "use when: always"\n---\n')
        self.assertIsNone(err)
        self.assertEqual(meta["description"], "use when: always")

    def test_ambiguous_or_unsupported_scalars_fail_closed(self):
        for value in ('[one, two]', '{key: value}', '&anchor text', '*alias', '!tag text',
                      '"unterminated', "'unterminated", '"x" trailing', '"bad\\q"',
                      'plain # silently truncated', 'text:'):
            with self.subTest(value=value):
                _, err = ns.parse_frontmatter('---\ndescription: ' + value + '\n---\n')
                self.assertIsNotNone(err)

    def test_quoted_escapes_follow_yaml_not_chained_replacements(self):
        meta, err = ns.parse_frontmatter(r'''---
name: demo
description: "path \\\\ and quote \\\""
---
''')
        self.assertIsNone(err)
        self.assertEqual(meta['description'], 'path \\\\ and quote \\"')
        meta, err = ns.parse_frontmatter("---\ndescription: 'it''s a skill: use it'\n---\n")
        self.assertIsNone(err)
        self.assertEqual(meta['description'], "it's a skill: use it")

    def test_invalid_indentation_cannot_be_reinterpreted_as_top_level(self):
        for header in (' name: demo\ndescription: task',
                       'name: demo\n  description: task',
                       'metadata:\n  owner: user\n    nested: value\nname: demo\ndescription: task',
                       'name: demo\nmetadata:\n\towner: user\ndescription: task'):
            with self.subTest(header=header):
                _, err = ns.parse_frontmatter('---\n' + header + '\n---\n')
                self.assertIsNotNone(err)

    def test_bom_before_frontmatter_is_ignored(self):
        # Some Windows editors prepend an invisible BOM; to a human the file starts with ---
        meta, err = ns.parse_frontmatter("\ufeff---\nname: foo\ndescription: bar\n---\nbody")
        self.assertIsNone(err)
        self.assertEqual(meta["name"], "foo")

    def test_folded_scalar_joins_with_spaces(self):
        # `description: >` is the YAML folded style: continuation lines join into one line
        meta, err = ns.parse_frontmatter(
            "---\nname: foo\ndescription: >\n  first part\n  second part\n---\n")
        self.assertIsNone(err)
        self.assertEqual(meta["description"], "first part second part")

    def test_literal_scalar_keeps_newlines(self):
        meta, err = ns.parse_frontmatter(
            "---\nname: foo\nnotes: |\n  line one\n  line two\n---\n")
        self.assertIsNone(err)
        self.assertEqual(meta["notes"], "line one\nline two")


class TestSyncBehaviour(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.parent = os.path.join(self.tmp, "parent")
        make_skill(self.parent, "parent", "parent skill",
                   body="## Handwritten section\nThis paragraph must survive.")
        make_skill(os.path.join(self.parent, "child-a"), "child-a", "does A")
        make_skill(os.path.join(self.parent, "child-b"), "child-b", "does B",
                   markers=False)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _read(self, path):
        with open(os.path.join(path, "SKILL.md"), encoding="utf-8") as f:
            return f.read()

    def _sync(self, dry=False):
        import argparse
        args = argparse.Namespace(path=self.tmp, dry_run=dry, auto_append=True)
        return ns.cmd_sync(args)

    def test_injection_contains_children(self):
        self._sync()
        text = self._read(self.parent)
        self.assertIn("child-a", text)
        self.assertIn("does A", text)
        self.assertIn("child-b", text)
        self.assertIn("does B", text)

    def test_idempotent(self):
        self._sync()
        first = self._read(self.parent)
        self._sync()
        second = self._read(self.parent)
        self.assertEqual(first, second, "sync twice must yield identical output")

    def test_handwritten_content_preserved(self):
        self._sync()
        text = self._read(self.parent)
        self.assertIn("This paragraph must survive.", text)
        self.assertIn("## Handwritten section", text)

    def test_auto_append_marker(self):
        # child-b has no markers but also no grandchildren -> add one
        gc = os.path.join(self.parent, "child-b", "grand")
        make_skill(gc, "grand", "grandchild skill")
        self._sync()
        text = self._read(os.path.join(self.parent, "child-b"))
        self.assertIn(ns.MARK_OPEN, text)
        self.assertIn("grand", text)

    def test_dry_run_no_write(self):
        before = self._read(self.parent)
        self._sync(dry=True)
        after = self._read(self.parent)
        self.assertEqual(before, after)

    def test_sorted_by_dirname(self):
        self._sync()
        text = self._read(self.parent)
        self.assertLess(text.index("child-a"), text.index("child-b"))


class TestCycleDetection(unittest.TestCase):
    def test_symlink_cycle(self):
        tmp = tempfile.mkdtemp()
        try:
            parent = os.path.join(tmp, "a")
            make_skill(parent, "a", "skill a")
            # symlink child pointing back to parent -> cycle
            try:
                os.symlink(parent, os.path.join(parent, "loop"))
            except (OSError, NotImplementedError):
                self.skipTest("symbolic links require permission on this system")
            skills, errors = ns.collect_skills(tmp)
            self.assertTrue(any("circular" in e for e in errors))
        finally:
            shutil.rmtree(tmp)


class TestUpdateReflectsNewChild(unittest.TestCase):
    """From version A: re-sync after adding a child must update the block
    without duplicating markers."""

    def test_update_no_duplicate_block(self):
        tmp = tempfile.mkdtemp()
        try:
            parent = os.path.join(tmp, "parent")
            make_skill(parent, "parent", "parent skill")
            make_skill(os.path.join(parent, "alpha"), "alpha", "does alpha")
            import argparse
            args = argparse.Namespace(path=tmp, dry_run=False, auto_append=True)
            ns.cmd_sync(args)
            make_skill(os.path.join(parent, "beta"), "beta", "does beta")
            ns.cmd_sync(args)
            with open(os.path.join(parent, "SKILL.md"), encoding="utf-8") as f:
                text = f.read()
            self.assertIn("does alpha", text)
            self.assertIn("does beta", text)
            self.assertEqual(text.count(ns.MARK_OPEN), 1)
            self.assertEqual(text.count(ns.MARK_CLOSE), 1)
        finally:
            shutil.rmtree(tmp)


class TestValidateRoundtrip(unittest.TestCase):
    """From version A: validate must fail on TODO description and on
    out-of-sync injection, and pass after sync."""

    def test_todo_description_fails(self):
        tmp = tempfile.mkdtemp()
        try:
            make_skill(os.path.join(tmp, "s"), "s",
                       "TODO: one sentence - what this skill does and when to use it")
            import argparse
            rc = ns.cmd_validate(argparse.Namespace(path=tmp))
            self.assertEqual(rc, 1)
        finally:
            shutil.rmtree(tmp)

    def test_out_of_sync_fails_then_passes(self):
        tmp = tempfile.mkdtemp()
        try:
            p = os.path.join(tmp, "p")
            make_skill(p, "p", "parent skill")
            make_skill(os.path.join(p, "c"), "c", "child skill")
            import argparse
            rc = ns.cmd_validate(argparse.Namespace(path=tmp))
            self.assertEqual(rc, 1)  # not synced yet -> stale
            ns.cmd_sync(argparse.Namespace(
                path=tmp, dry_run=False, auto_append=True))
            rc = ns.cmd_validate(argparse.Namespace(path=tmp))
            self.assertEqual(rc, 0)
        finally:
            shutil.rmtree(tmp)


class TestInitDesc(unittest.TestCase):
    """Merged feature: init --desc writes the description directly."""

    def test_desc_written(self):
        tmp = tempfile.mkdtemp()
        try:
            import argparse
            rc = ns.cmd_init(argparse.Namespace(
                name="foo", parent=None, root=tmp,
                desc="does foo when asked", dry_run=False))
            self.assertEqual(rc, 0)
            _, meta, err = ns.read_skill(os.path.join(tmp, "foo"))
            self.assertIsNone(err)
            self.assertEqual(meta["description"], "does foo when asked")
        finally:
            shutil.rmtree(tmp)

    def test_no_desc_leaves_todo_on_a_child_and_the_root_desc_on_a_root(self):
        """A child without --desc is a TODO validate rejects. A root is never routed to, so it
        gets the standard root description, the six reading rules and the three ledgers."""
        tmp = tempfile.mkdtemp()
        try:
            import argparse
            ns.cmd_init(argparse.Namespace(name="bar", parent=None, root=tmp, desc=None, dry_run=False, bare=True))
            root = os.path.join(tmp, "bar")
            _, meta, _ = ns.read_skill(root)
            self.assertEqual(meta["description"], ns.ROOT_DESC)
            self.assertEqual(meta["archive_count"], "0")
            for fn in ("_feedback.md", "synonyms.md", "ABSORB.md"):
                self.assertTrue(os.path.isfile(os.path.join(root, fn)), fn)
            ns.cmd_init(argparse.Namespace(name="kid", parent=root, root=None, desc=None, dry_run=False))
            _, meta, _ = ns.read_skill(os.path.join(root, "kid"))
            self.assertTrue(meta["description"].startswith("TODO"))
        finally:
            shutil.rmtree(tmp)


class TestDeepRootDiscovery(unittest.TestCase):
    """Merged feature (from A): find skills nested deeper than one level
    under a non-skill base directory."""

    def test_find_root_skills_deep(self):
        tmp = tempfile.mkdtemp()
        try:
            deep = os.path.join(tmp, "group", "sub")
            make_skill(os.path.join(deep, "sk"), "sk", "deep skill")
            roots = ns.find_root_skills(tmp)
            self.assertEqual(len(roots), 1)
            self.assertTrue(roots[0].endswith("sk"))
        finally:
            shutil.rmtree(tmp)


class TestDescRoundtrip(unittest.TestCase):
    """v1.2.0 fix: --desc with quotes/backslashes must round-trip losslessly
    (written escaped, decoded back to the original by parse_frontmatter),
    and the injected parent routing table must show the clean text."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _init(self, name, parent=None, desc=None):
        import argparse
        return ns.cmd_init(argparse.Namespace(
            name=name, parent=parent, root=self.tmp,
            desc=desc, dry_run=False))

    def test_double_quotes_roundtrip(self):
        original = 'Handles "quoted" input. Use when double quotes appear.'
        self._init("q", desc=original)
        _, meta, err = ns.read_skill(os.path.join(self.tmp, "q"))
        self.assertIsNone(err)
        self.assertEqual(meta["description"], original)  # lossless
        self.assertNotIn("\\", meta["description"])      # no residue

    def test_backslash_roundtrip(self):
        original = 'path C:\\data mixed with "quotes".'
        self._init("b", desc=original)
        _, meta, err = ns.read_skill(os.path.join(self.tmp, "b"))
        self.assertIsNone(err)
        self.assertEqual(meta["description"], original)

    def _fill_body_todos(self, skill_dir):
        """Replace the template's body TODO lines with real text."""
        p = os.path.join(skill_dir, "SKILL.md")
        with open(p, encoding="utf-8") as f:
            lines = f.read().split("\n")
        out = []
        n = 0
        for line in lines:
            if re.match(r"^\s{4}TODO\b", line):   # the three placeholder sentences under metadata.holon-triggers
                n += 1
                out.append(["    do the real thing", "    do the other real thing", "    something else should go to " + os.path.basename(skill_dir)][n - 1])
            elif re.match(r"^\s*(?:(?:[-*>]|\d+[.)])\s*)*TODO\b", line):
                out.append("1. Real first step.")
            else:
                out.append(line)
        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(out))

    def test_quoted_desc_validates_and_injects_clean(self):
        import argparse
        self._init("parent", desc="Parent capability. Used for routing.")
        parent = os.path.join(self.tmp, "parent")
        self._init("child", parent=parent, desc='Child capability, supports "quotes".')
        text, _, _ = ns.read_skill(parent)
        self.assertIn('Child capability, supports "quotes".', text)   # clean in routing table
        self.assertNotIn('\\"', text.split(ns.MARK_OPEN, 1)[1])
        self._fill_body_todos(parent)
        self._fill_body_todos(os.path.join(parent, "child"))
        rc = ns.cmd_validate(argparse.Namespace(path=self.tmp))
        self.assertEqual(rc, 0)


class TestBug6ValidateCatchesBodyTodo(unittest.TestCase):
    """REVIEW bug6: `init --desc` fills the description but the template
    body still holds `TODO:` placeholder lines. validate used to pass such
    a half-finished skill; it must now fail and name the line."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _validate(self):
        import argparse
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = ns.cmd_validate(argparse.Namespace(path=self.tmp))
        return rc, buf.getvalue()

    def _init(self, name, desc):
        import argparse
        ns.cmd_init(argparse.Namespace(
            name=name, parent=None, root=self.tmp, desc=desc, dry_run=False))

    def test_body_todo_lines_detected(self):
        body = "# t\n\n## When\nTODO: describe the trigger.\n\n```\nTODO inside fence is ignored\n```\n- TODO: list items count too\n"
        self.assertEqual(ns.body_todo_lines(body), [4, 9])

    def test_body_todo_in_numbered_list_detected(self):
        """The scaffold writes `1. TODO: ...`; a body written as steps may leave `3) TODO` behind."""
        body = "# t\n\n1. TODO: first step.\n2. Real step.\n3) TODO later\n"
        self.assertEqual(ns.body_todo_lines(body), [3, 5])

    def test_init_with_desc_but_untouched_body_fails_validate(self):
        """A child's scaffold body is one TODO step; validate refuses it. (A root's body is
        the reading rules and has no TODO.)"""
        self._init("s", desc="A root.")
        import argparse
        ns.cmd_init(argparse.Namespace(name="kid", parent=os.path.join(self.tmp, "s"), root=None,
                                       desc="Has a description but the body is untouched.", dry_run=False))
        rc, out = self._validate()
        self.assertEqual(rc, 1)
        self.assertIn("body still contains TODO placeholders", out)

    def test_filled_body_passes_validate(self):
        self._init("s", desc="Has a description and a written body.")
        p = os.path.join(self.tmp, "s", "SKILL.md")
        with open(p, encoding="utf-8") as f:
            text = f.read()
        n = [0]
        def fill(l):
            if re.match(r"^\s{4}TODO\b", l):     # placeholder sentences under metadata.holon-triggers
                n[0] += 1
                return ["    a real task", "    another real task", "    an unrelated task should go to s"][n[0] - 1]
            return "1. Filled in." if re.match(r"^\s*(?:\d+[.)]\s*)?TODO\b", l) else l
        text = "\n".join(fill(l) for l in text.split("\n"))
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        rc, _ = self._validate()
        self.assertEqual(rc, 0)


class TestNestedInitDescSyncsParent(unittest.TestCase):
    """From v1.1.0: init --parent --desc must immediately sync the parent."""

    def test_nested_init_with_desc_syncs_parent(self):
        tmp = tempfile.mkdtemp()
        try:
            import argparse
            ns.cmd_init(argparse.Namespace(
                name="parent", parent=None, root=tmp,
                desc="Parent capability. Used for routing.", dry_run=False))
            ns.cmd_init(argparse.Namespace(
                name="child", parent=os.path.join(tmp, "parent"), root=tmp,
                desc="Child capability. For testing.", dry_run=False))
            text, _, _ = ns.read_skill(os.path.join(tmp, "parent"))
            self.assertIn("Child capability. For testing.", text)
        finally:
            shutil.rmtree(tmp)


class TestTableShowsWordsFromBelow(unittest.TestCase):
    """The organizer's route lets a parent take a sentence by a word of any skill below it.
    The routing table the agent reads must show those words, or replay checks more than the
    agent sees ("build a pitch deck" reaches office-docs only through pptx's `deck`)."""

    def setUp(self):
        import argparse
        self.tmp = tempfile.mkdtemp()
        self.root = os.path.join(self.tmp, "lib")
        self.office = os.path.join(self.root, "office-docs")
        mk = lambda name, parent, desc: ns.cmd_init(argparse.Namespace(
            name=name, parent=parent, root=self.tmp, desc=desc, dry_run=False, bare=True))
        with contextlib.redirect_stdout(io.StringIO()):
            mk("lib", None, None)
            mk("office-docs", self.root, "Use for office files: covers Word, PDF; excludes theme")
            mk("pptx", self.office, "Use for slides: covers deck, slides, word")
            mk("form", os.path.join(self.office, "pptx"), "Use for speaker notes: covers notes")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_descendant_covers_skip_own_words_and_keep_order(self):
        self.assertEqual(ns.descendant_covers(self.office), ["deck", "slides", "notes"])

    def test_root_table_lists_grandchild_words_after_init(self):
        text, _, _ = ns.read_skill(self.root)
        self.assertIn("also takes, through its sub-skills: deck, slides, notes", text)

    def test_leaf_line_has_no_extra_line(self):
        text, _, _ = ns.read_skill(os.path.join(self.office, "pptx"))
        self.assertNotIn("also takes", text)

    def test_ancestor_sync_does_not_need_relpath(self):
        """On Windows CI the checkout is on D: and the temp folder on C:; os.path.relpath
        between them raises ValueError. Ancestor sync must not depend on it."""
        import argparse
        real = os.path.relpath

        def cross_drive(*a, **k):
            raise ValueError("path is on mount 'C:', start on mount 'D:'")
        os.path.relpath = cross_drive
        try:
            with contextlib.redirect_stdout(io.StringIO()) as out:
                rc = ns.cmd_init(argparse.Namespace(
                    name="speaker", parent=os.path.join(self.office, "pptx"), root=self.tmp,
                    desc="Use for talks: covers talk track", dry_run=False, bare=True))
        finally:
            os.path.relpath = real
        self.assertEqual(rc, 0)
        self.assertIn("also synced", out.getvalue())
        text, _, _ = ns.read_skill(self.root)
        self.assertIn("talk track", text)

    def test_tree_stays_in_sync_after_init(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            ns.cmd_sync(__import__("argparse").Namespace(path=self.root, dry_run=True, auto_append=True))
        self.assertIn("done: 0 file(s) would be updated", out.getvalue())


class TestInjectUnit(unittest.TestCase):
    def test_no_marker_status(self):
        text, status = ns.inject("plain text", "BLOCK")
        self.assertEqual(status, "no-marker")

    def test_replace_between_markers(self):
        src = "head\n%s\nold\n%s\ntail" % (ns.MARK_OPEN, ns.MARK_CLOSE)
        out, status = ns.inject(src, "NEW")
        self.assertEqual(status, "updated")
        self.assertIn("NEW", out)
        self.assertNotIn("old", out)
        self.assertTrue(out.startswith("head"))
        self.assertTrue(out.endswith("tail"))

    def test_skip_markers_in_fenced_code(self):
        """Markers inside fenced code blocks are documentation examples and must not be injected into."""
        src = (
            "intro\n"
            "```\n%s\nEXAMPLE\n%s\n```\n"
            "middle\n"
            "%s\nold\n%s\n"
        ) % (ns.MARK_OPEN, ns.MARK_CLOSE, ns.MARK_OPEN, ns.MARK_CLOSE)
        out, status = ns.inject(src, "NEW")
        self.assertEqual(status, "updated")
        self.assertIn("EXAMPLE", out)       # the code-block example is kept verbatim
        self.assertNotIn("old", out)        # the real block is rewritten
        self.assertIn("NEW", out)
        # idempotent: injecting again changes nothing
        out2, status2 = ns.inject(out, "NEW")
        self.assertEqual(status2, "unchanged")
        self.assertEqual(out, out2)

    def test_skip_inline_code_markers(self):
        """Inline code `<!-- sub-skills -->` is documentation and must not be injected into."""
        src = (
            "Use `%s` / `%s` to mark the injection point.\n\n"
            "%s\nold\n%s\n"
        ) % (ns.MARK_OPEN, ns.MARK_CLOSE, ns.MARK_OPEN, ns.MARK_CLOSE)
        out, status = ns.inject(src, "NEW")
        self.assertEqual(status, "updated")
        self.assertIn("Use `%s` / `%s` to mark the injection point." % (ns.MARK_OPEN, ns.MARK_CLOSE), out)
        self.assertNotIn("old", out)
        self.assertIn("NEW", out)

    def test_only_doc_examples_means_no_marker(self):
        """When the only markers are documentation examples, there is no real marker pair."""
        src = "```\n%s\n%s\n```\nNo real marker pair in the body.\n" % (ns.MARK_OPEN, ns.MARK_CLOSE)
        _, status = ns.inject(src, "NEW")
        self.assertEqual(status, "no-marker")

    def test_empty_block_clears_stale_table(self):
        """An empty block resets to an empty marker pair, clearing a stale routing table."""
        src = "head\n%s\nSTALE TABLE\n%s\ntail" % (ns.MARK_OPEN, ns.MARK_CLOSE)
        out, status = ns.inject(src, "")
        self.assertEqual(status, "updated")
        self.assertNotIn("STALE TABLE", out)
        self.assertIn("%s\n%s" % (ns.MARK_OPEN, ns.MARK_CLOSE), out)
        # idempotent
        out2, status2 = ns.inject(out, "")
        self.assertEqual(status2, "unchanged")
        self.assertEqual(out, out2)


class TestSyncClearsAfterChildRemoval(unittest.TestCase):
    """After every sub-skill is removed, sync must clear the stale routing table and validate must detect it."""

    def setUp(self):
        import argparse
        self.argparse = argparse
        self.tmp = tempfile.mkdtemp()
        self.p = os.path.join(self.tmp, "p")
        make_skill(self.p, "p", "parent")
        make_skill(os.path.join(self.p, "c"), "c", "child")
        ns.cmd_sync(argparse.Namespace(path=self.tmp, dry_run=False, auto_append=True))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _read_p(self):
        with open(os.path.join(self.p, "SKILL.md"), encoding="utf-8") as f:
            return f.read()

    def test_stale_table_detected_and_cleared(self):
        A = self.argparse
        self.assertIn("**c**", self._read_p())      # confirm it was injected first
        shutil.rmtree(os.path.join(self.p, "c"))
        # validate must detect the stale table
        rc = ns.cmd_validate(A.Namespace(path=self.tmp))
        self.assertNotEqual(rc, 0)
        # sync must clear it
        rc = ns.cmd_sync(A.Namespace(path=self.tmp, dry_run=False, auto_append=True))
        self.assertEqual(rc, 0)
        text = self._read_p()
        self.assertNotIn("**c**", text)
        self.assertNotIn(ns.BLOCK_TITLE, text)
        self.assertIn(ns.MARK_OPEN, text)           # marker pair is kept for future children
        # validate passes once cleared
        rc = ns.cmd_validate(A.Namespace(path=self.tmp))
        self.assertEqual(rc, 0)


class TestGroupsFile(unittest.TestCase):
    """A groups.md next to the parent SKILL.md sections the routing table; no sub-skill moves."""

    def setUp(self):
        import argparse
        self.argparse = argparse
        self.tmp = tempfile.mkdtemp()
        self.p = os.path.join(self.tmp, "p")
        make_skill(self.p, "p", "parent skill")
        for n in ("memo", "sheet", "banner", "motion", "aside"):
            make_skill(os.path.join(self.p, n), n, "does " + n)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _groups(self, text):
        with open(os.path.join(self.p, ns.GROUPS_FILE), "w", encoding="utf-8") as f:
            f.write(text)

    def _sync(self):
        return ns.cmd_sync(self.argparse.Namespace(path=self.tmp, dry_run=False, auto_append=True))

    def _read_p(self):
        with open(os.path.join(self.p, "SKILL.md"), encoding="utf-8") as f:
            return f.read()

    def test_sections_follow_groups_file_and_rest_goes_last(self):
        self._groups("Files: sheet, memo\nDesign: banner, motion\n")
        self._sync()
        text = self._read_p()
        self.assertIn("### Files", text)
        self.assertIn("### Design", text)
        self.assertIn("### Other", text)
        # sections follow file order; members follow the order written (authors can put common ones first)
        self.assertLess(text.index("### Files"), text.index("**sheet**"))
        self.assertLess(text.index("**sheet**"), text.index("**memo**"))
        self.assertLess(text.index("**memo**"), text.index("### Design"))
        self.assertLess(text.index("### Design"), text.index("**banner**"))
        self.assertLess(text.index("### Other"), text.index("**aside**"))
        self.assertEqual(text.count("**memo**"), 1)

    def test_child_in_two_groups_is_listed_twice_but_lives_once(self):
        self._groups("Files: sheet, memo, banner\nDesign: banner, motion\n")
        self._sync()
        text = self._read_p()
        self.assertEqual(text.count("**banner**"), 2)
        self.assertEqual(sorted(os.listdir(self.p)).count("banner"), 1)

    def test_sync_is_idempotent_with_groups(self):
        self._groups("Files: sheet, memo\n")
        self._sync()
        first = self._read_p()
        self._sync()
        self.assertEqual(first, self._read_p())
        rc = ns.cmd_validate(self.argparse.Namespace(path=self.tmp))
        self.assertEqual(rc, 0)

    def test_unknown_member_fails_validate(self):
        self._groups("Files: sheet, ledger-x\n")
        self._sync()
        rc = ns.cmd_validate(self.argparse.Namespace(path=self.tmp))
        self.assertEqual(rc, 1)

    def test_bad_line_and_duplicate_group_fail_validate(self):
        self._groups("Files sheet memo\n")
        self._sync()
        self.assertEqual(ns.cmd_validate(self.argparse.Namespace(path=self.tmp)), 1)
        self._groups("Files: sheet\nFiles: memo\n")
        self._sync()
        self.assertEqual(ns.cmd_validate(self.argparse.Namespace(path=self.tmp)), 1)

    def test_tree_shows_group_titles(self):
        import io, contextlib
        self._groups("Files: sheet, memo\n")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ns.cmd_tree(self.argparse.Namespace(path=self.tmp))
        out = buf.getvalue()
        self.assertIn("[Files]", out)
        self.assertIn("[Other]", out)
        self.assertLess(out.index("[Files]"), out.index("sheet —"))
        self.assertLess(out.index("[Other]"), out.index("motion —"))

    def test_removing_groups_file_flattens_table_again(self):
        self._groups("Files: sheet, memo\n")
        self._sync()
        os.remove(os.path.join(self.p, ns.GROUPS_FILE))
        rc = ns.cmd_validate(self.argparse.Namespace(path=self.tmp))
        self.assertEqual(rc, 1)  # table still has section headings -> out of sync
        self._sync()
        text = self._read_p()
        self.assertNotIn("### ", text)
        self.assertEqual(ns.cmd_validate(self.argparse.Namespace(path=self.tmp)), 0)


class TestConsoleEncoding(unittest.TestCase):
    """validate prints \u2713 / \u2717 and tree prints box-drawing characters. On a
    console or pipe whose encoding cannot represent them (cp1252 on Windows is
    the common case) the command must degrade to '?' and keep its exit code,
    not die with UnicodeEncodeError."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        make_skill(os.path.join(self.tmp, "p"), "p", "parent desc")
        make_skill(os.path.join(self.tmp, "p", "c"), "c", "child desc", markers=False)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _run(self, *args):
        import subprocess
        env = dict(os.environ, PYTHONIOENCODING="cp1252")
        script = os.path.join(os.path.dirname(__file__), "..", "scripts", "holon.py")
        return subprocess.run([sys.executable, script] + list(args),
                              capture_output=True, env=env)

    def test_validate_survives_cp1252_stdout(self):
        self._run("sync", self.tmp)
        r = self._run("validate", self.tmp)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn(b"UnicodeEncodeError", r.stderr)
        self.assertIn(b"OK: 2 skill(s)", r.stdout)

    def test_tree_survives_cp1252_stdout(self):
        r = self._run("tree", self.tmp)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn(b"UnicodeEncodeError", r.stderr)
        self.assertIn(b"child desc", r.stdout)


class TestAgentSkillsSpecForm(unittest.TestCase):
    """The Agent Skills spec (agentskills.io/specification) allows six frontmatter fields and
    a string-to-string `metadata` map. holon's two fields live there. The parser reads both
    the spec form and the pre-1.0 top-level form; validate reports the old form; migrate
    rewrites it."""

    SPEC = ('---\nname: docx\ndescription: "Use when x: covers Word"\nmetadata:\n'
            '  holon-triggers: |\n    write the report in Word\n    fix this docx\n    draw a poster should go to /\n'
            '  holon-archive-count: "3"\n---\n\n# docx\n\n1. Step.\n')
    OLD = ('---\nname: docx\ndescription: "Use when x: covers Word"\narchive_count: 3\ntriggers:\n'
           '  - write the report in Word\n  - fix this docx\n  - draw a poster should go to /\n---\n\n# docx\n\n1. Step.\n')

    def test_spec_form_parses_to_the_same_meta_as_old_form(self):
        a, body_a, err_a = ns.split_frontmatter(self.SPEC)
        b, body_b, err_b = ns.split_frontmatter(self.OLD)
        self.assertIsNone(err_a); self.assertIsNone(err_b)
        self.assertEqual(a["triggers"], b["triggers"])
        self.assertEqual(a["archive_count"], str(b["archive_count"]))
        self.assertEqual(body_a, body_b)
        self.assertEqual(a["metadata"]["holon-archive-count"], "3")

    def test_old_form_is_reported_and_spec_form_is_not(self):
        a, _, _ = ns.split_frontmatter(self.SPEC)
        b, _, _ = ns.split_frontmatter(self.OLD)
        self.assertEqual(ns.spec_field_problems(a, "docx"), [])
        probs = ns.spec_field_problems(b, "docx")
        self.assertEqual(len(probs), 2)
        self.assertTrue(all("migrate" in s for s in probs))

    def test_migrate_text_rewrites_old_form_and_is_idempotent(self):
        new, changed = ns.migrate_text(self.OLD)
        self.assertTrue(changed)
        m, _, err = ns.split_frontmatter(new)
        self.assertIsNone(err)
        self.assertEqual(ns.spec_field_problems(m, "docx"), [])
        self.assertEqual(m["triggers"], ["write the report in Word", "fix this docx", "draw a poster should go to /"])
        self.assertEqual(m["archive_count"], "3")
        again, changed2 = ns.migrate_text(new)
        self.assertFalse(changed2)
        self.assertEqual(again, new)

    def test_name_rules_from_the_spec(self):
        for bad in ("Docx", "-docx", "docx-", "doc--x", "doc x"):
            self.assertTrue(ns.spec_field_problems({"name": bad, "description": "d"}, bad), bad)
        self.assertEqual(ns.spec_field_problems({"name": "docx", "description": "d"}, "other"),
                         ["name 'docx' does not match its directory 'other'"])

    def test_init_writes_spec_form_that_validate_accepts_once_filled(self):
        tmp = tempfile.mkdtemp()
        try:
            root = os.path.join(tmp, "lib")
            self.assertEqual(ns.main(["init", "lib", "--root", tmp, "--desc", "Use for every task: covers task"]), 0)
            self.assertEqual(ns.main(["init", "docx", "--parent", root, "--desc", "Use when x: covers Word"]), 0)
            text = open(os.path.join(root, "docx", "SKILL.md"), encoding="utf-8").read()
            self.assertIn("metadata:\n  holon-triggers: |\n    TODO", text)
            self.assertNotIn("\ntriggers:", text)
            meta, _, _ = ns.split_frontmatter(text)
            self.assertEqual(ns.spec_field_problems(meta, "docx"), [])
        finally:
            shutil.rmtree(tmp)


class TestInstall(unittest.TestCase):
    """`install` is the one step that replaces clone, choose, copy, rename, check. It copies
    this package's tree (or a given one) into a skills directory, fills in the tool folders a
    tree needs where it lands, and validates the copy."""
    PKG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        ns.remove_tree(self.tmp)

    def test_default_source_is_this_package_and_the_copy_validates(self):
        rc = ns.main(["install", "--to", self.tmp])
        self.assertEqual(rc, 0)
        dest = os.path.join(self.tmp, "holon")
        for p in ("SKILL.md", "scripts/holon.py", "organizer/scripts/organizer_cli.py", "editing/SKILL.md"):
            self.assertTrue(os.path.isfile(os.path.join(dest, p)), p)
        for absent in ("examples", "tests", ".claude-plugin", "organizer/tests"):
            self.assertFalse(os.path.exists(os.path.join(dest, absent)), absent)
        self.assertEqual(ns.cmd_validate(argparse_ns(path=dest)), 0)

    def test_as_renames_and_a_second_install_refuses(self):
        self.assertEqual(ns.main(["install", "--to", self.tmp, "--as", "lib"]), 0)
        self.assertTrue(os.path.isfile(os.path.join(self.tmp, "lib", "SKILL.md")))
        self.assertEqual(ns.main(["install", "--to", self.tmp, "--as", "lib"]), 1)

    def test_host_names_resolve_under_home(self):
        home = os.path.expanduser("~")
        self.assertEqual(ns.install_dir_for("claude"), os.path.join(home, ".claude", "skills"))
        self.assertEqual(ns.install_dir_for("codex"), os.path.join(home, ".agents", "skills"))
        self.assertEqual(ns.install_dir_for(None), os.path.join(home, ".agents", "skills"))
        self.assertEqual(ns.install_dir_for(None, "~/x"), os.path.join(home, "x"))
        self.assertEqual(ns.install_dir_for("codex", project=True), os.path.join(os.getcwd(), ".agents", "skills"))
        with self.assertRaises(ValueError):
            ns.install_dir_for("emacs")


    def test_a_tree_kept_beside_the_package_gets_the_tools_it_points_at(self):
        # A tree whose organizer/ and editing/ are header-only stubs, the way a library kept
        # inside a larger checkout carries them. install must fill them in from this package.
        example = os.path.join(self.tmp, "src", "lib")
        os.makedirs(os.path.join(self.tmp, "src"))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(ns.main(["init", "lib", "--root", os.path.join(self.tmp, "src"), "--bare"]), 0)
        pkg_skill = lambda d: ns.read_skill(os.path.join(self.PKG, d))[0].split("\n---\n", 1)[0] + "\n---\n"
        for part in ("organizer", "editing"):
            os.makedirs(os.path.join(example, part))
            with open(os.path.join(example, part, "SKILL.md"), "w", encoding="utf-8") as f:
                f.write(pkg_skill(part) + "\n# %s\n\nKept beside the package: ../../%s/SKILL.md\n" % (part, part))
        with contextlib.redirect_stdout(io.StringIO()):
            ns.cmd_sync(argparse_ns(path=example, dry_run=False, auto_append=True))
        self.assertEqual(ns.main(["install", example, "--to", self.tmp, "--as", "holon"]), 0)
        dest = os.path.join(self.tmp, "holon")
        self.assertTrue(os.path.isfile(os.path.join(dest, "scripts", "holon.py")))
        self.assertTrue(os.path.isfile(os.path.join(dest, "organizer", "scripts", "organizer_cli.py")))
        text, _, _ = ns.read_skill(os.path.join(dest, "editing"))
        self.assertIn("scripts/holon.py", text)
        self.assertNotIn("../../", text)
        self.assertFalse(list(_walk_named(dest, "__pycache__")))

    def test_not_a_tree_and_dry_run(self):
        self.assertEqual(ns.main(["install", self.tmp, "--to", self.tmp]), 1)
        self.assertEqual(ns.main(["install", "--to", self.tmp, "--dry-run"]), 0)
        self.assertEqual(os.listdir(self.tmp), [])

    def _repo(self):
        repo = os.path.abspath(os.path.join(self.PKG, ".."))
        if not shutil.which("git") or not os.path.isdir(os.path.join(repo, ".git")):
            self.skipTest("git and a git checkout are required")
        return repo

    def test_git_url_source_is_cloned_and_the_package_found_inside(self):
        """The repository root is not a skill; the one child that carries scripts/holon.py is
        the tree. A file:// URL exercises the clone path without a network."""
        rc = ns.main(["install", Path(self._repo()).as_uri(), "--to", self.tmp])
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.isfile(os.path.join(self.tmp, "holon", "scripts", "holon.py")))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "holon", "examples")))

    def test_url_with_path_installs_that_folder_and_a_plain_skill_gets_no_tools(self):
        rc = ns.main(["install", Path(self._repo()).as_uri(), "--path", "holon/editing", "--to", self.tmp])
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.isfile(os.path.join(self.tmp, "editing", "SKILL.md")))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "editing", "organizer")))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "editing", "scripts")))

    def test_archive_url_is_unpacked_with_the_stdlib(self):
        import http.server
        import socketserver
        import threading
        import zipfile
        site = os.path.join(self.tmp, "site")
        os.makedirs(site)
        # An archive the way GitHub makes them: one wrapping folder, the repository inside.
        with zipfile.ZipFile(os.path.join(site, "repo.zip"), "w") as z:
            for dirpath, dirnames, files in os.walk(self.PKG):
                dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__", "examples", "tests")]
                for f in files:
                    full = os.path.join(dirpath, f)
                    z.write(full, os.path.join("repo-main", "holon", os.path.relpath(full, self.PKG)))

        class H(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *a, **k):
                super().__init__(*a, directory=site, **k)

            def log_message(self, *a):
                pass
        srv = socketserver.TCPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            url = "http://127.0.0.1:%d/repo.zip" % srv.server_address[1]
            dest = os.path.join(self.tmp, "out")
            self.assertEqual(ns.main(["install", url, "--to", dest]), 0)
            self.assertTrue(os.path.isfile(os.path.join(dest, "holon", "organizer", "SKILL.md")))
        finally:
            srv.shutdown()
            srv.server_close()

    @unittest.skipUnless(shutil.which("git"), "git is not installed")
    def test_a_repository_with_many_skills_and_no_package_asks_for_path(self):
        import contextlib
        import io
        import subprocess
        repo = os.path.join(self.tmp, "many")
        for n in ("alpha", "beta"):
            make_skill(os.path.join(repo, n), n, "Use when %s: covers %s" % (n, n))
        g = ["git", "-C", repo, "-c", "user.email=t@t", "-c", "user.name=t"]
        subprocess.run(["git", "init", "-q", repo], check=True)
        subprocess.run(g + ["add", "."], check=True)
        subprocess.run(g + ["commit", "-qm", "x"], check=True)
        out = os.path.join(self.tmp, "out")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = ns.main(["install", Path(repo).as_uri(), "--to", out])
        self.assertEqual(rc, 1)
        self.assertIn("--path", buf.getvalue())
        self.assertIn("alpha, beta", buf.getvalue())
        self.assertFalse(os.path.exists(out))

    def test_init_root_from_the_cli_brings_the_tools_and_is_clean(self):
        self.assertEqual(ns.main(["init", "mylib", "--root", self.tmp]), 0)
        root = os.path.join(self.tmp, "mylib")
        self.assertTrue(os.path.isfile(os.path.join(root, "scripts", "holon.py")))
        self.assertEqual(ns.cmd_validate(argparse_ns(path=root)), 0)
        text, _, _ = ns.read_skill(root)
        self.assertIn("**organizer** (`organizer/`)", text)
        self.assertEqual(ns.main(["init", "bare", "--root", self.tmp, "--bare"]), 0)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "bare", "scripts")))



class TestFunctionalRegressions(unittest.TestCase):
    """Small, real trees exercise write safety as well as successful CLI results."""

    def setUp(self):
        from pathlib import Path
        self.tmp = Path(tempfile.mkdtemp())
        from unittest import mock
        env = mock.patch.dict(os.environ, HOME=str(self.tmp), USERPROFILE=str(self.tmp))
        env.start()
        self.addCleanup(env.stop)
        self.src = self.tmp / "source" / "demo"
        make_skill(str(self.src), "demo", "Use for a demo task", body="1. Do the task.")
        self.dest = self.tmp / "installed"

    def tearDown(self):
        shutil.rmtree(str(self.tmp))

    def cli(self, *args):
        with contextlib.redirect_stdout(io.StringIO()):
            return ns.main(list(map(str, args)))

    def link(self, target, path, directory=False):
        try:
            path.symlink_to(target, target_is_directory=directory)
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links are unavailable")

    def test_custom_install_directory_is_normalized_on_windows(self):
        import ntpath
        from unittest import mock
        home = r"C:\Users\reader\isolated-home"
        with mock.patch.dict(os.environ, USERPROFILE=home), mock.patch.object(ns.os, "path", ntpath):
            self.assertEqual(ns.install_dir_for(None, "~/x"), ntpath.join(home, "x"))
            self.assertEqual(ns.install_dir_for(None, "folder/../chosen"), "chosen")

    def test_git_cleanup_handles_windows_readonly_files(self):
        import errno
        import stat
        from unittest import mock
        tree = self.tmp / "git-fixture"
        obj = tree / ".git" / "objects" / "ab" / "object"
        obj.parent.mkdir(parents=True)
        obj.write_bytes(b"git object fixture")
        obj.chmod(stat.S_IRUSR)
        unlink = os.unlink
        denied = []

        def windows_unlink(path, *args, **kwargs):
            mode = os.stat(path, dir_fd=kwargs.get("dir_fd"), follow_symlinks=False).st_mode
            if not mode & stat.S_IWUSR:
                denied.append(str(path))
                raise PermissionError(errno.EACCES, "Windows read-only file", str(path))
            return unlink(path, *args, **kwargs)

        with mock.patch.object(ns.os, "unlink", side_effect=windows_unlink):
            ns.remove_tree(str(tree))
        self.assertTrue(denied, "the simulated Windows denial must actually be exercised")
        self.assertFalse(tree.exists())

    def test_cleanup_does_not_hide_other_permission_errors(self):
        import errno
        from unittest import mock
        file = self.tmp / "writable.txt"
        file.write_text("keep", encoding="utf-8")
        denied = PermissionError(errno.EACCES, "unrelated access denial", str(file))

        def fail_tree(path, **kwargs):
            if "onexc" in kwargs:
                kwargs["onexc"](os.unlink, str(file), denied)
            else:
                kwargs["onerror"](os.unlink, str(file), (PermissionError, denied, None))

        with mock.patch.object(ns.shutil, "rmtree", side_effect=fail_tree):
            with self.assertRaises(PermissionError):
                ns.remove_tree(str(self.tmp))
        self.assertTrue(file.is_file())

    def test_generated_files_use_lf_with_windows_default_newlines(self):
        from unittest import mock
        real_open = open

        def windows_open(file, mode="r", *args, **kwargs):
            if "w" in mode and "b" not in mode and kwargs.get("newline") is None:
                kwargs["newline"] = "\r\n"
            return real_open(file, mode, *args, **kwargs)

        with mock.patch.object(ns, "open", side_effect=windows_open, create=True):
            self.assertEqual(self.cli("init", "portable", "--root", self.dest, "--bare"), 0)
            self.assertEqual(self.cli("init", "child", "--parent", self.dest / "portable"), 0)
        for file in self.dest.rglob("*.md"):
            self.assertNotIn(b"\r\n", file.read_bytes(), str(file))

    def test_invalid_names_never_write_outside_destination(self):
        original = (self.src / "SKILL.md").read_text(encoding="utf-8")
        for name in ("../escaped", str(self.tmp / "absolute"), "bad/name", "Bad", "bad--name"):
            with self.subTest(name=name):
                (self.src / "SKILL.md").write_text(original.replace("name: demo", "name: " + name), encoding="utf-8")
                self.assertEqual(self.cli("install", self.src, "--to", self.dest), 1)
                self.assertFalse(self.dest.exists())
                self.assertFalse((self.tmp / "escaped").exists())
                self.assertFalse((self.tmp / "absolute").exists())

    def test_init_rejects_invalid_name_and_multiline_description(self):
        for name in ("../escaped", "bad/name", "Bad"):
            self.assertEqual(self.cli("init", name, "--root", self.dest), 1)
        self.assertEqual(self.cli("init", "demo", "--root", self.dest, "--desc", "first\nsecond"), 1)
        self.assertFalse(self.dest.exists())

    def test_rename_updates_only_installed_frontmatter(self):
        original = (self.src / "SKILL.md").read_bytes()
        self.assertEqual(self.cli("install", self.src, "--to", self.dest, "--as", "renamed"), 0)
        _, meta, err = ns.read_skill(str(self.dest / "renamed"))
        self.assertIsNone(err)
        self.assertEqual(ns.spec_field_problems(meta, "renamed"), [])
        self.assertEqual((self.src / "SKILL.md").read_bytes(), original)

    def test_failed_force_preserves_old_install(self):
        self.assertEqual(self.cli("install", self.src, "--to", self.dest), 0)
        old = self.dest / "demo" / "user-data.txt"
        old.write_text("keep this", encoding="utf-8")
        make_skill(str(self.src), "demo", "TODO: unfinished")
        self.assertEqual(self.cli("install", self.src, "--to", self.dest, "--force"), 1)
        self.assertEqual(old.read_text(encoding="utf-8"), "keep this")

    def test_force_from_installed_copy_preserves_source(self):
        self.assertEqual(self.cli("install", self.src, "--to", self.dest), 0)
        source = self.dest / "demo"
        (source / "user-data.txt").write_text("keep this", encoding="utf-8")
        self.assertEqual(self.cli("install", source, "--to", self.dest, "--force"), 0)
        self.assertEqual((source / "user-data.txt").read_text(encoding="utf-8"), "keep this")

    def test_install_into_source_is_rejected_without_recursive_copy(self):
        self.assertEqual(self.cli("install", self.src, "--to", self.src / "nested"), 1)
        self.assertFalse((self.src / "nested").exists())

    def test_install_refuses_external_file_links(self):
        outside = self.tmp / "outside.txt"
        outside.write_text("private fixture", encoding="utf-8")
        self.link(outside, self.src / "linked.txt")
        self.assertEqual(self.cli("install", self.src, "--to", self.dest), 1)
        self.assertFalse(self.dest.exists())

    def test_internal_file_link_is_copied_as_a_regular_file(self):
        (self.src / "reference.txt").write_text("reference", encoding="utf-8")
        self.link("reference.txt", self.src / "linked.txt")
        self.assertEqual(self.cli("install", self.src, "--to", self.dest), 0)
        copied = self.dest / "demo" / "linked.txt"
        self.assertFalse(copied.is_symlink())
        self.assertEqual(copied.read_text(encoding="utf-8"), "reference")

    def test_sync_and_migrate_refuse_external_skill_links(self):
        outside = self.tmp / "outside"
        make_skill(str(outside), "outside", "external skill", body="Keep this.")
        self.link(outside, self.src / "outside", directory=True)
        before = {p: p.read_bytes() for p in (self.src / "SKILL.md", outside / "SKILL.md")}
        for command in ("sync", "migrate", "validate"):
            self.assertEqual(self.cli(command, self.src), 1)
        for p, data in before.items():
            self.assertEqual(p.read_bytes(), data)

    def test_malformed_fields_report_errors_instead_of_crashing(self):
        for header in ("name:\n  - demo\ndescription: task", "name: demo\ndescription:\n  - task",
                       "name: demo\ndescription: task\nmetadata: invalid", "name: demo\nname: other\ndescription: task"):
            with self.subTest(header=header):
                (self.src / "SKILL.md").write_text("---\n" + header + "\n---\nWork.\n", encoding="utf-8")
                self.assertEqual(self.cli("validate", self.src), 1)

    def test_invalid_utf8_is_a_validation_error(self):
        (self.src / "SKILL.md").write_bytes(b"---\nname: demo\ndescription: \xff\n---\n")
        self.assertEqual(self.cli("validate", self.src), 1)

    def test_empty_tree_does_not_pass_validation(self):
        self.dest.mkdir()
        self.assertEqual(self.cli("validate", self.dest), 1)

    def test_documented_claude_code_alias_is_accepted(self):
        self.assertEqual(self.cli("install", self.src, "--host", "claude-code", "--to", self.dest), 0)

    def test_remote_path_must_stay_inside_checkout(self):
        from unittest import mock
        checkout = self.tmp / "checkout"
        checkout.mkdir()
        with mock.patch.object(ns, "_fetch", return_value=str(checkout)):
            self.assertEqual(self.cli("install", "https://example.invalid/repo.git", "--path", self.src,
                                      "--to", self.dest), 1)
        self.assertFalse(self.dest.exists())

    def test_install_does_not_execute_supplied_checker(self):
        pkg = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        shutil.rmtree(str(self.src))
        shutil.copytree(pkg, str(self.src), ignore=shutil.ignore_patterns("tests", "__pycache__"))
        marker = self.tmp / "executed.txt"
        (self.src / "organizer/scripts/organizer_cli.py").write_text(
            "from pathlib import Path\nPath(%r).write_text('executed')\n" % str(marker), encoding="utf-8")
        self.assertEqual(self.cli("install", self.src, "--to", self.dest), 0)
        self.assertFalse(marker.exists())

    def test_sync_rejects_malformed_child_without_changing_parent(self):
        child = self.src / "child"
        make_skill(str(child), "child", "child task")
        (child / "SKILL.md").write_text("---\nname: child\ndescription:\n  - bad type\n---\n", encoding="utf-8")
        before = (self.src / "SKILL.md").read_bytes()
        self.assertEqual(self.cli("sync", self.src), 1)
        self.assertEqual((self.src / "SKILL.md").read_bytes(), before)

    def test_migrate_preflights_all_files_before_writing(self):
        (self.src / "SKILL.md").write_text(TestAgentSkillsSpecForm.OLD, encoding="utf-8")
        child = self.src / "child"
        make_skill(str(child), "child", "task")
        (child / "SKILL.md").write_bytes(b"\xff")
        before = (self.src / "SKILL.md").read_bytes()
        self.assertEqual(self.cli("migrate", self.src), 1)
        self.assertEqual((self.src / "SKILL.md").read_bytes(), before)

    def test_multi_destination_failure_rolls_back_every_copy(self):
        from unittest import mock
        for error in (OSError, KeyboardInterrupt):
            with self.subTest(error=error.__name__):
                base = self.tmp / error.__name__
                dests = [base / "a/demo", base / "b/demo"]
                for dest in dests:
                    make_skill(str(dest), "demo", "old version")
                    (dest / "user-data.txt").write_text("keep this", encoding="utf-8")
                replace = os.replace

                def fail_second(source, target):
                    if os.path.basename(source) == "new" and str(target) == str(dests[1]):
                        raise error("injected publication failure")
                    return replace(source, target)

                with mock.patch.object(ns.os, "replace", side_effect=fail_second):
                    with self.assertRaises(error):
                        ns._publish_install(str(self.src), list(map(str, dests)))
                for dest in dests:
                    self.assertEqual((dest / "user-data.txt").read_text(encoding="utf-8"), "keep this")
                    self.assertEqual(sorted(p.name for p in dest.parent.iterdir()), ["demo"])

    def test_non_skill_target_leaves_other_installs_untouched(self):
        from unittest import mock
        dirs = [str(self.tmp / "a"), str(self.tmp / "b")]
        make_skill(os.path.join(dirs[0], "demo"), "demo", "old version")
        self.tmp.joinpath("b/demo").mkdir(parents=True)
        before = self.tmp.joinpath("a/demo/SKILL.md").read_bytes()
        with mock.patch.object(ns, "plan_install", return_value=(dirs, {}, [], [])):
            self.assertEqual(self.cli("install", self.src, "--force"), 1)
        self.assertEqual(self.tmp.joinpath("a/demo/SKILL.md").read_bytes(), before)

    def test_linked_install_points_at_published_destination(self):
        from unittest import mock
        dirs = [str(self.tmp / "a"), str(self.tmp / "b")]
        with mock.patch.object(ns, "plan_install", return_value=(dirs, {}, [], [])):
            self.assertEqual(self.cli("install", self.src, "--link"), 0)
        self.assertEqual(self.tmp.joinpath("a/demo/SKILL.md").read_bytes(),
                         self.tmp.joinpath("b/demo/SKILL.md").read_bytes())

    def test_legacy_tar_fallback_rejects_escaping_entries(self):
        import tarfile
        from unittest import mock
        for name, kind in (("../escaped.txt", tarfile.REGTYPE), ("link", tarfile.SYMTYPE)):
            with self.subTest(name=name):
                archive = self.tmp / "unsafe.tar.gz"
                with tarfile.open(str(archive), "w:gz") as tar:
                    member = tarfile.TarInfo(name)
                    member.type = kind
                    member.linkname = "../escaped.txt" if kind == tarfile.SYMTYPE else ""
                    tar.addfile(member)
                # Exercise the old-Python branch without changing the stdlib module.
                with mock.patch.object(ns, "hasattr", return_value=False, create=True):
                    self.assertEqual(self.cli("install", archive.as_uri(), "--to", self.dest), 1)
                self.assertFalse(self.dest.exists())

    def test_legacy_tar_fallback_still_installs_regular_files(self):
        import tarfile
        from unittest import mock
        archive = self.tmp / "safe.tar.gz"
        with tarfile.open(str(archive), "w:gz") as tar:
            tar.add(str(self.src), arcname="demo")
        with mock.patch.object(ns, "hasattr", return_value=False, create=True):
            self.assertEqual(self.cli("install", archive.as_uri(), "--to", self.dest), 0)
        self.assertTrue((self.dest / "demo/SKILL.md").is_file())

    def test_migrate_dry_run_then_idempotent_conversion(self):
        f = self.src / "SKILL.md"
        f.write_text(TestAgentSkillsSpecForm.OLD, encoding="utf-8")
        before = f.read_bytes()
        self.assertEqual(self.cli("migrate", self.src, "--dry-run"), 0)
        self.assertEqual(f.read_bytes(), before)
        self.assertEqual(self.cli("migrate", self.src), 0)
        converted = f.read_bytes()
        self.assertEqual(self.cli("migrate", self.src), 0)
        self.assertEqual(f.read_bytes(), converted)


class TestWriteSafety(unittest.TestCase):
    """Real filesystem regressions; injected failures do not depend on root/Windows permissions."""

    def setUp(self):
        from unittest import mock
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(ns.remove_tree, str(self.tmp))
        env = mock.patch.dict(os.environ, HOME=str(self.tmp), USERPROFILE=str(self.tmp))
        env.start()
        self.addCleanup(env.stop)
        self.src = self.tmp / "flat" / "alpha"
        self.other = self.tmp / "flat" / "beta"
        self.root = self.tmp / "lib"
        for p in (self.src, self.other, self.root):
            make_skill(p, p.name, "Use for %s: covers %s" % (p.name, p.name), body="1. Work.")
        self.plan = self.tmp / "plan.txt"
        self.plan.write_text("flat/alpha -> lib/first\nflat/beta -> lib/second\n", encoding="utf-8")
        self.dest = self.tmp / "installed"
        self.backups = self.tmp / ".holon-backups"

    def cli(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            rc = ns.main(list(map(str, args)))
        return rc, out.getvalue()

    def snapshot(self, *roots):
        result = {}
        for root in roots:
            for p in sorted(root.rglob("*")):
                if p.is_symlink():
                    result[str(p)] = ("link", os.readlink(p))
                elif p.is_file():
                    result[str(p)] = p.read_bytes()
                elif p.is_dir():
                    result[str(p)] = ("directory",)
        return result

    def link(self, target, path, directory=False):
        try:
            path.symlink_to(target, target_is_directory=directory)
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links are unavailable")

    def test_install_reports_old_copies_after_host_set_changes(self):
        from unittest import mock
        env = {key: "" for key in ("XDG_CONFIG_HOME", "CLAUDE_CONFIG_DIR", "CODEX_HOME", "VIBE_HOME")}
        with mock.patch.dict(os.environ, env):
            rc, out = self.cli("install", self.src)
            self.assertEqual(rc, 0, out)
            shared = self.tmp / ".agents/skills/alpha"
            (shared / "user-data.txt").write_text("keep this", encoding="utf-8")
            (self.tmp / ".claude").mkdir(exist_ok=True)
            (self.tmp / ".cursor").mkdir(exist_ok=True)
            rc, out = self.cli("install", self.src)
            self.assertEqual(rc, 0, out)
            self.assertIn("existing copy:", out)
            self.assertIn(str(shared), out)
            self.assertIn("may read multiple copies", out)
            self.assertIn("Cursor", out)
            self.assertEqual((shared / "user-data.txt").read_text(encoding="utf-8"), "keep this")
            self.assertTrue((self.tmp / ".claude/skills/alpha/SKILL.md").exists())

    def test_invalid_yaml_is_rejected_before_install(self):
        (self.src / "SKILL.md").write_text('---\nname: alpha\ndescription: Use when: alpha\n---\n1. Work.\n', encoding="utf-8")
        self.assertEqual(self.cli("validate", self.src)[0], 1)
        self.assertEqual(self.cli("install", self.src, "--to", self.dest)[0], 1)
        self.assertFalse(self.dest.exists())

    def test_init_escapes_tabs_in_quoted_descriptions(self):
        description = "Use for documents:\tcovers sheet"
        rc, out = self.cli("init", "tabs", "--root", self.dest, "--bare", "--desc", description)
        self.assertEqual(rc, 0, out)
        meta, _, error = ns.read_skill_doc(str(self.dest / "tabs"))
        self.assertIsNone(error)
        self.assertEqual(meta["description"], description)
        self.assertEqual(self.cli("validate", self.dest / "tabs")[0], 0)

    def test_generated_numeric_or_boolean_names_remain_strings(self):
        for name in ("123", "on", "true"):
            with self.subTest(name=name):
                rc, out = self.cli("init", name, "--root", self.dest, "--bare")
                self.assertEqual(rc, 0, out)
                meta, _, error = ns.read_skill_doc(str(self.dest / name))
                self.assertIsNone(error)
                self.assertEqual(meta["name"], name)
                self.assertIn('name: "' + name + '"', (self.dest / name / "SKILL.md").read_text(encoding="utf-8"))
        rc, out = self.cli("install", self.src, "--to", self.dest, "--as", "no")
        self.assertEqual(rc, 0, out)
        self.assertEqual(ns.read_skill_doc(str(self.dest / "no"))[0]["name"], "no")

    @unittest.skipUnless(shutil.which("skills-ref"), "optional Agent Skills reference validator not installed")
    def test_quoted_mapping_value_agrees_with_reference_validator(self):
        import subprocess
        document = self.src / "SKILL.md"
        invalid = '---\nname: alpha\ndescription: Use when: alpha\n---\n1. Work.\n'
        for text, valid in ((invalid, False), (invalid.replace('Use when: alpha', '"Use when: alpha"'), True)):
            document.write_text(text, encoding="utf-8")
            local, out = self.cli("validate", self.src)
            external = subprocess.run([shutil.which("skills-ref"), "validate", str(self.src)],
                                      capture_output=True, text=True)
            self.assertEqual(local == 0, valid, out)
            self.assertEqual(external.returncode == 0, valid, external.stdout + external.stderr)

    def test_force_preserves_all_old_files_in_printed_backup(self):
        import tarfile
        self.assertEqual(self.cli("install", self.src, "--to", self.dest)[0], 0)
        old = self.dest / "alpha"
        make_skill(old / "my-reports", "my-reports", "reports")
        for name in ("synonyms.md", "_feedback.md", "ABSORB.md", "custom.txt"):
            (old / name).write_text("user-owned " + name, encoding="utf-8")
        (old / "SKILL.md").write_bytes((old / "SKILL.md").read_bytes() + b"\nUser edit.\n")
        files = {p.relative_to(old).as_posix(): p.read_bytes() for p in old.rglob("*") if p.is_file()}
        rc, out = self.cli("install", self.src, "--to", self.dest, "--force")
        self.assertEqual(rc, 0, out)
        archives = list(self.backups.glob("*.tar.gz"))
        self.assertEqual(len(archives), 1, out)
        self.assertIn(str(archives[0]), out)
        with tarfile.open(archives[0]) as archive:
            for name, data in files.items():
                self.assertEqual(archive.extractfile("trees/0/" + name).read(), data)
            self.assertIn("manifest.json", archive.getnames())
        self.assertFalse(any(p.name == "SKILL.md" for p in self.backups.rglob("*")))

    def test_force_backup_failure_prevents_any_replacement(self):
        from unittest import mock
        import tarfile
        self.assertEqual(self.cli("install", self.src, "--to", self.dest)[0], 0)
        before = self.snapshot(self.dest)
        with mock.patch.object(tarfile.TarFile, "add", side_effect=OSError("backup failed")):
            rc, out = self.cli("install", self.src, "--to", self.dest, "--force")
        self.assertEqual(rc, 1, out)
        self.assertEqual(self.snapshot(self.dest), before)
        self.assertFalse(list(self.backups.glob("*.tar.gz")))

    def test_force_dry_run_writes_neither_backup_nor_destination(self):
        self.assertEqual(self.cli("install", self.src, "--to", self.dest)[0], 0)
        before = self.snapshot(self.dest)
        rc, out = self.cli("install", self.src, "--to", self.dest, "--force", "--dry-run")
        self.assertEqual(rc, 0, out)
        self.assertIn("backup", out.lower())
        self.assertEqual(self.snapshot(self.dest), before)
        self.assertFalse(self.backups.exists())

    def test_force_repeated_backups_do_not_overwrite_history(self):
        self.assertEqual(self.cli("install", self.src, "--to", self.dest)[0], 0)
        for value in ("first", "second"):
            (self.dest / "alpha" / "custom.txt").write_text(value, encoding="utf-8")
            self.assertEqual(self.cli("install", self.src, "--to", self.dest, "--force")[0], 0)
        self.assertEqual(len(list(self.backups.glob("*.tar.gz"))), 2)

    def test_force_backups_capture_each_destination_and_survive_publish_failure(self):
        import tarfile
        from unittest import mock
        dirs = [self.tmp / "host-a", self.tmp / "host-b"]
        for i, directory in enumerate(dirs):
            make_skill(directory / "alpha", "alpha", "old version")
            (directory / "alpha" / "custom.txt").write_text("host-%d" % i, encoding="utf-8")
        before = self.snapshot(*dirs)
        replace = os.replace
        def fail_second(src, dest):
            if os.path.basename(src) == "new" and str(dest) == str(dirs[1] / "alpha"):
                raise OSError("publish failed")
            return replace(src, dest)
        with mock.patch.object(ns, "plan_install", return_value=(list(map(str, dirs)), {}, [], [])), \
                mock.patch.object(ns.os, "replace", side_effect=fail_second):
            rc, out = self.cli("install", self.src, "--force")
        self.assertEqual(rc, 1, out)
        self.assertEqual(self.snapshot(*dirs), before)
        archives = list(self.backups.glob("*.tar.gz"))
        self.assertEqual(len(archives), 1)
        with tarfile.open(archives[0]) as archive:
            for i in range(2):
                with archive.extractfile("trees/%d/custom.txt" % i) as f:
                    self.assertEqual(f.read(), ("host-%d" % i).encode())

    def test_force_backup_location_cannot_be_in_a_skills_directory(self):
        self.assertEqual(self.cli("install", self.src, "--to", self.dest)[0], 0)
        before = self.snapshot(self.dest)
        for directory in (self.dest / "backups", self.src / "backups", self.tmp / ".claude/skills/backups"):
            rc, out = self.cli("install", self.src, "--to", self.dest, "--force", "--backup-dir", directory)
            self.assertEqual(rc, 1, out)
            self.assertEqual(self.snapshot(self.dest), before)
            self.assertFalse(directory.exists())
        custom = self.tmp / "archives"
        rc, out = self.cli("install", self.src, "--to", self.dest, "--force", "--backup-dir", custom)
        self.assertEqual(rc, 0, out)
        self.assertEqual(len(list(custom.glob("*.tar.gz"))), 1)

    def test_force_backup_of_linked_install_contains_data_and_link_metadata(self):
        import json
        import tarfile
        self.dest.mkdir()
        self.link(self.src, self.dest / "alpha", directory=True)
        # Windows readlink may return the extended \\?\ path, unlike str(Path).
        recorded_link = os.readlink(self.dest / "alpha")
        original = (self.src / "SKILL.md").read_bytes()
        rc, out = self.cli("install", self.other, "--as", "alpha", "--to", self.dest, "--force")
        self.assertEqual(rc, 0, out)
        self.assertEqual((self.src / "SKILL.md").read_bytes(), original)
        with tarfile.open(next(self.backups.glob("*.tar.gz"))) as archive:
            with archive.extractfile("trees/0/SKILL.md") as f:
                self.assertEqual(f.read(), original)
            with archive.extractfile("manifest.json") as f:
                self.assertEqual(json.load(f)["installs"][0]["root_link"], recorded_link)

    def test_move_rolls_back_keyboard_interrupt(self):
        from unittest import mock
        before = self.snapshot(self.tmp / "flat", self.root)
        def interrupt(args):
            (self.root / "SKILL.md").write_text("partial table", encoding="utf-8")
            raise KeyboardInterrupt()
        with mock.patch.object(ns, "cmd_sync", side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.cli("move", "--plan", self.plan)
        self.assertEqual(self.snapshot(self.tmp / "flat", self.root), before)

    def test_move_rollback_failure_retains_original_and_recovery_map(self):
        import json
        from unittest import mock
        original = (self.src / "SKILL.md").read_bytes()
        replace = os.replace
        def block_restore(src, dest):
            if str(dest) == str(self.src):
                raise OSError("cannot restore source yet")
            return replace(src, dest)
        with mock.patch.object(ns, "cmd_sync", return_value=1), \
                mock.patch.object(ns.os, "replace", side_effect=block_restore):
            rc, out = self.cli("move", "--plan", self.plan)
        self.assertEqual(rc, 1, out)
        self.assertIn("rollback incomplete", out)
        line = next(line for line in out.splitlines() if "recovery retained: " in line)
        recovery = Path(line.split("recovery retained: ", 1)[1])
        self.addCleanup(ns.remove_tree, str(recovery))
        data = json.loads((recovery / "recovery.json").read_text(encoding="utf-8"))
        old = Path(next(item["old"] for item in data["items"] if item["src"] == str(self.src)))
        self.assertEqual((old / "SKILL.md").read_bytes(), original)
        self.assertTrue(all((recovery / d["backup"]).is_file() for d in data["documents"]))

    def test_move_copy_keeps_hidden_assets_and_tests(self):
        for name in (".hidden", "tests/check.py", ".git/config", "__pycache__/custom.bin"):
            file = self.src / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(b"user asset")
        before = self.snapshot(self.src)
        rc, out = self.cli("move", self.src, "--parent", self.root, "--copy")
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.snapshot(self.src), before)
        for name in (".hidden", "tests/check.py", ".git/config", "__pycache__/custom.bin"):
            self.assertEqual((self.root / "alpha" / name).read_bytes(), b"user asset")

    def test_move_rejects_hardlinked_skill_documents(self):
        outside = self.tmp / "hardlink.md"
        try:
            os.link(self.src / "SKILL.md", outside)
        except (OSError, NotImplementedError):
            self.skipTest("hard links unavailable")
        before = outside.read_bytes()
        self.assertEqual(self.cli("move", self.src, "--parent", self.root, "--as", "renamed")[0], 1)
        self.assertEqual(outside.read_bytes(), before)
        self.assertTrue(self.src.exists())

    def test_move_rejects_duplicate_and_nested_sources_even_in_dry_run(self):
        make_skill(self.src / "child", "child", "child")
        for second in ("flat/alpha", "flat/alpha/child"):
            self.plan.write_text("flat/alpha -> lib/first\n%s -> lib/second\n" % second, encoding="utf-8")
            before = self.snapshot(self.tmp / "flat", self.root)
            for extra in ([], ["--dry-run"], ["--copy"]):
                rc, out = self.cli("move", "--plan", self.plan, *extra)
                self.assertEqual(rc, 1, out)
                self.assertEqual(self.snapshot(self.tmp / "flat", self.root), before)

    def test_move_rejects_destination_parent_inside_another_source(self):
        make_skill(self.other / "child", "child", "child")
        self.plan.write_text("flat/alpha -> flat/beta/child/first\nflat/beta -> lib/second\n", encoding="utf-8")
        before = self.snapshot(self.tmp / "flat", self.root)
        self.assertEqual(self.cli("move", "--plan", self.plan)[0], 1)
        self.assertEqual(self.snapshot(self.tmp / "flat", self.root), before)

    def test_move_rejects_external_skill_file_link_before_writing(self):
        outside = self.tmp / "outside.md"
        original = (self.src / "SKILL.md").read_bytes()
        outside.write_bytes(original)
        (self.src / "SKILL.md").unlink()
        self.link(outside, self.src / "SKILL.md")
        for extra in ([], ["--copy"], ["--dry-run"]):
            rc, out = self.cli("move", self.src, "--parent", self.root, "--as", "renamed", *extra)
            self.assertEqual(rc, 1, out)
            self.assertTrue(self.src.exists())
            self.assertEqual(outside.read_bytes(), original)
            self.assertFalse((self.root / "renamed").exists())

    def test_move_rejects_nested_link_and_linked_parent(self):
        outside = self.tmp / "outside.txt"
        outside.write_text("keep", encoding="utf-8")
        self.link(outside, self.src / "reference.txt")
        self.assertEqual(self.cli("move", self.src, "--parent", self.root)[0], 1)
        (self.src / "reference.txt").unlink()
        alias = self.tmp / "alias"
        self.link(self.root, alias, directory=True)
        self.assertEqual(self.cli("move", self.src, "--parent", alias)[0], 1)
        self.assertTrue(self.src.exists())

    def test_move_rejects_malformed_source_and_destination_before_writing(self):
        for path in (self.src, self.root):
            before = (path / "SKILL.md").read_bytes()
            (path / "SKILL.md").write_text("---\nname: bad\ndescription:\n  - wrong\n---\n", encoding="utf-8")
            rc, out = self.cli("move", self.src, "--parent", self.root)
            self.assertEqual(rc, 1, out)
            self.assertTrue(self.src.exists())
            self.assertFalse((self.root / "alpha").exists())
            (path / "SKILL.md").write_bytes(before)

    def test_move_refuses_dangling_target_link(self):
        self.link(self.tmp / "missing", self.root / "alpha", directory=True)
        self.assertEqual(self.cli("move", self.src, "--parent", self.root)[0], 1)
        self.assertTrue(self.src.exists())
        self.assertTrue((self.root / "alpha").is_symlink())

    def test_move_rolls_back_second_publication_failure(self):
        from unittest import mock
        original_replace = os.replace
        before = self.snapshot(self.tmp / "flat", self.root)
        def fail_second(src, dest):
            if str(dest) == str(self.root / "second"):
                raise OSError("second publication failed")
            return original_replace(src, dest)
        with mock.patch.object(ns.os, "replace", side_effect=fail_second):
            rc, out = self.cli("move", "--plan", self.plan)
        self.assertEqual(rc, 1, out)
        self.assertEqual(self.snapshot(self.tmp / "flat", self.root), before)
        self.assertIn("restored", out)

    def test_move_rolls_back_rename_failure(self):
        from unittest import mock
        before = self.snapshot(self.tmp / "flat", self.root)
        with mock.patch.object(ns, "_rename_skill", side_effect=OSError("rename failed")):
            rc, out = self.cli("move", "--plan", self.plan)
        self.assertEqual(rc, 1, out)
        self.assertEqual(self.snapshot(self.tmp / "flat", self.root), before)

    def test_move_rolls_back_sync_failure_after_it_wrote_a_table(self):
        from unittest import mock
        before = self.snapshot(self.tmp / "flat", self.root)
        def failed_sync(args):
            (self.root / "SKILL.md").write_text("partial write", encoding="utf-8")
            return 1
        with mock.patch.object(ns, "cmd_sync", side_effect=failed_sync):
            rc, out = self.cli("move", "--plan", self.plan)
        self.assertEqual(rc, 1, out)
        self.assertEqual(self.snapshot(self.tmp / "flat", self.root), before)

    def test_move_copy_failure_leaves_no_partial_target(self):
        from unittest import mock
        original_copy = shutil.copytree
        before = self.snapshot(self.tmp / "flat", self.root)
        def fail_copy(src, dest, *args, **kwargs):
            if os.path.realpath(src) == os.path.realpath(self.other):
                Path(dest).mkdir()
                (Path(dest) / "SKILL.md").write_bytes((self.other / "SKILL.md").read_bytes())
                raise OSError("copy interrupted")
            return original_copy(src, dest, *args, **kwargs)
        with mock.patch.object(ns.shutil, "copytree", side_effect=fail_copy):
            rc, out = self.cli("move", "--plan", self.plan, "--copy")
        self.assertEqual(rc, 1, out)
        self.assertEqual(self.snapshot(self.tmp / "flat", self.root), before)


class TestInstallPlan(unittest.TestCase):
    """No host is the default. `install` writes where the hosts on this machine read, and
    never where one host would see the tree twice."""

    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.saved = {k: os.environ.get(k) for k in ("HOME", "USERPROFILE", "XDG_CONFIG_HOME", "CLAUDE_CONFIG_DIR", "CODEX_HOME", "VIBE_HOME")}
        os.environ["HOME"] = os.environ["USERPROFILE"] = self.home
        for k in ("XDG_CONFIG_HOME", "CLAUDE_CONFIG_DIR", "CODEX_HOME", "VIBE_HOME"):
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.home)

    def plan(self, present=(), hosts=None):
        for p in present:
            os.makedirs(os.path.join(self.home, *p.split("/")), exist_ok=True)
        dirs, _, doubled, missing = ns.plan_install(hosts)
        rel = [os.path.relpath(d, self.home).replace(os.sep, "/") for d in dirs]
        return rel, doubled, missing

    def test_nothing_found_means_the_shared_directory(self):
        self.assertEqual(self.plan(), ([".agents/skills"], [], []))

    def test_a_host_that_reads_the_shared_directory_needs_nothing_else(self):
        self.assertEqual(self.plan([".codex"])[0], [".agents/skills"])
        self.assertEqual(self.plan([".gemini"])[0], [".agents/skills"])

    def test_a_host_that_does_not_gets_its_own_and_the_shared_one_is_kept(self):
        self.assertEqual(self.plan([".claude"])[0], [".agents/skills", ".claude/skills"])

    def test_no_host_ever_sees_the_tree_twice(self):
        # Cursor and OpenCode read both ~/.claude/skills and ~/.agents/skills.
        for present in ([".claude", ".cursor"], [".claude", ".config/opencode"],
                        [".claude", ".cursor", ".config/opencode", ".codeium/windsurf", ".copilot", ".gemini"]):
            rel, doubled, missing = self.plan(present)
            self.assertEqual(doubled, [], (present, rel))
            self.assertEqual(missing, [], (present, rel))
            self.assertIn(".claude/skills", rel)

    def test_every_known_host_at_once(self):
        for h in ns.HOSTS:
            d = ns._resolve_dir(h[2][0])
            os.makedirs(os.path.dirname(d), exist_ok=True)
        rel, doubled, missing = self.plan()
        self.assertEqual((doubled, missing), ([], []), rel)

    def test_named_hosts_only(self):
        self.assertEqual(self.plan(hosts=["claude"])[0], [".claude/skills"])
        self.assertEqual(self.plan(hosts=["opencode"])[0], [".agents/skills"])
        self.assertEqual(self.plan(hosts=["windsurf", "codex"])[0], [".agents/skills", ".codeium/windsurf/skills"])
        self.assertEqual(self.plan(hosts=["agents"])[0], [".agents/skills"])

    def test_install_writes_real_copies_and_force_replaces(self):
        os.makedirs(os.path.join(self.home, ".claude"))
        self.assertEqual(ns.main(["install"]), 0)
        for d in (".agents/skills/holon", ".claude/skills/holon"):
            p = os.path.join(self.home, *d.split("/"))
            self.assertTrue(os.path.isfile(os.path.join(p, "scripts", "holon.py")), d)
            self.assertFalse(os.path.islink(p), d)
        self.assertEqual(ns.main(["install"]), 1)
        self.assertEqual(ns.main(["install", "--force"]), 0)

    def test_hosts_command_lists_every_host(self):
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(ns.main(["hosts"]), 0)
        out = buf.getvalue()
        for h in ns.HOST_IDS:
            self.assertIn(h, out)


class TestMove(unittest.TestCase):
    """Moving skills is a tree-tool feature; these tests need no evaluation harness."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.tool = Path(ns.__file__).resolve()
        flat = self.tmp / "flat"
        for name, desc in (("word-docs", "Use when editing Word files: covers Word, docx"),
                           ("slides", "Use when making slides: covers deck, slides"),
                           ("poster", "Use for posters: covers poster, flyer")):
            make_skill(flat / name, name, desc, body="1. Do it.")
        (flat / "word-docs" / "references").mkdir()
        (flat / "word-docs" / "references" / "styles.md").write_text("styles\n", encoding="utf-8")
        self.plan = self.tmp / "plan.txt"
        self.plan.write_text("flat/word-docs -> tree/lib/office/docx\n"
                             "flat/slides -> tree/lib/office/pptx\n"
                             "flat/poster -> tree/lib/\n", encoding="utf-8")
        rc, out = self.sh(self.tool, "init", "lib", "--root", self.tmp / "tree")
        self.assertEqual(rc, 0, out)
        self.root = self.tmp / "tree" / "lib"
        rc, out = self.sh(self.root / "scripts" / "holon.py", "init", "office", "--parent", self.root,
                          "--desc", "Use for office files: covers office document")
        self.assertEqual(rc, 0, out)

    def sh(self, *args):
        import subprocess
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
        p = subprocess.run([sys.executable] + [str(a) for a in args], env=env,
                           capture_output=True, text=True, encoding="utf-8")
        return p.returncode, p.stdout + p.stderr

    def move(self, *extra):
        return self.sh(self.root / "scripts" / "holon.py", "move", "--plan", self.plan, *extra)

    def test_plan_copies_renames_and_syncs(self):
        rc, out = self.move("--copy")
        self.assertEqual(rc, 0, out)
        self.assertTrue((self.tmp / "flat" / "slides").is_dir(), "--copy must leave the source")
        md = (self.root / "office" / "pptx" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("name: pptx", md)
        self.assertTrue((self.root / "office" / "docx" / "references" / "styles.md").is_file())
        self.assertTrue((self.root / "poster" / "SKILL.md").is_file())
        root_md = (self.root / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("also takes, through its sub-skills: Word, docx, deck, slides", root_md)
        rc, out = self.sh(self.root / "scripts" / "holon.py", "sync", self.root, "--dry-run")
        self.assertEqual(rc, 0, out)
        self.assertIn("done: 0 file(s) would be updated", out)

    def test_plan_is_all_or_nothing(self):
        with open(self.plan, "a", encoding="utf-8") as f:
            f.write("flat/missing -> tree/lib/\n")
        rc, out = self.move("--copy")
        self.assertEqual(rc, 1)
        self.assertIn("nothing was moved", out)
        self.assertFalse((self.root / "office" / "docx").exists())

    def test_refuses_existing_target_and_moving_into_itself(self):
        rc, out = self.move("--copy")
        self.assertEqual(rc, 0, out)
        rc, out = self.move("--copy")
        self.assertEqual(rc, 1)
        self.assertIn("already exists", out)
        rc, out = self.sh(self.root / "scripts" / "holon.py", "move", self.root / "office",
                          "--parent", self.root / "office" / "pptx")
        self.assertEqual(rc, 1)
        self.assertIn("into itself", out)

    def test_move_within_tree_resyncs_old_and_new_parent(self):
        rc, out = self.move("--copy")
        self.assertEqual(rc, 0, out)
        rc, out = self.sh(self.root / "scripts" / "holon.py", "move", self.root / "poster",
                          "--parent", self.root / "office")
        self.assertEqual(rc, 0, out)
        self.assertFalse((self.root / "poster").exists())
        self.assertTrue((self.root / "office" / "poster" / "SKILL.md").is_file())
        self.assertIn("**poster**", (self.root / "office" / "SKILL.md").read_text(encoding="utf-8"))
        rc, out = self.sh(self.tool, "validate", self.root)
        self.assertNotIn("out of date", out)

    def test_dry_run_changes_nothing(self):
        rc, out = self.move("--copy", "--dry-run")
        self.assertEqual(rc, 0, out)
        self.assertIn("[dry-run] would copy", out)
        self.assertFalse((self.root / "office" / "docx").exists())

    def test_plan_destination_does_not_depend_on_disk(self):
        moves, errors = ns.read_plan(str(self.plan))
        self.assertEqual(errors, [])
        self.assertEqual([(Path(p).name, n) for _, p, n in moves],
                         [("office", "docx"), ("office", "pptx"), ("lib", "poster")])


SPLIT_BODY = """
# report

1. Collect the figures.
2. Write the summary first.

## House style background

Our house style uses sentence case headings.
Numbers below ten are spelled out.

```text
Example heading
```

## Charts

1. Pick a chart type.
2. Export as PNG.
"""


class TestSplit(unittest.TestCase):
    """The agent decides the cut; split only checks the plan against the exact file and copies
    the named lines verbatim. Lines 15-23 are the house style section (with its fence) and
    lines 25-28 the charts section of SPLIT_BODY under a nine-line header."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(ns.remove_tree, str(self.tmp))
        self.root = self.tmp / "lib"
        make_skill(self.root, "lib", "Use for every task: covers library routing", markers=True)
        self.skill = self.root / "report"
        self.skill.mkdir()
        self.doc = self.skill / "SKILL.md"
        # Explicit newline="\n": in text mode Windows would write "\r\n", the plan's line numbers
        # and the CRLF test below would then mean something different there than on Linux.
        with open(self.doc, "w", encoding="utf-8", newline="\n") as f:
            f.write('---\nname: report\ndescription: "Use when writing reports: covers report, summary"\n'
                    'metadata:\n  holon-triggers: |\n    write the quarterly report\n'
                    '    summarise this report\n    draw a poster should go to /\n---\n'
                    + SPLIT_BODY + "\n" + ns.MARK_OPEN + "\n" + ns.MARK_CLOSE + "\n")
        self.cli("sync", self.root)
        self.original = self.doc.read_bytes()

    def cli(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            rc = ns.main(list(map(str, args)))
        return rc, out.getvalue()

    def sha(self):
        import hashlib
        return hashlib.sha256(self.doc.read_bytes()).hexdigest()

    def plan(self, chunks, sha=None):
        p = self.tmp / "plan.json"
        p.write_text(json.dumps({"source": "lib/report", "sha256": sha or self.sha(), "chunks": chunks}),
                     encoding="utf-8")
        return p

    REF = {"lines": "15-23", "to": "reference", "path": "references/house-style.md",
           "pointer": "3. Follow the house style in `references/house-style.md`."}
    SUB = {"lines": "25-28", "to": "skill", "name": "charts",
           "description": "Use when a report needs a chart: covers chart, plot",
           "triggers": ["add a chart to the report", "plot the figures", "write the summary should go to report"],
           "pointer": "4. For charts, use the charts sub-skill."}

    def test_show_numbers_lines_and_prints_the_hash(self):
        rc, out = self.cli("split", self.skill, "--show")
        self.assertEqual(rc, 0, out)
        self.assertIn("sha256: " + self.sha(), out)
        self.assertIn("   16  ## House style background", out)
        self.assertEqual(self.doc.read_bytes(), self.original)

    def test_plan_moves_lines_verbatim_and_resyncs(self):
        lines = self.original.decode("utf-8").splitlines(keepends=True)
        rc, out = self.cli("split", "--plan", self.plan([self.REF, self.SUB]))
        self.assertEqual(rc, 0, out)
        self.assertEqual((self.skill / "references" / "house-style.md").read_text(encoding="utf-8"),
                         "".join(lines[14:23]))
        child = (self.skill / "charts" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("".join(lines[24:28]), child)
        text = self.doc.read_text(encoding="utf-8")
        self.assertIn("3. Follow the house style in `references/house-style.md`.\n", text)
        self.assertNotIn("Numbers below ten", text)
        self.assertIn("**charts**", text)
        rc, out = self.cli("validate", self.root)
        self.assertEqual(rc, 0, out)

    def test_every_rejected_plan_writes_nothing(self):
        bad = [
            ([dict(self.REF, lines="15-22")], "code fence"),
            ([dict(self.REF, lines="2-4")], "frontmatter"),
            ([self.REF, dict(self.SUB, lines="20-26")], "already in chunk"),
            ([dict(self.REF, path="../outside.md")], "references/<name>.md"),
            ([dict(self.REF, pointer="see the style file")], "in backticks"),
            ([dict(self.SUB, name="Charts")], "not a valid skill name"),
            ([dict(self.SUB, triggers=[])], "triggers"),
            ([dict(self.REF, lines="15-99")], "within 1-"),
            ([dict(self.REF, to="delete")], "\"to\" must be"),
        ]
        for chunks, why in bad:
            with self.subTest(why=why):
                rc, out = self.cli("split", "--plan", self.plan(chunks))
                self.assertEqual(rc, 1, out)
                self.assertIn(why, out)
                self.assertIn("nothing was written", out)
                self.assertEqual(self.doc.read_bytes(), self.original)
                self.assertFalse((self.skill / "references").exists())
                self.assertFalse((self.skill / "charts").exists())

    def test_stale_plan_and_existing_target_are_refused(self):
        rc, out = self.cli("split", "--plan", self.plan([self.REF], sha="0" * 64))
        self.assertEqual(rc, 1, out)
        self.assertIn("changed since the plan was written", out)
        (self.skill / "references").mkdir()
        (self.skill / "references" / "house-style.md").write_text("mine\n", encoding="utf-8")
        rc, out = self.cli("split", "--plan", self.plan([self.REF]))
        self.assertEqual(rc, 1, out)
        self.assertIn("never overwrites", out)
        self.assertEqual((self.skill / "references" / "house-style.md").read_text(encoding="utf-8"), "mine\n")
        self.assertEqual(self.doc.read_bytes(), self.original)

    def test_dry_run_and_failed_sync_leave_the_tree_as_it_was(self):
        from unittest import mock
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        rc, out = self.cli("split", "--plan", self.plan([self.REF, self.SUB]), "--dry-run")
        self.assertEqual(rc, 0, out)
        self.assertEqual({p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}, before)
        with mock.patch.object(ns, "cmd_sync", return_value=1):
            rc, out = self.cli("split", "--plan", self.plan([self.REF, self.SUB]))
        self.assertEqual(rc, 1, out)
        self.assertIn("restored", out)
        self.assertEqual({p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}, before)
        self.assertFalse((self.skill / "charts").exists())
        self.assertFalse((self.skill / "references").exists())

    def test_crlf_document_keeps_crlf(self):
        self.doc.write_bytes(self.original.replace(b"\n", b"\r\n"))
        rc, out = self.cli("split", "--plan", self.plan([self.REF]))
        self.assertEqual(rc, 0, out)
        data = self.doc.read_bytes()
        self.assertIn(b"`references/house-style.md`.\r\n", data)
        self.assertNotIn(b"\n", data.replace(b"\r\n", b""))

    def test_show_and_plan_are_exclusive(self):
        for args in (("split",), ("split", self.skill), ("split", self.skill, "--show", "--plan", "x.json")):
            rc, out = self.cli(*args)
            self.assertEqual(rc, 1, out)


def argparse_ns(**kw):
    import argparse
    return argparse.Namespace(**kw)


def _walk_named(base, name):
    for dirpath, dirnames, _ in os.walk(base):
        for d in dirnames:
            if d == name:
                yield os.path.join(dirpath, d)


if __name__ == "__main__":
    unittest.main(verbosity=2)
