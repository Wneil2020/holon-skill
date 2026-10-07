#!/usr/bin/env python3
# Copyright (c) 2026 Wneil2020 and the holon skill contributors. Released under the MIT License.
"""
holon: CLI scaffold for trees of AI Agent Skills. A sub-skill folder works on its own if copied
out of the tree, and inside the tree it is one step of the skill above it.

Zero-dependency (Python 3.8+ stdlib only), so any agent sandbox can run:
    python3 scripts/holon.py <command> [args]

Commands:
    init <name> [--root DIR | --parent DIR] [--desc D]
                                  Create a new skill (optionally nested)
    move SRC... --parent DIR [--copy] [--as NAME]
                                  Move (or copy) skill folders under a parent and re-sync both trees
    move --plan FILE [--copy]     Apply a placement plan: one `SRC -> DEST` per line (`DEST/` = into DEST)
    split DIR --show              Print SKILL.md with line numbers and sha256, for an agent to plan a split
    split --plan FILE             Move the planned line ranges into references/ or new sub-skills, verbatim
    sync [PATH]                   Inject sub-skill name+description into parent SKILL.md
    tree [PATH]                   Print the skill hierarchy as a tree
    validate [PATH]               Validate frontmatter / TODO placeholders / cycles / sync freshness
    migrate [PATH]                Move holon's fields under metadata: (Agent Skills spec form)
    install [SRC] [--path P] [--host NAME [--project] | --to DIR] [--as NAME]
                                  Copy a tree into a host's skills directory and validate it there.
                                  SRC: a path, a git URL, GitHub owner/repo, or a .zip/.tar.gz URL
All writing commands support --dry-run.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys

SKILL_FILE = "SKILL.md"
# Optional. Lives next to a parent SKILL.md and only decides how the routing
# table is sectioned and ordered; it never moves a directory.
GROUPS_FILE = "groups.md"
MARK_OPEN = "<!-- sub-skills -->"
MARK_CLOSE = "<!-- /sub-skills -->"

# A SKILL.md under one of these directory names is NOT a skill. `.retired/`
# and `_inbox/` are quarantine areas defined by the judgement layer
# (organizer): they keep complete SKILL.md files that must not take part in
# routing. The rest are VCS / cache directories. The mechanism layer and the
# judgement layer must share ONE definition of "what counts as a skill", so
# organizer_cli.py imports this set instead of keeping its own.
SKIP_DIRS = frozenset({".retired", "_inbox", ".git", "__pycache__", "node_modules"})

# Where each host reads skill folders from. `install` has no default host: it writes the tree
# once to the shared location of the Agent Skills standard, then adds the directory of every
# host found on this machine that does not read the shared one.
#
# Each entry: id, name, the user-level directories the host reads (the first is where
# `install` writes for it), the project-level ones (same order). `~` is the home directory,
# `<config>` is $XDG_CONFIG_HOME or ~/.config. Rows marked (docs) were checked against the
# host's own documentation on 2026-09-23; the rest come from the agent table of the `skills`
# CLI reference (chillicream.com/docs/skills/reference) and list one directory each.
SHARED_USER = "~/.agents/skills"
SHARED_PROJECT = ".agents/skills"
HOSTS = [
    # (docs) code.claude.com: ~/.claude/skills, .claude/skills; honours CLAUDE_CONFIG_DIR.
    ("claude", "Claude Code", ["$CLAUDE_CONFIG_DIR/skills"], [".claude/skills"]),
    # (docs) developers.openai.com/codex/skills: ~/.agents/skills; ~/.codex/skills still read.
    ("codex", "Codex", [SHARED_USER, "$CODEX_HOME/skills"], [SHARED_PROJECT]),
    # (docs) cursor.com/docs/skills: also the Claude and Codex directories.
    ("cursor", "Cursor", ["~/.cursor/skills", SHARED_USER, "$CLAUDE_CONFIG_DIR/skills", "$CODEX_HOME/skills"],
     [".cursor/skills", SHARED_PROJECT, ".claude/skills", ".codex/skills"]),
    # (docs) docs.github.com Copilot CLI: ~/.copilot/skills or ~/.agents/skills.
    ("copilot", "GitHub Copilot", ["~/.copilot/skills", SHARED_USER], [".github/skills", SHARED_PROJECT]),
    # (docs) geminicli.com/docs/cli/skills: ~/.gemini/skills and the ~/.agents/skills alias.
    ("gemini", "Gemini CLI", ["~/.gemini/skills", SHARED_USER], [".gemini/skills", SHARED_PROJECT]),
    # (docs) opencode.ai/docs/skills: its own, the Claude-compatible and the agents directories.
    ("opencode", "OpenCode", ["<config>/opencode/skills", "$CLAUDE_CONFIG_DIR/skills", SHARED_USER],
     [".opencode/skills", ".claude/skills", SHARED_PROJECT]),
    ("adal", "AdaL", ["~/.adal/skills"], [".adal/skills"]),
    ("aider-desk", "AiderDesk", ["~/.aider-desk/skills"], [".aider-desk/skills"]),
    ("amp", "Amp", ["<config>/agents/skills"], [SHARED_PROJECT]),
    ("antigravity", "Antigravity", ["~/.gemini/antigravity/skills"], [SHARED_PROJECT]),
    ("augment", "Augment", ["~/.augment/skills"], [".augment/skills"]),
    ("bob", "IBM Bob", ["~/.bob/skills"], [".bob/skills"]),
    ("cline", "Cline", [SHARED_USER], [SHARED_PROJECT]),
    ("codebuddy", "CodeBuddy", ["~/.codebuddy/skills"], [".codebuddy/skills"]),
    ("continue", "Continue", ["~/.continue/skills"], [".continue/skills"]),
    ("crush", "Crush", ["<config>/crush/skills"], [".crush/skills"]),
    ("deepagents", "Deep Agents", ["~/.deepagents/agent/skills"], [SHARED_PROJECT]),
    ("devin", "Devin for Terminal", ["<config>/devin/skills"], [".devin/skills"]),
    ("droid", "Droid", ["~/.factory/skills"], [".factory/skills"]),
    ("goose", "Goose", ["<config>/goose/skills"], [".goose/skills"]),
    ("junie", "Junie", ["~/.junie/skills"], [".junie/skills"]),
    ("kilo", "Kilo Code", ["~/.kilocode/skills"], [".kilocode/skills"]),
    ("kimi", "Kimi Code CLI", ["<config>/agents/skills"], [SHARED_PROJECT]),
    ("kiro", "Kiro CLI", ["~/.kiro/skills"], [".kiro/skills"]),
    ("mistral-vibe", "Mistral Vibe", ["$VIBE_HOME/skills"], [".vibe/skills"]),
    ("openhands", "OpenHands", ["~/.openhands/skills"], [".openhands/skills"]),
    ("qwen", "Qwen Code", ["~/.qwen/skills"], [".qwen/skills"]),
    ("roo", "Roo Code", ["~/.roo/skills"], [".roo/skills"]),
    ("trae", "Trae", ["~/.trae/skills"], [".trae/skills"]),
    ("warp", "Warp", [SHARED_USER], [SHARED_PROJECT]),
    ("windsurf", "Windsurf", ["~/.codeium/windsurf/skills"], [".windsurf/skills"]),
    ("zencoder", "Zencoder", ["~/.zencoder/skills"], [".zencoder/skills"]),
]
HOST_IDS = [h[0] for h in HOSTS]
# Hosts documented to scan a skills directory recursively. In them every sub-skill of a tree
# is also listed on its own, beside the root. Routing through the root still works.
RECURSIVE_HOSTS = {"cursor"}


def _resolve_dir(spec, base=None):
    """Turn a table entry into an absolute path. `base` is set for project-level entries."""
    if base is not None:
        return os.path.normpath(os.path.join(base, spec))
    env = {"$CLAUDE_CONFIG_DIR": os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude",
           "$CODEX_HOME": os.environ.get("CODEX_HOME") or "~/.codex",
           "$VIBE_HOME": os.environ.get("VIBE_HOME") or "~/.vibe",
           "<config>": os.environ.get("XDG_CONFIG_HOME") or "~/.config"}
    for k, v in env.items():
        if spec.startswith(k):
            spec = v + spec[len(k):]
    return os.path.normpath(os.path.expanduser(spec))


def host_present(host_id):
    """A host counts as installed when the folder of its own skills directory exists
    (~/.claude for ~/.claude/skills, ~/.config/opencode for <config>/opencode/skills). The
    shared ~/.agents is not evidence of any host, so a host whose only directory is the
    shared one is never "found"; it is served whenever the shared directory is written."""
    for h in HOSTS:
        if h[0] == host_id:
            # Its own directory is the first entry that is not the shared one. The later
            # entries of a host (Cursor's reading of ~/.claude/skills) belong to other
            # hosts and say nothing about whether this one is installed.
            shared = _resolve_dir(SHARED_USER)
            own = [d for d in (_resolve_dir(x) for x in h[2]) if d != shared][:1]
            return any(os.path.isdir(os.path.dirname(d)) for d in own)
    return False


# Not copied by `install`: caches and test folders anywhere; at the top of the source,
# `examples/` (other trees, which a host that scans recursively would load as skills) and
# plugin manifests (a host that finds one loads the folder as a plugin, which lists skills
# flat and hides the root SKILL.md; the copy is meant to be a plain skill folder).
INSTALL_SKIP_ANY = frozenset({".git", "__pycache__", ".pytest_cache", "tests"})
INSTALL_SKIP_TOP = frozenset({"examples", ".claude-plugin", ".cursor-plugin"})

TODO_DESC = ("TODO: one sentence - what this skill does and when to use it "
             "(it is injected into the parent's routing table)")

TEMPLATE = """---
name: {name}
description: "{description}"
{triggers}---

# {name}

1. TODO: first step, one action with a visible result. Put constraints on the step they constrain; put background in references/.

{mark_open}
{mark_close}
"""

TRIGGERS_TEMPLATE = """metadata:
  holon-triggers: |
    TODO: a task this skill should take
    TODO: a second task it should take
    TODO: a task it should not take should go to <path>
"""

ROOT_TEMPLATE = """---
name: {name}
description: "{description}"
metadata:
  holon-archive-count: "0"
---

# {name}

A skill folder may contain sub-skill folders. Any subfolder with a `SKILL.md` is a sub-skill. A parent `SKILL.md` lists its sub-skills between `<!-- sub-skills -->` markers; that list is the routing table, and a tool writes it.

When a loaded `SKILL.md` contains such a list:

1. **Go down only when a line matches.** Compare the task with each sub-skill's description and with the words its line says it also takes through its sub-skills. When one matches, read the `SKILL.md` in that subfolder before acting.
2. **Repeat at each level.** If that sub-skill lists further sub-skills, compare again and go down again.
3. **Read only what is on the path.** Never load every sub-skill in advance.
4. **If nothing matches, stay here.** Act on the current `SKILL.md`. Do not force a descent.
5. **Come back up when done.** When a sub-skill finishes, return to the parent and continue its remaining steps. The child's output is the parent's input.
6. **Report misses.** If no sub-skill matches, or the one reached does not handle the task, append one line to `_feedback.md` at the tree root: `task sentence | path taken | outcome`. Then carry on. The next absorption reads that line.

{mark_open}
{mark_close}
"""

ROOT_DESC = ("Use for every task: this is the root of the skill tree; read the sub-skills list below "
             "and descend to the branch the task matches: covers skill, task, sub-skill, routing table")

ROOT_FILES = {
    "_feedback.md": """# _feedback.md -- routing feedback (append-only, never edit or delete)

> Agent carrying out a task: when no sub-skill matches, when the sub-skill reached does not handle the task, or when one task needs several leaves, append one line below in the form
> `task sentence | path taken | outcome`
> `outcome` is one of: `miss`, `wrong -> <leaf actually needed>`, `multi`.
> Agent absorbing skills: handle these lines first in every absorption; append ` done` to each handled line.
""",
    "synonyms.md": """# synonyms.md -- one group per line, comma-separated; the first word is the standard form
""",
    "ABSORB.md": """# ABSORB.md

