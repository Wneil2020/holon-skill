#!/usr/bin/env python3
# Copyright (c) 2026 Wneil2020 and the holon skill contributors. Released under the MIT License.
"""organizer CLI -- lexical and structural checks only (zero-dependency, Python 3.8+).

Boundary: every judgement (is this a skill or knowledge, whose step is it,
are these two skills the same thing, which side wins a conflict) is made by
the AI that has read organizer/SKILL.md, or by the library owner. This CLI
only checks formats, replays example sentences, does coarse word-set
screening, and moves things into .retired/.

Commands:
  lint     <root>                       Format checks. [E] must fix; [W] should fix; [·] just a hint
  replay   <root>                       Lexically replay every `triggers` sentence: positives must reach
                                        their skill, negatives must not land on it
  route    <root> "a sentence"          Walk one sentence from the root: who takes it at each gate,
                                        by which cover word, and where it lands
  overlap  <root> [--threshold]         Jaccard screening of sibling cover-word sets (after synonym folding)
  retire   <root> <path> --reason R     Move a skill directory into .retired/, write the header line,
                                        re-sync the parent routing table
  feedback <root>                       List unprocessed lines in _feedback.md
  counter  <root> [--bump]              Read the root archive_count; --bump increments it (bump BEFORE you
                                        start, so retire headers and the ABSORB.md section share one number)
  ask      <root>                       Print the checklist section of organizer/SKILL.md verbatim plus every
                                        `ruled:` line in the library's ABSORB.md

Frontmatter parsing and the definition of "what counts as a skill" are
imported from the mechanism layer, scripts/holon.py.
"""
import argparse
import re
import shutil
import sys
from collections import namedtuple
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _cand in (_HERE.parents[1] / "scripts", _HERE):
    if (_cand / "holon.py").is_file():
        sys.path.insert(0, str(_cand))
        break
try:
    import holon as ns  # noqa: E402
except ImportError:  # pragma: no cover
    sys.exit("error: mechanism-layer script scripts/holon.py not found. organizer/ must sit "
             "directly under the holon library root (<root>/scripts/holon.py next to <root>/organizer/).")

# ---- Parameters: same names and values as the table in organizer/SKILL.md; the dogfood test checks each ----
COVER_MAX = 5        # max cover words per description
DESC_MAX = 200       # max description length in characters (English needs more room than CJK; keep one table line readable)
MAX_BODY = 150       # body longer than this (non-blank lines) -> hint
FANOUT = 9           # more siblings than this under one parent -> hint
OVERLAP = 0.4        # sibling cover-word Jaccard above this -> suspected duplicate
COVER_MIN = 2        # cover words shorter than this almost always over-match
# ---- Fixed internal thresholds (not rules; they only decide when a hint appears) ----
SHORT_BODY = 5       # body shorter than this -> "very short" hint
HOLLOW_BODY = 3      # parent body at most this long with exactly one child -> "hollow" hint
FEEDBACK_FILE = "_feedback.md"
ABSORB_FILE = "ABSORB.md"
RULES_FILE = _HERE.parent / "SKILL.md"      # the organizer rulebook; `ask` reads the checklist from it
CHECKLIST_HEAD = "## Before creating a parent: four questions"  # section title; the dogfood test guards it
RETIRED_DIR = ".retired"
LEGACY_FIELDS = ("axis", "last-verified", "ledger")
ANTI_KEYWORD = "should go to"
ANTI_RE = re.compile(r"^(?P<sent>.*?)\s+should go to\s+(?P<target>\S+)\s*$")
RETIRED_HEAD_RE = re.compile(r"^retired @(\d+) \S")
ABSORB_LINE_RE = re.compile(r"(learned|merged|ruled):")
RULED_RE = re.compile(r"ruled:")
WORD_SPLIT = r"[,\uff0c\u3001/]"   # comma, full-width comma, ideographic comma, slash
ROOT_LABEL = "root (nobody took it)"

Skill = namedtuple("Skill", "meta body err")


# ---------------- parsing ----------------

def parse_frontmatter(text):
    return ns.split_frontmatter(text)


def load_synonyms(root):
    """synonyms.md: one comma-separated group per line; the first word is the canonical form."""
    syn = {}
    f = root / "synonyms.md"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            line = re.sub(r"@\d+\s*$", "", line.strip())
            if line.startswith("#"):
                continue   # a comment or heading, not a group
            words = [w.strip() for w in re.split(r"[,\uff0c\u3001]", line) if w.strip()]
            if len(words) >= 2:
                for w in words:
                    syn[w.lower()] = words[0].lower()
    return syn


def normalize(word, syn):
    return syn.get(word.lower(), word.lower())


def parse_desc(desc):
    """Three-part description -> (set of cover words, set of exclude words)."""
    covers, excludes, _ = ns.description_clauses(desc)
    return set(covers), set(excludes)


def split_anti(trigger):
    """A negative example is recognised only by a trailing `should go to <path>`.
    Returns (sentence, target) or None."""
    m = ANTI_RE.match(trigger.strip())
    if not m:
        return None
    return m.group("sent").strip(), m.group("target").split("#", 1)[0].strip("/")


def find_skills(root):
    dirs, cycle_errors = ns.collect_skills(str(root))
    out = {}
    errors = list(cycle_errors)
    if not dirs:
        errors.append("no skill found under %s" % root)
    for d in dirs:
        meta, body, err = ns.read_skill_doc(d)
        if err:
            errors.append("%s: %s" % (d, err))
        out[Path(d)] = Skill(meta, body, err)
    return out, errors


def children_of(d, skills):
    return sorted(c for c in skills if c.parent == d)


def rel(root, d):
    """Skill identifiers use '/' on every OS; filesystem operations keep Path objects."""
    return d.relative_to(root).as_posix() if d != root else "."


