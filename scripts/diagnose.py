#!/usr/bin/env python3
# Copyright (c) 2026 Wneil2020 and the holon skill contributors. Released under the MIT License.
r"""Offline, standard-library diagnostics. Tests run on a copy with an isolated home.

    py -3 scripts\diagnose.py                 # Windows
    python3 scripts/diagnose.py               # macOS / Linux
    python3 scripts/diagnose.py --probe-only   # environment checks only

No packages are installed, no repository is pushed, and no real skills are installed.
Logs may contain local paths; review them before sharing. Exit codes: 0 pass, 1
failure, 2 invalid arguments, 130 interrupted. Optional omissions remain visible.
"""
import argparse
import datetime
import json
import locale
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".ruff_cache", ".venv", "venv",
             "node_modules", "build", "dist", ".idea", ".vscode"}
HOME_OVERRIDES = ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "VIBE_HOME", "XDG_CONFIG_HOME",
                  "XDG_DATA_HOME", "HOLON_SKILL_ARCHIVE", "PYTHONPATH", "PYTHONHOME")


def child_environment(home):
    env = dict(os.environ)
    for name in HOME_OVERRIDES:
        env.pop(name, None)
    env.update(HOME=str(home), USERPROFILE=str(home), PYTHONUTF8="1",
               PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    return env


def environment_report(scratch):
    report = {"os": platform.system(), "os_release": platform.release(),
              "architecture": platform.machine(), "python": platform.python_version(),
              "executable": sys.executable, "filesystem_encoding": sys.getfilesystemencoding(),
              "locale_encoding": locale.getpreferredencoding(False),
              "stdout_encoding": getattr(sys.stdout, "encoding", None),
              "git_available": shutil.which("git") is not None,
              "skills_ref_available": shutil.which("skills-ref") is not None}
    source = scratch / "probe.txt"
    source.write_bytes(b"ok\n")
    try:
        (scratch / "probe-link").symlink_to(source)
        report["symlinks_available"] = True
    except (OSError, NotImplementedError):
        report["symlinks_available"] = False
    warnings = []
    if not report["git_available"]:
        warnings.append("Git is unavailable: git-dependent tests are skipped; local installation still works.")
    if not report["symlinks_available"]:
        warnings.append("Symbolic links are unavailable: link-specific tests are skipped. Windows Developer Mode may enable them.")
    if not report["skills_ref_available"]:
        warnings.append("skills-ref is unavailable: external specification validation is skipped; nothing will be downloaded.")
    return report, warnings


def copy_project(repo, destination):
    def ignore(directory, names):
        skipped = {name for name in names if name in SKIP_DIRS or name.startswith(".env")
                   or ".git-backup-" in name or name.endswith((".log", ".pyc"))}
        for name in set(names) - skipped:
            if (Path(directory) / name).is_symlink():
                raise ValueError("diagnostics require a source copy without symbolic links: " + name)
        return skipped
    shutil.copytree(str(repo), str(destination), ignore=ignore)


def stop_process(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        try:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            pass
        if process.poll() is None:
            process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait()


def test_summary(text):
    """Count the outer unittest suite, not summaries quoted in failure details."""
    summaries = list(re.finditer(r"^Ran (\d+) tests? in [^\r\n]+", text, re.M))
    if not summaries:
        return 0, 0
    last = summaries[-1]
    verdict = re.search(r"^(?:OK|FAILED)\b[^\r\n]*", text[last.end():], re.M)
    skipped = re.search(r"\bskipped=(\d+)", verdict.group(0)) if verdict else None
    return int(last.group(1)), int(skipped.group(1)) if skipped else 0


def run_step(label, command, cwd, env, logfile, timeout):
    print("Running: " + label, flush=True)
    started = time.monotonic()
    flags = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    with logfile.open("wb") as stream:
        try:
            process = subprocess.Popen(command, cwd=str(cwd), env=env, stdout=stream,
                                       stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, **flags)
        except OSError as error:
            stream.write(str(error).encode("utf-8", errors="replace"))
            return {"step": label, "exit_code": 1, "log": logfile.name, "error": str(error)}
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            stop_process(process)
            stream.write(b"\nDIAGNOSTIC TIMEOUT\n")
            code = 124
        except KeyboardInterrupt:
            stop_process(process)
            stream.write(b"\nDIAGNOSTIC INTERRUPTED\n")
            code = 130
    text = logfile.read_text(encoding="utf-8", errors="replace")
    count, skipped = test_summary(text)
    result = {"step": label, "exit_code": code, "log": logfile.name,
              "seconds": round(time.monotonic() - started, 2),
              "test_count": count, "skipped_tests": skipped}
    print("  %s (exit %s); log: %s" % ("PASS" if code == 0 else "FAIL", code, logfile), flush=True)
    return result


def write_report(directory, report):
    with (directory / "report.json").open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path, help="new directory outside the repository; contains full logs and report.json")
    parser.add_argument("--probe-only", action="store_true", help="check environment without running tests")
    parser.add_argument("--timeout", type=int, default=600, help="timeout per test suite in seconds (default: 600)")
    args = parser.parse_args(argv)
    if sys.version_info < (3, 8):
        parser.error("Python 3.8 or newer is required; Python 3.12 or 3.13 is recommended")
    if args.timeout < 1:
        parser.error("--timeout must be positive")
    repo = args.repo.expanduser().resolve()
    if not (repo / "holon/scripts/holon.py").is_file():
        parser.error("--repo must be the holon-skill repository, not its holon subfolder")
    directory = args.output_dir.expanduser().resolve() if args.output_dir else (
        Path.home() / "holon-diagnostics" / datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    if directory == repo or repo in directory.parents:
        parser.error("--output-dir must be outside the repository")
    if directory.exists():
        parser.error("--output-dir already exists; choose a new directory")
    directory.mkdir(parents=True)
    report = {"schema_version": 1, "mode": "probe-only" if args.probe_only else "full",
              "source": str(repo), "steps": [], "status": "running"}
    code = 0
    try:
        with tempfile.TemporaryDirectory(prefix="holon-diagnose-") as temporary:
            scratch = Path(temporary)
            report["environment"], report["warnings"] = environment_report(scratch)
            print(json.dumps(report["environment"], ensure_ascii=False, indent=2))
            for warning in report["warnings"]:
                print("NOTE: " + warning)
            write_report(directory, report)
            if not args.probe_only:
                run_checks(repo, scratch, directory, report, args.timeout)
            code = 130 if any(s["exit_code"] == 130 for s in report["steps"]) else (
                1 if any(s["exit_code"] != 0 for s in report["steps"]) else 0)
    except KeyboardInterrupt:
        code = 130
    except (OSError, ValueError) as error:
        report["error"] = str(error)
        code = 1
    report["exit_code"] = code
    report["status"] = "passed" if code == 0 else ("interrupted" if code == 130 else "failed")
    write_report(directory, report)
    print("\n%s. Report: %s" % (report["status"].upper(), directory / "report.json"))
    print("Review logs for local paths before sharing. No repository was pushed or made public.")
    return code


def run_checks(repo, scratch, directory, report, timeout):
    work = scratch / "workspace with spaces" / "holon-skill"
    work.parent.mkdir()
    copy_project(repo, work)
    home = scratch / "isolated-home"
    home.mkdir()
    env = child_environment(home)
    py = sys.executable
    package = work / "holon"
    report["warnings"].append("Tests use a copy without .git: two checkout-clone tests are skipped; temporary-git tests run if Git is installed.")
    steps = [
        ("core-tests", [py, "tests/test_holon.py"], package),
        ("organizer-tests", [py, "organizer/tests/test_organizer_cli.py"], package),
        ("readme-tests", [py, "tests/test_readme_outputs.py"], package),
        ("validate", [py, "scripts/holon.py", "validate", "."], package),
        ("lint", [py, "organizer/scripts/organizer_cli.py", "lint", "."], package),
        ("replay", [py, "organizer/scripts/organizer_cli.py", "replay", "."], package),
        ("local-install", [py, "install.py"], work),
        ("fresh-root", [py, "holon/scripts/holon.py", "init", "mylib", "--root", str(scratch / "trees 中文")], work),
    ]
    def run(label, command, cwd):
        log = directory / ("%02d-%s.log" % (len(report["steps"]) + 1, label))
        result = run_step(label, command, cwd, env, log, timeout)
        report["steps"].append(result)
        write_report(directory, report)
        return result["exit_code"]

    for label, command, cwd in steps:
        if run(label, command, cwd) == 130:
            return
    tree = scratch / "trees 中文" / "mylib"
    if report["steps"][-1]["exit_code"] == 0:
        for label, script in (("validate", "scripts/holon.py"), ("lint", "organizer/scripts/organizer_cli.py"),
                              ("replay", "organizer/scripts/organizer_cli.py")):
            if run("fresh-" + label, [py, script, label, "."], tree) == 130:
                return
    if report["environment"]["skills_ref_available"]:
        for skill in sorted(package.rglob("SKILL.md")):
            if "tests" not in skill.parts:
                if run("spec-" + skill.parent.name, [shutil.which("skills-ref"), "validate", str(skill.parent)], work) == 130:
                    return


if __name__ == "__main__":
    sys.exit(main())