Each absorption is one section, `## @n <what came in> (<date>)`, with `learned:`, `merged:` and `ruled:` lines. Run `counter --bump` before writing a section; `@n` is the counter's new value.
""",
}

BLOCK_TITLE = "## Sub-skills (auto-generated, do not edit by hand)"
OTHER_SECTION = "Other"
ROUTING_RULE = (
    "Routing rule: when the task matches one of the sub-skills above, read the SKILL.md "
    "in that subdirectory for detailed instructions before acting;\n"
    "if that sub-skill lists deeper sub-skills, repeat the descent. "
    "Load only the documents on the matching path."
)


# ---------------------------------------------------------------- frontmatter

def _yaml_scalar(value, legacy_number=False):
    """Read our string-only YAML subset, refusing syntax we cannot interpret faithfully."""
    import json
    if any(ord(ch) < 32 and ch != "\t" for ch in value):
        raise ValueError("unescaped control character in scalar")
    if value.startswith('"'):
        try:
            return json.loads(value)
        except (ValueError, UnicodeError) as exc:
            raise ValueError("invalid or unsupported quoted scalar (use JSON-style double quotes): %s" % exc)
    if value.startswith("'"):
        if not re.fullmatch(r"'(?:[^']|'')*'", value):
            raise ValueError("invalid single-quoted scalar; double embedded apostrophes")
        return value[1:-1].replace("''", "'")
    if (not value or value[0] in "[]{}&*!|>@`%" or re.match(r"[-?:](?:\s|$)", value)
            or re.search(r":(?:\s|$)|(?:^|\s)#", value)):
        raise ValueError("unsupported or ambiguous plain scalar; quote the complete value")
    implicit = value.lower() in {"null", "~", "true", "false", "yes", "no", "on", "off", ".nan", ".inf", "-.inf", "+.inf"}
    if implicit or (re.match(r"[-+]?(?:[0-9]|\.[0-9])", value) and not legacy_number):
        raise ValueError("quote values that YAML could interpret as a number, boolean, null or date")
    return value


def _yaml_string(value):
    import json
    try:
        _yaml_scalar(value)
        return value
    except ValueError:
        return json.dumps(value, ensure_ascii=False)


def split_frontmatter(text):
    """Split SKILL.md text into (meta_dict, body_text, error_or_None).

    This is THE frontmatter parser for the whole tree: the organizer CLI
    imports it instead of keeping its own, so both tools always agree on
    what a file means. Supported YAML subset (all a SKILL.md needs):

      key: value            scalar; quotes are stripped and, for double
                            quotes, \\" and \\\\ are decoded, so values written
                            by `init --desc` round-trip losslessly
      key:                  followed by `- item` lines  -> list (triggers:)
      key: |                followed by indented lines -> multi-line string,
                            one line per source line
      key: >                followed by indented lines -> folded: the lines
                            are joined with single spaces (description:)

    A leading BOM (U+FEFF, left by some Windows editors) is ignored.
    Anything else is an error, and it is an error for BOTH tools.
    """
    text = text.lstrip("\ufeff")  # invisible BOM left by some editors is not content
    if not text.startswith("---"):
        return {}, text, "missing frontmatter (file must start with ---)"
    lines = text.splitlines()
    if lines[0].strip() != "---":
        return {}, text, "invalid opening frontmatter delimiter"
    end = None
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            end = i
            break
    if end is None:
        return {}, "", "unterminated frontmatter (no closing ---)"
    body = "\n".join(lines[end + 1:])
    meta = {}
    target = meta       # dict being filled: meta, or meta["metadata"] while inside that map
    cur_list = None
    cur_block = None    # (dict, key) of the block scalar whose indented lines we are collecting
    block_sep = "\n"    # `|` keeps newlines; `>` folds continuation lines into one
    block_indent = None
    block_parent_indent = 0
    map_indent = None
    list_parent_indent, list_indent = 0, None
    for raw in lines[1:end]:
        line = raw.strip()
        indent = len(raw) - len(raw.lstrip(" \t"))
        if "\t" in raw[:indent]:
            return {}, body, "tabs are not supported for frontmatter indentation"
        if not line:
            continue
        if cur_block is not None and indent > block_parent_indent and (block_indent is None or indent >= block_indent):
            d, k = cur_block
            block_indent = indent if block_indent is None else block_indent
            d[k] += (block_sep if d[k] else "") + line
            continue
        if line.startswith("#"):
            continue
        cur_block = None
        block_indent = None
        if line.startswith("- ") and cur_list is not None:
            if indent < list_parent_indent or (list_indent is not None and indent != list_indent):
                return {}, body, "inconsistent list indentation"
            list_indent = indent
            try:
                cur_list.append(_yaml_scalar(line[2:].strip()))
            except ValueError as exc:
                return {}, body, str(exc)
            continue
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_-]* *:(?:[ \t]|$)", line):
            return meta, body, "invalid or unsupported frontmatter mapping line: %r" % raw
        if indent == 0:
            target = meta   # a top-level key ends the metadata map
        elif target is meta:
            return {}, body, "unexpected indentation outside metadata or a block scalar"
        elif map_indent is None:
            map_indent = indent
        elif indent != map_indent:
            return {}, body, "metadata must be a flat map with consistent indentation"
        key, _, value = line.partition(":")
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", key):
            return {}, body, "unsupported frontmatter key: %r" % key
        value = value.strip()
        if key in target:
            return {}, body, "duplicate frontmatter field: %s" % key
        if value == "" and key == METADATA_KEY and target is meta:
            meta[METADATA_KEY] = {}
            target = meta[METADATA_KEY]
            map_indent = None
            cur_list = None
            continue
        if value == "":  # empty value => start of a list field
            target[key] = []
            cur_list = target[key]
            list_parent_indent, list_indent = indent, None
            continue
        cur_list = None
        if value in ("|", "|-", ">", ">-"):  # start of a block scalar
            target[key] = ""
            cur_block = (target, key)
            block_parent_indent = indent
            block_sep = " " if value[0] == ">" else "\n"
            continue
        try:
            target[key] = _yaml_scalar(value, legacy_number=(target is meta and key == "archive_count"))
        except ValueError as exc:
            return {}, body, "%s: %s" % (key, exc)
    type_error = frontmatter_type_error(meta)
    if type_error:
        return {}, body, type_error
    _lift_holon_metadata(meta)
    return meta, body, None


METADATA_KEY = "metadata"
TRIGGERS_META = "holon-triggers"          # metadata key: one example sentence per line
ARCHIVE_META = "holon-archive-count"      # metadata key: the root's absorption counter
SPEC_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}


def frontmatter_type_error(meta):
    """Keep malformed YAML values out of the string-based routing tools."""
    for key in ("name", "description", "license", "compatibility", "allowed-tools"):
        if key in meta and not isinstance(meta[key], str):
            return "%s must be a string" % key
    if METADATA_KEY in meta:
        md = meta[METADATA_KEY]
        if not isinstance(md, dict) or any(not isinstance(v, str) for v in md.values()):
            return "metadata must be a map of strings"
    return None


def _lift_holon_metadata(meta):
    """The Agent Skills spec allows only six frontmatter fields, and `metadata` must be a
    map of string to string. holon's two fields live there: `holon-triggers`, a block
    scalar with one sentence per line, and `holon-archive-count`. This lifts them to
    meta["triggers"] (a list) and meta["archive_count"] so the rest of both tools reads
    them as before. Old-style top-level `triggers:` / `archive_count:` still parse; the
    validate command reports them, and `migrate` rewrites them."""
    md = meta.get(METADATA_KEY)
    if not isinstance(md, dict):
        return
    if TRIGGERS_META in md and "triggers" not in meta:
        meta["triggers"] = [s.strip() for s in str(md[TRIGGERS_META]).splitlines() if s.strip()]
    if ARCHIVE_META in md and "archive_count" not in meta:
        meta["archive_count"] = str(md[ARCHIVE_META]).strip()


def spec_field_problems(meta, dirname=None):
    """What the Agent Skills spec (agentskills.io/specification) would reject. Returned as
    a list of strings; empty when the frontmatter is spec-clean."""
    type_error = frontmatter_type_error(meta)
    if type_error:
        return [type_error]
    out = []
    extra = sorted(k for k in meta if k not in SPEC_FIELDS and k not in ("triggers", "archive_count"))
    if extra:
        out.append("frontmatter has fields the Agent Skills spec does not allow: %s" % ", ".join(extra))
    md = meta.get(METADATA_KEY)
    if "triggers" in meta and not (isinstance(md, dict) and TRIGGERS_META in md):
        out.append("`triggers:` is a top-level field; the spec allows it only as metadata.%s (run `holon.py migrate`)" % TRIGGERS_META)
    if "archive_count" in meta and not (isinstance(md, dict) and ARCHIVE_META in md):
        out.append("`archive_count:` is a top-level field; the spec allows it only as metadata.%s (run `holon.py migrate`)" % ARCHIVE_META)
    name = meta.get("name", "")
    if name:
        if len(name) > 64:
            out.append("name is longer than 64 characters")
        if name != name.lower() or not all(c.isalnum() or c == "-" for c in name):
            out.append("name %r: the spec allows lowercase letters, digits and hyphens only" % name)
        if name.startswith("-") or name.endswith("-") or "--" in name:
            out.append("name %r: no leading, trailing or doubled hyphen" % name)
        if dirname is not None and dirname and name != dirname:
            out.append("name %r does not match its directory %r" % (name, dirname))
    desc = meta.get("description", "")
    if len(desc) > 1024:
        out.append("description is longer than 1024 characters")
    return out


def parse_frontmatter(text):
    """Parse frontmatter only -> (dict, error_or_None). See split_frontmatter."""
    meta, _, err = split_frontmatter(text)
    return meta, err


def body_todo_lines(body):
    """Return 1-based line numbers of TODO placeholder lines in the body.

    A line counts when it starts with `TODO` (after optional list bullet,
    numbered-list or blockquote marks) and sits outside fenced code blocks.
    `init` writes one such line into every new SKILL.md; validate must not
    let it ship.
    """
    fences = _fence_spans(body)
    hits = []
    pos = 0
    for n, line in enumerate(body.splitlines(), 1):
        start = pos
        pos += len(line) + 1
        if any(a <= start < b for a, b in fences):
            continue
        if re.match(r"^\s*(?:(?:[-*>]|\d+[.)])\s*)*TODO\b", line):
            hits.append(n)
    return hits


def read_skill(path):
    """Read SKILL.md in a skill directory -> (text, meta, error)."""
    fp = os.path.join(path, SKILL_FILE)
    try:
        with open(fp, "r", encoding="utf-8") as f:
            text = f.read()
    except (OSError, UnicodeError) as e:
        return None, {}, "cannot read %s: %s" % (fp, e)
    meta, err = parse_frontmatter(text)
    return text, meta, err


def read_skill_doc(path):
    """Read SKILL.md -> (meta, body, error). Body excludes the frontmatter."""
    fp = os.path.join(path, SKILL_FILE)
    try:
        with open(fp, "r", encoding="utf-8") as f:
            text = f.read()
    except (OSError, UnicodeError) as e:
        return {}, "", "cannot read %s: %s" % (fp, e)
    return split_frontmatter(text)


# ---------------------------------------------------------------- discovery

def is_skill_dir(path):
    return os.path.isfile(os.path.join(path, SKILL_FILE))


def _subdirs(path):
    """Sorted immediate subdirectories, minus SKIP_DIRS."""
    try:
        entries = sorted(os.listdir(path))
    except OSError:
        return []
    return [os.path.join(path, n) for n in entries
            if n not in SKIP_DIRS and os.path.isdir(os.path.join(path, n))]


def child_skill_dirs(path):
    """Immediate sub-skill directories, sorted by directory name."""
    return [sub for sub in _subdirs(path) if is_skill_dir(sub)]


def _scan_non_skill(root):
    """When root itself is not a skill, scan one level down for skill dirs."""
    return _subdirs(root)


def find_root_skills(base):
    """Find all top-level skills under base at ANY depth (a top-level skill
    is a skill dir whose ancestors are not skill dirs). If base itself is a
    skill, it is the single root."""
    if is_skill_dir(base):
        return [base]
    roots = []
    for dirpath, dirnames, _ in os.walk(base, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        if is_skill_dir(dirpath):
            roots.append(dirpath)
            dirnames[:] = []  # descendants handled by skill-tree recursion
    return roots


def path_within(path, root):
    """Containment follows links and handles paths on different Windows drives."""
    try:
        root = os.path.realpath(root)
        return os.path.commonpath([os.path.realpath(path), root]) == root
    except ValueError:
        return False


def remove_tree(path):
    """Remove temporary trees, retrying Windows read-only regular files only."""
    import stat

    def retry(function, filename, error):
        if not isinstance(error, PermissionError):
            raise error
        mode = os.stat(filename, follow_symlinks=False).st_mode
        if not stat.S_ISREG(mode) or mode & stat.S_IWUSR:
            raise error
        os.chmod(filename, mode | stat.S_IWUSR)
        function(filename)

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=retry)
    else:
        shutil.rmtree(path, onerror=lambda function, filename, info: retry(function, filename, info[1]))


def collect_skills(root):
    """Return (skill_dir_list, cycle_error_list)."""
    errors = []
    skills = []

    def rec(path, visited):
        real = os.path.realpath(path)
        if not path_within(path, root) or not path_within(os.path.join(path, SKILL_FILE), root):
            errors.append("path escapes the skill tree: %s" % path)
            return
        if real in visited:
            errors.append("circular reference detected at: %s" % path)
            return
        visited = visited | {real}
        if is_skill_dir(path):
            skills.append(path)
            for sub in child_skill_dirs(path):
                rec(sub, visited)
        else:
            for sub in _scan_non_skill(path):
                rec(sub, visited)

    rec(root, set())
    return skills, errors


# ---------------------------------------------------------------- groups

def read_groups(parent_dir):
    """Read the optional groups.md next to a parent SKILL.md.

    One group per line: `Title: child-dir, child-dir`. Returns
    (ordered list of (title, [names]), error list). A child may appear in
    several groups (it is then listed under each); children in no group are
    rendered under a trailing "Other" section. The file only shapes the
    routing table -- nothing on disk moves."""
    fp = os.path.join(parent_dir, GROUPS_FILE)
    if not os.path.isfile(fp):
        return [], []
    groups, errors, seen = [], [], set()
    try:
        with open(fp, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        return [], ["cannot read %s: %s" % (fp, e)]
    children = {os.path.basename(c) for c in child_skill_dirs(parent_dir)}
    for n, raw in enumerate(text.lstrip("\ufeff").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        title, sep, rest = line.partition(":")
        if not sep:
            title, sep, rest = line.partition("\uff1a")  # full-width colon
        title = title.strip()
        if not sep or not title:
            errors.append("%s line %d is not of the form `Title: child-dir, child-dir`: %r"
                          % (GROUPS_FILE, n, raw))
            continue
        if title in seen:
            errors.append("%s line %d: group '%s' appears twice" % (GROUPS_FILE, n, title))
            continue
        seen.add(title)
        names = [w.strip() for w in re.split(r"[,\uff0c\u3001]", rest) if w.strip()]
        if not names:
            errors.append("%s line %d: group '%s' has no members" % (GROUPS_FILE, n, title))
            continue
        for w in names:
            if w not in children:
                errors.append("%s line %d: '%s' in group '%s' is not a sub-skill here"
                              % (GROUPS_FILE, n, w, title))
        groups.append((title, names))
    return groups, errors


# ---------------------------------------------------------------- rendering

COVER_SPLIT = r"[,\uff0c\u3001/]"   # the organizer's WORD_SPLIT: comma, full-width comma, ideographic comma, slash


def description_clauses(desc):
    """Shared, ordered covers/excludes lists; prose words are not clause markers."""
    text = desc or ""
    matches = list(re.finditer(r"(?:^|[:\uff1a;\uff1b])\s*(covers|excludes)(?=\s|$)", text, re.I))
    values, errors = {"covers": [], "excludes": []}, []
    seen = set()
    for i, match in enumerate(matches):
        key = match.group(1).lower()
        if key in seen:
            errors.append("duplicate %s clause" % key)
        seen.add(key)
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        value = re.split(r"[;\uff1b]", text[match.end():end], maxsplit=1)[0]
        values[key].extend(w.strip() for w in re.split(COVER_SPLIT, value) if w.strip())
    return values["covers"], values["excludes"], errors


def description_covers(desc):
    """Cover words of a three-part description, in the order written."""
    return description_clauses(desc)[0]


def descendant_covers(sub):
    """Cover words of every skill below `sub` that `sub`'s own description does not already
    list, case-insensitively de-duplicated, nearest level first. A sub-skill is a step of its
    parent, so the organizer's `route` lets a parent take a sentence by a word of any skill
    below it. Listing those words in the parent's line puts the same words in front of the
    agent that reads the table, so what `replay` checks is what the agent sees."""
    _, meta, err = read_skill(sub)
    seen = {w.lower() for w in description_covers(meta.get("description", ""))} if not err else set()
    out, level = [], child_skill_dirs(sub)
    while level:
        nxt = []
        for d in level:
            _, m, e = read_skill(d)
            if not e:
                for w in description_covers(m.get("description", "")):
                    if w.lower() not in seen:
                        seen.add(w.lower())
                        out.append(w)
            nxt += child_skill_dirs(d)
        level = nxt
    return out


def _entry_line(sub):
    name = os.path.basename(sub)
    _, meta, err = read_skill(sub)
    desc = meta.get("description", "") if not err else "(frontmatter parse error)"
    display = meta.get("name") or name
    line = "- **%s** (`%s/`): %s" % (display, name, desc or "(missing description)")
    below = descendant_covers(sub)
    if below:
        line += "\n  - also takes, through its sub-skills: " + ", ".join(below)
    return line


def grouped_children(parent_dir):
    """Children as ordered (title, [dirs]) sections. Without groups.md it is a
    single section with title None; with it, one section per group plus a
    trailing "Other" for children in no group. Shared by render_block and tree
    so the routing table and the printed tree always agree."""
    subs = child_skill_dirs(parent_dir)
    groups, _ = read_groups(parent_dir)
    if not groups:
        return [(None, subs)]
    by_name = {os.path.basename(s): s for s in subs}
    sections, grouped = [], set()
    for title, names in groups:
        members = [by_name[n] for n in names if n in by_name]
        if members:
            grouped.update(names)
            sections.append((title, members))
    rest = [s for s in subs if os.path.basename(s) not in grouped]
    if rest:
        sections.append((OTHER_SECTION, rest))
    return sections


def render_block(parent_dir):
    """Render the injected sub-skills block content for a parent skill.
    With a groups.md present the list is split into `### Title` sections
    (unlisted children go under `### Other`); otherwise it is one flat list."""
    lines = [BLOCK_TITLE, ""]
    sections = grouped_children(parent_dir)
    for title, members in sections:
        if title:
            lines.append("### " + title)
        lines += [_entry_line(s) for s in members]
        lines.append("")
    lines.pop()  # blank line between sections; not after the last one
    lines += ["", ROUTING_RULE]
    return "\n".join(lines)


def _fence_spans(text):
    """Return (start, end) spans of fenced code blocks (``` or ~~~).

    Markers inside these spans are documentation examples, never real
    injection targets. An unclosed fence extends to end of text.
    """
    spans = []
    open_at = None
    for m in re.finditer(r"^(?:```|~~~)", text, re.MULTILINE):
        if open_at is None:
            open_at = m.start()
        else:
            spans.append((open_at, m.end()))
            open_at = None
    if open_at is not None:
        spans.append((open_at, len(text)))
    return spans