def where(root, d):
    """Human-readable landing point: the root is spelled out, not written as '.'."""
    return ROOT_LABEL if d == root else str(rel(root, d))


def body_lines(sk):
    return len([l for l in sk.body.splitlines() if l.strip()])


# ---------------- lexical matching (mixed scripts) ----------------

def _pattern(w):
    """ASCII words match on word boundaries (so `db` does not hit `mongodb`);
    words containing other scripts match as substrings."""
    if re.fullmatch(r"[A-Za-z0-9_.\-]+", w):
        return re.compile(r"(?<![A-Za-z0-9_])" + re.escape(w) + r"(?![A-Za-z0-9_])", re.I)
    return re.compile(re.escape(w), re.I)


def contains(sentence, word):
    return bool(word) and _pattern(word).search(sentence) is not None


def _piece(w):
    """Regex fragment (uncompiled) for one word; same rule as _pattern."""
    if re.fullmatch(r"[A-Za-z0-9_.\-]+", w):
        return r"(?<![A-Za-z0-9_])" + re.escape(w) + r"(?![A-Za-z0-9_])"
    return re.escape(w)


def canonicalize(text, syn):
    """Fold the whole sentence to canonical forms and lower-case it. All aliases and
    canonical forms are compiled into ONE regex, scanned once, longest first: each
    position is replaced at most once and a word that is already canonical is left
    alone (`word -> word document` must not turn `word document` into `word document document`)."""
    s = text.lower()
    if not syn:
        return s
    words = set(syn) | set(syn.values())
    big = re.compile("|".join(_piece(w) for w in sorted(words, key=len, reverse=True)), re.I)
    return big.sub(lambda m: syn.get(m.group(0).lower(), m.group(0)), s)


def match_node(sentence_canon, meta, syn):
    """One skill's own header: a cover word is in the sentence and no exclude word is."""
    covers, excl = parse_desc(meta.get("description", ""))
    hit = any(contains(sentence_canon, canonicalize(c, syn)) for c in covers)
    blocked = any(contains(sentence_canon, canonicalize(e, syn)) for e in excl)
    return hit and not blocked


def inherited_covers(d, skills):
    """Cover words of every skill below d, as (word, owner). A sub-skill is a step of its
    parent, so a sentence that names the step names the parent's job too: the tree already
    says React is under web, and web answers to it without listing it."""
    out = []
    for k in sorted(skills):
        if k != d and d in k.parents:
            covers, _ = parse_desc(skills[k].meta.get("description", ""))
            out += [(c, k) for c in sorted(covers, key=str.lower)]
    return out


def match_skill(sentence_canon, d, skills, syn):
    """Does skill d take the sentence: by its own cover words, or by a descendant's.
    Only d's own `excludes` block; a child's `excludes` separates it from its siblings
    and says nothing about the parent."""
    meta = skills[d].meta
    if match_node(sentence_canon, meta, syn):
        return True
    _, excl = parse_desc(meta.get("description", ""))
    if any(contains(sentence_canon, canonicalize(e, syn)) for e in excl):
        return False
    return any(contains(sentence_canon, canonicalize(c, syn)) for c, _ in inherited_covers(d, skills))


def blocked_by(sentence_canon, meta, syn):
    """If a cover word would take the sentence but an `excludes` word blocks it,
    return the blocking exclude words; otherwise an empty list."""
    covers, excl = parse_desc(meta.get("description", ""))
    if not any(contains(sentence_canon, canonicalize(c, syn)) for c in covers):
        return []
    return sorted(e for e in excl if contains(sentence_canon, canonicalize(e, syn)))


def covers_text(meta):
    """Cover words in their original order, comma-joined (for messages)."""
    return ",".join(ns.description_covers(meta.get("description", "")))


def alias_covers(meta, syn):
    """Cover words that are themselves aliases of some canonical word in synonyms.md:
    returns [(cover word, canonical word)]. Such a cover word is replaced by the canonical
    word before matching, so every sentence containing the canonical word hits -- which the
    author usually did not intend. If the skill also lists the canonical word itself, the
    wide match is deliberate and not reported."""
    covers, _ = parse_desc(meta.get("description", "") or "")
    listed = {x.lower() for x in covers}
    out = []
    for c in covers:
        canon = normalize(c, syn)
        if canon != c.lower() and canon not in listed:
            out.append((c, canon))
    return out


def hit_covers_text(sentence_canon, meta, syn):
    """Which of this skill's cover words (as written) the sentence hits; aliases say what
    they fold to."""
    covers = [w for w in covers_text(meta).split(",") if w]   # original order, so output is stable
    alias = dict(alias_covers(meta, syn))
    groups = {}   # spellings that fold to one canonical word count once; extra spellings are appended
    for c in covers:
        canon = canonicalize(c, syn)
        if contains(sentence_canon, canon):
            groups.setdefault(canon, []).append(c)
    parts = []
    for canon, cs in groups.items():
        c = cs[0]
        if c in alias:
            s = f"'{c}' (an alias of '{alias[c]}' in synonyms.md, so it takes every sentence containing '{alias[c]}')"
        else:
            s = f"'{c}'"
        if len(cs) > 1:
            s += " (" + ",".join(f"'{x}'" for x in cs[1:]) + " fold to the same word)"
        parts.append(s)
    return ",".join(parts)


def hit_text(sentence_canon, d, root, skills, syn):
    """hit_covers_text for a skill, and when its own words did not hit, the descendant's
    word that did: `'React' (web/web-artifacts-builder's word; web answers to it as the parent)`."""
    own = hit_covers_text(sentence_canon, skills[d].meta, syn)
    if own:
        return own
    parts = []
    for c, owner in inherited_covers(d, skills):
        if contains(sentence_canon, canonicalize(c, syn)):
            parts.append(f"'{c}' ({rel(root, owner)}'s word; {rel(root, d)} answers to it as the parent)")
    return ",".join(parts)


