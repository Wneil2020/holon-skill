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
  ask      <root> [--grep RE] [--since N] [--current]
                                        Print the checklist section of organizer/SKILL.md verbatim plus the
                                        `ruled:` lines in the library's ABSORB.md (all, or the filtered ones)
  replay   <root> --probes FILE         Also route outside sentences (`sentence<TAB>expected`) and score them
                                        separately; the score never changes the exit code
  feedback <root> --stats               Count _feedback.md lines by outcome (miss/wrong/multi/fallback/ok) and skill
  retire   <root> <dir/references/x.md> --reason R
                                        Retire a single knowledge file the same way a card is retired

Frontmatter parsing and the definition of "what counts as a skill" are
imported from the mechanism layer, scripts/holon.py.
"""
import argparse
import functools
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
EXCLUDES_MAX = 5     # more excludes words than this -> hint: the skill is being defined by what it refuses
STEP_WORDS = 120     # a numbered step longer than this many words -> hint: several steps, or knowledge, in one
REF_BUDGET = 12000   # ~tokens of references/ files one skill's steps name; above it -> hint
PROBE_AFTER = 10     # after this many absorptions with no outside probe result recorded -> warning
# The values this package ships with. lint names any parameter a library has changed, so a
# changed rulebook is visible in every lint run instead of only in a diff of this file.
SHIPPED = {"COVER_MAX": 5, "DESC_MAX": 200, "MAX_BODY": 150, "FANOUT": 9, "OVERLAP": 0.4, "COVER_MIN": 2,
           "EXCLUDES_MAX": 5, "STEP_WORDS": 120, "REF_BUDGET": 12000, "PROBE_AFTER": 10}
# ---- Fixed internal thresholds (not rules; they only decide when a hint appears) ----
SHORT_BODY = 5       # body shorter than this -> "very short" hint
HOLLOW_BODY = 3      # parent body at most this long with exactly one child -> "hollow" hint
STALE_DAYS = 365     # a references/ file verified longer ago than this, with no review-after date -> hint
PROBES_FILE = "probes.tsv"   # sentences someone other than the skill authors wrote, with where each should land
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
# Lines an absorption section may carry beyond the three above. lint reads them; none is required
# in an old section, so a library written before they existed needs no migration.
#   for:      the task sentence, _feedback.md line or owner request this absorption serves, or `no-demand`
#   source:   where the newcomer came from (repository, URL, document)
#   repeat:   why a source absorbed before is absorbed again
#   probe:    the outside probe score after the change, `x/y` (from `replay --probes`)
#   evidence: structural | route x/y | task <what was run and what it showed>
#   supersedes: @n.k -- a ruling of an earlier section that this section replaces
EXTRA_LINE_RE = re.compile(r"(for|source|repeat|probe|evidence|supersedes):\s*(.*)$")
FEEDBACK_OUTCOMES = ("miss", "wrong", "multi", "fallback", "ok")
EVIDENCE_LEVELS = ("structural", "route", "task")
RULED_RE = re.compile(r"ruled:")
WORD_SPLIT = r"[,\uff0c\u3001/]"   # comma, full-width comma, ideographic comma, slash
ROOT_LABEL = "root (nobody took it)"

Skill = namedtuple("Skill", "meta body err")


class SkillMap(dict):
    """The skills of ONE load (find_skills), keyed by directory. It carries an index that
    replay and route reuse for every sentence: each directory's child skills and the cover
    words of every skill below it. The index is built on first use from this object's own
    entries and dropped whenever an entry changes, so it never outlives the load or describes
    another tree. A plain dict passed in by a caller gets the same answers, computed per call."""

    _index = None

    def index(self):
        if self._index is None:
            kids, below = {}, {}
            for k in sorted(self):
                kids.setdefault(k.parent, []).append(k)
                covers, _ = parse_desc(self[k].meta.get("description", ""))
                words = [(c, k) for c in sorted(covers, key=str.lower)]
                for p in k.parents:
                    below.setdefault(p, []).extend(words)
            self._index = (kids, below)
        return self._index

    def __setitem__(self, key, value):
        self._index = None
        super().__setitem__(key, value)

    def __delitem__(self, key):
        self._index = None
        super().__delitem__(key)

    def clear(self):
        self._index = None
        super().clear()

    def pop(self, *args):
        self._index = None
        return super().pop(*args)

    def popitem(self):
        self._index = None
        return super().popitem()

    def setdefault(self, *args):
        self._index = None
        return super().setdefault(*args)

    def update(self, *args, **kwargs):
        self._index = None
        super().update(*args, **kwargs)


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


# Unbounded on purpose: a cache of 4,096 entries thrashed once a library had more distinct
# cover words than that, and lint went from seconds to minutes.
@functools.lru_cache(maxsize=None)
def _clauses(desc):
    """description_clauses for one description string (a pure function of the string)."""
    covers, excludes, _ = ns.description_clauses(desc)
    return tuple(covers), tuple(excludes)


def parse_desc(desc):
    """Three-part description -> (set of cover words, set of exclude words). New sets every call."""
    if isinstance(desc, str):
        covers, excludes = _clauses(desc)
    else:
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
    out = SkillMap()
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
    if isinstance(skills, SkillMap):
        return list(skills.index()[0].get(d, ()))
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

@functools.lru_cache(maxsize=None)
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
    if re.fullmatch(r"[A-Za-z0-9_.\- ]+", w) and " " in w:
        # A multi-word alias is matched as one phrase, but the word boundary belongs to
        # its first and its last word: "author ids" must not match inside "author idsX",
        # where the trailing "s" is the first letter of the next word.
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
    big = _fold_pattern(frozenset(syn.items()))
    return _fold_padded(s, big, syn)


_WORDCH = set("abcdefghijklmnopqrstuvwxyz0123456789_")


def _fold_padded(s, big, table):
    """Replace every alias with its canonical form, keeping a word boundary on each side.

    Without padding, a canonical form written where a CJK alias stood is glued to its
    neighbour: with `papers, 找文献`, "找文献pdf" became "paperspdf", one word, so neither
    the cover word `papers` nor `pdf` (nor a sibling's `excludes pdf`) matched and the
    sentence fell through to the root. Two neighbouring aliases glued the same way
    ("按相关度排个序" -> "sortsort"). A space is put between the canonical form and any
    word character it would touch, on the left by looking at what has already been
    written (so two replacements in a row are separated too), on the right by looking at
    the next character of the input. One pass; cover words go through the same function,
    so a sentence and a cover word are always folded alike."""
    out = []
    pos = 0
    for m in big.finditer(s):
        out.append(s[pos:m.start()])
        canon = table.get(m.group(0).lower(), m.group(0))
        prev = out[-1][-1:] if out and out[-1] else ""
        if not prev:
            prev = next((piece[-1] for piece in reversed(out) if piece), "")
        if prev in _WORDCH and canon[:1] in _WORDCH:
            out.append(" ")
        out.append(canon)
        if m.end() < len(s) and s[m.end()] in _WORDCH and canon[-1:] in _WORDCH:
            out.append(" ")
        pos = m.end()
    out.append(s[pos:])
    return "".join(out)


@functools.lru_cache(maxsize=64)
def _fold_pattern(items):
    """The one regex canonicalize scans with, for one exact synonyms table (keyed by its
    content, so an edited table gets a new regex)."""
    words = {a for a, _ in items} | {c for _, c in items}
    return re.compile("|".join(_piece(w) for w in sorted(words, key=len, reverse=True)), re.I)


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
    if isinstance(skills, SkillMap):
        return list(skills.index()[1].get(d, ()))
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


def _hit_words(d, sentence_canon, skills, syn):
    """The canonical cover words of d (own or inherited) that the sentence hits."""
    words = set(parse_desc(skills[d].meta.get("description", ""))[0])
    words |= {c for c, _ in inherited_covers(d, skills)}
    return frozenset(canonicalize(w, syn) for w in words if contains(sentence_canon, canonicalize(w, syn)))


def _ranked(hits, sentence_canon, skills, syn):
    """Several hit children, best first: most hit cover words, then their total length, then name."""
    hs = {h: _hit_words(h, sentence_canon, skills, syn) for h in hits}
    return sorted(hits, key=lambda h: (-len(hs[h]), -sum(len(w) for w in hs[h]), str(h)))


def _descend(cur, sentence_canon, skills, syn, pick):
    """Greedy single-route walk from cur down (used by route and by each root-beam start)."""
    path = [cur]
    while True:
        hits = hits_under(cur, sentence_canon, skills, syn)
        if pick and len(hits) > 1:
            hits = _ranked(hits, sentence_canon, skills, syn)[:1]
        if len(hits) == 1:
            cur = hits[0]
            path.append(cur)
        elif len(hits) > 1 and cur == path[0]:
            return path + [("AMBIG", hits)]
        else:
            return path


def route(sentence, root, skills, syn, pick=False, beam=2):
    """Lexical descent. Returns the path as a list.
    Several children hit at one level: if that level is a skill (a parent), a sentence that
    spans two of its children is the parent's own step -- stop at the parent. If that level
    is the root (the root is not a skill; nobody can take it), it is an ambiguity and the
    last item is ("AMBIG", [hit nodes...]).
    pick=True never stops on several hits: it takes the best by _ranked (for a landing point,
    not for review). beam=k with pick also tries the k best root children and keeps the path
    with the most hit cover words; most misses go wrong at the first hop. The default keeps
    the strict contract replay and lint use to surface overlapping cover words."""
    sentence_canon = canonicalize(sentence, syn)
    if not (pick and beam > 1):
        return _descend(root, sentence_canon, skills, syn, pick)
    hits = hits_under(root, sentence_canon, skills, syn)
    if len(hits) <= 1:
        return _descend(root, sentence_canon, skills, syn, pick)
    paths = [[root] + _descend(h, sentence_canon, skills, syn, True)
             for h in _ranked(hits, sentence_canon, skills, syn)[:beam]]
    return max(paths, key=lambda p: (sum(len(_hit_words(d, sentence_canon, skills, syn)) for d in p[1:]), str(p[-1])))


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


# Folders a skill keeps its own files in. A path into one of them names an input, never an output.
SKILL_FILE_DIRS = frozenset({"references", "reference", "scripts", "assets", "templates", "shared"})


def check_file_refs(r, d, root, sk):
    """A body that names a file path in backticks, alone or inside a command, is telling the
    agent to open or run it. If the file is not where the path says, relative to this skill
    or to the tree root, the step cannot be followed. A bare filename with no directory is
    not checked: it may be an output the step writes. Globs and placeholders are skipped.

    Three outcomes for a path that is not there:
    - the file exists under an ancestor skill: the text was cut from that ancestor and the
      path was not rewritten (the evals/ case in design-notes section 19) -- a warning that
      names where the file is;
    - the path starts in a folder a skill keeps its own files in (references/, scripts/,
      assets/, templates/, shared/), or in a folder that exists, or climbs with ../: the
      file is missing -- a warning;
    - any other first folder that exists nowhere: most likely an output the step creates
      (`evals/evals.json`) -- a hint, so a real output does not leave a standing warning."""
    issues = []
    seen = set()
    ancestors = []
    cur = d
    while cur != root and root in cur.parents:
        cur = cur.parent
        ancestors.append(cur)
    for span in re.finditer(r"`[^`\n]+`", sk.body):
        for m in PATH_IN_TICKS.finditer(span.group(0)):
            ref = m.group(1)
            if ref in seen or "*" in ref or "{" in ref:
                continue
            seen.add(ref)
            if (d / ref).exists() or (root / ref).exists():
                continue   # relative to the skill, or written as "at the tree root"
            owner = next((a for a in ancestors if a != root and (a / ref).exists()), None)
            if owner is not None:
                issues.append(f"[W] {r}: body points at `{ref}`, which exists under {owner.relative_to(root).as_posix()}/ "
                              f"and not under {r}/ -- the text was probably moved from there; write the path "
                              "relative to this skill, or move the file with it")
                continue
            first = ref.split("/", 1)[0]
            if first in (".", "..") or first in SKILL_FILE_DIRS or (d / first).exists() or (root / first).exists():
                issues.append(f"[W] {r}: body points at `{ref}` and there is no such file under {r}/ or at the tree root -- "
                              "the step that names it cannot be followed; add the file or fix the path")
            else:
                issues.append(f"[·] {r}: body names `{ref}`, and no `{first}/` exists under {r}/ or at the tree root -- "
                              "fine if the step creates it; otherwise add the file or fix the path")
    return issues


# ---------------- knowledge: references/ files ----------------
#
# A step names the files it needs; that is how knowledge is reached (organizer rule 2). The
# checks below treat references/ as part of the library rather than as an attic: a file no
# step and no other file names is never opened; a file can say where it came from and when
# it was last checked; the files one skill's steps name are what an agent following that
# skill reads, so their size is the real cost of the skill.

REF_HEADER_RE = re.compile(r"^\s*(?:[-*>]\s*|<!--\s*)?(source|verified|review-after|applies-when|supersedes)\s*:\s*(.*?)\s*(?:-->)?\s*$",
                           re.I)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MD_LINK = re.compile(r"\]\(([^)\s#]+\.md)(?:#[^)]*)?\)")


def reference_files(root, skills):
    """Every Markdown file under a references/ (or reference/) folder of a skill in this tree,
    as {path: owning skill dir}. Files in sub-skill folders belong to the sub-skill."""
    out = {}
    for d in skills:
        for name in ("references", "reference"):
            base = d / name
            if base.is_dir():
                for f in sorted(base.rglob("*.md")):
                    if RETIRED_DIR not in f.relative_to(root).parts:
                        out[f] = d
    return out


def reference_header(path):
    """The optional header of a references/ file: `source:`, `verified:`, `review-after:`,
    `applies-when:`, `supersedes:` lines among the first twelve lines (plain, as a list item,
    in a quote or in an HTML comment). Returns {field: value} with lower-case keys."""
    out = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[:12]
    except (OSError, UnicodeError):
        return out
    for line in lines:
        m = REF_HEADER_RE.match(line)
        if m and m.group(1).lower() not in out:
            out[m.group(1).lower()] = m.group(2).strip()
    return out


def named_paths(text):
    """Paths a document names: in backticks (as check_file_refs reads them) and as Markdown links."""
    found = []
    for span in re.finditer(r"`[^`\n]+`", text):
        found += [m.group(1) for m in PATH_IN_TICKS.finditer(span.group(0))]
    found += MD_LINK.findall(text)
    return [f for f in found if "*" not in f and "{" not in f and "://" not in f]


def resolve_named(ref, here, d, root):
    """Where a named path can point: next to the naming file, under its skill, under any
    ancestor skill, or at the tree root. Returns the existing resolved paths."""
    if ref.split("/", 1)[0] in (".", ".."):
        # An explicitly relative path means relative to the file that writes it, as in Markdown.
        c = here / ref
        return [c.resolve()] if c.is_file() else []
    cands = [here / ref, d / ref, root / ref]
    cur = d
    while cur != root and root in cur.parents:
        cur = cur.parent
        cands.append(cur / ref)
    out = []
    for c in cands:
        try:
            if c.is_file():
                out.append(c.resolve())
        except OSError:
            pass
    return out


def step_named_refs(d, sk, root, refs):
    """The references/ files that skill d's body names, resolved, as a set of paths."""
    resolved = {f.resolve(): f for f in refs}
    got = set()
    for ref in named_paths(sk.body):
        for c in resolve_named(ref, d, d, root):
            if c in resolved:
                got.add(resolved[c])
    return got


def check_references(root, skills, today=None):
    """Orphans, stale or malformed headers, broken pointers inside references/, identical
    copies, and the references/ cost of each skill's steps."""
    import datetime
    today = today or datetime.date.today()
    refs = reference_files(root, skills)
    resolved = {f.resolve(): f for f in refs}
    named_by = {f: set() for f in refs}
    issues = []
    # who names whom: skill bodies, then other references files
    for d, sk in skills.items():
        for f in step_named_refs(d, sk, root, refs):
            named_by[f].add(d)
    for f, d in refs.items():
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        links = set(MD_LINK.findall(text))
        for ref in named_paths(text):
            hits = resolve_named(ref, f.parent, d, root)
            for c in hits:
                if c in resolved and resolved[c] != f:
                    named_by[resolved[c]].add(f)
            # Inside a references file, prose often mentions paths of other libraries as examples.
            # Only a relative path (./ or ../) or a Markdown link is read as a pointer to follow.
            if not hits and (ref.split("/", 1)[0] in (".", "..") or ref in links):
                issues.append(f"[W] {rel(root, f)}: points at `{ref}`, which does not exist next to it, under "
                              f"{rel(root, d)}/ or any skill above it -- a reader who follows the pointer finds nothing")
    # orphans: a file nobody names is never opened. A file named only by other orphans is an orphan too.
    reach, todo = set(), [f for f, by in named_by.items() if any(isinstance(b, Path) and b in skills for b in by)]
    while todo:
        f = todo.pop()
        if f in reach:
            continue
        reach.add(f)
        todo += [g for g, by in named_by.items() if f in by and g not in reach]
    for f in sorted(refs):
        if f not in reach:
            issues.append(f"[W] {rel(root, f)}: no step names this file (nor any file a step names), so an agent "
                          f"following the skills never opens it -- name it in the step that needs it, or retire it "
                          f"(`retire <root> {rel(root, f)} --reason R`)")
    # headers
    for f in sorted(refs):
        h = reference_header(f)
        for key in ("verified", "review-after"):
            if key in h and not DATE_RE.match(h[key]):
                issues.append(f"[W] {rel(root, f)}: `{key}: {h[key]}` is not a date (YYYY-MM-DD)")
        if "review-after" in h and DATE_RE.match(h["review-after"]):
            if datetime.date.fromisoformat(h["review-after"]) < today:
                issues.append(f"[W] {rel(root, f)}: review-after {h['review-after']} has passed -- check the facts "
                              f"against `source:` and write a new `verified:` date, or retire the file")
        elif "verified" in h and DATE_RE.match(h["verified"]):
            age = (today - datetime.date.fromisoformat(h["verified"])).days
            if age > STALE_DAYS:
                issues.append(f"[·] {rel(root, f)}: verified {age} days ago and no review-after date -- "
                              "re-check it if it describes an outside API, tool or service")
        if ("verified" in h or "review-after" in h) and not h.get("source"):
            issues.append(f"[·] {rel(root, f)}: has a date but no `source:` -- a later reader cannot re-check it")
    # identical copies
    by_hash = {}
    for f in refs:
        try:
            body = re.sub(r"\s+", " ", f.read_text(encoding="utf-8")).strip()
        except (OSError, UnicodeError):
            continue
        if len(body) >= 200:
            by_hash.setdefault(hash(body), []).append(f)
    for fs in by_hash.values():
        if len(fs) > 1:
            names = ", ".join(str(rel(root, f)) for f in sorted(fs))
            issues.append(f"[W] identical references files: {names} -- keep one under the common parent and point to it")
    # the cost of each skill's steps
    for d, sk in sorted(skills.items()):
        files = step_named_refs(d, sk, root, refs)
        cost = sum(ns._tokens(f.read_text(encoding="utf-8", errors="replace")) for f in files)
        if cost > REF_BUDGET:
            issues.append(f"[·] {rel(root, d)}: its steps name {len(files)} references files, ~{cost:,} tokens "
                          f"> REF_BUDGET {REF_BUDGET:,} -- an agent that opens what the steps list reads all of it; "
                          "is some of it never needed by this job, or does one step name what only a later step needs?")
    return issues


def ref_cost(d, sk, root, refs):
    """~tokens of the references/ files skill d's body names."""
    return sum(ns._tokens(f.read_text(encoding="utf-8", errors="replace")) for f in step_named_refs(d, sk, root, refs))


# ---------------- steps ----------------

STEP_RE = re.compile(r"^(\d+)[.)]\s", re.M)


def _words(text):
    """Words, counting two CJK characters as one word (a rough cross-script measure)."""
    cjk = sum(1 for c in text if "\u3000" <= c <= "\u9fff" or "\uac00" <= c <= "\ud7af")
    return len(re.findall(r"[A-Za-z0-9_'`/.\-]+", text)) + cjk // 2


def numbered_steps(body):
    """The numbered steps of a body: a line starting `N.` or `N)` at column 0, up to the next blank
    line (the step's own paragraph), within the text before the sub-skills block."""
    body = body.split(ns.MARK_OPEN, 1)[0]
    starts = [m.start() for m in STEP_RE.finditer(body)]
    out = []
    for i, a in enumerate(starts):
        b = starts[i + 1] if i + 1 < len(starts) else len(body)
        # A step is its own paragraph: indented paragraphs and sub-lists after a blank line are
        # structure the writer already gave it. One long paragraph is what a line count misses.
        out.append(re.split(r"\n\s*\n", body[a:b], maxsplit=1)[0])
    return out


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
    steps = numbered_steps(sk.body)
    long_steps = [(i + 1, _words(t)) for i, t in enumerate(steps) if _words(t) > STEP_WORDS]
    if long_steps:
        worst = max(long_steps, key=lambda x: x[1])
        hints.append(f"[·] {r}: {len(long_steps)} numbered step(s) over STEP_WORDS {STEP_WORDS} words, the longest "
                     f"step {worst[0]} at {worst[1]} -- a long step is usually several steps, or a rule list that "
                     "belongs in references/ (line counts do not see this: one line can hold a page)")
    covers, excl = parse_desc(sk.meta.get("description", "") or "")
    if len(excl) > EXCLUDES_MAX or (len(excl) > 2 and len(excl) > 2 * max(len(covers), 1)):
        hints.append(f"[·] {r}: {len(excl)} excludes words against {len(covers)} cover words -- the skill is being "
                     "defined by what it refuses; every excludes word also removes a sentence the parent could take. "
                     "Is the boundary a result (keep it) or a noun shared with a sibling (drop it, or state it as the "
                     "deliverable in Use when ...)?")
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
    issues += check_dead_synonyms(root, skills, load_synonyms(root))
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


def check_dead_synonyms(root, skills, syn):
    """A synonym group folds sentences to its first word. If no skill's cover or excludes
    word contains that word after folding, the group can never change a route: the
    aliases were added for a skill that does not list the word, or the word was renamed."""
    words = set()
    for sk in skills.values():
        covers, excl = parse_desc(sk.meta.get("description", ""))
        words |= {canonicalize(w, syn) for w in covers | excl}
    issues = []
    for canon in sorted(set(syn.values())):
        if not any(contains(w, canon) for w in words):
            aliases = sorted(a for a, c in syn.items() if c == canon and a != canon)
            issues.append(f"[·] synonyms.md: group '{canon}' ({', '.join(aliases)}) reaches no skill -- no cover or "
                          f"excludes word contains '{canon}', so folding to it changes no route; list '{canon}' "
                          "in the skill the aliases were meant for, or drop the group")
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


def absorb_sections(root):
    """ABSORB.md as a list of sections: (number or None, heading, [stripped lines])."""
    f = root / ABSORB_FILE
    if not f.is_file():
        return []
    out = []
    for line in f.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            m = re.match(r"## @(\d+) \S", line)
            out.append((int(m.group(1)) if m else None, line[3:].strip(), []))
        elif out:
            out[-1][2].append(line.strip())
    return out


def section_extras(lines):
    """The extra lines of one section: {key: [values]} for for/source/repeat/probe/evidence/supersedes."""
    got = {}
    for l in lines:
        m = EXTRA_LINE_RE.match(l)
        if m:
            got.setdefault(m.group(1), []).append(m.group(2).strip())
    return got


def _source_key(value):
    """A source as a comparable key: lower case, no scheme, no trailing .git or slash."""
    v = value.strip().lower()
    v = re.sub(r"^(https?://)?(www\.)?(github\.com/)?", "", v)
    v = re.sub(r"(\.git)?/*$", "", v)
    return v.split()[0] if v.split() else v


def check_ledger(root, counter):
    """What the absorption ledger can show mechanically about demand, repeats and evidence.
    Every check here reads an optional line, so a ledger written before those lines existed
    produces no message except the probe reminder, which is the point of it."""
    secs = absorb_sections(root)
    issues = []
    if not secs:
        return issues
    seen_src, uses_for = {}, False
    last_probe, numbered = None, [n for n, _, _ in secs if n is not None]
    for n, head, lines in secs:
        ex = section_extras(lines)
        learned = any(l.startswith("learned:") and l[8:].strip() for l in lines)
        if "for" in ex:
            uses_for = True
            if any(v.lower().startswith("no-demand") for v in ex["for"]) and learned:
                issues.append(f"[W] {ABSORB_FILE}: '{head}' says `for: no-demand` and still has a learned: line -- "
                              "an absorption that serves no task, feedback line or owner request stops at step 0")
        elif uses_for and n is not None and learned:
            issues.append(f"[·] {ABSORB_FILE}: '{head}' has no `for:` line -- which task sentence, feedback line or "
                          "owner request did it serve? (`for: no-demand` if none, and then learn nothing)")
        for src in ex.get("source", []):
            key = _source_key(src)
            if key in seen_src and "repeat" not in ex:
                issues.append(f"[W] {ABSORB_FILE}: '{head}' absorbs `{src}` again (first in '{seen_src[key]}') -- "
                              "say what is new in a `repeat:` line, or merge into the earlier section's skills")
            seen_src.setdefault(key, head)
        for ev in ex.get("evidence", []):
            if not ev.split() or ev.split()[0].lower() not in EVIDENCE_LEVELS:
                issues.append(f"[W] {ABSORB_FILE}: '{head}': `evidence: {ev}` should start with one of "
                              f"{', '.join(EVIDENCE_LEVELS)}")
        for pr in ex.get("probe", []):
            if not re.match(r"^\d+/\d+\b", pr):
                issues.append(f"[W] {ABSORB_FILE}: '{head}': `probe: {pr}` should start with x/y")
            elif n is not None:
                last_probe = n
        for sup in ex.get("supersedes", []):
            m = re.match(r"@(\d+)", sup)
            if not m or int(m.group(1)) not in numbered:
                issues.append(f"[W] {ABSORB_FILE}: '{head}': `supersedes: {sup}` names no section of this ledger")
    if numbered:
        since = sum(1 for n in numbered if last_probe is None or n > last_probe)
        if since >= PROBE_AFTER:
            when = f"since @{last_probe}" if last_probe is not None else "ever"
            issues.append(f"[W] {ABSORB_FILE}: {since} absorptions with no outside probe result recorded ({when}) -- "
                          f"run `replay <root> --probes {PROBES_FILE}` on sentences the skill authors did not write and "
                          "add a `probe: x/y` line to the next section; replay on the skills' own examples only shows "
                          "the tree agrees with itself")
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
    retired_files = [f for f in base.rglob("*.md")
                     if f.name == "SKILL.md" or "references" in f.parts or "reference" in f.parts]
    for f in sorted(retired_files):
        if f.name != "SKILL.md" and (f.parent / "SKILL.md").exists():
            continue
        if f.name != "SKILL.md" and any((p / "SKILL.md").is_file() and RETIRED_HEAD_RE.match(
                (p / "SKILL.md").read_text(encoding="utf-8").split("\n", 1)[0]) for p in f.parents if base in p.parents):
            continue   # a references file inside a retired card: the card's header covers it
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


def count_retired_files(root):
    """How many single references files sit in .retired/ (retired on their own, not inside a card)."""
    d = root / RETIRED_DIR
    if not d.is_dir():
        return 0
    n = 0
    for f in d.rglob("*.md"):
        if f.name == "SKILL.md":
            continue
        if not any((p / "SKILL.md").is_file() for p in f.parents if d in p.parents or p == d):
            n += 1
    return n


def check_feedback_lines(root):
    """A _feedback.md line is `task sentence | path taken | outcome`; outcome starts with one of
    FEEDBACK_OUTCOMES. A malformed line cannot be counted and is usually skipped by the reader."""
    f = root / FEEDBACK_FILE
    if not f.is_file():
        return []
    issues = []
    for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith(("#", ">")):
            continue
        parts = [p.strip() for p in line.split("|")]
        outcome = re.sub(r"(\s+done)+$", "", parts[2]).strip() if len(parts) >= 3 else ""
        kind = outcome.split()[0].lower() if outcome.split() else ""
        target_ok = True
        if kind in ("wrong", "fallback"):
            m = re.match(r"^\w+\s*->\s*([\w./-]*[\w])\s*$", outcome)
            target_ok = bool(m)
        if len(parts) != 3 or not parts[0] or kind not in FEEDBACK_OUTCOMES or not target_ok:
            issues.append(f"[W] {FEEDBACK_FILE}:{i}: not `task sentence | path taken | outcome` with outcome one of "
                          f"{', '.join(FEEDBACK_OUTCOMES)} (`wrong -> <path>` and `fallback -> <path>` name the skill): "
                          f"{line.strip()[:90]}")
    return issues


def check_setup(root):
    """Parameters changed from the shipped values, and a rulebook that is no longer a skill."""
    issues = []
    here = globals()
    changed = [f"{k} {here[k]} (shipped {v})" for k, v in SHIPPED.items() if here.get(k) != v]
    if changed:
        issues.append("[·] parameters changed from the shipped values: " + ", ".join(changed)
                      + " -- record each change as a ruled: line; upgrading the tools resets them")
    for part in ("organizer", "editing"):
        d = root / part
        if d.is_dir() and not (d / "SKILL.md").is_file():
            issues.append(f"[W] {part}/ has no SKILL.md: the rules are no longer a skill of this tree, so they are not "
                          "routed to and not checked -- rename the file back to SKILL.md")
    return issues


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
    issues += check_duplicate_names(root, skills)
    issues += check_references(root, skills)
    issues += check_ledger(root, read_counter(root))
    issues += check_feedback_lines(root)
    issues += check_setup(root)
    for line in issues:
        print(line)
    errs = sum(1 for i in issues if i.startswith("[E]"))
    hints = sum(1 for i in issues if i.startswith("[·]"))
    warns = len(issues) - errs - hints
    tail = f", {hints} hints" if hints else ""
    retired = count_retired(root)
    rfiles = count_retired_files(root)
    rt = f", {retired} retired" if retired else ""
    rt += f", {rfiles} retired references file(s)" if rfiles else ""
    print(f"\nlint: {errs} errors, {warns} warnings{tail}, {len(skills)} skills{rt}")
    print(body_summary(root, skills))
    return 1 if errs else 0


def check_duplicate_names(root, skills):
    """Two skills with one name: a table or a person that says "use chart" cannot tell them apart.
    A warning, not an error: the paths still differ, and some trees may want it."""
    seen, out = {}, []
    for d, sk in sorted(skills.items(), key=lambda kv: str(rel(root, kv[0]))):
        name = (sk.meta.get("name") or "").strip()
        if not name:
            continue
        if name in seen:
            out.append(f"[W] {rel(root, d)}: has the same name as {rel(root, seen[name])}; "
                       "rename one so the two can be told apart")
        else:
            seen[name] = d
    return out


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


def read_probes(path):
    """A probe file: one `sentence<TAB>expected` per line; `#` lines and blank lines are skipped.
    expected is a skill path (`office-docs/pdf`), `/` or `root` for "no skill should take it",
    and may end in `/*` to accept any skill below that path. Returns [(line no, sentence, expected)]
    and a list of malformed line numbers."""
    rows, bad = [], []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 2 or not parts[0].strip() or not parts[1].strip():
            bad.append(i)
            continue
        rows.append((i, parts[0].strip(), parts[1].strip()))
    return rows, bad


def probe_verdict(path, expected, root):
    """Did the route end where the probe expects? Returns (ok, where it landed as text)."""
    last = path[-1]
    if isinstance(last, tuple):
        return False, "ambiguous [" + ", ".join(str(rel(root, h)) for h in last[1]) + "]"
    got = "/" if last == root else str(rel(root, last))
    want = expected.strip()
    if want in ("/", "root", "."):
        return last == root, got
    want = want.strip("/")
    if want.endswith("/*"):
        base = root / want[:-2]
        return last == base or base in last.parents, got
    return last == root / want, got


def cmd_probes(root, probe_file, pick=False):
    """Route sentences that the skill authors did not write, and score them on their own.
    This never changes the exit code of replay: the score is a measurement to record in
    ABSORB.md (`probe: x/y`), not a gate the tree can be tuned to pass sentence by sentence."""
    skills, errors = find_skills(root)
    if errors:
        print("\n".join("[E] " + error for error in errors))
        return 1
    f = Path(probe_file)
    if not f.is_file() and (root / probe_file).is_file():
        f = root / probe_file
    if not f.is_file():
        print(f"error: probe file {probe_file} not found (one `sentence<TAB>expected path` per line)", file=sys.stderr)
        return 2
    rows, bad = read_probes(f)
    syn = load_synonyms(root)
    ok_n, pos, pos_ok, neg, neg_ok, misses = 0, 0, 0, 0, 0, []
    for i, sent, want in rows:
        ok, got = probe_verdict(route(sent, root, skills, syn, pick=pick), want, root)
        is_neg = want.strip() in ("/", "root", ".")
        neg += is_neg
        pos += not is_neg
        if ok:
            ok_n += 1
            neg_ok += is_neg
            pos_ok += not is_neg
        else:
            misses.append(f"[MISS] {f.name}:{i}: expected {want}, landed on {got}")
    for m in misses:
        print(m)
    for i in bad:
        print(f"[SKIP] {f.name}:{i}: not `sentence<TAB>expected`")
    mode = "pick" if pick else "strict"
    print(f"\nprobes ({mode}, {f.name}): {ok_n}/{len(rows)} landed where expected "
          f"(should take: {pos_ok}/{pos}, should stay at the root: {neg_ok}/{neg})")
    print(f"A measurement, not a check: the exit code does not change. Record it as `probe: {ok_n}/{len(rows)} "
          f"{f.name} {mode}` in this absorption's {ABSORB_FILE} section. Do not edit the tree to pass one sentence: "
          "a miss names wording the tree lacks, and the fix is the general one (a synonym group, a word users say, "
          "a boundary between results).")
    return 0


# ---------------- route: where does this sentence land ----------------

def cmd_route(root, sentence, pick=False):
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
        if pick and len(hits) > 1:
            hits = _ranked(hits, canon, skills, syn)[:1]
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
    if pick:
        print(f"with the 2 best root children tried: {where(root, route(sentence, root, skills, syn, True)[-1])}")
    read = sum((d / ns.SKILL_FILE).stat().st_size for d in path)
    total = sum((d / ns.SKILL_FILE).stat().st_size for d in skills)
    print(f"read: {len(path)} file(s), {read:,} bytes of {total:,} in the library ({100 * read // max(total, 1)}%)")
    return 0


# ---------------- retire: nothing is really deleted ----------------

def cmd_retire(root, target, reason):
    src = (root / target.strip("/")).resolve()
    if src == root.resolve():
        print("error: the root cannot be retired", file=sys.stderr)
        return 1
    if root.resolve() not in src.parents:
        print(f"error: '{target}' is outside the library (a path or link leads out of {root})", file=sys.stderr)
        return 1
    is_file = src.is_file() and src.suffix == ".md" and ("references" in src.parts or "reference" in src.parts)
    if not is_file and not (src / "SKILL.md").is_file():
        print(f"error: '{target}' has no SKILL.md, so it is not a skill in this library "
              "(a single knowledge file can be retired too: name a .md file under a references/ folder)",
              file=sys.stderr)
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
    if is_file:
        return _retire_file(root, src, dst, counter, reason.strip())
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


def _retire_file(root, src, dst, counter, reason):
    """Retire one references/ file: move it to .retired/<same path> with a first line
    `retired @n reason`. Continuous absorption grows knowledge files, not cards, so a
    card-only retire never fires for what actually accumulates."""
    if src.is_symlink():
        print("error: refusing to retire a link", file=sys.stderr)
        return 1
    if dst.exists():
        n = 2
        while (dst.parent / f"{dst.stem}~{n}{dst.suffix}").exists():
            n += 1
        dst = dst.parent / f"{dst.stem}~{n}{dst.suffix}"
    old = src.resolve()
    dst.parent.mkdir(parents=True, exist_ok=True)
    text = src.read_text(encoding="utf-8")
    with dst.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(f"retired @{counter} {reason}\n" + text)
    src.unlink()
    left = []
    for d, sk in find_skills(root)[0].items():
        for ref in named_paths(sk.body):
            if (d / ref).resolve() == old or (root / ref).resolve() == old:
                left.append(f"{rel(root, d)}/SKILL.md names `{ref}`")
    print(f"moved to {rel(root, dst)}, first line 'retired @{counter} {reason}' "
          f"(this absorption's section heading in {ABSORB_FILE} should also be @{counter})")
    for l in left:
        print(f"check: {l}, which is now retired -- remove the pointer or name the file that replaces it")
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


def superseded_rulings(root):
    """Ruling ids that a later `supersedes:` line names: `@n.k` (the k-th ruled: line of section
    @n, counting from 1) or `@n` for every ruling of that section."""
    out = set()
    for _, _, lines in absorb_sections(root):
        for v in section_extras(lines).get("supersedes", []):
            m = re.match(r"(@\d+(?:\.\d+)?)", v)
            if m:
                out.add(m.group(1))
    return out


def cmd_ask(root, grep=None, since=None, current=False):
    sec = checklist_section()
    if sec is None:
        print(f"error: section '{CHECKLIST_HEAD}' not found in {RULES_FILE} -- has the rulebook been edited?",
              file=sys.stderr)
        return 1
    print(sec)
    print()
    rulings = ruling_lines(root)
    total = len(rulings)
    if since is not None or grep or current:
        sup = superseded_rulings(root) if current else set()
        kept, k_in = [], {}
        for head, line in rulings:
            m = re.match(r"@(\d+)", head)
            n = int(m.group(1)) if m else None
            k_in[head] = k_in.get(head, 0) + 1
            rid = f"@{n}.{k_in[head]}" if n is not None else None
            if since is not None and (n is None or n < since):
                continue
            if grep and not re.search(grep, line + " " + head, re.I):
                continue
            if current and n is not None and (rid in sup or f"@{n}" in sup):
                continue
            kept.append((head, line if rid is None else f"{line}  [{rid}]"))
        rulings = kept
        flt = [x for x in (f"--grep {grep}" if grep else "", f"--since {since}" if since is not None else "",
                           "--current" if current else "") if x]
        print(f"(showing {len(rulings)} of {total} ruling(s): {', '.join(flt)})")
        if not rulings and total:
            print("No ruling matches; widen the filter before deciding a matter the library may already have ruled on.")
            return 0
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

def cmd_feedback(root, stats=False):
    f = root / FEEDBACK_FILE
    if not f.exists():
        print(f"(no {FEEDBACK_FILE})")
        return 0
    if stats:
        return feedback_stats(f)
    pending = [l for l in f.read_text(encoding="utf-8").splitlines()
               if l.strip() and not l.lstrip().startswith(("#", ">"))
               and not l.rstrip().endswith(" done")]
    for l in pending:
        print(l)
    print(f"\nfeedback: {len(pending)} line(s) pending (process them before absorbing)")
    return 0


def feedback_stats(f):
    """Count every line, handled or not, by outcome and by the skill named after `->`. A skill
    often reached only by `fallback` is one the word layer does not find; a skill often named in
    `wrong` is one something else takes from it."""
    by_kind, by_skill, bad = {}, {}, 0
    for line in f.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith(("#", ">")):
            continue
        parts = [p.strip() for p in line.split("|")]
        outcome = re.sub(r"(\s+done)+$", "", parts[2]).strip() if len(parts) == 3 else ""
        kind = outcome.split()[0].lower() if outcome.split() else ""
        if kind not in FEEDBACK_OUTCOMES:
            bad += 1
            continue
        by_kind[kind] = by_kind.get(kind, 0) + 1
        m = re.match(r"^\w+\s*->\s*([\w./-]*\w)", outcome)
        if m and m.group(1).strip("/"):
            kinds = by_skill.setdefault(m.group(1).strip("/"), {})
            kinds[kind] = kinds.get(kind, 0) + 1
    total = sum(by_kind.values())
    print(f"feedback: {total} line(s)" + (f", {bad} malformed (lint lists them)" if bad else ""))
    for k in FEEDBACK_OUTCOMES:
        if by_kind.get(k):
            print(f"  {k:9} {by_kind[k]}")
    if by_skill:
        print("by skill named after '->':")
        for name, kinds in sorted(by_skill.items(), key=lambda kv: (-sum(kv[1].values()), kv[0])):
            print(f"  {name}: " + ", ".join(f"{k} {n}" for k, n in sorted(kinds.items())))
    if total == 0:
        print("No line is not evidence that routing works: the agent writes a line only when it notices. "
              "If the tree is in use, check that the root's rule 7 is being followed.")
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


def _replay_and_probes(root, probes, pick):
    """replay's exit code is the skills' own examples only; probes are printed after and never change it."""
    rc = cmd_replay(root)
    if probes:
        print()
        if cmd_probes(root, probes, pick) == 2:
            return 2
    return rc


def main(argv=None):
    ns._tolerate_console_encoding()   # same reason as in holon.py: [·] hints must not crash a cp1252 console
    ap = argparse.ArgumentParser(prog="organizer", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["lint", "replay", "route", "overlap", "retire", "feedback", "counter", "ask"])
    ap.add_argument("root", type=Path)
    ap.add_argument("target", nargs="?", help="retire: skill path to move (relative to root); route: the sentence to try")
    ap.add_argument("--reason", help="retire: reason, written into the first line of the file")
    ap.add_argument("--bump", action="store_true", help="counter: increment by 1")
    ap.add_argument("--pick", action="store_true",
                    help="route: when several children take the sentence, pick one deterministic winner "
                         "instead of reporting an ambiguity / stopping at the parent")
    ap.add_argument("--probes", metavar="FILE",
                    help=f"replay: also route the sentences in FILE (`sentence<TAB>expected path`, conventionally "
                         f"{PROBES_FILE}) and print their score separately; it never changes the exit code")
    ap.add_argument("--grep", help="ask: only rulings matching this regular expression")
    ap.add_argument("--since", type=int, help="ask: only rulings from absorption @N on")
    ap.add_argument("--current", action="store_true", help="ask: leave out rulings a later `supersedes:` line replaced")
    ap.add_argument("--stats", action="store_true", help="feedback: count every line by outcome and by skill")
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
          "replay": lambda: _replay_and_probes(a.root, a.probes, a.pick),
          "route": lambda: cmd_route(a.root, a.target, a.pick),
          "overlap": lambda: cmd_overlap(a.root, a.threshold),
          "retire": lambda: cmd_retire(a.root, a.target, a.reason),
          "feedback": lambda: cmd_feedback(a.root, a.stats),
          "counter": lambda: cmd_counter(a.root, a.bump),
          "ask": lambda: cmd_ask(a.root, a.grep, a.since, a.current)}[a.command]
    try:
        return fn()
    except (OSError, UnicodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
