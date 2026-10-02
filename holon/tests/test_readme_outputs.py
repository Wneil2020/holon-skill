#!/usr/bin/env python3
# Copyright (c) 2026 Wneil2020 and the holon skill contributors. Released under the MIT License.
"""Every command output quoted in README.md and README.zh-CN.md is the real output.

The READMEs make this promise and this test keeps it. It copies this package into
an empty folder (without tests/ and caches), then runs the quoted commands in the
order the README quotes them, against that copy, and compares each output with the
quoted text. The README is a walkthrough: each command sees the tree the previous
ones left behind.

A quoted block is a fenced block whose first line starts with `$ python3`. Other
fences (file contents, directory listings) are not checked. For `replay`, only the
last line is quoted and compared. Before the first `replay`, the three skills the
walkthrough created get the finished text the README shows or describes.
"""
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
READMES = ("README.md", "README.zh-CN.md")


def finished(name, desc, triggers, body):
    lines = "".join("    %s\n" % t for t in triggers)
    return ('---\nname: %s\ndescription: "%s"\nmetadata:\n  holon-triggers: |\n%s---\n\n# %s\n\n%s\n'
            % (name, desc, lines, name, body))


# The docx text is quoted in the README as "a finished skill"; the test checks that the
# quote and this constant agree, so the README cannot show one thing and test another.
DOCX_SKILL = finished(
    "docx",
    "Use when writing or editing Word documents: covers Word, docx, report; excludes spreadsheet",
    ["write the quarterly report in Word",
     "fix the heading styles in this docx",
     "draw a poster for the launch should go to /"],
    "1. Open or create the document with python-docx.\n"
    "2. Apply the house styles from `references/styles.md` before adding content.\n"
    "3. Write content section by section; never paste raw text into a heading.\n"
    "4. Save and re-open once to confirm the file is not corrupt.")

PDF_SKILL = finished(
    "pdf",
    "Use when the input or output is a PDF: covers PDF, form, fill in, merge pages",
    ["fill in this PDF form",
     "merge pages from three PDF files",
     "fix the heading styles in this docx should go to office-docs/docx"],
    "1. Read the PDF with pypdf and list its pages and form fields.\n"
    "2. Merge, split or fill fields as the task asks, writing to a new file.\n"
    "3. Open the new file and compare its page count and field values with what was asked.")

OFFICE_SKILL = finished(
    "office-docs",
    "Use when producing or reading office documents: covers Word, PDF, spreadsheet, docx",
    ["convert the Word report to a PDF",
     "put the Word table into the PDF",
     "build the web app UI should go to /"],
    "1. Open the source with the sub-skill for its format.\n"
    "2. Hand the result to the sub-skill for the target format.\n"
    "3. Open the output once to confirm it is not corrupt.\n\n"
    "<!-- sub-skills -->\n<!-- /sub-skills -->")


# The READMEs quote what the tools print with the parameters the package ships with. A
# library that changes them (organizer/SKILL.md, "Parameters") still gets this test: the
# walkthrough runs on a copy whose checker is set back to these values, so the test keeps
# checking the documents and does not fail because an owner chose other numbers.
README_PARAMS = {"COVER_MAX": "5", "DESC_MAX": "200", "MAX_BODY": "150", "FANOUT": "9",
                 "OVERLAP": "0.4", "COVER_MIN": "2"}
README_TABLE = {"COVER_MAX": "5 words", "COVER_MIN": "2 characters", "DESC_MAX": "200 characters",
                "MAX_BODY": "150 lines", "FANOUT": "9", "OVERLAP": "0.4"}


def reset_params(tree):
    p = os.path.join(tree, "organizer", "scripts", "organizer_cli.py")
    with open(p, encoding="utf-8") as f:
        text = f.read()
    for name, value in README_PARAMS.items():
        text, n = re.subn(r"^%s = \S+" % name, "%s = %s" % (name, value), text, count=1, flags=re.M)
        assert n == 1, "organizer_cli.py no longer defines " + name
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    # `route` prints the size of the whole library, organizer/SKILL.md included, so its
    # parameter table goes back to the same values.
    p = os.path.join(tree, "organizer", "SKILL.md")
    with open(p, encoding="utf-8") as f:
        text = f.read()
    for name, value in README_TABLE.items():
        text, n = re.subn(r"^\| %s \| [^|]+ \|" % name, "| %s | %s |" % (name, value), text, count=1, flags=re.M)
        assert n == 1, "organizer/SKILL.md no longer lists " + name
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def run(args, cwd):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    p = subprocess.run([sys.executable] + args, cwd=cwd, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, text=True, encoding="utf-8", env=env)
    # The README shows POSIX paths; on Windows the tools print backslashes.
    return p.stdout.rstrip("\n").replace("\\", "/")