def _find_marker_pair(text):
    """Locate the first real (outside-code-fence) marker pair.

    Returns (open_idx, close_idx); close_idx is None when only the opening
    marker exists outside fences; (None, None) when no real marker exists.
    """
    spans = _fence_spans(text)

    def is_doc_example(i, marker):
        # inside a fenced code block
        if any(a <= i < b for a, b in spans):
            return True
        # wrapped in inline code: `<!-- sub-skills -->`
        end = i + len(marker)
        if i > 0 and text[i - 1] == "`" and end < len(text) and text[end] == "`":
            return True
        return False

    pos = 0
    while True:
        i = text.find(MARK_OPEN, pos)
        if i == -1:
            return None, None
        if is_doc_example(i, MARK_OPEN):
            pos = i + len(MARK_OPEN)
            continue
        j = text.find(MARK_CLOSE, i + len(MARK_OPEN))
        while j != -1 and is_doc_example(j, MARK_CLOSE):
            j = text.find(MARK_CLOSE, j + len(MARK_CLOSE))
        return i, (j if j != -1 else None)


def inject(text, block):
    """Replace content between markers with block. Returns (new_text, status).

    status: 'updated' | 'unchanged' | 'no-marker' | 'appended-marker'
    Idempotent: running twice yields identical output. Marker pairs that sit
    inside fenced code blocks are treated as documentation and skipped.
    """
    if block:
        wrapped = "%s\n%s\n%s" % (MARK_OPEN, block, MARK_CLOSE)
    else:  # no sub-skills: reset to an empty marker pair, clearing any stale table
        wrapped = "%s\n%s" % (MARK_OPEN, MARK_CLOSE)
    i, j = _find_marker_pair(text)
    if i is None:
        return text, "no-marker"
    if j is not None:
        new_text = text[:i] + wrapped + text[j + len(MARK_CLOSE):]
        return new_text, ("unchanged" if new_text == text else "updated")
    # opening marker only -> complete it
    new_text = text[:i] + wrapped + text[i + len(MARK_OPEN):]
    return new_text, "updated"


def append_marker(text, block):
    wrapped = "%s\n%s\n%s" % (MARK_OPEN, block, MARK_CLOSE)
    if not text.endswith("\n"):
        text += "\n"
    return text + "\n" + wrapped + "\n"


# ---------------------------------------------------------------- commands