def why_stopped(d, path, sentence_canon, root, skills, syn, who="this skill"):
    """When a positive example lands on an ancestor of d, say which gate failed and why.
    The first node on d's ancestor chain that is not on the path is the failed gate. A
    parent answers to every cover word below it, so an ancestor that did not take the
    sentence means d's own words are absent too; an ancestor that took it and was still
    not entered was tied with a sibling; an ancestor can also block with its own `excludes`.
    `who` is how d is referred to: "this skill" for positives; "target <path>" for negatives,
    where d is the declared target rather than the skill on the line."""
    chain = [p for p in reversed(d.parents) if p in skills and p != root] + [d]
    gate = next((n for n in chain if n not in path), None)
    if gate is None:
        return ""
    meta = skills[gate].meta
    if gate == d:
        ex = blocked_by(sentence_canon, meta, syn)
        if ex:
            return f" ({who} is blocked by its own 'excludes {','.join(ex)}')"
        return f" ({who} did not take it: the sentence contains none of its cover words {covers_text(meta)})"
    ex = blocked_by(sentence_canon, meta, syn)
    if ex:
        return (f" (the sentence was stopped at ancestor {rel(root, gate)}: blocked by "
                f"{rel(root, gate)}'s 'excludes {','.join(ex)}')")
    if match_skill(sentence_canon, gate, skills, syn):
        # The gate itself took the sentence; the route still did not enter it, so a
        # sibling of the gate took it too and the route stopped at their parent.
        rivals = [k for k in hits_under(gate.parent, sentence_canon, skills, syn) if k != gate]
        names = ", ".join(str(rel(root, k)) for k in rivals)
        return (f" (the sentence was stopped at {rel(root, gate.parent)}: {rel(root, gate)} took it, but so did "
                f"its sibling(s) {names}, and a sentence two children take stays with their parent -- "
                f"drop the sibling's word from this example, or accept that this sentence is {rel(root, gate.parent)}'s job)")
    return (f" (the sentence was stopped at ancestor {rel(root, gate)}: it contains none of "
            f"{rel(root, gate)}'s cover words {covers_text(meta)} and none of the cover words below it, "
            f"so none of {who}'s either -- write the sentence with one of {who}'s words, "
            "or fold its wording to one in synonyms.md)")


def hits_under(cur, sentence_canon, skills, syn):
    """Children of cur whose cover words take the sentence."""
    return [k for k in children_of(cur, skills) if match_skill(sentence_canon, k, skills, syn)]


def route(sentence, root, skills, syn):
    """Lexical descent. Returns the path as a list.
    Several children hit at one level: if that level is a skill (a parent), a sentence that
    spans two of its children is the parent's own step -- stop at the parent. If that level
    is the root (the root is not a skill; nobody can take it), it is an ambiguity and the
    last item is ("AMBIG", [hit nodes...])."""
    sentence_canon = canonicalize(sentence, syn)
    cur, path = root, [root]
    while True:
        hits = hits_under(cur, sentence_canon, skills, syn)
        if len(hits) == 1:
            cur = hits[0]
            path.append(cur)
        elif len(hits) > 1 and cur == root:
            return path + [("AMBIG", hits)]
        else:
            return path


def touched_nodes(path):
    out = set()
    for p in path:
        out.update(p[1]) if isinstance(p, tuple) else out.add(p)
    return out


def still_reachable(d, path):
    """Negative-example verdict: only a route that STOPS at d counts as a hit -- d is the end
    point, d is one of the ambiguity candidates, or the ambiguity is among d's ancestors (the
    route might still descend into d). Passing through d on the way to one of its children
    does not count: an intermediate skill's negatives often rightly belong to its own child."""
    last = path[-1]
    if isinstance(last, tuple):
        return d in last[1] or any(c in d.parents for c in last[1])
    return last == d


# ---------------- lint ----------------

def check_frontmatter(r, sk):
    issues = []
    if sk.err:
        issues.append(f"[E] {r}: frontmatter parse error: {sk.err}")
    if not sk.meta.get("name"):
        issues.append(f"[E] {r}: missing name")
    legacy = sorted(k for k in LEGACY_FIELDS if k in sk.meta)
    if legacy:
        issues.append(f"[W] {r}: legacy field(s) {', '.join(legacy)} have no meaning any more and can be removed "
                      f"(structural decisions go into {ABSORB_FILE})")
    return issues


def check_description(r, d, root, sk):
    issues = []
    desc = sk.meta.get("description", "")
    if not desc:
        return [f"[E] {r}: missing description"]
    if len(desc) > DESC_MAX:
        issues.append(f"[E] {r}: description is {len(desc)} characters > {DESC_MAX}")
    covers, excl = parse_desc(desc)
    for error in ns.description_clauses(desc)[2]:
        issues.append(f"[E] {r}: {error}; use one covers clause and at most one excludes clause")
    if d != root and not covers:
        issues.append(f"[E] {r}: description has no 'covers' word list "
                      "(three-part form: Use when ...: covers w, w; excludes w)")
    if len(covers) > COVER_MAX:
        issues.append(f"[E] {r}: {len(covers)} cover words > {COVER_MAX}")
    for w in sorted(covers | excl):
        if len(w) < COVER_MIN:
            issues.append(f"[W] {r}: word '{w}' is only {len(w)} character(s) long and will almost certainly over-match")
    return issues


