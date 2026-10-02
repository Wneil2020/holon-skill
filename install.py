#!/usr/bin/env python3
# Copyright (c) 2026 Wneil2020 and the holon skill contributors. Released under the MIT License.
"""One-command installer for holon skill. Needs Python 3.8+ and nothing else (no git).

Run it straight from GitHub (the same line works in Windows cmd, PowerShell, macOS and Linux;
on Windows write `py` instead of `python3`):

    python3 -c "import urllib.request as u; exec(u.urlopen('https://raw.githubusercontent.com/Wneil2020/holon-skill/main/install.py').read())"

or, from a downloaded copy of the repository:

    python3 install.py [--host NAME] [--project] [--force] [--dry-run] ...

To install a fixed release instead of the latest `main`, add `--ref` with a tag:

    python3 -c "import urllib.request as u; exec(u.urlopen('https://raw.githubusercontent.com/Wneil2020/holon-skill/v1.0.0/install.py').read())" --ref v1.0.0

It downloads the repository as a zip from GitHub, unpacks it in a temporary folder, and runs
`holon/scripts/holon.py install` on the `holon/` package inside, which copies the tree to
every agent tool on this machine and checks the copy. Any option is passed on to that command.
When run from inside a downloaded copy, nothing is downloaded.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

REPO = "Wneil2020/holon-skill"   # the GitHub repository, owner/name; a fork changes this line
REF = "main"                     # the branch or tag downloaded when --ref is not given


def split_ref(argv):
    """Take `--ref TAG` (or `--ref=TAG`) out of the options; the rest go to holon.py install."""
    ref, rest, i = REF, [], 0
    while i < len(argv):
        a = argv[i]
        if a == "--ref":
            if i + 1 >= len(argv):
                sys.exit("error: --ref needs a tag or branch, e.g. --ref v1.0.0")
            ref, i = argv[i + 1], i + 2
            continue
        if a.startswith("--ref="):
            ref = a[len("--ref="):]
        else:
            rest.append(a)
        i += 1
    return ref, rest


def archive_url(ref=REF):
    # HOLON_SKILL_ARCHIVE points at another zip (a mirror, a fork, or a test archive).
    # github.com/OWNER/REPO/archive/REF.zip serves both branches and tags.
    return os.environ.get("HOLON_SKILL_ARCHIVE") or "https://github.com/%s/archive/%s.zip" % (REPO, ref)


def local_package():
    """The holon/ package next to this file, when it runs from a copy of the repository."""
    here = globals().get("__file__")
    if not here or here.startswith("<"):
        return None
    pkg = os.path.join(os.path.dirname(os.path.abspath(here)), "holon")
    return pkg if os.path.isfile(os.path.join(pkg, "scripts", "holon.py")) else None


def download(tmp, ref=REF):
    import urllib.request
    url = archive_url(ref)
    if REPO == "OWNER/REPO" and "HOLON_SKILL_ARCHIVE" not in os.environ:
        sys.exit("error: install.py does not name its repository yet (REPO = \"OWNER/REPO\"). "
                 "Set REPO at the top of install.py to the repository's owner/name.")
    print("downloading %s" % url, flush=True)
    fn = os.path.join(tmp, "holon-skill.zip")
    try:
        with urllib.request.urlopen(url) as r, open(fn, "wb") as f:
            shutil.copyfileobj(r, f)
    except Exception as e:
        hint = ""
        if "CERTIFICATE" in str(e).upper():
            hint = " (on macOS run 'Install Certificates.command' in the Python folder, then try again)"
        sys.exit("error: could not download %s: %s%s" % (url, e, hint))
    out = os.path.join(tmp, "src")
    with zipfile.ZipFile(fn) as z:
        for name in z.namelist():   # refuse paths that would land outside `out`
            target = os.path.abspath(os.path.join(out, name))
            if not target.startswith(os.path.abspath(out) + os.sep) and target != os.path.abspath(out):
                sys.exit("error: the archive contains an unsafe path: %s" % name)
        z.extractall(out)
    for d, dirs, files in os.walk(out):
        if os.path.basename(d) == "holon" and os.path.isfile(os.path.join(d, "scripts", "holon.py")):
            return d
        if d.count(os.sep) - out.count(os.sep) >= 2:
            dirs[:] = []
    sys.exit("error: no holon/scripts/holon.py in %s" % url)


def main(argv=None):
    ref, argv = split_ref(list(sys.argv[1:] if argv is None else argv))
    tmp = None
    pkg = local_package()
    if pkg is not None and ref != REF:
        print("note: running from a local copy, so --ref %s is ignored" % ref, flush=True)
    try:
        if pkg is None:
            tmp = tempfile.mkdtemp(prefix="holon-skill-")
            pkg = download(tmp, ref)
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
        cmd = [sys.executable, os.path.join(pkg, "scripts", "holon.py"), "install", pkg] + argv
        return subprocess.call(cmd, env=env)
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    code = main()
    if code:
        sys.exit(code)
