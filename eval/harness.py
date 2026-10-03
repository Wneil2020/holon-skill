#!/usr/bin/env python3
# Copyright (c) 2026 Wneil2020 and the holon skill contributors. Released under the MIT License.
"""Evaluation harness for holon trees (Python 3.8+, standard library only).

It answers the question `replay` cannot: does an agent, reading the tree, pick the skill a
person expected, and how much does it read to get there, compared with the same skills laid
out flat. eval/README.md says what is compared and why; this file does the runs.

    python3 eval/harness.py flatten TREE OUT              # arrangement B: the tree's skills, side by side
    python3 eval/harness.py freeze SENTENCES               # fix the test split before tuning the tree
    python3 eval/harness.py run SENTENCES --tree TREE [--flat A_DIR] [--trimmed B_DIR]
                            [--runner word-model|claude-code|command] [--runs 3] [--out results.csv]
    python3 eval/harness.py report results.csv             # the tables eval/README.md asks for

SENTENCES is a tab-separated file with a header line `id split sentence expected`. `split` is
`test` or `tune`; only `test` lines are counted. `expected` is one or more skill folder names,
`|`-separated, or `none` when no skill should take the sentence.

Runners:
  word-model   the organizer's lexical routing (no model, no cost). The baseline, and what CI runs.
  claude-code  `claude -p` in a scratch project whose .claude/skills/ holds the arrangement,
               with an isolated HOME; reads the stream-json events for files read and tokens.
  command      any agent: --runner-cmd is run with {skills}, {prompt_file}, {workdir}
               substituted and must print one JSON object as its last line:
               {"files_read": [...], "chosen": "folder-name or none", "input_tokens": N}
"""
import argparse
import csv
import hashlib
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent / "holon"
sys.path.insert(0, str(PKG / "organizer" / "scripts"))
sys.path.insert(0, str(PKG / "scripts"))
import holon as ns  # noqa: E402
import organizer_cli as oc  # noqa: E402

TOOL_SKILLS = ("organizer", "editing")   # the tree's own maintenance skills; not part of the library
LOCK_SUFFIX = ".lock"
FIELDS = ["sentence_id", "split", "run", "runner", "model", "arrangement", "expected", "chosen",
          "route_ok", "task_ok", "files_read", "bytes_read", "input_tokens", "cost_usd",
          "wall_time", "word_model", "agrees_word_model", "skills_seen", "error"]
ROUTE_ONLY_PROMPT = (
    "This is an evaluation run. Do not carry out the user's task and do not write any files. "
    "Use the skills available to you exactly as you normally would to decide whose instructions "
    "you would follow, reading whatever you would normally read. Then end your reply with one "
    "line `SKILL: <folder name of that skill>`, or `SKILL: none` if no skill applies.")


# ---------------------------------------------------------------- sentences

def read_sentences(path):
    rows = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        missing = {"id", "split", "sentence", "expected"} - set(reader.fieldnames or [])
        if missing:
            sys.exit("error: %s needs the columns id, split, sentence, expected (missing: %s)"
                     % (path, ", ".join(sorted(missing))))
        for n, r in enumerate(reader, 2):
            if r["split"] not in ("test", "tune"):
                sys.exit("error: %s line %d: split is %r; use test or tune" % (path, n, r["split"]))
            rows.append({k: (r[k] or "").strip() for k in ("id", "split", "sentence", "expected")})
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        sys.exit("error: %s has duplicate ids" % path)
    return rows


def test_digest(rows):
    h = hashlib.sha256()
    for r in rows:
        if r["split"] == "test":
            h.update(("%s\t%s\t%s\n" % (r["id"], r["sentence"], r["expected"])).encode("utf-8"))
    return h.hexdigest()


def cmd_freeze(args):
    rows = read_sentences(args.sentences)
    n = sum(r["split"] == "test" for r in rows)
    Path(args.sentences + LOCK_SUFFIX).write_text(test_digest(rows) + "\n", encoding="utf-8")
    print("froze %d test sentence(s) in %s%s" % (n, args.sentences, LOCK_SUFFIX))
    return 0