def check_triggers(r, sk, skills, root):
    trig = sk.meta.get("triggers", [])
    if not isinstance(trig, list) or len(trig) < 3:
        return [f"[E] {r}: triggers needs 2 sentences it should take + 1 it should not, i.e. >= 3 entries"]
    if any(str(s).startswith("TODO") for s in trig):
        return [f"[E] {r}: triggers are still the TODO placeholders from init; write 2 sentences it should take + 1 it should not"]
    issues = []
    antis = [a for a in (split_anti(t) for t in trig) if a]
    if not antis:
        issues.append(f"[E] {r}: triggers has no negative example (end the sentence with '{ANTI_KEYWORD} <path>')")
    if len(trig) - len(antis) < 2:
        issues.append(f"[E] {r}: triggers has only {len(trig) - len(antis)} positive sentence(s), needs >= 2")
    for _, target in antis:
        if (root / target) not in skills:
            issues.append(f"[E] {r}: negative-example target '{target}' is not a skill in this library")
    return issues


# A path with at least one directory and a file extension, inside backticks: a bare
# `references/x.md`, or inside a command line such as `python scripts/run.py in.pdf`.
# `.xml` is not in the list: office bodies name paths inside a zip (`ppt/slides/slideN.xml`)
# that are not files of the skill.
PATH_IN_TICKS = re.compile(r"(?<![\w.\-/<])((?:\.\.?/)?(?:[\w.\-]+/)+[\w.\-]+\.(?:md|py|txt|json|sh|js|ts|yaml|yml|csv))(?![\w.\-/>])")


def check_file_refs(r, d, root, sk):
    """A body that names a file path in backticks, alone or inside a command, is telling the
    agent to open or run it. If the file is not where the path says, relative to this skill
    or to the tree root, the step cannot be followed. A bare filename with no directory is
    not checked: it may be an output the step writes. Globs and placeholders are skipped."""
    issues = []
    seen = set()
    for span in re.finditer(r"`[^`\n]+`", sk.body):
        for m in PATH_IN_TICKS.finditer(span.group(0)):
            ref = m.group(1)
            if ref in seen or "*" in ref or "{" in ref:
                continue
            seen.add(ref)
            if (d / ref).exists() or (root / ref).exists():
                continue   # relative to the skill, or written as "at the tree root"
            issues.append(f"[W] {r}: body points at `{ref}` and there is no such file under {r}/ or at the tree root -- "
                          "the step that names it cannot be followed; add the file or fix the path")
    return issues


def hints_for(r, d, root, sk, kids):
    """Hints, not rules: a nudge to look again, never counted as a warning."""
    hints = []
    lines = body_lines(sk)
    if lines > MAX_BODY:
        hints.append(f"[·] {r}: body has {lines} non-blank lines > {MAX_BODY} -- is knowledge mixed in "
                     "(move it to references/), or several separately nameable jobs?")
    elif d != root and lines < SHORT_BODY and "TODO" not in sk.body:
        # A scaffold still carrying TODO is reported by validate; a second message here would be noise.
        hints.append(f"[·] {r}: body has {lines} non-blank lines, very short -- if you removed it, could the AI "
                     "still do the job? Only if not is it a skill")
    groups, _ = ns.read_groups(str(d))
    if len(kids) > FANOUT and not groups:
        hints.append(f"[·] {r}: {len(kids)} sub-skills at one level > {FANOUT}; run `organizer_cli.py ask <root>` "
                     "and answer the four questions first -- if several deliver the same kind of thing, create a "
                     f"parent and move them in; only if none do, write a {ns.GROUPS_FILE} to section the table")
    if d != root and len(kids) == 1 and lines <= HOLLOW_BODY:
        hints.append(f"[·] {r}: exactly one sub-skill and a {lines}-line body -- looks hollow; "
                     "promote the child and retire the parent")
    return hints


def check_groups(r, d):
    """groups.md only shapes the routing table. Malformed lines are errors; a one-member group is a warning."""
    groups, errs = ns.read_groups(str(d))
    issues = [f"[E] {r}: {e}" for e in errs]
    for title, names in groups:
        if len(names) == 1:
            issues.append(f"[W] {r}: group '{title}' in {ns.GROUPS_FILE} has only 1 member; one card is not a section "
                          f"-- delete the line and it falls into the trailing '{ns.OTHER_SECTION}' section "
                          "(a parent card is no exception), or merge it into another group")
    return issues


def check_root_files(root, skills):
    issues = []
    if root in skills and FEEDBACK_FILE not in skills[root].body:
        issues.append(f"[W] .: root SKILL.md does not tell the AI to report routing misses to {FEEDBACK_FILE}")
    if not (root / FEEDBACK_FILE).is_file():
        issues.append(f"[W] .: library root has no {FEEDBACK_FILE}")
    counter = read_counter(root)
    issues += check_absorb(root, counter)
    issues += check_retired(root)
    issues += check_alias_overlap(root, skills, load_synonyms(root))
    issues += check_alias_covers(root, skills, load_synonyms(root))
    issues += check_excludes_reach(root, skills, load_synonyms(root))
    return issues


def _swallowed(alias, cover, syn):
    """Splice an alias and a cover word in every way they could abut in a sentence and actually
    fold it: is the cover word still there afterwards? If not, the alias swallowed part of it.
    Returns the colliding splice (for the message) or None."""
    cover_c = canonicalize(cover, syn)
    probes = []
    for first, second in ((alias, cover), (cover, alias)):  # only end-to-start overlap; full containment is normal
        for k in range(2, min(len(first), len(second))):  # a 1-character overlap is almost always a coincidence
            if first.endswith(second[:k]) and _seam_ok(first, second, k):
                probes.append(first + second[k:])
    for s in probes:
        if not contains(canonicalize(s, syn), cover_c):
            return s
    return None


def _seam_ok(first, second, k):
    """The overlap must not cut an ASCII word in half on either side (nobody writes `algorithmic ar|t|oken`)."""
    def word(ch):
        return bool(ch) and re.fullmatch(r"[A-Za-z0-9_]", ch) is not None
    seg = second[:k]
    left = first[-k - 1] if len(first) > k else ""
    right = second[k] if len(second) > k else ""
    return not (word(left) and word(seg[0])) and not (word(seg[-1]) and word(right))


