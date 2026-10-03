#!/usr/bin/env python3
# Copyright (c) 2026 Wneil2020 and the holon skill contributors. Released under the MIT License.
"""Tests for eval/harness.py and `holon.py move`. They need no model: the word-model runner,
a fake `claude` that prints recorded stream-json, and a `command` runner that echoes JSON."""
import contextlib
import csv
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVAL = HERE.parent
REPO = EVAL.parent
sys.path.insert(0, str(EVAL))
import harness  # noqa: E402

PY = sys.executable
HOLON = REPO / "holon" / "scripts" / "holon.py"
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")


def sh(*args, cwd=None):
    p = subprocess.run([PY] + [str(a) for a in args], cwd=cwd, env=ENV, capture_output=True,
                       text=True, encoding="utf-8")
    return p.returncode, p.stdout + p.stderr


def skill(folder, name, desc, body="1. Do it."):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text('---\nname: %s\ndescription: "%s"\n---\n\n# %s\n\n%s\n'
                                     % (name, desc, name, body), encoding="utf-8")


class Lab(unittest.TestCase):
    """A flat library of three skills, a plan, and the tree built from them."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        flat = self.tmp / "flat"
        skill(flat / "word-docs", "word-docs", "Use when editing Word files: covers Word, docx")
        skill(flat / "slides", "slides", "Use when making slides: covers deck, slides")
        skill(flat / "poster", "poster", "Use for posters: covers poster, flyer")
        (flat / "word-docs" / "references").mkdir()
        (flat / "word-docs" / "references" / "styles.md").write_text("styles\n", encoding="utf-8")
        self.plan = self.tmp / "plan.txt"
        self.plan.write_text("flat/word-docs -> tree/lib/office/docx\nflat/slides -> tree/lib/office/pptx\n"
                             "flat/poster -> tree/lib/\n", encoding="utf-8")
        rc, out = sh(HOLON, "init", "lib", "--root", self.tmp / "tree")
        self.assertEqual(rc, 0, out)
        self.root = self.tmp / "tree" / "lib"
        rc, out = sh(self.root / "scripts" / "holon.py", "init", "office", "--parent", self.root,
                     "--desc", "Use for office files: covers office document")
        self.assertEqual(rc, 0, out)
        self.sentences = self.tmp / "s.tsv"
        self.sentences.write_text(
            "id\tsplit\tsentence\texpected\n"
            "a\ttest\tfix this Word file\tdocx\n"
            "b\ttest\tbuild a pitch deck\tpptx\n"
            "c\ttest\twhat time is it\tnone\n"
            "d\ttune\tmake a flyer\tposter\n", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def move(self, *extra):
        return sh(self.root / "scripts" / "holon.py", "move", "--plan", self.plan, *extra)


class TestMove(Lab):
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
        rc, out = sh(self.root / "scripts" / "holon.py", "sync", self.root, "--dry-run")
        self.assertIn("done: 0 file(s) would be updated", out)

    def test_plan_is_all_or_nothing(self):
        with open(self.plan, "a", encoding="utf-8") as f:
            f.write("flat/missing -> tree/lib/\n")
        rc, out = self.move("--copy")
        self.assertEqual(rc, 1)
        self.assertIn("nothing was moved", out)
        self.assertFalse((self.root / "office" / "docx").exists())

    def test_refuses_existing_target_and_moving_into_itself(self):
        self.assertEqual(self.move("--copy")[0], 0)
        rc, out = self.move("--copy")
        self.assertEqual(rc, 1)
        self.assertIn("already exists", out)
        rc, out = sh(self.root / "scripts" / "holon.py", "move", self.root / "office",
                     "--parent", self.root / "office" / "pptx")
        self.assertEqual(rc, 1)
        self.assertIn("into itself", out)

    def test_move_within_tree_resyncs_old_and_new_parent(self):
        self.assertEqual(self.move("--copy")[0], 0)
        rc, out = sh(self.root / "scripts" / "holon.py", "move", self.root / "poster", "--parent", self.root / "office")
        self.assertEqual(rc, 0, out)
        self.assertIn("**poster**", (self.root / "office" / "SKILL.md").read_text(encoding="utf-8"))
        rc, out = sh(HOLON, "validate", self.root)
        self.assertNotIn("out of date", out)

    def test_dry_run_changes_nothing(self):
        rc, out = self.move("--copy", "--dry-run")
        self.assertEqual(rc, 0, out)
        self.assertIn("[dry-run] would copy", out)
        self.assertFalse((self.root / "office" / "docx").exists())

    def test_plan_destination_does_not_depend_on_disk(self):
        moves, errors = harness.ns.read_plan(str(self.plan))
        self.assertEqual(errors, [])
        self.assertEqual([(Path(p).name, n) for _, p, n in moves], [("office", "docx"), ("office", "pptx"), ("lib", "poster")])


class TestHarness(Lab):
    def setUp(self):
        super().setUp()
        self.assertEqual(self.move("--copy")[0], 0)
        self.trimmed = self.tmp / "trimmed"
        self.results = self.tmp / "r.csv"

    def h(self, *args):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            try:
                rc = harness.main([str(a) for a in args])
            except SystemExit as e:
                rc = e.code if isinstance(e.code, int) else 1
                print(e.code)
        return rc, out.getvalue()

    def rows(self):
        with open(self.results, encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def test_flatten_drops_tool_skills_and_routing_tables(self):
        rc, out = self.h("flatten", self.root, self.trimmed)
        self.assertEqual(rc, 0, out)
        self.assertEqual(sorted(p.name for p in self.trimmed.iterdir()), ["docx", "office", "poster", "pptx"])
        office = (self.trimmed / "office" / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("**docx**", office)
        self.assertFalse((self.trimmed / "office" / "docx").exists())

    def test_run_refuses_unfrozen_split(self):
        rc, out = self.h("run", self.sentences, "--tree", self.root, "--out", self.results)
        self.assertNotEqual(rc, 0)
        self.assertIn("not frozen", out)

    def test_changed_split_after_freeze_is_refused(self):
        self.h("freeze", self.sentences)
        with open(self.sentences, "a", encoding="utf-8") as f:
            f.write("e\ttest\tone more\tnone\n")
        rc, out = self.h("run", self.sentences, "--tree", self.root, "--out", self.results)
        self.assertIn("changed after it was frozen", out)
        rc, out = self.h("run", self.sentences, "--tree", self.root, "--out", self.results, "--unfrozen", "--runs", "1")
        self.assertEqual(rc, 0, out)
        self.assertIn("not evidence", harness.report(self.rows()))

    def test_word_model_all_three_arrangements(self):
        self.h("flatten", self.root, self.trimmed)
        self.h("freeze", self.sentences)
        rc, out = self.h("run", self.sentences, "--tree", self.root, "--flat", self.tmp / "flat",
                         "--trimmed", self.trimmed, "--names", self.plan, "--runs", "2", "--out", self.results)
        self.assertEqual(rc, 0, out)
        rows = self.rows()
        self.assertEqual(len(rows), 3 * 3 * 2, "tune sentences are not run")
        by = {(r["sentence_id"], r["arrangement"]): r for r in rows if r["run"] == "1"}
        self.assertEqual(by[("a", "A")]["chosen"], "docx", "A's folder names are mapped through the plan")
        self.assertEqual(by[("b", "C")]["chosen"], "pptx")
        self.assertEqual(by[("b", "C")]["agrees_word_model"], "1")
        self.assertEqual(by[("c", "C")]["route_ok"], "1")
        self.assertGreater(int(by[("a", "A")]["bytes_read"]), 0)
        text = harness.report(rows)
        self.assertIn("| A | 6 | 3 |", text)
        self.assertIn("agent vs word model: same choice in 6/6", text)

    def test_claude_runner_reads_stream_json(self):
        fake = self.tmp / "claude"
        events = [
            {"type": "system", "subtype": "init", "skills": ["lib"]},
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Skill", "input": {"skill": "lib"}}]}},
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Read", "input": {"file_path": "SKILLS/lib/office/SKILL.md"}}]}},
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Read", "input": {"file_path": "SKILLS/lib/office/pptx/SKILL.md"}}]}},
            {"type": "result", "subtype": "success", "result": "I would use the pptx skill.\nSKILL: pptx",
             "usage": {"input_tokens": 100, "cache_read_input_tokens": 900}, "total_cost_usd": 0.01},
        ]
        fake.write_text("#!%s\nimport json, os, sys\nskills = os.path.join(os.getcwd(), '.claude', 'skills')\n"
                        "assert os.environ['HOME'] != %r, 'HOME must be isolated'\n"
                        "assert '--append-system-prompt' in sys.argv\n"
                        "for e in %r:\n    print(json.dumps(e).replace('SKILLS', skills))\n"
                        % (PY, os.environ.get("HOME", ""), events), encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        self.h("freeze", self.sentences)
        raw = self.tmp / "raw"
        rc, out = self.h("run", self.sentences, "--tree", self.root, "--runner", "claude-code",
                         "--claude", fake, "--runs", "1", "--out", self.results, "--raw-dir", raw)
        self.assertEqual(rc, 0, out)
        self.assertEqual(len(list(raw.glob("*.jsonl"))), 3)
        b = [r for r in self.rows() if r["sentence_id"] == "b"][0]
        self.assertEqual(b["skills_seen"], "lib")
        self.assertEqual(b["chosen"], "pptx")
        self.assertEqual(b["route_ok"], "1")
        self.assertEqual(b["input_tokens"], "1000")
        self.assertEqual(b["files_read"].split(";"), ["lib/SKILL.md", "lib/office/SKILL.md", "lib/office/pptx/SKILL.md"])
        self.assertEqual(b["error"], "")
        a = [r for r in self.rows() if r["sentence_id"] == "a"][0]
        self.assertEqual(a["route_ok"], "0", "the fake always answers pptx")

    def test_a_run_that_reached_no_model_is_not_counted(self):
        fake = self.tmp / "claude"
        fake.write_text("#!%s\nimport json\nprint(json.dumps({'type': 'result', 'result': 'credits cannot be used',"
                        " 'usage': {'input_tokens': 0}}))\n" % PY, encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        self.h("freeze", self.sentences)
        rc, out = self.h("run", self.sentences, "--tree", self.root, "--runner", "claude-code",
                         "--claude", fake, "--runs", "1", "--out", self.results)
        self.assertEqual(rc, 0, out)
        rows = self.rows()
        self.assertTrue(all(r["route_ok"] == "" and "no model call" in r["error"] for r in rows))
        text = harness.report(rows)
        self.assertIn("NOT COUNTED: 3 run(s)", text)
        self.assertNotIn("| C |", text, "no completed run, so no rate")

    def test_command_runner(self):
        self.h("freeze", self.sentences)
        echo = "%s -c \"import json; print(json.dumps({'chosen': 'docx', 'files_read': [], 'input_tokens': 5}))\"" % PY
        rc, out = self.h("run", self.sentences, "--tree", self.root, "--runner", "command",
                         "--runner-cmd", echo, "--runs", "1", "--out", self.results)
        self.assertEqual(rc, 0, out)
        self.assertEqual([r["route_ok"] for r in self.rows()], ["1", "0", "0"])

    def test_sentence_file_errors(self):
        bad = self.tmp / "bad.tsv"
        bad.write_text("id\tsentence\n1\tx\n", encoding="utf-8")
        rc, out = self.h("freeze", bad)
        self.assertIn("needs the columns", out)


if __name__ == "__main__":
    unittest.main(verbosity=1)