def cmd_init(args):
    problems = spec_field_problems({"name": args.name, "description": args.desc or ""})
    if not args.name or problems or (args.desc and len(args.desc.splitlines()) != 1):
        print("error: give a valid skill name and a one-line description")
        return 1
    parent = args.parent
    if parent:
        if not is_skill_dir(parent):
            print("error: --parent %r is not a skill directory (no SKILL.md)" % parent)
            return 1
        target = os.path.join(parent, args.name)
    else:
        target = os.path.join(args.root or ".", args.name)
    skill_md = os.path.join(target, SKILL_FILE)
    if os.path.exists(skill_md):
        print("error: %s already exists" % skill_md)
        return 1
    # Escape for a double-quoted YAML scalar: backslashes first, then quotes.
    # parse_frontmatter() decodes these, so the description round-trips as-is.
    desc = args.desc or TODO_DESC
    import json
    desc = json.dumps(desc)[1:-1]
    if parent:
        # Every skill below the root carries three example sentences (the organizer's replay
        # test) and a body the writer fills in.
        content = TEMPLATE.format(name=args.name, description=desc, triggers=TRIGGERS_TEMPLATE,
                                  mark_open=MARK_OPEN, mark_close=MARK_CLOSE)
        extra = {}
    else:
        # A root is never routed to. Its body is the six reading rules, its description says
        # it is the entry point, and it carries the three ledgers the rules write to.
        root_desc = args.desc or ROOT_DESC
        root_desc = json.dumps(root_desc)[1:-1]
        content = ROOT_TEMPLATE.format(name=args.name, description=root_desc,
                                       mark_open=MARK_OPEN, mark_close=MARK_CLOSE)
        extra = ROOT_FILES
    content = re.sub(r"(?m)^name:.*$", lambda m: "name: " + _yaml_string(args.name), content, count=1)
    if args.dry_run:
        print("[dry-run] would create %s:\n%s" % (skill_md, content))
        for fn in extra:
            print("[dry-run] would create %s" % os.path.join(target, fn))
        if not parent and not getattr(args, "bare", True):
            print("[dry-run] would copy scripts/, organizer/, editing/ into %s" % target)
        return 0
    os.makedirs(target, exist_ok=True)
    with open(skill_md, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("created: %s" % skill_md)
    for fn, text in extra.items():
        fp = os.path.join(target, fn)
        if not os.path.exists(fp):
            with open(fp, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            print("created: %s" % fp)
    if parent:
        ns = argparse.Namespace(path=parent, dry_run=False, auto_append=True)
        cmd_sync(ns)
        _sync_ancestors(parent)
    elif not getattr(args, "bare", True):
        # A root is maintained where it lands, so it gets the tree tool, the rules and the
        # editing steps from the package this script belongs to. --bare leaves them out.
        _complete_tools(target, _this_package())
        ns = argparse.Namespace(path=target, dry_run=False, auto_append=True)
        cmd_sync(ns)
    return 0


def _sync_ancestors(path):
    """Re-render the routing table of every skill above `path`. A parent's line lists the
    cover words of the skills below it, so a new grandchild changes the grandparent's table.
    Paths are printed in the form they were given (`office-docs` -> `.`), never through
    os.path.relpath, which fails across Windows drives (a tree under %TEMP% on C:, run from D:)."""
    cur = os.path.normpath(path)
    while True:
        up = os.path.dirname(cur) or "."
        if os.path.abspath(up) == os.path.abspath(cur) or not is_skill_dir(up):
            return
        cur = up
        text, _, err = read_skill(cur)
        if text is None or err:
            return
        new_text, status = inject(text, render_block(cur))
        if status == "updated":
            with open(os.path.join(cur, SKILL_FILE), "w", encoding="utf-8", newline="\n") as f:
                f.write(new_text)
            print("also synced %s/SKILL.md (it lists the words of the skills below it)" % cur.replace(os.sep, "/"))


def cmd_sync(args):
    root = args.path or "."
    skills, cycles = collect_skills(root)
    for c in cycles:
        print("error: %s" % c)
    if cycles:
        return 1
    if not skills:
        print("no skill (directory containing SKILL.md) found under %s" % root)
        return 1
    documents = {sk: read_skill(sk) for sk in skills}
    for sk, (_, _, err) in documents.items():
        if err:
            print("error: %s: %s" % (sk, err))
            return 1
    changed = 0
    for sk in skills:
        subs = child_skill_dirs(sk)
        text, meta, err = documents[sk]
        if text is None:
            print("skip  %s: %s" % (sk, err))
            continue
        if not subs:
            # all sub-skills removed: reset any stale routing table to an empty marker pair
            new_text, status = inject(text, "")
            if status == "updated":
                changed += 1
                if args.dry_run:
                    print("[dry-run] would clear stale routing table in %s/SKILL.md (no sub-skills left)" % sk)
                else:
                    with open(os.path.join(sk, SKILL_FILE), "w", encoding="utf-8", newline="\n") as f:
                        f.write(new_text)
                    print("synced %s/SKILL.md (no sub-skills left; routing table cleared)" % sk)
            continue
        block = render_block(sk)
        new_text, status = inject(text, block)
        if status == "no-marker":
            if args.auto_append:
                new_text = append_marker(text, block)
                status = "updated"
                print("note  %s/SKILL.md had no marker pair; appended at end of file" % sk)
            else:
                print("warn  %s/SKILL.md has no %s marker; skipped" % (sk, MARK_OPEN))
                continue
        if status == "updated":
            changed += 1
            if args.dry_run:
                print("[dry-run] would update %s/SKILL.md (%d sub-skills)" % (sk, len(subs)))
            else:
                with open(os.path.join(sk, SKILL_FILE), "w", encoding="utf-8", newline="\n") as f:
                    f.write(new_text)
                print("synced %s/SKILL.md (%d sub-skills)" % (sk, len(subs)))
        else:
            print("ok     %s/SKILL.md is up to date" % sk)
    print("done: %d file(s) %s" % (changed, "would be updated" if args.dry_run else "updated"))
    return 0


def tree_root_of(path):
    """The top skill of the tree `path` belongs to: walk up while the parent folder is a skill."""
    cur = os.path.abspath(path)
    while is_skill_dir(os.path.dirname(cur)) and os.path.dirname(cur) != cur:
        cur = os.path.dirname(cur)
    return cur


def read_plan(path):
    """A placement plan: one `SRC -> DEST` per line, `#` comments. DEST is where the skill
    folder ends up, parent and name together (`flat/word-docs -> lib/office-docs/docx`); a DEST
    ending in `/` is a parent and the folder keeps its name. The meaning of a line does not
    depend on what exists on disk, so a plan reads the same before and after it is applied.
    Relative paths are relative to the plan file. Returns ([(src, parent, name)], errors)."""
    base = os.path.dirname(os.path.abspath(path))
    moves, errors = [], []
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().lstrip("\ufeff").splitlines()
    for n, raw in enumerate(lines, 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        src, sep, dst = line.partition("->")
        src, dst = src.strip(), dst.strip()
        if not sep or not src or not dst:
            errors.append("%s line %d is not `SRC -> DEST`: %r" % (path, n, raw))
            continue
        src = os.path.normpath(os.path.join(base, os.path.expanduser(src)))
        into = dst.endswith(("/", "\\"))
        dst = os.path.normpath(os.path.join(base, os.path.expanduser(dst)))
        if into:
            moves.append((src, dst, os.path.basename(src)))
        else:
            moves.append((src, os.path.dirname(dst), os.path.basename(dst)))
    return moves, errors


def check_move(src, parent, name, planned=()):
    """Why moving `src` to `parent/name` is not possible, or None."""
    if not is_skill_dir(src):
        return "%s is not a skill folder (no %s)" % (src, SKILL_FILE)
    if not is_skill_dir(parent):
        return "%s is not a skill folder; create the parent first with init" % parent
    if spec_field_problems({"name": name, "description": "x"}):
        return "%r is not a valid skill folder name (lowercase letters, digits, single hyphens)" % name
    target = os.path.join(parent, name)
    if os.path.lexists(target) or os.path.normcase(os.path.realpath(target)) in planned:
        return "%s already exists" % target
    if path_within(parent, src):
        return "cannot move %s into itself (%s)" % (src, parent)
    if os.path.islink(src):
        return "%s is a link; move the folder it points to" % src
    return None


def _rename_skill(skill_md, name):
    """Make `name:` in the header equal the new folder name (the spec requires it)."""
    with open(skill_md, "r", encoding="utf-8") as f:
        text = f.read()
    new = re.sub(r"(?m)^(name:[ \t]*).*$", lambda m: m.group(1) + _yaml_string(name), text, count=1)
    if new != text:
        with open(skill_md, "w", encoding="utf-8", newline="\n") as f:
            f.write(new)
        return True
    return False


def _move_documents(root):
    """Preflight every document sync may write; snapshots are byte-for-byte, not parsed text."""
    import stat
    if os.path.islink(root):
        raise OSError("move does not accept a linked tree root: %s" % root)
    skills, errors = collect_skills(root)
    if errors:
        raise OSError("; ".join(errors))
    documents = {}
    for sk in skills:
        fp = os.path.join(sk, SKILL_FILE)
        mode = os.lstat(fp)
        if (os.path.islink(sk) or getattr(os.lstat(sk), "st_file_attributes", 0) & 0x400
                or not stat.S_ISREG(mode.st_mode) or mode.st_nlink != 1):
            raise OSError("move requires unlinked, regular skill documents: %s" % fp)
        _, _, err = read_skill(sk)
        if err:
            raise OSError("%s: %s" % (sk, err))
        with open(fp, "rb") as f:
            documents[fp] = f.read()
    return documents


def _check_move_files(src):
    """Conservative move policy: no symlinks, junctions or special files, even in assets."""
    import stat
    def visit(path):
        info = os.lstat(path)
        if os.path.islink(path) or getattr(os.path, "isjunction", lambda p: False)(path):
            raise OSError("move does not accept links or junctions: %s" % path)
        # Windows junction detection on Python versions before os.path.isjunction.
        if getattr(info, "st_file_attributes", 0) & 0x400:
            raise OSError("move does not accept reparse points: %s" % path)
        if stat.S_ISDIR(info.st_mode):
            for name in os.listdir(path):
                visit(os.path.join(path, name))
        elif not stat.S_ISREG(info.st_mode):
            raise OSError("move requires regular files: %s" % path)
    visit(src)


def _execute_move(moves, roots, documents, copy=False):
    """Stage all copies, retain originals until sync succeeds, restore on caught failures.

    Not an atomic multi-directory transaction: no concurrent writers or crash recovery promise.
    A journal and original copies are retained if rollback itself fails.
    """
    import json
    import tempfile
    items, recovery, keep = [], None, False
    outcome = 1
    try:
        recovery = tempfile.mkdtemp(prefix="holon-move-recovery-")
        saved = []
        for i, (path, data) in enumerate(sorted(documents.items())):
            name = "%d.bin" % i
            with open(os.path.join(recovery, name), "wb") as f:
                f.write(data)
            saved.append({"path": path, "backup": name})
        for src, parent, name in moves:
            work = tempfile.mkdtemp(prefix=".holon-move-", dir=parent)
            item = {"src": src, "target": os.path.join(parent, name), "work": work,
                    "new": os.path.join(work, "new"), "old_work": None, "old": None,
                    "published": False, "hidden": False, "renamed": False}
            items.append(item)
            if not copy:
                item["old_work"] = tempfile.mkdtemp(prefix=".holon-move-", dir=os.path.dirname(src))
                item["old"] = os.path.join(item["old_work"], "old")
        # Paths for restoring both folders and original routing tables, even after an interruption.
        with open(os.path.join(recovery, "recovery.json"), "w", encoding="utf-8") as f:
            json.dump({"copy": copy, "documents": saved,
                       "note": "Path map only: inspect current files before manual recovery.",
                       "items": [{k: item[k] for k in ("src", "target", "work", "new", "old_work", "old")}
                                 for item in items]}, f, ensure_ascii=False, indent=2)
        for item in items:
            # Keep all assets, hidden files and tests; moving must not silently discard user files.
            shutil.copytree(item["src"], item["new"], symlinks=False)
            item["renamed"] = _rename_skill(os.path.join(item["new"], SKILL_FILE),
                                            os.path.basename(item["target"]))
        for item in items:
            if os.path.lexists(item["target"]):
                raise OSError("destination appeared during move: %s" % item["target"])
            if not copy:
                os.replace(item["src"], item["old"])
                item["hidden"] = True
            os.replace(item["new"], item["target"])
            item["published"] = True
        for root in sorted(roots):
            if cmd_sync(argparse.Namespace(path=root, dry_run=False, auto_append=True)):
                raise OSError("sync failed for %s" % root)
        for item in items:
            print("%s: %s -> %s%s" % ("copied" if copy else "moved", item["src"], item["target"],
                                      " (name: set to %s)" % os.path.basename(item["target"])
                                      if item["renamed"] else ""))
        outcome = 0
    except BaseException as exc:
        failures = []
        for item in reversed(items):
            try:
                if item["published"]:
                    remove_tree(item["target"])
                if item["hidden"]:
                    if os.path.lexists(item["src"]):
                        raise OSError("source reappeared; not overwriting it: %s" % item["src"])
                    os.replace(item["old"], item["src"])
            except OSError as err:
                failures.append(str(err))
        for path, data in documents.items():
            try:
                with open(path, "rb") as f:
                    same = f.read() == data
                if not same:
                    with open(path, "wb") as f:
                        f.write(data)
            except OSError as err:
                failures.append(str(err))
        if failures:
            keep = True
            print("error: move rollback incomplete; recovery retained: %s" % recovery)
            print("stop editing these trees; recovery.json maps original folders and saved SKILL.md bytes")
            for item in items:
                if item["old"] and os.path.exists(item["old"]):
                    print("restore folder: %s -> %s" % (item["old"], item["src"]))
                if os.path.exists(item["target"]):
                    print("inspect remaining target: %s" % item["target"])
            for error in failures:
                print("error: " + error)
        else:
            print("move failed; original folders and routing tables restored")
        if not isinstance(exc, (OSError, UnicodeError, ValueError)):
            raise
        print("error: %s" % exc)
    finally:
        if not keep:
            cleanup = [p for item in items for p in (item["work"], item["old_work"]) if p]
            # Clean working copies first. If cleanup fails, retain the recovery map as well.
            for path in cleanup:
                try:
                    remove_tree(path)
                except OSError as err:
                    keep = True
                    outcome = 1
                    print("error: retained move work at %s: %s" % (path, err))
            if recovery and not keep:
                try:
                    remove_tree(recovery)
                except OSError as err:
                    outcome = 1
                    print("error: recovery cleanup incomplete at %s: %s" % (recovery, err))
            elif recovery:
                print("recovery retained: %s" % recovery)
    return outcome


def cmd_move(args):
    """Preflight a whole plan, stage changes and restore originals on caught execution errors."""
    if args.plan:
        if args.src or args.parent or args.as_name:
            print("error: give either --plan FILE or SRC... --parent DIR, not both")
            return 1
        moves, errors = read_plan(args.plan)
    else:
        if not args.src or not args.parent:
            print("error: give SRC... --parent DIR, or --plan FILE")
            return 1
        if args.as_name and len(args.src) != 1:
            print("error: --as names one folder; give a single SRC")
            return 1
        errors = []
        moves = [(s, args.parent, args.as_name or os.path.basename(os.path.normpath(s))) for s in args.src]
    moves = [(os.path.abspath(s), os.path.abspath(p), n) for s, p, n in moves]
    planned = set()
    for i, (src, parent, name) in enumerate(moves):
        why = check_move(src, parent, name, planned)
        if why:
            errors.append(why)
        planned.add(os.path.normcase(os.path.realpath(os.path.join(parent, name))))
        for other, _, _ in moves[:i]:
            if path_within(src, other) or path_within(other, src):
                errors.append("duplicate or overlapping sources: %s and %s" % (other, src))
        for source, _, _ in moves:
            if path_within(parent, source):
                errors.append("destination parent is inside a planned source: %s" % parent)
    roots, documents = set(), {}
    if not errors:
        try:
            inspected = set()
            for src, parent, _ in moves:
                _check_move_files(src)
                if os.path.islink(parent):
                    raise OSError("move does not accept a linked destination parent: %s" % parent)
                old_root, new_root = tree_root_of(src), tree_root_of(parent)
                for root in (old_root, new_root):
                    if root not in inspected:
                        documents.update(_move_documents(root))
                        inspected.add(root)
                roots.add(new_root)
                if not args.copy and old_root != src:
                    roots.add(old_root)
        except (OSError, UnicodeError) as exc:
            errors.append(str(exc))
    if errors:
        for error in errors:
            print("error: %s" % error)
        print("nothing was moved")
        return 1
    if args.dry_run:
        for src, parent, name in moves:
            print("[dry-run] would %s %s -> %s" % ("copy" if args.copy else "move", src, os.path.join(parent, name)))
        return 0
    rc = _execute_move(moves, roots, documents, copy=args.copy)
    if rc:
        return rc
    print("next: check each moved description has `covers` words and three example sentences "
          "(organizer_cli.py lint), then validate and replay")
    return 0


# ---------------------------------------------------------------- split
#
# The agent decides how a SKILL.md body is cut (organizer rules 1-3); this command only
# carries the decision out. `split DIR --show` prints the file with line numbers and its
# sha256. The agent writes a JSON plan naming line ranges of that exact file; `split --plan`
# checks the whole plan, moves each range verbatim into a references/ file or a new
# sub-skill, leaves one pointer line in its place, and re-syncs the tree.

def _sha256(data):
    import hashlib
    return hashlib.sha256(data).hexdigest()


def cmd_split_show(skill_dir):
    fp = os.path.join(skill_dir, SKILL_FILE)
    with open(fp, "rb") as f:
        data = f.read()
    text = data.decode("utf-8")
    _, _, err = split_frontmatter(text)
    if err:
        print("error: %s: %s" % (fp, err))
        return 1
    body_start, _, _ = _split_regions(text)
    print("file: %s" % fp.replace(os.sep, "/"))
    print("sha256: %s" % _sha256(data))
    print("body: lines %d-%d (frontmatter and the sub-skills block cannot be split)" % (body_start, len(text.splitlines())))
    for n, line in enumerate(text.splitlines(), 1):
        print("%5d  %s" % (n, line))
    return 0


def _split_regions(text):
    """(first body line, set of protected line numbers, list of fence (start, end) line spans).
    Protected: frontmatter and the routing table between the markers, which sync owns."""
    lines = text.splitlines()
    end = next(i for i in range(1, len(lines)) if lines[i].rstrip() == "---")
    protected = set(range(1, end + 2))
    i, j = _find_marker_pair(text)
    if i is not None:
        first = text.count("\n", 0, i) + 1
        last = text.count("\n", 0, j if j is not None else i) + 1
        protected |= set(range(first, last + 1))
    fences, open_at = [], None
    for n, line in enumerate(lines, 1):
        if n <= end + 1:
            continue
        if re.match(r"^(?:```|~~~)", line):
            if open_at is None:
                open_at = n
            else:
                fences.append((open_at, n))
                open_at = None
    if open_at is not None:
        fences.append((open_at, len(lines)))
    return end + 2, protected, fences


def _parse_range(value):
    m = re.fullmatch(r"\s*(\d+)\s*(?:-\s*(\d+))?\s*", str(value))
    if not m:
        return None
    a = int(m.group(1))
    b = int(m.group(2) or a)
    return (a, b) if 1 <= a <= b else None


def read_split_plan(path):
    """Check a split plan against the file it names. Returns (plan, errors). Nothing is written."""
    import json
    errors = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            plan = json.loads(f.read().lstrip("\ufeff"))
    except (OSError, ValueError) as exc:
        return None, ["cannot read plan %s: %s" % (path, exc)]
    if not isinstance(plan, dict) or not isinstance(plan.get("chunks"), list) or not plan["chunks"]:
        return None, ["plan must be a JSON object with \"source\", \"sha256\" and a non-empty \"chunks\" list"]
    base = os.path.dirname(os.path.abspath(path))
    src = os.path.normpath(os.path.join(base, str(plan.get("source", ""))))
    fp = os.path.join(src, SKILL_FILE)
    if not is_skill_dir(src):
        return None, ["source %s is not a skill folder (no %s)" % (src, SKILL_FILE)]
    with open(fp, "rb") as f:
        data = f.read()
    if plan.get("sha256") != _sha256(data):
        return None, ["%s changed since the plan was written (sha256 differs); run `split %s --show` again "
                      "and renumber the plan" % (fp, src)]
    text = data.decode("utf-8")
    meta, _, err = split_frontmatter(text)
    if err:
        return None, ["%s: %s" % (fp, err)]
    _, protected, fences = _split_regions(text)
    n_lines = len(text.splitlines())
    taken, targets, out = {}, set(), []
    for k, chunk in enumerate(plan["chunks"], 1):
        where = "chunk %d" % k
        if not isinstance(chunk, dict):
            errors.append("%s is not an object" % where)
            continue
        rng = _parse_range(chunk.get("lines", ""))
        if rng is None or rng[1] > n_lines:
            errors.append("%s: \"lines\" must be \"A-B\" within 1-%d" % (where, n_lines))
            continue
        a, b = rng
        if any(n in protected for n in range(a, b + 1)):
            errors.append("%s: lines %d-%d touch the frontmatter or the sub-skills block, which only sync writes" % (where, a, b))
        for n in range(a, b + 1):
            if n in taken:
                errors.append("%s: line %d is already in chunk %d" % (where, n, taken[n]))
                break
            taken[n] = k
        for fa, fb in fences:
            if (a <= fa <= b) != (a <= fb <= b) or (fa < a and b < fb):
                errors.append("%s: lines %d-%d cut the code fence at lines %d-%d; take the whole fence or none of it" % (where, a, b, fa, fb))
        pointer = chunk.get("pointer")
        if not isinstance(pointer, str) or not pointer.strip() or "\n" in pointer:
            errors.append("%s: \"pointer\" must be one non-empty line; it replaces the moved text and tells the "
                          "agent when to go there" % where)
        kind = chunk.get("to")
        item = {"lines": (a, b), "pointer": pointer, "to": kind}
        if kind == "reference":
            rel = str(chunk.get("path", ""))
            if not re.fullmatch(r"references/[a-z0-9][a-z0-9._-]*\.md", rel):
                errors.append("%s: \"path\" must be references/<name>.md (one level deep, lowercase)" % where)
            elif isinstance(pointer, str) and "`%s`" % rel not in pointer:
                errors.append("%s: the pointer must name `%s` in backticks, so lint can check the file exists" % (where, rel))
            target = os.path.join(src, *rel.split("/"))
            item["path"] = target
        elif kind == "skill":
            name = chunk.get("name", "")
            desc = chunk.get("description", "")
            trig = chunk.get("triggers", [])
            if not isinstance(name, str) or spec_field_problems({"name": name, "description": "x"}):
                errors.append("%s: %r is not a valid skill name (lowercase letters, digits, single hyphens)" % (where, name))
            if not isinstance(desc, str) or not desc.strip() or "\n" in desc or spec_field_problems({"description": desc}):
                errors.append("%s: \"description\" must be one line in the three-part form" % where)
            if (not isinstance(trig, list) or not trig
                    or any(not isinstance(t, str) or not t.strip() or "\n" in t for t in trig)):
                errors.append("%s: \"triggers\" must be a list of one-line example sentences" % where)
            target = os.path.join(src, str(name))
            item.update(path=target, name=name, description=desc, triggers=trig)
        else:
            errors.append("%s: \"to\" must be \"reference\" or \"skill\"" % where)
            continue
        key = os.path.normcase(os.path.abspath(target))
        if key in targets:
            errors.append("%s: two chunks write %s; merge them into one range or name two files" % (where, target))
        targets.add(key)
        if os.path.lexists(target):
            errors.append("%s: %s already exists; split never overwrites" % (where, target))
        out.append(item)
    if errors:
        return None, errors
    return {"source": src, "file": fp, "data": data, "text": text, "chunks": out, "name": meta.get("name")}, []


def _apply_split(plan):
    """Text of the new source document and the files to create, all in memory."""
    import json
    lines = plan["text"].splitlines(keepends=True)
    eol = "\r\n" if plan["text"].count("\r\n") * 2 > plan["text"].count("\n") else "\n"
    creates = []
    by_start = {c["lines"][0]: c for c in plan["chunks"]}
    new_lines, n = [], 1
    while n <= len(lines):
        c = by_start.get(n)
        if c is None:
            new_lines.append(lines[n - 1])
            n += 1
            continue
        a, b = c["lines"]
        moved = "".join(lines[a - 1:b])
        if not moved.endswith("\n"):
            moved += "\n"
        new_lines.append(c["pointer"].strip() + eol)
        if c["to"] == "reference":
            creates.append((c["path"], moved))
        else:
            trig = "".join("    %s\n" % t.strip() for t in c["triggers"])
            doc = ("---\nname: %s\ndescription: %s\nmetadata:\n  holon-triggers: |\n%s---\n\n# %s\n\n%s\n%s\n%s\n"
                   % (_yaml_string(c["name"]), json.dumps(c["description"], ensure_ascii=False), trig,
                      c["name"], moved, MARK_OPEN, MARK_CLOSE))
            creates.append((os.path.join(c["path"], SKILL_FILE), doc))
        n = b + 1
    return "".join(new_lines), creates


def cmd_split(args):
    if bool(args.show_flag) == bool(args.plan) or bool(args.show_flag) != bool(args.show):
        print("error: give `split DIR --show` to number a SKILL.md, or `split --plan FILE` to apply a plan")
        return 1
    if args.show_flag:
        return cmd_split_show(args.show)
    plan, errors = read_split_plan(args.plan)
    if not errors:
        root = tree_root_of(plan["source"])
        try:
            documents = _move_documents(root)
            for c in plan["chunks"]:
                parent = os.path.dirname(c["path"])
                if os.path.lexists(parent) and (os.path.islink(parent) or not path_within(parent, plan["source"])):
                    raise OSError("split does not write through links: %s" % parent)
        except (OSError, UnicodeError) as exc:
            errors = [str(exc)]
    if errors:
        for e in errors:
            print("error: %s" % e)
        print("nothing was written")
        return 1
    new_text, creates = _apply_split(plan)
    for c in plan["chunks"]:
        print("%s lines %d-%d -> %s" % ("[dry-run] would move" if args.dry_run else "move",
                                       c["lines"][0], c["lines"][1], c["path"].replace(os.sep, "/")))
    if args.dry_run:
        print("[dry-run] %s keeps one pointer line per chunk; the moved text is copied byte for byte" % plan["file"])
        return 0
    made = []
    try:
        for path, content in creates:
            parent = os.path.dirname(path)
            if not os.path.isdir(parent):
                os.makedirs(parent)
                made.append(parent)
            with open(path, "x", encoding="utf-8", newline="\n") as f:
                f.write(content)
            made.append(path)
        with open(plan["file"], "wb") as f:
            f.write(new_text.encode("utf-8"))
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            rc = cmd_sync(argparse.Namespace(path=root, dry_run=False, auto_append=True))
        if rc:
            raise OSError("sync failed after split")
    except BaseException as exc:
        problems = []
        for path in reversed(made):
            try:
                os.rmdir(path) if os.path.isdir(path) else os.unlink(path)
            except OSError as err:
                problems.append("%s: %s" % (path, err))
        for path, data in documents.items():
            try:
                with open(path, "rb") as f:
                    if f.read() == data:
                        continue
                with open(path, "wb") as f:
                    f.write(data)
            except OSError as err:
                problems.append("%s: %s" % (path, err))
        if problems:
            print("error: split rollback incomplete: %s" % "; ".join(problems))
        else:
            print("split failed; the source document and routing tables were restored")
        if isinstance(exc, (OSError, UnicodeError)):
            print("error: %s" % exc)
            return 1
        raise
    print("split %s into %d chunk(s); routing tables re-synced" % (plan["file"].replace(os.sep, "/"), len(creates)))
    print("next: run validate, organizer_cli.py lint and replay; give each new sub-skill three example sentences")
    return 0


def cmd_tree(args):
    root = args.path or "."
    roots = find_root_skills(root)
    if not roots:
        print("no skill found under %s" % root)
        return 1

    def show(path, prefix, is_last, visited):
        real = os.path.realpath(path)
        if real in visited:
            print(prefix + ("└── " if is_last else "├── ") + "[cycle] " + path)
            return
        visited = visited | {real}
        _, meta, err = read_skill(path)
        name = meta.get("name") or os.path.basename(path)
        # Never truncate the description: the trailing exclusion clause
        # ("excludes ...") is exactly the part routing needs most.
        desc = meta.get("description", "") if not err else "(parse error: %s)" % err
        connector = "" if prefix == "" and is_last is None else ("└── " if is_last else "├── ")
        print("%s%s%s — %s" % (prefix, connector, name, desc))
        child_prefix = prefix if is_last is None else prefix + ("    " if is_last else "│   ")
        # With a groups.md, print by section exactly like the routing table;
        # a child listed in several groups appears once per group.
        sections = grouped_children(path)
        for si, (title, members) in enumerate(sections):
            if title:
                print(child_prefix + "│   [" + title + "]")
            for i, sub in enumerate(members):
                last = si == len(sections) - 1 and i == len(members) - 1
                show(sub, child_prefix, last, visited)

    for r in roots:
        show(r, "", None, set())
    return 0


def cmd_validate(args):
    root = args.path or "."
    skills, cycles = collect_skills(root)
    problems = list(cycles)
    if not skills:
        problems.append("no skill found under %s" % root)
    for sk in skills:
        rel = sk
        text, meta, err = read_skill(sk)
        if text is None or err:
            problems.append("%s: %s" % (rel, err))
            continue
        if not meta.get("name"):
            problems.append("%s: frontmatter is missing `name`" % rel)
        desc = meta.get("description", "")
        if not desc or desc.startswith("TODO"):
            problems.append("%s: description is missing or still a TODO" % rel)
        trig = meta.get("triggers", [])
        if isinstance(trig, list) and any(str(s).startswith("TODO") for s in trig):
            problems.append("%s: example sentences (metadata.%s) are still TODO placeholders" % (rel, TRIGGERS_META))
        dirname = os.path.basename(os.path.abspath(sk))
        problems += ["%s: %s" % (rel, s) for s in spec_field_problems(meta, dirname if sk != root else None)]
        _, body, _ = split_frontmatter(text)
        todo_lines = body_todo_lines(body)
        if todo_lines:
            problems.append("%s: body still contains TODO placeholders (body line %s)"
                            % (rel, ", ".join(str(n) for n in todo_lines)))
        subs = child_skill_dirs(sk)
        _, gerrs = read_groups(sk)
        problems += ["%s: %s" % (rel, g) for g in gerrs]
        if subs:
            block = render_block(sk)
            _, status = inject(text, block)
            if status == "no-marker":
                problems.append("%s: has %d sub-skill(s) but no %s marker (run sync to append it)"
                                % (rel, len(subs), MARK_OPEN))
            elif status == "updated":
                problems.append("%s: routing table is out of date with the sub-skills on disk (run sync)" % rel)
        else:
            _, status = inject(text, "")
            if status == "updated":
                problems.append("%s: all sub-skills were removed but the routing table still has entries (run sync to clear)" % rel)
    if problems:
        print("Found %d problem(s):" % len(problems))
        for p in problems:
            print("  ✗ " + p)
        return 1
    print("✓ OK: %d skill(s) valid and in sync" % len(skills))
    return 0


# ---------------------------------------------------------------- migrate

def migrate_text(text):
    """Rewrite top-level `triggers:` and `archive_count:` into the spec's `metadata:` map.
    Returns (new_text, changed). Everything else in the file is left byte for byte."""
    text_nobom = text.lstrip("\ufeff")
    lines = text_nobom.splitlines(keepends=True)
    if not lines or not lines[0].startswith("---"):
        return text, False
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return text, False
    fm = lines[1:end]
    triggers, count, keep = [], None, []
    i = 0
    while i < len(fm):
        line = fm[i]
        s = line.strip()
        if s == "triggers:" or s.startswith("triggers:") and s[len("triggers:"):].strip() == "":
            i += 1
            while i < len(fm) and fm[i].lstrip().startswith("- "):
                triggers.append(fm[i].strip()[2:].strip())
                i += 1
            continue
        m = re.match(r"^archive_count:\s*(\d+)\s*$", s)
        if m:
            count = m.group(1)
            i += 1
            continue
        keep.append(line)
        i += 1
    if not triggers and count is None:
        return text, False
    # find an existing metadata: map to extend, else append one
    md_at = next((j for j, l in enumerate(keep) if l.strip() == "metadata:"), None)
    add = []
    if triggers:
        add.append("  %s: |\n" % TRIGGERS_META)
        add += ["    %s\n" % s for s in triggers]
    if count is not None:
        add.append("  %s: \"%s\"\n" % (ARCHIVE_META, count))
    if md_at is None:
        keep.append("metadata:\n")
        keep += add
    else:
        j = md_at + 1
        while j < len(keep) and keep[j][:1] in (" ", "\t"):
            j += 1
        keep[j:j] = add
    new = lines[0] + "".join(keep) + "".join(lines[end:])
    if text.startswith("\ufeff"):
        new = "\ufeff" + new
    return new, True


def cmd_migrate(args):
    """Move holon's two fields under `metadata:` in every SKILL.md of the tree, so each file
    passes the Agent Skills reference validator. Idempotent."""
    root = args.path or "."
    skills, errors = collect_skills(root)
    if errors or not skills:
        print("error: %s" % ("; ".join(errors) or "no skill found under %s" % root))
        return 1
    edits = []
    for sk in skills:
        fp = os.path.join(sk, SKILL_FILE)
        text, _, err = read_skill(sk)
        if err:
            print("error: %s: %s" % (fp, err))
            return 1
        new, did = migrate_text(text)
        _, err = parse_frontmatter(new)
        if err:
            print("error: cannot migrate %s: %s" % (fp, err))
            return 1
        if did:
            edits.append((fp, new))
    changed = len(edits)
    for fp, new in edits:
        if args.dry_run:
            print("[dry-run] would rewrite %s" % fp)
            continue
        with open(fp, "w", encoding="utf-8", newline="\n") as f:
            f.write(new)
        print("migrated: %s" % fp)
    print("%d file(s) %s" % (changed, "would change" if args.dry_run else "changed"))
    return 0


# ---------------------------------------------------------------- install

def _install_ignore(src_top):
    """shutil.copytree ignore callback: skip caches and tests everywhere, and the
    repository-only folders at the top of the source."""
    src_top = os.path.abspath(src_top)

    def ignore(d, names):
        out = {n for n in names if n in INSTALL_SKIP_ANY}
        if os.path.abspath(d) == src_top:
            out |= {n for n in names if n in INSTALL_SKIP_TOP}
        return out
    return ignore


def _host(host_id):
    for h in HOSTS:
        if h[0] == host_id:
            return h
    raise ValueError("unknown host %r; one of: agents, %s" % (host_id, ", ".join(HOST_IDS)))


def _reads(h, project, base):
    """The absolute directories host `h` reads, user-level or project-level."""
    specs = h[3] if project else h[2]
    return [_resolve_dir(x, base if project else None) for x in specs]


def plan_install(hosts=None, to=None, project=False, base=None):
    """Where `install` writes. Returns (dirs, covered, doubled, missing):
    dirs     the directories to write to, the first one holding the real copy;
    covered  {dir: [host names that read it]};
    doubled  names of hosts that read two or more of `dirs` (they list the tree twice);
    missing  names of requested hosts that no chosen directory reaches (empty in practice).

    With `to`: that directory only. With `hosts`: exactly those hosts ("agents" is the
    shared directory itself, and then it is always written). With neither: every host found
    on this machine; with no host found, the shared directory alone.

    Which directories, in three steps:
    1. A host that does not read the shared directory gets its own first directory.
    2. Every host not yet served reads the shared directory. It is served there, unless a
       host already served in step 1 also reads the shared directory: that host would then
       see the tree twice (OpenCode requires names to be unique; others list it twice), so
       the unserved host is served by the first of its own directories that no served host
       reads. Only if it has none is the shared directory used anyway, and the host that
       sees two copies is reported.
    3. Without --host, the shared directory is added when that makes no host see the tree
       twice, so that a host installed later that follows the standard finds it."""
    base = base or os.getcwd()
    shared = _resolve_dir(SHARED_PROJECT, base) if project else _resolve_dir(SHARED_USER)
    if to:
        return [os.path.abspath(os.path.expanduser(to))], {}, [], []
    explicit = bool(hosts)
    want_shared = False
    if hosts:
        targets = []
        for hid in hosts:
            if hid == "agents":
                want_shared = True
            elif _host(hid) not in targets:
                targets.append(_host(hid))
    else:
        targets = [h for h in HOSTS if host_present(h[0])]
    reads = {h[0]: _reads(h, project, base) for h in targets}
    sees = lambda h, ds: sum(1 for d in ds if d in reads[h[0]])
    dirs = []
    for h in targets:  # step 1
        if shared not in reads[h[0]] and not sees(h, dirs):
            dirs.append(reads[h[0]][0])
    clash = lambda ds: any(sees(h, ds) > 1 for h in targets)
    for h in targets:  # step 2
        if sees(h, dirs):
            continue
        if not clash(dirs + [shared]):
            dirs.append(shared)
            continue
        free = [d for d in reads[h[0]] if d != shared and not any(sees(o, [d]) for o in targets if sees(o, dirs))]
        dirs.append(free[0] if free else shared)
    if shared not in dirs and (want_shared or not explicit) and not clash(dirs + [shared]):  # step 3
        dirs.append(shared)
    if want_shared and shared not in dirs:
        dirs.append(shared)
    if not dirs:
        dirs = [shared]
    if shared in dirs:
        dirs.remove(shared)
        dirs.insert(0, shared)
    covered = {d: [h[1] for h in targets if d in reads[h[0]]] for d in dirs}
    doubled = [h[1] for h in targets if sum(1 for d in dirs if d in reads[h[0]]) > 1]
    missing = [h[1] for h in targets if not any(d in reads[h[0]] for d in dirs)]
    return dirs, covered, doubled, missing


def install_dir_for(host=None, to=None, project=False):
    """The one directory a single host reads first (kept for callers that want one path)."""
    if to:
        return os.path.normpath(os.path.expanduser(to))
    if host in (None, "agents"):
        return _resolve_dir(SHARED_PROJECT, os.getcwd()) if project else _resolve_dir(SHARED_USER)
    h = _host(host)
    return _reads(h, project, os.getcwd())[0]


def cmd_hosts(args):
    """Print every host holon knows, whether it was found here, and what it reads."""
    project = getattr(args, "project", False)
    base = os.getcwd()
    if getattr(args, "ids", False):
        for h in HOSTS:
            print(h[0])
        return 0
    print("shared: %s  (read by every tool marked *)" % (_resolve_dir(SHARED_PROJECT, base) if project else _resolve_dir(SHARED_USER)))
    shared = _resolve_dir(SHARED_PROJECT, base) if project else _resolve_dir(SHARED_USER)
    for h in HOSTS:
        dirs = _reads(h, project, base)
        mark = "*" if shared in dirs else " "
        found = "found" if host_present(h[0]) else "     "
        print("%s %-13s %s  %s" % (mark, h[0], found, ", ".join(dirs)))
    return 0


def _this_package():
    """The holon package this script belongs to, or None when the script runs from stdin
    or from a path that is not <package>/scripts/holon.py."""
    here = os.path.dirname(os.path.abspath(__file__))
    pkg = os.path.abspath(os.path.join(here, ".."))
    if os.path.basename(here) == "scripts" and is_skill_dir(pkg) and os.path.isfile(os.path.join(here, "holon.py")):
        return pkg
    return None


def is_holon_root(path):
    """A tree kept under the organizer rules: its root carries the absorption counter, or
    already has (even as stubs) the folders the rules live in. A plain skill folder from
    elsewhere is not one, and `install` neither adds tools to it nor lints it."""
    _, meta, err = read_skill(path)
    if err:
        return False
    if meta.get("archive_count") is not None:
        return True
    # Any skill may have a scripts/ folder; only these two name the rules.
    return any(is_skill_dir(os.path.join(path, d)) for d in ("organizer", "editing"))


def _complete_tools(dest, pkg):
    """A tree needs scripts/holon.py, organizer/ and editing/ to be maintained where it lands.
    A tree that was kept beside the holon package (a library inside a larger checkout that
    keeps only the headers of organizer/ and editing/) has them two levels up, which the
    copy loses. Fill
    each one in from `pkg`, replacing a header-only stub."""
    added = False
    if pkg is None or os.path.abspath(dest) == os.path.abspath(pkg):
        return added
    # What each folder must hold for the tree to be maintained: the tree tool, the rules
    # checker, and the editing steps (which name `scripts/holon.py`). A header-only stub
    # holds none of these.
    needed = {
        "scripts": lambda d: os.path.isfile(os.path.join(d, "holon.py")),
        "organizer": lambda d: os.path.isfile(os.path.join(d, "scripts", "organizer_cli.py")),
        "editing": lambda d: "scripts/holon.py" in (split_frontmatter(read_skill(d)[0] or "")[1] or ""),
    }
    for part, has in needed.items():
        src_part = os.path.join(pkg, part)
        dst_part = os.path.join(dest, part)
        if not os.path.isdir(src_part) or not has(src_part):
            continue
        if os.path.isdir(dst_part) and has(dst_part):
            continue
        if os.path.isdir(dst_part):
            shutil.rmtree(dst_part)
        shutil.copytree(src_part, dst_part, ignore=_install_ignore(src_part), symlinks=False)
        print("completed: %s/ from %s" % (part, pkg))
        added = True
    return added


# A source that is not a local path: a git URL, GitHub `owner/repo`, or an archive URL.
REMOTE_SRC = re.compile(r"^(?:https?://|file://|git@|ssh://|[\w.-]+/[\w.-]+$)")


def _fetch(src, tmp):
    """Bring a remote source to disk under tmp and return the checkout directory. A .zip or
    .tar.gz URL is downloaded and unpacked with the standard library; anything else is
    cloned with git (shallow). `owner/repo` means github.com."""
    lower = src.lower().split("?")[0]
    if lower.endswith((".zip", ".tar.gz", ".tgz")):
        import urllib.request
        fn = os.path.join(tmp, "src.archive")
        with urllib.request.urlopen(src) as r, open(fn, "wb") as f:
            shutil.copyfileobj(r, f)
        out = os.path.join(tmp, "unpacked")
        if lower.endswith(".zip"):
            import zipfile
            with zipfile.ZipFile(fn) as z:
                z.extractall(out)
        else:
            import tarfile
            with tarfile.open(fn) as t:
                if hasattr(tarfile, "data_filter"):   # 3.12+: refuse paths outside `out`
                    t.extractall(out, filter="data")
                else:
                    # Older Python releases have no extraction filter. Only regular
                    # files and directories are safe without link-aware filtering.
                    members = t.getmembers()
                    for member in members:
                        name = member.name.replace("\\", "/")
                        if (os.path.isabs(name) or not path_within(os.path.join(out, name), out)
                                or not (member.isfile() or member.isdir())):
                            raise ValueError("unsafe archive member: %s" % member.name)
                    t.extractall(out, members=members)
        # GitHub archives wrap everything in one top-level folder.
        entries = [os.path.join(out, e) for e in os.listdir(out)]
        return entries[0] if len(entries) == 1 and os.path.isdir(entries[0]) else out
    url = src
    if REMOTE_SRC.match(src) and not src.startswith(("http", "file://", "git@", "ssh://")):
        url = "https://github.com/%s.git" % src
    out = os.path.join(tmp, "clone")
    r = subprocess.run(["git", "clone", "--quiet", "--depth", "1", url, out],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        raise RuntimeError("git clone failed: %s" % r.stderr.decode("utf-8", errors="replace").strip())
    return out


def _tree_in(checkout):
    """Where the tree is inside a checkout: the checkout itself if it is a skill; else its one
    child folder that is a skill and carries scripts/holon.py (the holon package in this
    repository). Anything else is a guess, and a wrong guess installs the wrong folder, so
    None is returned and the caller asks for --path."""
    if is_skill_dir(checkout):
        return checkout
    kids = child_skill_dirs(checkout)
    with_tool = [k for k in kids if os.path.isfile(os.path.join(k, "scripts", "holon.py"))]
    if len(with_tool) == 1:
        return with_tool[0]
    return None


def _skill_dirs_two_deep(checkout):
    """Skill folders at depth one and two, relative, for the message that asks for --path."""
    out = []
    for d in _subdirs(checkout):
        if is_skill_dir(d):
            out.append(os.path.relpath(d, checkout))
        for dd in _subdirs(d):
            if is_skill_dir(dd):
                out.append(os.path.relpath(dd, checkout))
    return out


def cmd_install(args):
    """Copy a skill tree into a host's skills directory and validate the copy there. One
    command replaces clone, choose folder, copy, rename, run the checks. The source is the
    tree this script lives in unless given; a URL or `owner/repo` is fetched first, so the
    command also works with the script piped from a URL and no checkout at all."""
    import tempfile
    pkg = _this_package()
    tmp = None
    if args.src and REMOTE_SRC.match(args.src) and not os.path.exists(args.src):
        tmp = tempfile.mkdtemp(prefix="holon-install-")
        try:
            checkout = _fetch(args.src, tmp)
        except Exception as e:  # network, git, archive: one message, exit 1
            print("error: could not fetch %s: %s" % (args.src, e))
            remove_tree(tmp)
            return 1
        found = _tree_in(checkout)
        src = os.path.join(checkout, args.path) if getattr(args, "path", None) else found
        if src is not None and not path_within(src, checkout):
            print("error: --path must stay inside the fetched repository")
            remove_tree(tmp)
            return 1
        if src is None:
            cands = _skill_dirs_two_deep(checkout)
            print("error: %s is not itself a skill tree and holds no holon package; say which folder "
                  "to install with --path. Skill folders in it: %s"
                  % (args.src, ", ".join(cands[:12]) + (" ..." if len(cands) > 12 else "") if cands else "none"))
            remove_tree(tmp)
            return 1
        # When this script has no package of its own (piped from a URL), the fetched
        # repository's holon package supplies the tools.
        if pkg is None and found and os.path.isfile(os.path.join(found, "scripts", "holon.py")):
            pkg = found
        print("fetched: %s" % args.src)
    elif args.src:
        src = os.path.abspath(args.src)
    elif pkg:
        src = pkg
    else:
        print("error: no source given and this script is not inside a holon package; "
              "give a path, a git URL or owner/repo")
        return 1
    src = os.path.abspath(src)
    if not is_skill_dir(src):
        print("error: %s has no %s; give the root folder of a skill tree" % (src, SKILL_FILE))
        if tmp:
            remove_tree(tmp)
        return 1
    try:
        return _install_from(src, pkg, args)
    finally:
        if tmp:
            remove_tree(tmp)


def _check_copy_source(src):
    """Reject escaping links and cycles before copytree follows them."""
    ignore = _install_ignore(src)

    def visit(directory, ancestors):
        real = os.path.realpath(directory)
        if not path_within(directory, src) or real in ancestors:
            raise ValueError("escaping or circular directory link: %s" % directory)
        names = os.listdir(directory)
        skipped = ignore(directory, names)
        for name in names:
            if name in skipped:
                continue
            path = os.path.join(directory, name)
            if not path_within(path, src):
                raise ValueError("link escapes the source tree: %s" % path)
            if os.path.isdir(path):
                visit(path, ancestors | {real})
            elif not os.path.isfile(path):
                raise ValueError("not a regular file: %s" % path)

    visit(src, set())


def _check_staged_install(dest, pkg):
    """Validate before publishing, using the running tool's checker, not downloaded code."""
    holon_root = is_holon_root(dest)
    if holon_root and _complete_tools(dest, pkg):
        if cmd_sync(argparse.Namespace(path=dest, dry_run=False, auto_append=True)):
            return 1
    rc = cmd_validate(argparse.Namespace(path=dest))
    trusted = _this_package()
    lint = os.path.join(trusted, "organizer", "scripts", "organizer_cli.py") if trusted else None
    if rc == 0 and holon_root:
        if lint is None or not os.path.isfile(lint):
            print("lint, replay: not run; no checker in the running tool's package")
        else:
            for sub in ("lint", "replay"):
                env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
                r = subprocess.run([sys.executable, lint, sub, dest], stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, env=env)
                lines = (r.stdout + r.stderr).decode("utf-8", errors="replace").splitlines()
                verdict = [line for line in lines if line.startswith(sub + ":")]
                print(verdict[-1] if verdict else (lines[-1] if lines else "%s: (no output)" % sub))
                rc = rc or r.returncode
    return rc


def _install_backup_dir(args, src, dirs):
    """Backups must not live inside a source tree or any known host skills directory."""
    directory = os.path.abspath(os.path.expanduser(getattr(args, "backup_dir", None) or "~/.holon-backups"))
    forbidden = [src] + list(dirs) + [_resolve_dir(SHARED_USER), _resolve_dir(SHARED_PROJECT, os.getcwd())]
    for host in HOSTS:
        forbidden.extend(_reads(host, False, os.getcwd()))
        forbidden.extend(_reads(host, True, os.getcwd()))
    if any(path_within(directory, root) for root in forbidden):
        raise ValueError("backup directory must be outside the source tree and host skills directories; use --backup-dir")
    return directory


def _backup_installs(dests, directory):
    """A durable archive of ALL previous contents; never cleaned up after publishing.

    Nested links are recorded, not followed. A linked installation's root is dereferenced
    so its data is retained as well as its original link target in the manifest.
    """
    import datetime
    import io
    import json
    import tarfile
    import tempfile
    os.makedirs(directory, mode=0o700, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    fd, temporary = tempfile.mkstemp(prefix="install-%s-" % stamp, suffix=".partial", dir=directory)
    archive_path = temporary[:-len(".partial")] + ".tar.gz"
    manifest = {"version": 1, "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "installs": [{"destination": dest, "archive_root": "trees/%d" % i,
                              "root_link": os.readlink(dest) if os.path.islink(dest) else None}
                             for i, dest in enumerate(dests)]}
    try:
        with os.fdopen(fd, "wb") as raw:
            with tarfile.open(fileobj=raw, mode="w:gz", dereference=False) as archive:
                for i, dest in enumerate(dests):
                    archive.add(os.path.realpath(dest), arcname="trees/%d" % i)
                data = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
                info = tarfile.TarInfo("manifest.json")
                info.size, info.mode = len(data), 0o600
                archive.addfile(info, io.BytesIO(data))
            raw.flush()
            os.fsync(raw.fileno())
        # Read the compressed archive back before any destination can be replaced.
        with tarfile.open(temporary, "r:gz") as archive:
            for member in archive:
                if member.isfile():
                    with archive.extractfile(member) as f:
                        while f.read(1024 * 1024):
                            pass
        os.rename(temporary, archive_path)
    except BaseException as exc:
        if os.path.exists(temporary):
            os.unlink(temporary)
        if isinstance(exc, tarfile.TarError):
            raise OSError("backup archive could not be verified: %s" % exc) from exc
        raise
    print("backup: %s" % archive_path)
    print("previous contents are in trees/0, trees/1, ...; manifest.json maps them to their original locations")
    print("restore into an empty directory, inspect it, then copy the required files back; this is replacement, not a merge upgrade")
    return archive_path


def _publish_install(staged, dests, link=False):
    """Prepare every copy first; keep previous installs until all replacements succeed."""
    import tempfile
    pending = []
    try:
        for i, dest in enumerate(dests):
            parent = os.path.dirname(os.path.abspath(dest))
            os.makedirs(parent, exist_ok=True)
            work = tempfile.mkdtemp(prefix=".holon-install-", dir=parent)
            item = {"dest": dest, "work": work, "old": os.path.join(work, "old"),
                    "new": os.path.join(work, "new"), "published": False, "how": "copied"}
            pending.append(item)
            if i and link:
                try:
                    os.symlink(os.path.abspath(dests[0]), item["new"], target_is_directory=True)
                    item["how"] = "linked"
                except (OSError, NotImplementedError):
                    print("note: could not create a link at %s; copying instead" % dest)
            if item["how"] == "copied":
                shutil.copytree(staged, item["new"])
        for item in pending:
            if os.path.lexists(item["dest"]):
                os.replace(item["dest"], item["old"])
            os.replace(item["new"], item["dest"])
            item["published"] = True
    except BaseException:  # Cancellation must restore previous installs too.
        for item in reversed(pending):
            try:
                if item["published"]:
                    if os.path.islink(item["dest"]):
                        os.unlink(item["dest"])
                    else:
                        shutil.rmtree(item["dest"])
                if os.path.lexists(item["old"]):
                    os.replace(item["old"], item["dest"])
            except OSError:
                print("error: rollback incomplete; previous install retained in %s" % item["work"])
                item["work"] = None  # Do not delete the user's recovery copy.
        raise
    finally:
        for item in pending:
            if item["work"]:
                shutil.rmtree(item["work"], ignore_errors=True)
    return [item["how"] for item in pending]


def _report_existing_installs(name, dirs, project=False):
    """Inspect disk as well as this run's plan. Never remove or update unselected copies."""
    base = os.getcwd()
    reads = {h[0]: _reads(h, project, base) for h in HOSTS}
    candidates = set(dirs)
    for paths in reads.values():
        candidates.update(paths)
    shared = _resolve_dir(SHARED_PROJECT, base) if project else _resolve_dir(SHARED_USER)
    candidates.add(shared)
    key = lambda p: os.path.normcase(os.path.abspath(p))
    selected = {key(d) for d in dirs}
    existing = {key(d): d for d in sorted(candidates) if is_skill_dir(os.path.join(d, name))}
    for k, directory in existing.items():
        if k not in selected:
            print("existing copy: %s (not selected; left unchanged)" % os.path.join(directory, name))
    prospective = dict(existing)
    prospective.update({key(d): d for d in dirs})
    for host in HOSTS:
        if not host_present(host[0]):
            continue
        paths = {key(d) for d in reads[host[0]]} & set(prospective)
        if len(paths) > 1:
            copies = ", ".join(os.path.join(prospective[k], name) for k in sorted(paths))
            print("warning: %s may read multiple copies of %s: %s; compare them and choose a maintained source; no old copy is deleted" %
                  (host[1], name, copies))


def _install_from(src, pkg, args):
    _, meta, err = read_skill(src)
    if err:
        print("error: %s: %s" % (os.path.join(src, SKILL_FILE), err))
        return 1
    dirs, covered, doubled, missing = plan_install(getattr(args, "host", None), args.to,
                                                   getattr(args, "project", False))
    name = args.as_name or meta.get("name") or os.path.basename(src)
    problems = spec_field_problems(dict(meta, name=name))
    if problems:
        print("error: %s" % "; ".join(problems))
        return 1
    dests = [os.path.abspath(os.path.join(d, name)) for d in dirs]
    for dest in dests:
        if os.path.realpath(dest) != os.path.realpath(src) and (path_within(dest, src) or path_within(src, dest)):
            print("error: source and destination must not contain one another")
            return 1
    try:
        _check_copy_source(src)
    except (OSError, ValueError) as e:
        print("error: %s" % e)
        return 1
    _report_existing_installs(name, dirs, getattr(args, "project", False))
    taken = [d for d in dests if os.path.lexists(d)]
    if taken and not getattr(args, "force", False):
        print("error: %s already exists; use --as another-name to keep it, or --force to back it up and replace it (not merge)" % ", ".join(taken))
        return 1
    backup_dir = None
    if taken:
        try:
            backup_dir = _install_backup_dir(args, src, dirs)
        except ValueError as e:
            print("error: %s" % e)
            return 1
    if args.dry_run:
        if taken:
            print("[dry-run] would backup all previous contents to %s before replacing them" % backup_dir)
        for i, d in enumerate(dests):
            how = "link" if (i and args.link) else "copy"
            who = ", ".join(covered.get(dirs[i], [])) or "any host pointed here"
            print("[dry-run] would %s %s -> %s  (%s)" % (how, src, d, who))
        return 0
    for d in taken:
        if not os.path.islink(d) and not is_skill_dir(d):
            print("error: %s exists and is not a skill folder; not replacing it" % d)
            return 1
    import tempfile
    try:
        with tempfile.TemporaryDirectory(prefix="holon-stage-") as tmp:
            staged = os.path.join(tmp, name)
            shutil.copytree(src, staged, ignore=_install_ignore(src), symlinks=False)
            if name != meta.get("name"):
                fp = os.path.join(staged, SKILL_FILE)
                with open(fp, encoding="utf-8") as f:
                    text = f.read()
                text = re.sub(r"^name:[^\n]*", lambda m: "name: " + _yaml_string(name), text, count=1, flags=re.M)
                with open(fp, "w", encoding="utf-8", newline="\n") as f:
                    f.write(text)
            rc = _check_staged_install(staged, pkg)
            if rc:
                return rc
            if taken:
                _backup_installs(taken, backup_dir)
            hows = _publish_install(staged, dests, args.link)
    except (OSError, ValueError) as e:
        print("error: install failed: %s" % e)
        return 1
    dest = dests[0]
    print("installed: %s" % dest)
    for extra, how in zip(dests[1:], hows[1:]):
        print("%s: %s" % (how, extra))
    if len(dests) > 1:
        if args.link:
            print("the tree is edited in %s; each linked path shows the same folder" % dest)
        else:
            print("%d copies, one per directory; after editing one, run install --force from it to refresh the others" % len(dests))
    shared = _resolve_dir(SHARED_PROJECT, os.getcwd()) if getattr(args, "project", False) else _resolve_dir(SHARED_USER)
    for d in dirs:
        who = covered.get(d, [])
        if d == shared:
            print("read by: %s  <- %s" % (", ".join(who + ["any tool that follows the Agent Skills standard"]), d))
        elif who:
            print("read by: %s  <- %s" % (", ".join(who), d))
    if doubled:
        print("note: %s %s more than one of these directories and may list the tree twice"
              % (", ".join(doubled), "reads" if len(doubled) == 1 else "read"))
    if missing:
        print("note: no directory chosen is read by %s; use --to" % ", ".join(missing))
    rec = [h[1] for h in HOSTS if h[0] in RECURSIVE_HOSTS and any(h[1] in v for v in covered.values())]
    if rec:
        print("note: %s %s skill folders recursively and also %s each sub-skill on its own; "
              "routing through the root still works"
              % (", ".join(rec), "scans" if len(rec) == 1 else "scan", "lists" if len(rec) == 1 else "list"))
    print("done. Files are installed; verify discovery and task behavior in a new host session.")
    return 0


# ---------------------------------------------------------------- main

def _tolerate_console_encoding():
    """Output contains ✓ ✗ and box-drawing characters. When stdout is a pipe
    or a redirected file on Windows, its encoding is often cp1252, which
    cannot represent them, and Python raises UnicodeEncodeError on the first
    such print. Prefer a '?' in the log to a traceback and exit code 1."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(errors="replace")
            except (ValueError, OSError):
                pass


def main(argv=None):
    _tolerate_console_encoding()
    parser = argparse.ArgumentParser(prog="holon",
                                     description="Scaffold for holon trees of AI Agent Skills")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("init", help="create a new skill")
    p.add_argument("name")
    p.add_argument("--parent", help="parent skill directory (create as a nested sub-skill)")
    p.add_argument("--root", help="root directory for a top-level skill (default: current directory)")
    p.add_argument("--desc", help="write the description directly (otherwise a TODO is left, which validate rejects; "
                                  "a root without --parent gets the standard root description)")
    p.add_argument("--bare", action="store_true",
                   help="for a root: do not copy scripts/, organizer/ and editing/ in from this package")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_init, bare=False)

    p = sub.add_parser("move", help="move or copy skill folders under a parent (or apply a plan) and re-sync")
    p.add_argument("src", nargs="*", help="skill folders to move")
    p.add_argument("--parent", help="the skill folder to put them under")
    p.add_argument("--as", dest="as_name", help="new folder name (one SRC only)")
    p.add_argument("--plan", help="a file of `SRC -> DEST` lines (DEST = parent/name; `parent/` keeps the name); preflight, stage, sync; restore on caught failure")
    p.add_argument("--copy", action="store_true", help="copy instead of moving (leave the source library as it is)")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_move)

    p = sub.add_parser("split", help="show a SKILL.md with line numbers, or apply an agent-written plan that moves "
                                     "line ranges into references/ files or new sub-skills")
    p.add_argument("show", nargs="?", metavar="DIR", help="with --show: the skill folder to number")
    p.add_argument("--show", dest="show_flag", action="store_true", help="print DIR/SKILL.md with line numbers and its sha256")
    p.add_argument("--plan", help="a JSON split plan written against the --show output")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_split)

    p = sub.add_parser("sync", help="inject sub-skill descriptions into parent SKILL.md files")
    p.add_argument("path", nargs="?")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-auto-append", dest="auto_append", action="store_false",
                   help="do not append a marker pair when one is missing")
    p.set_defaults(func=cmd_sync, auto_append=True)

    p = sub.add_parser("tree", help="print the skill hierarchy as a tree")
    p.add_argument("path", nargs="?")
    p.set_defaults(func=cmd_tree)

    p = sub.add_parser("validate", help="check frontmatter / TODO placeholders / cycles / sync freshness / Agent Skills spec fields")
    p.add_argument("path", nargs="?")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("migrate", help="move triggers: and archive_count: under metadata: (Agent Skills spec form)")
    p.add_argument("path", nargs="?")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_migrate)

    p = sub.add_parser("install", help="copy a skill tree into a host's skills directory and validate the copy")
    p.add_argument("src", nargs="?", help="root of the tree to copy: a path, a git URL, GitHub owner/repo, or a "
                                          ".zip/.tar.gz URL (default: the tree this script is in)")
    p.add_argument("--path", help="with a URL: the tree's folder inside the repository (default: found)")
    p.add_argument("--to", help="destination skills directory (overrides --host)")
    p.add_argument("--host", action="append", type=lambda h: "claude" if h == "claude-code" else h,
                   choices=["agents"] + HOST_IDS, metavar="HOST",
                   help="install for this host only; repeatable. Default: the shared ~/.agents/skills "
                        "plus every host found on this machine that does not read it. `hosts` lists them")
    p.add_argument("--project", action="store_true",
                   help="use the project-level skills directories under the current directory, not under ~")
    p.add_argument("--link", action="store_true",
                   help="link each extra directory to the first copy instead of copying; some hosts "
                        "do not follow links to skill folders")
    p.add_argument("--force", action="store_true",
                   help="back up and replace earlier installs; does not merge user changes or upgrade in place")
    p.add_argument("--backup-dir", help="archive directory for --force (default: ~/.holon-backups); must be outside skills directories")
    p.add_argument("--as", dest="as_name", help="folder name at the destination (default: the root's name)")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_install)

    p = sub.add_parser("hosts", help="list the hosts install knows, which were found here, and the directories each reads")
    p.add_argument("--project", action="store_true")
    p.add_argument("--ids", action="store_true", help="print only the host ids, one per line")
    p.set_defaults(func=cmd_hosts)

    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    try:
        return args.func(args)
    except (OSError, UnicodeError) as e:
        print("error: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