def check_alias_overlap(root, skills, syn):
    """When an alias from synonyms.md and a skill's cover word abut in a sentence, folding
    replaces the alias first and bites off part of the cover word, so that sentence can never
    hit the cover word again. Point it out so the author changes one of them."""
    issues = []
    aliases = sorted(a for a, c in syn.items() if a != c)
    for d in sorted(skills):
        covers, _ = parse_desc(skills[d].meta.get("description", ""))
        for cover in sorted(c.lower() for c in covers):
            for alias in aliases:
                if syn[alias] == syn.get(cover, cover):
                    continue
                probe = _swallowed(alias, cover, syn)
                if probe:
                    issues.append(f"[W] synonyms.md: alias '{alias}' (folds to {syn[alias]}) overlaps {rel(root, d)}'s "
                                  f"cover word '{cover}' in a sentence: \"{probe}\" folds to \"{canonicalize(probe, syn)}\" "
                                  f"and cover word '{cover}' is gone")
    return issues


def check_excludes_reach(root, skills, syn):
    """Two kinds of `excludes` word. A word that some other skill covers sends the
    sentence to that skill: a *redirect*. A word no skill covers only stops this
    skill from taking the sentence: a *refusal*. Both are legitimate. A refusal is
    reported as a hint because it is the less common intent and is often a redirect
    whose target was renamed, retired or never written; the reader decides."""
    issues = []
    all_covers = {}
    for d, sk in skills.items():
        covers, _ = parse_desc(sk.meta.get("description", ""))
        for c in covers:
            all_covers.setdefault(canonicalize(c, syn), set()).add(d)
    for d, sk in sorted(skills.items()):
        _, excl = parse_desc(sk.meta.get("description", ""))
        for e in sorted(excl):
            ec = canonicalize(e, syn)
            owners = {o for c, os_ in all_covers.items() for o in os_ if contains(c, ec) or contains(ec, c)}
            owners.discard(d)
            if not owners:
                issues.append(f"[·] {rel(root, d)}: excludes '{e}' is a refusal (no skill covers that word), "
                              "not a redirect -- fine if the library has no skill for it; if one was meant, name its cover word")
    return issues


def check_alias_covers(root, skills, syn):
    """A cover word that is itself an alias is replaced by the canonical word before matching,
    so it takes far more than the author thinks."""
    issues = []
    for d in sorted(skills):
        if d == root:
            continue
        for c, canon in alias_covers(skills[d].meta, syn):
            issues.append(f"[W] {rel(root, d)}: cover word '{c}' is an alias of '{canon}' in synonyms.md and becomes '{canon}' "
                          f"before matching -- every sentence containing '{canon}' will hit this skill. To take that much, "
                          f"write '{canon}' directly; otherwise pick a word that is not in a synonym group")
    return issues


def check_absorb(root, counter):
    f = root / ABSORB_FILE
    if not f.is_file():
        return []
    issues, cur, has_line, seen = [], None, False, {}
    for line in f.read_text(encoding="utf-8").splitlines() + ["## @0 end"]:
        if line.startswith("## "):
            if cur and not has_line:
                issues.append(f"[W] {ABSORB_FILE}: '{cur}' should contain at least one learned:/merged:/ruled: line")
            cur, has_line = line.rstrip(), False
            m = re.match(r"## @(\d+) \S", cur)
            if cur == "## @0 end":
                break
            if not m:
                issues.append(f"[W] {ABSORB_FILE}: section heading should be '## @<count> <source name>', got: {cur}")
            else:
                n = int(m.group(1))
                if counter is not None and n > counter:
                    issues.append(f"[W] {ABSORB_FILE}: @{n} is ahead of the root archive_count {counter}")
                if n in seen:
                    issues.append(f"[W] {ABSORB_FILE}: @{n} is used twice ('{seen[n]}' and '{cur}'); "
                                  "each absorption has its own number -- run `counter --bump` before each")
                seen[n] = cur
        elif cur and ABSORB_LINE_RE.match(line.strip()):
            has_line = True
    return issues


def absorb_heads(root):
    """Set of section numbers {N,...} that appear in ABSORB.md."""
    f = root / ABSORB_FILE
    if not f.is_file():
        return set()
    return {int(m.group(1)) for m in re.finditer(r"^## @(\d+) \S", f.read_text(encoding="utf-8"), re.M)}


def check_retired(root):
    issues = []
    base = root / RETIRED_DIR
    if not base.is_dir():
        return issues
    heads = absorb_heads(root)
    for f in sorted(base.rglob("SKILL.md")):
        first = f.read_text(encoding="utf-8").split("\n", 1)[0]
        m = RETIRED_HEAD_RE.match(first)
        if not m:
            issues.append(f"[W] {rel(root, f.parent)}: first line should be 'retired @<count> <reason>'")
        elif int(m.group(1)) not in heads:
            issues.append(f"[·] {rel(root, f.parent)}: header says @{m.group(1)} but {ABSORB_FILE} has no "
                          f"'## @{m.group(1)}' section -- a card retired in one absorption and that absorption's "
                          "section heading should carry the same number")
    return issues


def count_retired(root):
    """How many cards (SKILL.md files) sit in .retired/. They are outside the tree and easy to forget."""
    d = root / RETIRED_DIR
    return sum(1 for _ in d.rglob("SKILL.md")) if d.is_dir() else 0