def quoted_blocks(readme):
    """Return a list of (command_line, expected_output) from fenced blocks."""
    blocks = re.findall(r"```\n(\$ python3 [^\n]*)\n(.*?)```", readme, re.S)
    return [(cmd[2:], out.rstrip("\n")) for cmd, out in blocks]


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def finish_walkthrough_skills(tree):
    """What the README tells the reader to do before `replay`: write the sentences and
    steps of the three new skills. The parent keeps its generated routing table."""
    write(os.path.join(tree, "office-docs", "docx", "SKILL.md"), DOCX_SKILL)
    write(os.path.join(tree, "office-docs", "pdf", "SKILL.md"), PDF_SKILL)
    write(os.path.join(tree, "office-docs", "SKILL.md"), OFFICE_SKILL)
    run([os.path.join("scripts", "holon.py"), "sync", "."], tree)


class TestReadmeOutputs(unittest.TestCase):
    def walk(self, readme_name):
        with open(os.path.join(ROOT, readme_name), encoding="utf-8") as f:
            text = f.read()
        blocks = quoted_blocks(text)
        self.assertGreaterEqual(len(blocks), 8, readme_name + " quotes fewer commands than expected")
        tmp = tempfile.mkdtemp()
        try:
            tree = os.path.join(tmp, "holon")
            shutil.copytree(ROOT, tree, ignore=shutil.ignore_patterns(
                "__pycache__", ".git", ".retired", "tests", ".pytest_cache"))
            # README measurements describe UTF-8/LF files. Canonicalize only this
            # disposable fixture, never the checkout or the tool's byte accounting.
            for directory, _, files in os.walk(tree):
                if "SKILL.md" in files:
                    path = os.path.join(directory, "SKILL.md")
                    with open(path, encoding="utf-8") as f:
                        content = f.read()
                    write(path, content)
            reset_params(tree)
            finished_skills = False
            for cmd, expected in blocks:
                args = shlex.split(cmd)
                self.assertEqual(args[0], "python3", cmd)
                if " replay " in cmd and not finished_skills:
                    finish_walkthrough_skills(tree)
                    finished_skills = True
                actual = run(args[1:], tree)
                if " replay " in cmd:
                    actual = actual.splitlines()[-1]
                self.assertEqual(actual, expected,
                                 "\n%s\n$ %s\n--- expected\n%s\n--- actual\n%s" % (readme_name, cmd, expected, actual))
            self.assertTrue(finished_skills, readme_name + " no longer shows replay")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        return text

    def test_english_readme_outputs_are_real(self):
        text = self.walk("README.md")
        self.assertIn(DOCX_SKILL.strip(), text, "README.md shows a finished docx that the test does not use")

    def test_chinese_readme_outputs_are_real(self):
        text = self.walk("README.zh-CN.md")
        self.assertIn(DOCX_SKILL.strip(), text, "README.zh-CN.md shows a finished docx that the test does not use")

    def test_windows_newline_default_does_not_change_fixture_bytes(self):
        from unittest import mock
        real_open = open

        def windows_open(file, mode="r", *args, **kwargs):
            if "w" in mode and "b" not in mode and kwargs.get("newline") is None:
                kwargs["newline"] = "\r\n"
            return real_open(file, mode, *args, **kwargs)

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "SKILL.md")
            with mock.patch.object(sys.modules[__name__], "open", side_effect=windows_open, create=True):
                write(path, DOCX_SKILL)
            with open(path, "rb") as f:
                self.assertEqual(f.read(), DOCX_SKILL.encode("utf-8"))

    def test_crlf_checkout_keeps_the_documented_lf_baseline(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "holon")
            shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns("__pycache__", ".git"))
            for directory, _, files in os.walk(source):
                if "SKILL.md" in files:
                    path = os.path.join(directory, "SKILL.md")
                    with open(path, encoding="utf-8") as f:
                        text = f.read()
                    with open(path, "w", encoding="utf-8", newline="\r\n") as f:
                        f.write(text)
            with mock.patch.object(sys.modules[__name__], "ROOT", source):
                self.walk("README.md")

    def test_host_count_in_readmes_is_the_table(self):
        """Both READMEs state how many agent tools `install` knows; the table decides."""
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import holon as tree_tool
        n = len(tree_tool.HOSTS)
        for name, pat in (("README.md", r"lists the (\d+) tools"), ("README.zh-CN.md", r"列出 `install` 认识的 (\d+) 个")):
            with open(os.path.join(ROOT, name), encoding="utf-8") as f:
                m = re.search(pat, f.read())
            self.assertIsNotNone(m, name + " no longer states the number of tools")
            self.assertEqual(int(m.group(1)), n, name)


if __name__ == "__main__":
    unittest.main(verbosity=1)