def check_frozen(path, rows, allow):
    lock = Path(path + LOCK_SUFFIX)
    if not lock.exists():
        msg = "the test split is not frozen (run `freeze` before changing cover words or synonyms.md)"
    elif lock.read_text(encoding="utf-8").strip() != test_digest(rows):
        msg = "the test split changed after it was frozen; a sentence used for tuning belongs in `tune`"
    else:
        return "frozen"
    if not allow:
        sys.exit("error: " + msg + "; give --unfrozen to run anyway (the report will say so)")
    print("warning: " + msg)
    return "unfrozen"


def expected_set(text):
    return {w.strip().lower() for w in text.split("|") if w.strip()}


# ---------------------------------------------------------------- arrangements

def library_skills(root, exclude=TOOL_SKILLS):
    """Every skill below the root of a tree, minus the tree's own maintenance skills."""
    skills, errors = oc.find_skills(Path(root))
    if errors:
        sys.exit("error: " + "; ".join(errors))
    root = Path(root).resolve()
    out = []
    for d in sorted(skills):
        d = Path(d).resolve()
        if d == root:
            continue
        top = d.relative_to(root).parts[0]
        if top in exclude:
            continue
        out.append(d)
    return out


def cmd_flatten(args):
    """Arrangement B: every skill of the tree as a top-level folder, routing tables removed."""
    out = Path(args.out)
    if out.exists() and any(out.iterdir()):
        sys.exit("error: %s exists and is not empty" % out)
    skills = library_skills(args.tree)
    names = [d.name for d in skills]
    dup = sorted({n for n in names if names.count(n) > 1})
    if dup:
        sys.exit("error: two skills share a folder name, which a flat folder cannot hold: %s" % ", ".join(dup))
    out.mkdir(parents=True, exist_ok=True)
    for d in skills:
        dst = out / d.name
        shutil.copytree(d, dst, ignore=lambda folder, items: [
            i for i in items if i == "__pycache__"
            or ((Path(folder) / i).is_dir() and (Path(folder) / i / ns.SKILL_FILE).exists())])
        md = dst / ns.SKILL_FILE
        text, _ = ns.inject(md.read_text(encoding="utf-8"), "")
        with open(md, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    print("flattened %d skill(s) into %s" % (len(names), out))
    return 0


def flat_skills(folder):
    folder = Path(folder)
    return sorted(p for p in folder.iterdir() if (p / ns.SKILL_FILE).is_file())


def stage(arrangement, src, dest):
    """Copy an arrangement into a skills folder the way a user would install it."""
    dest.mkdir(parents=True, exist_ok=True)
    if arrangement == "C":
        root = Path(src).resolve()
        shutil.copytree(root, dest / root.name, ignore=shutil.ignore_patterns("tests", "__pycache__", ".git"))
    else:
        for d in flat_skills(src):
            shutil.copytree(d, dest / d.name, ignore=shutil.ignore_patterns("__pycache__", ".git"))
    return dest


# ---------------------------------------------------------------- runners

def word_model_choice(arrangement, src, sentence):
    """What the lexical model picks, and the SKILL.md files it reads on the way."""
    if arrangement == "C":
        root = Path(src).resolve()
        skills, _ = oc.find_skills(root)
        syn = oc.load_synonyms(root)
        path = oc.route(sentence, root, skills, syn)
        read = [p for p in path if not isinstance(p, tuple)]
        files = [str((Path(p) / ns.SKILL_FILE).relative_to(root.parent)) for p in read]
        last = path[-1]
        if isinstance(last, tuple) or Path(last) == root:
            return "none", files
        return Path(last).name, files
    syn = {}
    hits = []
    for d in flat_skills(src):
        meta, _, err = ns.read_skill_doc(str(d))
        if not err and oc.match_node(oc.canonicalize(sentence, syn), meta, syn):
            hits.append(d.name)
    chosen = hits[0] if len(hits) == 1 else "none"
    return chosen, ([str(Path(chosen) / ns.SKILL_FILE)] if chosen != "none" else [])


def run_word_model(arrangement, src, sentence, opts):
    chosen, files = word_model_choice(arrangement, src, sentence)
    return {"chosen": chosen, "files_read": files, "input_tokens": "", "cost_usd": ""}


def parse_claude_stream(lines, skills_dir):
    """Files read, skill chosen and tokens from `claude -p --output-format stream-json`."""
    skills_dir = Path(skills_dir).resolve()
    files, final, usage, cost = [], "", {}, ""

    def add(p):
        try:
            rel = str(Path(p).resolve().relative_to(skills_dir))
        except (ValueError, OSError):
            return
        if rel not in files:
            files.append(rel)

    for raw in lines:
        try:
            e = json.loads(raw)
        except ValueError:
            continue
        if e.get("type") == "assistant":
            for c in e.get("message", {}).get("content", []):
                if c.get("type") != "tool_use":
                    continue
                inp = c.get("input", {})
                if c.get("name") == "Read" and inp.get("file_path"):
                    add(inp["file_path"])
                elif c.get("name") == "Skill":   # a Skill call loads that SKILL.md into context
                    name = (inp.get("skill") or inp.get("name") or inp.get("command") or "").lstrip("/")
                    for md in sorted(skills_dir.rglob(ns.SKILL_FILE), key=lambda m: len(m.parts)):
                        if md.parent.name == name:
                            add(md)
                            break
        elif e.get("type") == "result":
            final = e.get("result") or ""
            usage = e.get("usage") or {}
            cost = e.get("total_cost_usd", "")
    chosen = ""
    for line in reversed(final.splitlines()):
        if line.strip().upper().startswith("SKILL:"):
            chosen = line.split(":", 1)[1].strip().strip("`").strip().rstrip("/").split("/")[-1]
            break
    if not chosen:   # no answer line: the deepest skill it opened
        mds = [f for f in files if f.endswith(ns.SKILL_FILE)]
        chosen = Path(max(mds, key=lambda f: f.count("/"))).parent.name if mds else "none"
    tokens = sum(int(usage.get(k) or 0) for k in
                 ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    out = {"chosen": chosen or "none", "files_read": files, "input_tokens": tokens, "cost_usd": cost}
    if not tokens:   # nothing reached a model: a refused key, an exhausted quota, a proxy message
        out["error"] = "no model call (0 input tokens): %s" % (final.strip().splitlines() or ["no result"])[0][:200]
    return out


def _init_skills(lines):
    """The skill names Claude Code reported at start-up (the `system`/`init` event)."""
    for raw in lines:
        try:
            e = json.loads(raw)
        except ValueError:
            continue
        if e.get("type") == "system" and e.get("subtype") == "init":
            return ",".join(e.get("skills") or [])
    return ""


def _scratch(arrangement, src):
    work = Path(tempfile.mkdtemp(prefix="holon-eval-"))
    proj, home = work / "project", work / "home"
    home.mkdir()
    skills = stage(arrangement, src, proj / ".claude" / "skills")
    return work, proj, home, skills


def run_claude(arrangement, src, sentence, opts):
    work, proj, home, skills = _scratch(arrangement, src)
    try:
        cmd = [opts.claude, "-p", sentence, "--output-format", "stream-json", "--verbose",
               "--no-session-persistence", "--max-turns", str(opts.max_turns),
               "--allowedTools", "Read,Glob,Grep,Skill"]
        if opts.mode == "route":
            cmd += ["--append-system-prompt", ROUTE_ONLY_PROMPT]
        if opts.model:
            cmd += ["--model", opts.model]
        env = dict(os.environ)
        if not opts.keep_home:
            # An empty HOME keeps the user's own ~/.claude/skills and CLAUDE.md out of the run.
            # It also hides a subscription login; then give ANTHROPIC_API_KEY, or --keep-home.
            env.update(HOME=str(home), USERPROFILE=str(home))
            for k in ("CLAUDE_CONFIG_DIR", "XDG_CONFIG_HOME"):
                env.pop(k, None)
        p = subprocess.run(cmd, cwd=str(proj), env=env, stdin=subprocess.DEVNULL, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=opts.timeout)
        if opts.raw_dir:
            raw = Path(opts.raw_dir)
            raw.mkdir(parents=True, exist_ok=True)
            n = len(list(raw.glob("*.jsonl"))) + 1
            (raw / ("%04d-%s.jsonl" % (n, arrangement))).write_text(
                json.dumps({"sentence": sentence, "arrangement": arrangement, "cmd": cmd[3:]}) + "\n"
                + p.stdout + ("\n# stderr\n" + p.stderr if p.stderr else ""), encoding="utf-8")
        out = parse_claude_stream(p.stdout.splitlines(), skills)
        out["skills_seen"] = _init_skills(p.stdout.splitlines())
        if p.returncode or out.get("error"):
            out["error"] = out.get("error") or "exit %d: %s" % (p.returncode, (p.stderr or p.stdout).strip()[-300:])
        out["task_ok"] = run_check(opts, proj, sentence) if opts.mode == "task" else ""
        return out
    finally:
        shutil.rmtree(work, ignore_errors=True)


def run_command(arrangement, src, sentence, opts):
    work, proj, home, skills = _scratch(arrangement, src)
    try:
        prompt = work / "prompt.txt"
        prompt.write_text(sentence + ("\n\n" + ROUTE_ONLY_PROMPT if opts.mode == "route" else ""), encoding="utf-8")
        cmd = opts.runner_cmd
        for key, value in (("{skills}", skills), ("{prompt_file}", prompt), ("{workdir}", proj)):
            cmd = cmd.replace(key, str(value))   # plain replace: the command may contain other braces
        p = subprocess.run(cmd, shell=True, cwd=str(proj), stdin=subprocess.DEVNULL, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=opts.timeout)
        last = (p.stdout.strip().splitlines() or ["{}"])[-1]
        try:
            out = json.loads(last)
        except ValueError:
            out = {"chosen": "none", "files_read": [], "error": "last line is not JSON: %r" % last[:200]}
        if p.returncode:
            out["error"] = "exit %d: %s" % (p.returncode, (p.stderr or "").strip()[-300:])
        out["task_ok"] = run_check(opts, proj, sentence) if opts.mode == "task" else ""
        return out
    finally:
        shutil.rmtree(work, ignore_errors=True)


def run_check(opts, workdir, sentence):
    if not opts.check:
        return ""
    p = subprocess.run(opts.check, shell=True, cwd=str(workdir), env=dict(os.environ, HOLON_EVAL_SENTENCE=sentence))
    return "1" if p.returncode == 0 else "0"


RUNNERS = {"word-model": run_word_model, "claude-code": run_claude, "command": run_command}


def listing_bytes(arrangement, src):
    """What a host shows before any file is opened: the name and description of every
    top-level skill folder. Flat: every skill. Tree: the root alone."""
    tops = [Path(src).resolve()] if arrangement == "C" else flat_skills(src)
    total = 0
    for d in tops:
        meta, _, err = ns.read_skill_doc(str(d))
        if not err:
            total += len(("%s: %s\n" % (meta.get("name", d.name), meta.get("description", ""))).encode("utf-8"))
    return total


def bytes_of(arrangement, src, files):
    """Listing plus every file opened. A rough stand-in for context; tokens come from the host."""
    base = Path(src).resolve().parent if arrangement == "C" else Path(src).resolve()
    total = listing_bytes(arrangement, src)
    for f in files:
        p = base / f
        if p.is_file():
            total += p.stat().st_size
    return total


# ---------------------------------------------------------------- run

def cmd_run(args):
    rows = read_sentences(args.sentences)
    frozen = check_frozen(args.sentences, rows, args.unfrozen)
    arrangements = [("C", args.tree)]
    if args.trimmed:
        arrangements.insert(0, ("B", args.trimmed))
    if args.flat:
        arrangements.insert(0, ("A", args.flat))
    if args.runner == "command" and not args.runner_cmd:
        sys.exit("error: --runner command needs --runner-cmd")
    if args.runner == "claude-code" and not shutil.which(args.claude):
        sys.exit("error: %s not found; install Claude Code or give --claude PATH" % args.claude)
    names = {}
    if args.names:   # original flat names -> tree names, from a `move --plan` file
        for src, _, name in ns.read_plan(args.names)[0]:
            names[os.path.basename(os.path.normpath(src)).lower()] = name.lower()
    runner = RUNNERS[args.runner]
    todo = [r for r in rows if args.all_splits or r["split"] == "test"]
    out_path = Path(args.out)
    new = not out_path.exists()
    with open(out_path, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for r in todo:
            wm_choice, _ = word_model_choice("C", args.tree, r["sentence"])
            for arr, src in arrangements:
                for k in range(1, args.runs + 1):
                    t0 = time.time()
                    try:
                        res = runner(arr, src, r["sentence"], args)
                    except subprocess.TimeoutExpired:
                        res = {"chosen": "none", "files_read": [], "error": "timeout"}
                    failed = bool(res.get("error"))
                    chosen = "" if failed else (res.get("chosen") or "none").lower()
                    mapped = names.get(chosen, chosen) if arr == "A" else chosen
                    files = res.get("files_read") or []
                    w.writerow({
                        "sentence_id": r["id"], "split": r["split"], "run": k, "runner": args.runner,
                        "model": args.model or "", "arrangement": arr, "expected": r["expected"],
                        "chosen": mapped, "route_ok": "" if failed else int(mapped in expected_set(r["expected"])),
                        "task_ok": res.get("task_ok", ""), "files_read": ";".join(files),
                        "bytes_read": bytes_of(arr, src, files), "input_tokens": res.get("input_tokens", ""),
                        "cost_usd": res.get("cost_usd", ""), "wall_time": "%.1f" % (time.time() - t0),
                        "word_model": wm_choice if arr == "C" else "",
                        "agrees_word_model": int(mapped == wm_choice.lower()) if arr == "C" and not failed else "",
                        "skills_seen": res.get("skills_seen", ""),
                        "error": res.get("error", "") or ("" if frozen == "frozen" else "unfrozen split"),
                    })
                    f.flush()
                    print("%s %s run %d: %s (expected %s)" % (r["id"], arr, k, "ERROR " + res["error"][:120] if failed
                                                               else mapped, r["expected"]), flush=True)
    print("wrote %s" % out_path)
    return 0


# ---------------------------------------------------------------- report

def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _median(vals):
    vals = [v for v in vals if v is not None]
    return ("%.0f" % statistics.median(vals)) if vals else "-"


def report(rows, only_test=True):
    if only_test:
        rows = [r for r in rows if r["split"] == "test"]
    out = []
    unfrozen = sum(r["error"] == "unfrozen split" for r in rows)
    errors = [r for r in rows if r["route_ok"] == ""]
    rows = [r for r in rows if r["route_ok"] != ""]
    out.append("runs: %d completed (test split), runner(s): %s, model(s): %s"
               % (len(rows), ", ".join(sorted({r["runner"] for r in rows})) or "-",
                  ", ".join(sorted({r["model"] or "default" for r in rows})) or "-"))
    if unfrozen:
        out.append("WARNING: %d run(s) used a test split that was not frozen; they are not evidence." % unfrozen)
    if errors:
        out.append("NOT COUNTED: %d run(s) did not complete; they are left out of every rate below: %s"
                   % (len(errors), "; ".join(sorted({r["error"][:80] for r in errors}))[:400]))
    out.append("")
    out.append("| arrangement | runs | sentences | route_ok | task_ok | median bytes read | median input tokens |")
    out.append("|---|---|---|---|---|---|---|")
    for arr in ("A", "B", "C"):
        rs = [r for r in rows if r["arrangement"] == arr]
        if not rs:
            continue
        ok = sum(int(r["route_ok"]) for r in rs)
        tk = [r for r in rs if r["task_ok"] in ("0", "1")]
        out.append("| %s | %d | %d | %d/%d (%.0f%%) | %s | %s | %s |" % (
            arr, len(rs), len({r["sentence_id"] for r in rs}), ok, len(rs), 100.0 * ok / len(rs),
            ("%d/%d" % (sum(r["task_ok"] == "1" for r in tk), len(tk))) if tk else "-",
            _median(_num(r["bytes_read"]) for r in rs), _median(_num(r["input_tokens"]) for r in rs)))
    c = [r for r in rows if r["arrangement"] == "C" and r["agrees_word_model"] != ""]
    if c:
        agree = sum(int(r["agrees_word_model"]) for r in c)
        diff = [r for r in c if r["agrees_word_model"] == "0"]
        agent_right = sum(int(r["route_ok"]) for r in diff)
        wm_right = sum(r["word_model"].lower() in expected_set(r["expected"]) for r in diff)
        out.append("")
        out.append("C, agent vs word model: same choice in %d/%d runs (%.0f%%). Where they differ (%d): "
                   "agent right %d, word model right %d." % (agree, len(c), 100.0 * agree / len(c),
                                                              len(diff), agent_right, wm_right))
    fails = [r for r in rows if r["route_ok"] == "0"]
    if fails:
        out.append("")
        out.append("wrong choices:")
        for r in sorted(fails, key=lambda r: (r["sentence_id"], r["arrangement"], int(r["run"]))):
            out.append("  %s %s run %s: chose %s, expected %s" % (
                r["sentence_id"], r["arrangement"], r["run"], r["chosen"], r["expected"]))
    return "\n".join(out)


def cmd_report(args):
    with open(args.results, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    print(report(rows, only_test=not args.all_splits))
    return 0


# ---------------------------------------------------------------- main

def main(argv=None):
    p = argparse.ArgumentParser(prog="harness", description="Measure whether a holon tree helps an agent pick skills.")
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("flatten", help="arrangement B: copy every skill of a tree into one flat folder")
    s.add_argument("tree")
    s.add_argument("out")
    s.set_defaults(func=cmd_flatten)

    s = sub.add_parser("freeze", help="fix the test split of a sentence file")
    s.add_argument("sentences")
    s.set_defaults(func=cmd_freeze)

    s = sub.add_parser("run", help="run every test sentence on each arrangement")
    s.add_argument("sentences")
    s.add_argument("--tree", required=True, help="arrangement C: the root of the holon tree")
    s.add_argument("--flat", help="arrangement A: the original flat skills folder")
    s.add_argument("--trimmed", help="arrangement B: the output of `flatten`")
    s.add_argument("--names", help="a `holon.py move --plan` file, to map A's folder names to the tree's")
    s.add_argument("--runner", choices=sorted(RUNNERS), default="word-model")
    s.add_argument("--runner-cmd", help="for --runner command")
    s.add_argument("--claude", default="claude", help="path of the claude executable")
    s.add_argument("--model", help="passed to the agent")
    s.add_argument("--mode", choices=("route", "task"), default="route",
                   help="route: the agent only chooses (cheap); task: it does the task, and --check grades it")
    s.add_argument("--check", help="for --mode task: a shell command run in the project folder; exit 0 = task_ok")
    s.add_argument("--keep-home", action="store_true",
                   help="claude-code: keep the real HOME (needed for a subscription login without ANTHROPIC_API_KEY); "
                        "your own ~/.claude/skills and CLAUDE.md are then visible to every run")
    s.add_argument("--raw-dir", help="claude-code: save each run's raw stream-json here, to check what the agent saw")
    s.add_argument("--runs", type=int, default=3)
    s.add_argument("--max-turns", type=int, default=8)
    s.add_argument("--timeout", type=int, default=600)
    s.add_argument("--out", default="results.csv", help="appended to, so a run can be resumed or extended")
    s.add_argument("--unfrozen", action="store_true", help="run although the test split is not frozen")
    s.add_argument("--all-splits", action="store_true", help="also run the tune split")
    s.set_defaults(func=cmd_run)

    s = sub.add_parser("report", help="summarise a results file")
    s.add_argument("results")
    s.add_argument("--all-splits", action="store_true")
    s.set_defaults(func=cmd_report)

    args = p.parse_args(argv)
    if not getattr(args, "command", None):
        p.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