def cmd_lint(root):
    skills, errors = find_skills(root)
    issues = [f"[E] {e}" for e in errors]
    issues += check_root_files(root, skills)
    for d, sk in skills.items():
        r = rel(root, d)
        kids = children_of(d, skills)
        issues += check_frontmatter(r, sk)
        issues += check_groups(r, d)
        issues += check_description(r, d, root, sk)
        if d != root:
            issues += check_triggers(r, sk, skills, root)
        issues += check_file_refs(r, d, root, sk)
        issues += hints_for(r, d, root, sk, kids)
    for line in issues:
        print(line)
    errs = sum(1 for i in issues if i.startswith("[E]"))
    hints = sum(1 for i in issues if i.startswith("[·]"))
    warns = len(issues) - errs - hints
    tail = f", {hints} hints" if hints else ""
    retired = count_retired(root)
    rt = f", {retired} retired" if retired else ""
    print(f"\nlint: {errs} errors, {warns} warnings{tail}, {len(skills)} skills{rt}")
    print(body_summary(root, skills))
    return 1 if errs else 0


def body_summary(root, skills):
    """One line on how evenly the work is cut: body lines of every skill but the root, smallest,
    median, largest, and how many are past MAX_BODY. This is the number rules 1 to 3 exist to
    keep small; it is printed so that it is looked at, not so that any value of it fails."""
    lines = sorted(body_lines(sk) for d, sk in skills.items() if d != root)
    if not lines:
        return "bodies: none"
    mid = lines[len(lines) // 2] if len(lines) % 2 else (lines[len(lines) // 2 - 1] + lines[len(lines) // 2]) // 2
    over = sum(1 for n in lines if n > MAX_BODY)
    return (f"bodies: {len(lines)} skills, {lines[0]} to {lines[-1]} non-blank lines, median {mid}, "
            f"{over} over {MAX_BODY}")


# ---------------- overlap ----------------

def tokenize(desc, syn):
    """Each cover phrase is one token, folded to its canonical form (so `dark mode` and
    `dark theme` count as one word, and multi-word phrases are never split)."""
    covers, _ = parse_desc(desc)
    return {normalize(c, syn) for c in covers}


def cmd_overlap(root, threshold=OVERLAP):
    skills, errors = find_skills(root)
    if errors:
        print("\n".join("[E] " + error for error in errors))
        return 1
    syn = load_synonyms(root)
    hits = 0
    for parent in sorted({d.parent for d in skills if d != root}):
        sibs = children_of(parent, skills)
        for i in range(len(sibs)):
            for j in range(i + 1, len(sibs)):
                a, b = sibs[i], sibs[j]
                ta = tokenize(skills[a].meta.get("description", ""), syn)
                tb = tokenize(skills[b].meta.get("description", ""), syn)
                if not ta or not tb:
                    continue
                jac = len(ta & tb) / len(ta | tb)
                if jac > threshold:
                    hits += 1
                    print(f"[OVERLAP j={jac:.2f}] {rel(root, a)} x {rel(root, b)}")
                    print(f"    shared words: {sorted(ta & tb)} -> suspected duplicate; cross-replay both "
                          "skills' triggers to see who really takes them")
    print(f"\noverlap: {hits} pair(s) above threshold {threshold}")
    return 0


# ---------------- replay ----------------

def replay_skill(d, sk, root, skills, syn):
    """Replay every trigger of one skill. Returns (total, failures, notes)."""
    fails, notes = [], []
    trig = sk.meta.get("triggers")
    if not isinstance(trig, list):
        return 0, fails, notes
    r = rel(root, d)
    for t in trig:
        anti = split_anti(t)
        if anti:
            sent, target = anti
            if (root / target) not in skills:
                fails.append(f"[FAIL negative target missing] {r}: \"{sent}\" {ANTI_KEYWORD} {target}, "
                             "but that skill is not in the library")
                continue
            path = route(sent, root, skills, syn)
            if still_reachable(d, path):
                how = ("one of the ambiguity candidates (or their ancestor)" if isinstance(path[-1], tuple)
                       else "the route's end point")
                fails.append(f"[FAIL negative hit] {r}: \"{sent}\" -- this skill is {how}")
            elif (root / target) not in touched_nodes(path):
                last = path[-1]
                got = ("ambiguous " + str([str(rel(root, h)) for h in last[1]])
                       if isinstance(last, tuple) else where(root, last))
                why = ""
                if not isinstance(last, tuple):
                    why = why_stopped(root / target, path, canonicalize(sent, syn), root, skills, syn,
                                      who=f"target {target}")
                notes.append(f"[NOTE negative did not reach its target] {r}: \"{sent}\" is declared to go to {target}, "
                             f"but lexical routing lands on {got} -- most likely synonyms.md or the target's cover "
                             f"words lack the wording used in this sentence{why}")
        else:
            path = route(t, root, skills, syn)
            last = path[-1]
            if isinstance(last, tuple):
                hits = ", ".join(str(rel(root, h)) for h in last[1])
                fails.append(f"[FAIL ambiguous] {r}: \"{t}\" is taken by {len(last[1])} top-level skills at once "
                             f"[{hits}] -> suspected duplicate, or a missing 'excludes'")
            elif last != d:
                msg = f"[FAIL not reached] {r}: \"{t}\" lands on {where(root, last)}"
                if d in last.parents:
                    canon = canonicalize(t, syn)
                    shy = [(k, blocked_by(canon, skills[k].meta, syn))
                           for k in children_of(d, skills) if k != last]
                    shy = [(k, ex) for k, ex in shy if ex]
                    if shy:
                        who = "; ".join(f"sibling {rel(root, k)}'s cover words also take this sentence, but its own "
                                        f"'excludes {','.join(ex)}' blocks it" for k, ex in shy)
                        msg += (f" ({who} -> this sentence should span two children and stop at the parent; "
                                "'excludes' is for separating siblings that compete for the same sentence, "
                                "not for blocking sentences that span children)")
                    else:
                        msg += (f" (only child {rel(root, last)} took this sentence, so routing descended into it -> "
                                f"a parent's positive example must contain cover words of two or more children; "
                                f"this one only has {rel(root, last)}'s -- if the child is new, this sentence is now its job: "
                                f"move it to the child's triggers and give the parent one that spans two children)")
                elif last in d.parents:
                    canon = canonicalize(t, syn)
                    sibs = ([k for k in hits_under(last, canon, skills, syn) if k != d]
                            if last == d.parent else [])
                    if sibs:
                        who = "; ".join(f"sibling {rel(root, k)} also takes this sentence, via its cover word "
                                        f"{hit_text(canon, k, root, skills, syn)}" for k in sibs)
                        who_sib = rel(root, sibs[0]) if len(sibs) == 1 else "it"
                        msg += f" ({who} -> either a real duplicate, or add an 'excludes' to {who_sib})"
                    else:
                        msg += why_stopped(d, path, canon, root, skills, syn)
                fails.append(msg)
    return len(trig), fails, notes


def cmd_replay(root):
    skills, errors = find_skills(root)
    if errors:
        print("\n".join("[E] " + error for error in errors))
        return 1
    syn = load_synonyms(root)
    total, all_fails, all_notes = 0, [], []
    for d, sk in sorted(skills.items()):
        if d == root:
            continue
        n, fails, notes = replay_skill(d, sk, root, skills, syn)
        total += n
        all_fails += fails
        all_notes += notes
    for line in all_fails + all_notes:
        print(line)
    print(f"\nreplay: {total - len(all_fails)}/{total} passed"
          + (f", {len(all_notes)} note(s)" if all_notes else ""))
    return 1 if all_fails else 0


# ---------------- route: where does this sentence land ----------------

def cmd_route(root, sentence):
    """Walk one sentence down from the root, one line per gate: who takes it and by which cover
    word; children whose cover words would take it but whose own 'excludes' blocks them are named too."""
    skills, errors = find_skills(root)
    if errors:
        print("\n".join("[E] " + error for error in errors))
        return 1
    syn = load_synonyms(root)
    canon = canonicalize(sentence, syn)
    print(f"sentence: \"{sentence}\"")
    if canon != sentence.lower():
        print(f"folded: \"{canon}\" (aliases replaced by their canonical words per synonyms.md, then matched case-insensitively)")
    cur = root
    path = [root]
    while True:
        kids = children_of(cur, skills)
        name = "root" if cur == root else str(rel(root, cur))
        if not kids:
            print(f"{name} -> no sub-skills")
            break
        hits = hits_under(cur, canon, skills, syn)
        shy = [(k, blocked_by(canon, skills[k].meta, syn)) for k in kids if k not in hits]
        shy = [(k, ex) for k, ex in shy if ex]
        got = ", ".join(f"{rel(root, k)} (via {hit_text(canon, k, root, skills, syn)})" for k in hits) or "(none)"
        line = f"{name} -> taken by: {got}"
        if shy:
            line += "; " + "; ".join(f"{rel(root, k)} would take it but is blocked by its own 'excludes {','.join(ex)}'"
                                     for k, ex in shy)
        if len(hits) > 1 and cur != root:
            line += f" -> two or more children take it; a sentence spanning children is the parent's job, stop at {name}"
        print(line)
        if len(hits) == 1:
            cur = hits[0]
            path.append(cur)
        elif len(hits) > 1 and cur == root:
            names = ", ".join(str(rel(root, h)) for h in hits)
            print(f"lands on: ambiguous, {len(hits)} top-level skills take it at once [{names}] "
                  "(the root is not a skill, nobody can take it -> suspected duplicate, or a missing 'excludes')")
            return 0
        else:
            break
    print(f"lands on: {where(root, cur)}")
    read = sum((d / ns.SKILL_FILE).stat().st_size for d in path)
    total = sum((d / ns.SKILL_FILE).stat().st_size for d in skills)
    print(f"read: {len(path)} file(s), {read:,} bytes of {total:,} in the library ({100 * read // max(total, 1)}%)")
    return 0


# ---------------- retire: nothing is really deleted ----------------

def cmd_retire(root, target, reason):
    src = (root / target.strip("/")).resolve()
    if src == root.resolve() or not (src / "SKILL.md").is_file() or root.resolve() not in src.parents:
        print(f"error: '{target}' is not a skill in this library (the root cannot be retired)", file=sys.stderr)
        return 1
    if not reason or not reason.strip():
        print("error: --reason is required; it is written into the file header", file=sys.stderr)
        return 1
    counter = read_counter(root) or 0
    relp = src.relative_to(root.resolve())
    dst = root / RETIRED_DIR / relp
    if not ns.path_within(dst, root) or ns.path_within(dst, src):
        print("error: retirement destination must stay inside the library", file=sys.stderr)
        return 1
    try:
        ns._check_copy_source(str(src))
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if dst.exists():
        n = 2
        while (dst.parent / f"{dst.name}~{n}").exists():
            n += 1
        dst = dst.parent / f"{dst.name}~{n}"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    for f in dst.rglob("SKILL.md"):
        text = f"retired @{counter} {reason.strip()}\n" + f.read_text(encoding="utf-8")
        with f.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
    ns.main(["sync", str(root)])
    print(f"moved to {rel(root, dst)}, first line 'retired @{counter} {reason.strip()}' "
          f"(this absorption's section heading in {ABSORB_FILE} should also be @{counter}; if you have not bumped yet, "
          "run counter --bump before retire); parent routing table re-synced")
    return 0


# ---------------- ask: look before you act ----------------

def checklist_section():
    """Cut the checklist section out of the rulebook verbatim (from its heading to the next ##).
    Returns None if it cannot be found."""
    if not RULES_FILE.is_file():
        return None
    text = RULES_FILE.read_text(encoding="utf-8")
    start = text.find(CHECKLIST_HEAD)
    if start < 0:
        return None
    end = text.find("\n## ", start + 1)
    return text[start:end if end > 0 else len(text)].rstrip()


def ruling_lines(root):
    """Every `ruled:` line in the library's ABSORB.md, with the heading of its section."""
    f = root / ABSORB_FILE
    if not f.is_file():
        return []
    out, cur = [], None
    for line in f.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            cur = line[3:].strip()
        elif cur and RULED_RE.match(line.strip()):
            out.append((cur, line.strip()))
    return out


def cmd_ask(root):
    sec = checklist_section()
    if sec is None:
        print(f"error: section '{CHECKLIST_HEAD}' not found in {RULES_FILE} -- has the rulebook been edited?",
              file=sys.stderr)
        return 1
    print(sec)
    print()
    rulings = ruling_lines(root)
    if not rulings:
        print(f"This library has no ruled: lines yet ({ABSORB_FILE} records no owner rulings). "
              "Answer the four questions and go ahead.")
        return 0
    print(f"This library has {len(rulings)} ruling(s); do not re-judge the same matter ({ABSORB_FILE}):")
    last = None
    for head, line in rulings:
        if head != last:
            print(f"  {head}")
            last = head
        print(f"    {line}")
    return 0


# ---------------- feedback / counter ----------------

def cmd_feedback(root):
    f = root / FEEDBACK_FILE
    if not f.exists():
        print(f"(no {FEEDBACK_FILE})")
        return 0
    pending = [l for l in f.read_text(encoding="utf-8").splitlines()
               if l.strip() and not l.lstrip().startswith(("#", ">"))
               and not l.rstrip().endswith(" done")]
    for l in pending:
        print(l)
    print(f"\nfeedback: {len(pending)} line(s) pending (process them before absorbing)")
    return 0


def read_counter(root):
    f = root / "SKILL.md"
    if not f.is_file():
        return None
    meta, _, _ = parse_frontmatter(f.read_text(encoding="utf-8"))
    try:
        return int(str(meta.get("archive_count", "0")).strip() or 0)
    except ValueError:
        return 0


def cmd_counter(root, bump=False):
    f = root / "SKILL.md"
    if not ns.path_within(f, root):
        print("error: root SKILL.md points outside the library", file=sys.stderr)
        return 1
    if not f.is_file():
        print(f"error: no root SKILL.md under {root}; the counter lives in the root skill's frontmatter", file=sys.stderr)
        return 1
    text = f.read_text(encoding="utf-8")
    meta, _, err = parse_frontmatter(text)
    if err:
        print(f"error: root SKILL.md frontmatter parse error: {err}", file=sys.stderr)
        return 1
    raw = str(meta.get("archive_count", "0")).strip()
    if not raw.isascii() or not raw.isdigit():
        print("error: archive_count must be a non-negative integer", file=sys.stderr)
        return 1
    old = n = int(raw)
    if bump:
        n += 1
        text = write_counter(text, n)
        with f.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        print(f"archive_count: {old} -> {n}")
    else:
        print(f"archive_count: {n}")
    return 0


def write_counter(text, n):
    """Set the counter in the spec form, `metadata.holon-archive-count`. A top-level
    `archive_count:` (pre-spec form) is replaced in place so the file gets no second copy."""
    lines = text.splitlines(keepends=True)
    end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    header = "".join(lines[1:end])
    header = re.sub(r"^archive_count:[^\r\n]*\r?\n", "", header, count=1, flags=re.M)
    key = ns.ARCHIVE_META
    pattern = r"^([ \t]+%s:[ \t]*)[^\r\n]*" % re.escape(key)
    header, changed = re.subn(pattern, lambda m: f'{m.group(1)}"{n}"', header, count=1, flags=re.M)
    if not changed:
        line = f'  {key}: "{n}"\n'
        m = re.search(r"^metadata:[ \t]*\r?\n", header, re.M)
        if m:
            header = header[:m.end()] + line + header[m.end():]
        else:
            header += "metadata:\n" + line
    return lines[0] + header + "".join(lines[end:])


def main(argv=None):
    ns._tolerate_console_encoding()   # same reason as in holon.py: [·] hints must not crash a cp1252 console
    ap = argparse.ArgumentParser(prog="organizer", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["lint", "replay", "route", "overlap", "retire", "feedback", "counter", "ask"])
    ap.add_argument("root", type=Path)
    ap.add_argument("target", nargs="?", help="retire: skill path to move (relative to root); route: the sentence to try")
    ap.add_argument("--reason", help="retire: reason, written into the first line of the file")
    ap.add_argument("--bump", action="store_true", help="counter: increment by 1")
    ap.add_argument("--threshold", type=float, default=OVERLAP,
                    help=f"overlap: Jaccard threshold (default OVERLAP={OVERLAP})")
    a = ap.parse_args(argv)
    if not a.root.is_dir():
        print(f"error: {a.root} is not a directory", file=sys.stderr)
        return 2
    a.root = a.root.resolve()   # Path('.').parent == Path('.'); unresolved, the root would be its own child
    if a.command == "overlap" and not 0 <= a.threshold <= 1:
        print("error: --threshold must be between 0 and 1", file=sys.stderr)
        return 2
    if a.command == "retire" and not a.target:
        print("error: retire needs a skill path", file=sys.stderr)
        return 2
    if a.command == "route" and not a.target:
        print('error: route needs a sentence, e.g. route <root> "convert this report to PDF"', file=sys.stderr)
        return 2
    fn = {"lint": lambda: cmd_lint(a.root),
          "replay": lambda: cmd_replay(a.root),
          "route": lambda: cmd_route(a.root, a.target),
          "overlap": lambda: cmd_overlap(a.root, a.threshold),
          "retire": lambda: cmd_retire(a.root, a.target, a.reason),
          "feedback": lambda: cmd_feedback(a.root),
          "counter": lambda: cmd_counter(a.root, a.bump),
          "ask": lambda: cmd_ask(a.root)}[a.command]
    try:
        return fn()
    except (OSError, UnicodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
