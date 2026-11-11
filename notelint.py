#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
notelint - a linter for a knowledge base of project notes.

Documentation does not rot because people are lazy. It rots because nothing
ever checks whether it is still true. notelint checks.

Point it at a directory. Every subdirectory with a `notes/`, `todo/` or
`ideas/` folder is a project: what is true today, the open work and the loose
ideas. A `history/` folder beside them holds the notes that are past. Notes are global
across projects (links may cross), but each project also gets its own index,
its own list of open work and, if it has a past, its own history.

    python notelint.py                 # lint the current directory, write indexes
    python notelint.py path/to/base    # lint somewhere else
    python notelint.py --report-only   # do not write INDEX.md / OPEN.md / HISTORY.md
    python notelint.py --lang es       # Spanish field names
    python notelint.py --project Alpha # report on one project only
    python notelint.py --width 80      # wrap the findings at 80 columns

    python notelint.py search poll interval --project Alpha --type todo
        # find notes by words and filters; lints nothing, writes nothing
    python notelint.py open feed-poll-interval [--with obsidian|code]
        # open one note (or the only one its words match) and print its path

    python notelint.py new Alpha todo ship-the-importer --title "Ship the importer"
        # write a note from the template, dated today, where its type belongs
    python notelint.py review feed-poll-interval [more ids]
        # set 'reviewed' to today and fingerprint what those notes depend on
    python notelint.py close ship-the-importer [--title "..."] [--keep]
        # a todo that is done becomes a fact; to history/ if nothing rests on it

Findings come in two levels. ERRORS are things written wrong or broken; they
go to zero. REVIEWS ask for a look and are a queue. Exit code is 1 when there
are errors, so it works in CI; --strict also fails on reviews, and --exit-zero
always exits 0.

On a terminal the findings wrap to its width. Piped or redirected, each one
stays on a single line, so grep and diff see whole findings; --width N fixes
the width either way, and --width 0 never wraps.

No dependencies. Python 3.8+.
"""
import os, sys, re, json, shutil, hashlib, datetime, textwrap, unicodedata, argparse
from pathlib import Path

__version__ = "2.0.0"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

TODAY = datetime.date.today()

# Two clocks. What moves (todo, fact, and a decision that does not say what it
# rests on) is re-confirmed every 60 days; what describes (reference, incident)
# and a decision with depends-on links, every 180. An idea does not age.
DAYS_UNREVIEWED = 60
DAYS_UNREVIEWED_LONG = 180
# A doubt nobody resolves in two weeks is no longer a doubt: it is an abandoned note.
DAYS_UNVERIFIED = 14

# Size caps. A title past MAX_TITLE characters is carrying the body; a note past
# MAX_LINES lines is two claims, or one still carrying its past.
MAX_TITLE = 160
MAX_LINES = 150

# Directories at the base that are never projects.
NEVER_A_PROJECT = {"templates", "tools", "docs", ".git", ".github", "node_modules"}

# Regenerable junk: not material that anyone should have to claim with a note.
GENERATED = {"__pycache__", ".pytest_cache", ".mypy_cache", "node_modules",
             "target", ".venv", "venv"}

# A project keeps what is true today in notes/, the work still to do in todo/
# and the ideas nobody has committed to in ideas/. The three are read alike:
# the folder is where `notelint new` files a note by its type, so the open work
# and the loose ideas do not bury the claims. Beside them, history/ holds the
# notes that no longer describe the present: closed notes, and facts, incidents
# and ideas about what already happened. They are loaded, so links into them
# still resolve, but they do not age, their evidence is not watched, and they
# stay out of the views and out of search unless asked for. Same id, same file:
# moving a note there is the whole operation.
NOTES, TODO_DIR, IDEAS_DIR, HISTORY = "notes", "todo", "ideas", "history"
LIVE_FOLDERS = (NOTES, TODO_DIR, IDEAS_DIR)

# Where `review`, `new` and `close` keep what each note's dependencies said
# when it was last confirmed (see `propagation` in check()). One file per base.
STATE_DIR, FINGERPRINTS = ".notelint", "fingerprints.json"

# Findings come in two levels. ERRORS: something is written wrong or broken;
# it goes to zero before the work is called done, and it is what fails the
# exit code. REVIEWS: something asks for a look; a queue worked down a few at
# a time, oldest first. --strict fails on both. A category missing from both
# lists still prints, under ERRORS, rather than vanish.
ERRORS = ["inbox", "duplicate id", "format", "wrong project", "broken link", "ambiguous link",
          "dead evidence", "zombie", "depends on history", "supersedes a live note",
          "no successor", "unblocked", "permanent block", "hidden todo", "past version",
          "no verification", "long title", "long note", "unclaimed"]
REVIEWS = ["evidence changed", "touched unreviewed", "expired", "unreviewed",
           "stale unverified", "propagation", "duplicate?"]

# ---------------------------------------------------------------------------
# Vocabulary. The note format is the same in every language; only the field
# names change, so a team can keep notes in its own language.
# ---------------------------------------------------------------------------
VOCAB = {
    "en": {
        "fields": {"title": "title", "type": "type", "project": "project",
                   "status": "status", "created": "created", "reviewed": "reviewed",
                   "expires": "expires", "evidence": "evidence", "links": "links",
                   "installed": "installed-version"},
        "types": ["decision", "fact", "todo", "idea", "incident", "reference"],
        "statuses": ["current", "superseded", "dropped", "unverified"],
        "edges": ["depends-on", "supersedes", "blocks", "related"],
        "index": "INDEX.md", "open": "OPEN.md", "history": "HISTORY.md",
        "inbox": "INBOX.md", "inbox_open": "to process",
        "what": "What it is", "verify": "How to verify", "the_idea": "The idea",
        "was_todo": "Was a todo until {date}.",
    },
    "es": {
        "fields": {"title": "titulo", "type": "tipo", "project": "proyecto",
                   "status": "estado", "created": "creada", "reviewed": "revisada",
                   "expires": "caduca", "evidence": "evidencia", "links": "enlaces",
                   "installed": "version-instalada"},
        "types": ["decision", "hecho", "pendiente", "idea", "incidente", "referencia"],
        "statuses": ["vigente", "superado", "descartado", "en-duda"],
        "edges": ["depende-de", "supera-a", "bloquea", "relacionada"],
        "index": "INDICE.md", "open": "ABIERTO.md", "history": "HISTORIAL.md",
        "inbox": "BUZON.md", "inbox_open": "por procesar",
        "what": "Qué es", "verify": "Cómo se comprueba", "the_idea": "La idea",
        "was_todo": "Era pendiente hasta el {date}.",
    },
}

# Marks a loose task written in a note's body. In a todo note it is fine; in
# any other type it is work that OPEN.md will never list.
PENDING_MARK = "⏳"   # ⏳

# An evidence line ending in this mark is only checked for existence. Source
# code changes with every build, and citing it would otherwise report
# `evidence changed` with every build until nobody reads the report. The note
# still ages like any other, which is what gets it re-checked. Either
# language's mark is understood under either vocabulary.
EXISTS_ONLY = re.compile(r"\s*\((?:existence only|s[oó]lo que exista)\)\s*$", re.I)

RE_WIKI = re.compile(r"\[\[([^\]|#]+)")
RE_VERSION = re.compile(r"\bv(\d+)\b")
RE_CODE = re.compile(r"```.*?```|`[^`\n]*`", re.S)


def strip_code(txt):
    """`[[ratelimits]]` inside backticks is TOML, not a link."""
    return RE_CODE.sub(" ", txt)


def as_date(v):
    try:
        return datetime.date.fromisoformat(v.strip())
    except Exception:
        return None


def fold(s):
    s = unicodedata.normalize("NFKD", s.strip().lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def unquote(v):
    """YAML lets a value sit in quotes, and a title with a colon needs them:
    "current" and current are the same status."""
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return v


def plural(count, word):
    """'1 note', '2 notes': the first line a new user reads must not say '1 notes'."""
    return str(count) + " " + word + ("" if count == 1 else "s")


def detect_lang(base):
    """Pick the vocabulary whose status field appears in the notes."""
    for note in [p for d in LIVE_FOLDERS for p in base.glob("*/" + d + "/*.md")]:
        try:
            head = note.read_text(encoding="utf-8", errors="replace")[:600]
        except OSError:
            continue                # parse() reports it; it cannot pick a language
        for lang, v in VOCAB.items():
            if re.search(r"^" + v["fields"]["status"] + r"\s*:", head, re.M):
                return lang
    return "en"


def projects(base):
    """Directories with notes/, todo/ or ideas/, or with only history/ left: a
    project whose last note went to history is still loaded, or links into it
    would break."""
    out = []
    for d in sorted(base.iterdir()):
        if (d.is_dir() and d.name not in NEVER_A_PROJECT and not d.name.startswith(".")
                and any((d / sub).is_dir() for sub in LIVE_FOLDERS + (HISTORY,))):
            out.append(d)
    return out


# ---------------------------------------------------------------------------
# Parsing. A deliberately small YAML subset, so the tool stays dependency-free
# and the format stays simple enough to write by hand.
# ---------------------------------------------------------------------------
def parse(path, folder, V):
    F, E = V["fields"], V["edges"]
    n = {"id": path.stem, "path": path, "folder": folder, "body": "", "errors": [],
         "mtime": None, "unreadable": False}
    for k in ("title", "type", "project", "status", "created", "reviewed", "expires",
              "installed"):
        n[k] = ""
    n["evidence"] = []
    n["links"] = {e: [] for e in E}
    try:
        try:
            txt = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            txt = path.read_text(encoding="utf-8", errors="replace")
            n["errors"].append("not valid UTF-8: decoded with replacements")
        n["mtime"] = path.stat().st_mtime
    except OSError as e:
        # A folder named x.md, a link that leads nowhere, a file without
        # permission: a finding to fix, not a traceback that exits 1 like one.
        n["errors"].append("cannot be read (" + (e.strerror or type(e).__name__) + ")")
        n["unreadable"] = True
        return n
    back = {v: k for k, v in F.items()}

    if not txt.startswith("---"):
        n["errors"].append("no frontmatter")
        n["body"] = txt
        return n
    parts = txt.split("\n---", 1)
    head = parts[0][3:]
    n["body"] = parts[1] if len(parts) > 1 else ""
    if len(parts) == 1:
        n["errors"].append("frontmatter never closed with ---")

    section, last_edge = None, None
    for line in head.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        s = line.strip()
        if indent == 0 and ":" in s:
            key, _, val = s.partition(":")
            key, val = key.strip(), val.strip()
            section, last_edge = None, None
            if key == F["evidence"] or key == F["links"]:
                section = back[key]
                if val:
                    n["errors"].append("'" + key + ":' takes a list on following lines")
            elif key in back:
                n[back[key]] = unquote(val)
            continue
        if section == "evidence" and s.startswith("- "):
            n["evidence"].append(s[2:].strip().strip('"').strip("'"))
        elif section == "links" and ":" in s:
            key, _, val = s.partition(":")
            key = key.strip()
            if key not in E:
                n["errors"].append("unknown link type: " + key)
                continue
            val = val.strip()
            if val.startswith("[") and val.endswith("]"):
                val = val[1:-1]
            n["links"][key] = [unquote(x.strip()) for x in val.split(",") if x.strip()]
            last_edge = key
        elif section == "links" and s.startswith("- ") and last_edge:
            n["links"][last_edge].append(s[2:].strip().strip('"').strip("'"))
    return n


def load(folders, V):
    """Read every note. Returns (notes, clashes, ambiguous).

    Two projects can each hold a `decisions.md`, and that has to keep
    working: both notes are loaded and checked. What a clash costs is the
    bare name as a link target - it no longer points at one note - so those
    are keyed `Project/id` (`Project/history/id` for one in history) and
    listed in `ambiguous`.
    """
    seen = {}
    for c in folders:
        for sub in LIVE_FOLDERS + (HISTORY,):
            for p in sorted((c / sub).glob("*.md")):
                n = parse(p, c, V)
                n["history"] = sub == HISTORY
                seen.setdefault(n["id"], []).append(n)

    notes, clashes, ambiguous = {}, [], set()
    for i in sorted(seen):
        group = seen[i]
        if len(group) == 1:
            notes[i] = group[0]
            continue
        ambiguous.add(i)
        first = place(group[0])
        for other in group[1:]:
            clashes.append((i, first, place(other)))
        for n in group:
            notes[place(n) + "/" + i] = n
    return notes, clashes, ambiguous


def place(n):
    """Where a note lives, for a person to read: `Alpha`, `Alpha/todo`,
    `Alpha/ideas` or `Alpha/history`."""
    sub = n["path"].parent.name
    return n["folder"].name + ("" if sub == NOTES else "/" + sub)


def keywords(t):
    stop = {"the", "and", "for", "with", "that", "this", "from", "into", "not",
            "los", "las", "del", "para", "por", "que", "una", "con", "sin", "mas"}
    return {w for w in re.findall(r"[a-z0-9]+", fold(t)) if w not in stop and len(w) > 3}


def cite_path(item):
    """The path part of a citation, with any trailing comment removed.

    One definition, used by both the evidence check and the claim check.
    They used to cut on different delimiters - one on an em dash, the other
    on a plain hyphen - so the same line could be live evidence and
    unclaimed at the same time.

    A plain hyphen is NOT a delimiter: it is far too common inside real
    file names. To put a comment after a path use " — ", " (" or " §".
    The existence-only mark goes first, so it may follow a comment.
    """
    item = EXISTS_ONLY.sub("", item)
    for sep in (" §", " (", " —"):
        item = item.split(sep)[0]
    return item.strip()


def evidence_path(e, folder, base):
    """Where a cited path lives on disk, or None if it is a URL or gone."""
    if e.startswith("http://") or e.startswith("https://"):
        return None
    raw = cite_path(e).replace("\\", "/")
    p = Path(raw)
    if p.is_absolute():
        return p if p.exists() else None
    for root in (folder, base):
        if (root / raw).exists():
            return root / raw
    return None


def evidence_exists(e, folder, base):
    if e.startswith("http://") or e.startswith("https://"):
        return True
    return evidence_path(e, folder, base) is not None


RE_ABSOLUTE = re.compile(r"^([A-Za-z]:/|/|~/)")


def inside_base(e, folder, base):
    """If an evidence line is an absolute path into the base, the same path
    written relative (to the base, or to the note's project); otherwise None.

    An absolute path works on the machine that wrote it and nowhere else: a
    clone, a second computer or a teammate finds dead evidence. It is matched
    two ways: it resolves into the base here, or it passes through a folder
    named like the base or like the note's project and the rest exists here
    (`C:\\Users\\dana\\notes\\Kestrel\\evidence\\x.md` read anywhere else).
    """
    if e.startswith("http://") or e.startswith("https://"):
        return None
    raw = cite_path(e).replace("\\", "/")
    if not RE_ABSOLUTE.match(raw):
        return None
    try:
        rel = Path(raw).expanduser().resolve().relative_to(base.resolve())
        if str(rel) != ".":
            return rel.as_posix()
    except (ValueError, OSError, RuntimeError):
        pass
    parts = [p for p in raw.split("/") if p]
    for k, p in enumerate(parts):
        rest = parts[k + 1:]
        if not rest:
            break
        for name, root in ((base.name, base), (folder.name, folder)):
            if p.lower() == name.lower() and root.joinpath(*rest).exists():
                return "/".join(rest)
    return None


def under_git(base):
    """True when the base sits inside a git work tree.

    A clone, a checkout or a branch switch rewrites the modification time of
    every file it touches, so there the two checks that read it would report
    every note at once. Inside git, `git log` is the better witness anyway.
    """
    return any((d / ".git").exists() for d in [base] + list(base.parents))


def modified(path):
    try:
        return datetime.date.fromtimestamp(path.stat().st_mtime)
    except OSError:
        return None


# ---------------------------------------------------------------------------
# Fingerprints. When a note is confirmed, the body of each note it depends on
# is hashed and kept, so that a later review of a dependency that changed
# nothing does not ask for the note to be confirmed all over again. Content,
# not dates: a clone keeps them, which is why this works inside git too.
# ---------------------------------------------------------------------------
def body_sha(n):
    """sha256 of what follows the frontmatter, line endings and edges evened out."""
    body = n["body"].replace("\r\n", "\n").strip()
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def read_fingerprints(base):
    """{A: {B: {"sha", "date"}}}, or {} when there is no file or it is unreadable."""
    try:
        data = json.loads((base / STATE_DIR / FINGERPRINTS).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    prints = data.get("fingerprints") if isinstance(data, dict) else None
    if not isinstance(prints, dict):
        return {}
    return {a: {b: h for b, h in deps.items() if isinstance(h, dict)}
            for a, deps in prints.items() if isinstance(deps, dict)}


def save_fingerprints(base, notes, ids, V):
    """Record, for each of `ids`, the body of every note it depends on as it is now."""
    prints = read_fingerprints(base)
    for a in ids:
        n = notes.get(a)
        if n is None:
            continue
        entry = prints.setdefault(a, {})
        for b in n["links"][V["edges"][0]]:
            o = notes.get(b)
            if o and not o["unreadable"]:
                entry[b] = {"sha": body_sha(o), "date": str(TODAY)}
    folder = base / STATE_DIR
    folder.mkdir(parents=True, exist_ok=True)
    tmp = folder / (FINGERPRINTS + ".tmp")
    with open(str(tmp), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"fingerprints": prints}, indent=1, ensure_ascii=False,
                            sort_keys=True) + "\n")
    os.replace(str(tmp), str(folder / FINGERPRINTS))


# ---------------------------------------------------------------------------
# The checks.
# ---------------------------------------------------------------------------
RE_BACKTICK = re.compile(r"`([^`\n]+)`")


def claimed_paths(project_notes, folder):
    """Paths the notes of one project claim, relative to that project.

    Material is claimed by citing its path, not by naming the file. What counts
    is the `evidence:` field and paths written between backticks in the body.
    Citing something deep also claims its parent directories, so that quoting
    `evidence/artifacts/x.md` does not leave `evidence` looking unclaimed.

    Returns (claimed, cited): every claimed path including the implied
    parents, and the paths cited in full. A directory cited in full claims
    what it holds; an implied parent does not, or one file would claim
    every sibling.

    Matching on the bare name instead is what made a new directory called
    `legal`, `src` or `tests` never show up: those words were already written
    somewhere in the notes for an unrelated reason.

    The two sources are not filtered alike. A backticked span in the body is
    prose, and may be a shell command: one whose first segment holds a space
    is not taken for a path. `evidence:` is one path per line, so there that
    guard protects nothing, and it used to make a top-level `Q3 Report.pdf`
    impossible to claim however it was cited.
    """
    raw = []
    for n in project_notes:
        raw.extend((e, True) for e in n["evidence"])
        raw.extend((b, False) for b in RE_BACKTICK.findall(n["body"]))

    out, cited = set(), set()
    for item, structured in raw:
        if item.startswith("http://") or item.startswith("https://"):
            continue
        # Evidence lines may carry a trailing comment; keep the path part.
        path = cite_path(item)
        path = path.strip().strip("/\\").replace("\\", "/")
        if not path or path.startswith("-"):
            continue
        if not structured and " " in path.split("/")[0]:
            continue
        parts = [p for p in path.split("/") if p not in ("", ".")]
        if not parts or ".." in parts:
            continue
        # Either relative to the project, or to the base naming the project first.
        if parts[0].lower() == folder.name.lower():
            parts = parts[1:]
        elif not (folder / parts[0]).exists():
            continue
        for i in range(1, len(parts) + 1):
            out.add("/".join(parts[:i]).lower())
        if parts:
            cited.add("/".join(parts).lower())
    return out, cited


RE_SECTION = re.compile(r"^##\s+(.+?)\s*$", re.M)


def sections(body):
    """[(title, text)] for each '## ' heading in the body, in order."""
    out = []
    marks = list(RE_SECTION.finditer(body))
    for k, m in enumerate(marks):
        end = marks[k + 1].start() if k + 1 < len(marks) else len(body)
        out.append((m.group(1), body[m.end():end]))
    return out


def is_verification(title):
    """'How to apply' is the heading for a rule of conduct: it says how you
    notice the rule was broken, which is its way of being checked."""
    t = fold(title)
    return (t.startswith("how to verify") or t.startswith("how to check")
            or t.startswith("how to apply")
            or t.startswith("como se comprueba") or t.startswith("como se aplica"))


def window(n, V):
    """Days a current note may go unreviewed before it is reported."""
    DECISION, FACT, TODO, IDEA, INCIDENT, REFERENCE = V["types"]
    if n["type"] in (REFERENCE, INCIDENT):
        return DAYS_UNREVIEWED_LONG
    if n["type"] == DECISION and n["links"][V["edges"][0]]:
        return DAYS_UNREVIEWED_LONG
    return DAYS_UNREVIEWED


def days_unreviewed(n):
    r = as_date(n["reviewed"])
    return (TODAY - r).days if r else None


def age(n):
    d = days_unreviewed(n)
    return "" if d is None else "  (" + str(d) + "d)"


def topo_order(notes, V):
    """Position of each note with its dependencies before it.

    Reviewing bottom-up is what stops you firing spurious propagation findings
    at yourself: confirm what something rests on before confirming it.
    """
    DEPENDS = V["edges"][0]
    pending = {i: [d for d in n["links"][DEPENDS] if d in notes and d != i]
               for i, n in notes.items()}
    pos, done = {}, []
    left = set(pending)
    while left:
        layer = sorted(i for i in left if all(d in pos for d in pending[i]))
        if not layer:                      # a cycle: break it alphabetically
            layer = [min(left)]
        for i in layer:
            pos[i] = len(done)
            done.append(i)
        left -= set(layer)
    return pos


def print_verifications(notes, folders, V, days):
    """Print every 'How to verify' section, dependencies first.

    It runs nothing. You run each one and touch `reviewed` only on the ones that
    gave what the note predicted. A different result is a finding: fix the note.
    """
    CURRENT = V["statuses"][0]
    IDEA = V["types"][3]
    names = {c.name for c in folders}
    which = [n for n in notes.values()
             if n["folder"].name in names and n["status"] == CURRENT
             and n["type"] != IDEA and not n["history"]]
    if days is not None:
        which = [n for n in which if (days_unreviewed(n) or 0) > days]
    pos = topo_order(notes, V)
    which.sort(key=lambda n: (pos.get(n["id"], 0), n["id"]))

    print("")
    print("  " + plural(len(which), "verification")
          + ", dependencies first (the ones others rest on).")
    print("  Nothing is run: you run each, and touch 'reviewed' only if it holds.")
    for n in which:
        found = [body for t, body in sections(n["body"]) if is_verification(t)]
        text = found[0].strip() if found else "(no section)"
        print("")
        print("  -- " + n["id"] + "  [" + n["folder"].name + "]  reviewed "
              + n["reviewed"] + age(n))
        for line in text.splitlines():
            print("     " + line)
    print("")


def oldest_block(notes, V, how_many=8):
    """The current notes longest unreviewed, across every project.

    Turns the 60-day cliff into a trickle: review a few each session and the
    warning never arrives all at once.
    """
    CURRENT = V["statuses"][0]
    IDEA = V["types"][3]
    alive = [n for n in notes.values()
             if n["status"] == CURRENT and n["type"] != IDEA and not n["history"]
             and as_date(n["reviewed"])]
    if not alive:
        return []
    alive.sort(key=lambda n: (as_date(n["reviewed"]), n["id"]))
    out = ["## The " + str(how_many) + " longest unreviewed", "",
           "Across every project. Reviewing a few each session keeps the 60-day",
           "warning from arriving all at once.", ""]
    for n in alive[:how_many]:
        out.append("- [" + n["title"] + "](" + link_to(n, None) + ") _("
                   + n["folder"].name + ")_ - reviewed " + n["reviewed"] + age(n))
    return out + [""]


def inbox(base, V):
    """The lines under '## To process' in INBOX.md at the base.

    It is where someone who changed something by hand - outside the routine,
    without touching any note - leaves word of what and why. Whoever updates
    the base turns each line into a note, or a fix to one, and moves the line
    under '## Processed'. Until then it is a finding: the base does not yet
    account for what happened.
    """
    path = base / V["inbox"]
    if not path.is_file():
        return []
    try:
        txt = path.read_text(encoding="utf-8-sig")
    except (UnicodeDecodeError, ValueError, OSError):
        return ["(" + V["inbox"] + " could not be read)"]
    inside, lines = False, []
    for line in txt.splitlines():
        if line.startswith("## "):
            inside = fold(line[3:]).startswith(V["inbox_open"])
            continue
        if inside and line.strip().startswith("- "):
            lines.append(line.strip()[2:].strip())
    return lines


def check(notes, clashes, base, V, ambiguous=()):
    out = [("inbox", V["inbox"], line) for line in inbox(base, V)]
    CURRENT, SUPERSEDED, DROPPED, UNVERIFIED = V["statuses"]
    DEPENDS, SUPERSEDES, BLOCKS, RELATED = V["edges"]
    FACT, IDEA, INCIDENT = V["types"][1], V["types"][3], V["types"][4]
    ids = set(notes)
    use_mtime = not under_git(base)

    for i, a, b in clashes:
        out.append(("duplicate id", i, "exists in " + a + " and in " + b))

    for i, n in sorted(notes.items()):
        for e in n["errors"]:
            out.append(("format", i, e))
        if n["unreadable"]:
            continue                # anything more would be noise about the same fault
        if n["type"] not in V["types"]:
            out.append(("format", i, "invalid type: " + repr(n["type"])))
        if n["status"] not in V["statuses"]:
            out.append(("format", i, "invalid status: " + repr(n["status"])))
        if not n["title"]:
            out.append(("format", i, "no title"))
        if fold(n["project"]) != fold(n["folder"].name):
            out.append(("wrong project", i,
                        "says '" + n["project"] + "' but lives in " + n["folder"].name))
        F = V["fields"]
        for k in ("created", "reviewed", "expires"):
            if n[k] and not as_date(n[k]):
                out.append(("format", i, "malformed date in '" + F[k] + "': " + n[k]
                            + " (use YYYY-MM-DD)"))
        c, r = as_date(n["created"]), as_date(n["reviewed"])
        if c and r and r < c:
            out.append(("format", i, "'" + F["reviewed"] + "' (" + str(r)
                        + ") is earlier than '" + F["created"] + "' (" + str(c) + ")"))

        # 1. broken links
        targets = set()
        for e in V["edges"]:
            targets |= set(n["links"][e])
        targets |= set(m.strip() for m in RE_WIKI.findall(strip_code(n["body"])))
        for d in sorted(targets):
            if d in ambiguous:
                out.append(("ambiguous link", i,
                            "[[" + d + "]] names more than one note; rename one"))
            elif d not in ids:
                out.append(("broken link", i, "[[" + d + "]] does not exist"))

        # 1b. history: its format and its links are checked, and that it belongs
        #     there; nothing else. It does not age and its evidence is not
        #     watched, because the past is not re-verified.
        if n["history"]:
            if n["status"] not in (SUPERSEDED, DROPPED) and not (
                    n["status"] == CURRENT and n["type"] in (FACT, INCIDENT, IDEA)):
                out.append(("format", i, HISTORY + "/ holds closed notes, and facts, incidents"
                            " and ideas about the past; this is " + n["status"] + " "
                            + n["type"] + ": move it back to " + NOTES + "/"))
            continue

        # 2. evidence that no longer exists on disk, or that changed after the
        #    note was last confirmed: what it says may no longer match. A line
        #    marked existence-only is spared the second half.
        for e in n["evidence"]:
            rel = inside_base(e, n["folder"], base)
            if rel:
                out.append(("format", i, "absolute path into the base: write `" + rel
                            + "`, which works on any machine and in any clone"))
                # What it points at is there: one finding, not a second one
                # saying the same path is dead on every other machine.
                if evidence_exists(rel, n["folder"], base):
                    continue
            if not evidence_exists(e, n["folder"], base):
                out.append(("dead evidence", i, e))
            elif use_mtime and r and n["status"] == CURRENT and not EXISTS_ONLY.search(e):
                p = evidence_path(e, n["folder"], base)
                mod = modified(p) if p and p.is_file() else None
                if mod and mod > r:
                    out.append(("evidence changed", i, e + " changed on " + str(mod)
                                + ", after the review of " + str(r)))

        # 2b. touched, not reviewed: the note itself changed on disk after its
        #     `reviewed` date. Someone edited it outside the routine - by hand,
        #     or an agent that did not bump the date. Not an error: the signal
        #     that it needs a look. Same one-day resolution as the check above.
        if use_mtime and r and n["mtime"]:
            mod = datetime.date.fromtimestamp(n["mtime"])
            if mod > r:
                out.append(("touched unreviewed", i, "the file changed on " + str(mod)
                            + " and '" + F["reviewed"] + "' says " + str(r)))

        # 3. expired, or unreviewed for too long
        if n["status"] == CURRENT:
            x = as_date(n["expires"])
            if x and x < TODAY:
                out.append(("expired", i, "expired on " + str(x) + " and still current"))
            if r and r > TODAY:
                # A future date gives a negative age and would silence the warning forever.
                out.append(("format", i, "'" + F["reviewed"] + "' is in the future: " + str(r)))
            elif r and n["type"] != IDEA and (TODAY - r).days > window(n, V):
                out.append(("unreviewed", i, str((TODAY - r).days)
                            + " days since last review (allows " + str(window(n, V)) + ")"))
            if not n["reviewed"]:
                out.append(("format", i, "'" + F["reviewed"] + "' is missing"))

            # 3b. the third rule, enforced and not just stated. An idea is
            #     exempt: it asserts nothing to check.
            if n["type"] != IDEA:
                secs = sections(n["body"])
                found = [(t, b) for t, b in secs if is_verification(t)]
                if not found:
                    out.append(("no verification", i,
                                "current note without a 'How to verify' section"))
                elif not found[0][1].strip():
                    out.append(("no verification", i, "the 'How to verify' section is empty"))
                else:
                    k = [t for t, _ in secs].index(found[0][0])
                    after = [t for t, _ in secs[k + 1:]]
                    if after:
                        out.append(("format", i, "sections after 'How to verify' ("
                                    + "; ".join(after) + "): the verification goes last"))
        elif n["status"] == UNVERIFIED and r and (TODAY - r).days > DAYS_UNVERIFIED:
            out.append(("stale unverified", i, str((TODAY - r).days)
                        + " days unverified: check it, or drop it with the reason"))

    # 4. zombies: a closed note still treated as alive by a current one.
    #    `related` towards a dropped note is legitimate: the cheap link may point
    #    at what was dropped, that is why it is kept. Towards a superseded note
    #    it is not: link to whatever superseded it.
    for i, n in sorted(notes.items()):
        if n["status"] in (SUPERSEDED, DROPPED) or n["history"]:
            continue
        for e in V["edges"]:
            if e == SUPERSEDES:
                continue
            for d in n["links"][e]:
                o = notes.get(d)
                if not o or o["status"] not in (SUPERSEDED, DROPPED):
                    continue
                if e == RELATED and o["status"] == DROPPED:
                    continue
                out.append(("zombie", i, e + ": " + d + " points at a " + o["status"] + " note"))

    # 4a. resting on history: a live note that depends on, or blocks, a note in
    #     history that is still current. Either that note is not past, or the
    #     link is `related`. (Towards a closed one, `zombie` already fires.)
    for i, n in sorted(notes.items()):
        if n["status"] in (SUPERSEDED, DROPPED) or n["history"]:
            continue
        for e in (DEPENDS, BLOCKS):
            for d in n["links"][e]:
                o = notes.get(d)
                if o and o["history"] and o["status"] not in (SUPERSEDED, DROPPED):
                    out.append(("depends on history", i, e + ": " + d + " is in " + HISTORY
                                + "/: move it back to " + NOTES + "/, or the link is " + RELATED))

    # 4b. supersedes: only a closed note can be superseded, and every
    #     superseded note has a successor that says so
    succeeded = set()
    for i, n in sorted(notes.items()):
        for d in n["links"][SUPERSEDES]:
            succeeded.add(d)
            o = notes.get(d)
            if o and o["status"] not in (SUPERSEDED, DROPPED):
                out.append(("supersedes a live note", i, d + " is still '" + o["status"]
                            + "': either it becomes " + SUPERSEDED + ", or the link is wrong"))
    for i, n in sorted(notes.items()):
        if n["status"] == SUPERSEDED and n["id"] not in succeeded and i not in succeeded:
            out.append(("no successor", i, "no note declares it with " + SUPERSEDES))

    # 5. stale blocker: A blocks B, but A is closed - B is free now.
    # Closed means superseded or dropped. An unverified blocker still blocks:
    # checking it is the first job, not a reason to start what it held back.
    for i, n in sorted(notes.items()):
        if n["status"] not in (SUPERSEDED, DROPPED):
            continue
        for d in n["links"][BLOCKS]:
            if d in notes and notes[d]["status"] == CURRENT:
                out.append(("unblocked", d, "was blocked by " + i + ", now " + n["status"]))

    # 5b. permanent block: only a todo can block, because only a todo gets
    #     closed. A fact or a decision that blocks holds its target forever.
    TODO = V["types"][2]
    for i, n in sorted(notes.items()):
        if n["status"] in (SUPERSEDED, DROPPED) or n["type"] == TODO:
            continue
        for d in n["links"][BLOCKS]:
            if d in notes:
                out.append(("permanent block", i, "type '" + n["type"] + "' blocks " + d
                            + ": make it a " + TODO + ", or change the link to "
                            + DEPENDS + " or " + RELATED))

    # 6. propagation: B was reviewed after A, and A said it depends on B, and
    #    B's body is no longer the one A was confirmed against. `notelint
    #    review A` keeps a fingerprint of B; re-confirming B without changing a
    #    word then fires nothing at A. With no fingerprint it fires as it always
    #    did: noisy, never silent.
    prints = read_fingerprints(base)
    for i, n in sorted(notes.items()):
        ra = as_date(n["reviewed"])
        if not ra or n["status"] != CURRENT or n["history"]:
            continue
        for d in n["links"][DEPENDS]:
            o = notes.get(d)
            if not o:
                continue
            rb = as_date(o["reviewed"])
            if rb and rb > ra:
                h = prints.get(i, {}).get(d)
                if h and not o["unreadable"] and h.get("sha") == body_sha(o):
                    continue
                out.append(("propagation", i,
                            d + " was reviewed " + str(rb) + ", this is still at " + str(ra)
                            + (" (and its body changed)" if h else "")))

    # 6b. hidden todo: the ⏳ marker inside a note that is not a todo never
    #     reaches OPEN.md, so the work drops out of sight.
    for i, n in sorted(notes.items()):
        if (n["type"] != TODO and n["status"] == CURRENT and not n["history"]
                and PENDING_MARK in n["body"]):
            out.append(("hidden todo", i, "carries " + PENDING_MARK + " but its type is '"
                        + n["type"] + "': it never shows in " + V["open"]))

    # 6c. past version: a current todo whose file name names a build older than
    #     the installed one, or whose title names an older one as the highest.
    #     It is what is left when a decision changes and a note is fixed inside
    #     but not outside. The name is checked on its own: a corrected title
    #     does not cover an old file name.
    #     Only in projects with a current note carrying `installed-version: N`,
    #     and only vN with as many digits as N: the v2 of a protocol is not a build.
    installed = {}
    for i, n in sorted(notes.items()):
        if not n["installed"] or n["status"] != CURRENT or n["history"]:
            continue
        m = re.fullmatch(r"v?(\d+)", n["installed"].strip().lower())
        if m:
            installed[n["folder"]] = (int(m.group(1)), i)
        else:
            out.append(("format", i, "'" + F["installed"] + "' takes a number or vN: "
                        + n["installed"]))
    for i, n in sorted(notes.items()):
        if (n["folder"] not in installed or n["type"] != TODO or n["status"] != CURRENT
                or n["history"]):
            continue
        v, source = installed[n["folder"]]
        for where, text, pick in (("the name", n["id"], min),
                                  ("the title", n["title"].lower(), max)):
            named = [int(x) for x in RE_VERSION.findall(text) if len(x) == len(str(v))]
            if named and pick(named) < v:
                old = str(pick(named))
                out.append(("past version", i, where + " names v" + old
                            + " and the installed one is v" + str(v) + " (" + source + "): "
                            + "fix it, and search the other notes for v" + old))

    # 7. unclaimed material: something is in the project and no note claims it.
    #    Notes in history still claim what they cite.
    for c in {n["folder"] for n in notes.values()}:
        claimed, cited = claimed_paths([n for n in notes.values() if n["folder"] == c], c)
        for entry in sorted(c.iterdir()):
            if (entry.name in LIVE_FOLDERS + (HISTORY, V["index"], V["open"], V["history"])
                    or entry.name in GENERATED or entry.name.startswith(".")):
                continue
            children = sorted(entry.iterdir()) if entry.is_dir() else []
            for cand in [entry] + children:
                if cand.name.startswith("."):
                    continue
                rel = str(cand.relative_to(c)).replace("\\", "/")
                low = rel.lower()
                if low in claimed or any(low.startswith(d + "/") for d in cited):
                    continue
                out.append(("unclaimed", c.name, rel))

    # 8. probable duplicates, within one project
    live = [(i, keywords(n["title"]), n["folder"].name)
            for i, n in notes.items() if n["status"] == CURRENT and not n["history"]]
    for x in range(len(live)):
        for y in range(x + 1, len(live)):
            a, b = live[x], live[y]
            if a[2] != b[2] or not a[1] or not b[1]:
                continue
            j = len(a[1] & b[1]) / len(a[1] | b[1])
            if j >= 0.6:
                out.append(("duplicate?", a[0],
                            "looks like " + b[0] + " (" + str(int(j * 100)) + "%)"))

    # 9. size. One claim fits in a title and a page; past the caps, the title is
    #    doing the body's job, or the note holds two claims. Closed notes are
    #    left alone, and so is history: nobody is meant to keep reading them.
    for i, n in sorted(notes.items()):
        if n["status"] in (SUPERSEDED, DROPPED) or n["history"]:
            continue
        if len(n["title"]) > MAX_TITLE:
            out.append(("long title", i, str(len(n["title"])) + " characters (limit "
                        + str(MAX_TITLE) + "): the title says what it is, the detail goes in the body"))
        lines = len(n["body"].splitlines())
        if lines > MAX_LINES:
            out.append(("long note", i, str(lines) + " lines (limit " + str(MAX_LINES)
                        + "): it is two notes"))
    return out




# ---------------------------------------------------------------------------
# Generated views. Never edited by hand: delete them and they come back.
# ---------------------------------------------------------------------------
def index_block(group, prefix, V):
    out = []
    for t in V["types"]:
        rows = sorted([n for n in group if n["type"] == t], key=lambda n: n["id"])
        if not rows:
            continue
        out += ["### " + t, ""]
        for n in rows:
            mark = "" if n["status"] == V["statuses"][0] else " `" + n["status"] + "`"
            out.append("- [" + n["title"] + "](" + prefix + in_project(n) + ")" + mark)
        out.append("")
    return out


def history_line(hist, prefix, V):
    """The one mention of history in an index: how many, and where."""
    if not hist:
        return []
    one = len(hist) == 1
    return ["_In `" + prefix + HISTORY + "/`: " + str(len(hist))
            + (" note that no longer describes" if one else " notes that no longer describe")
            + " the present, listed in `" + prefix + V["history"] + "`. "
            + ("It stays" if one else "They stay") + " out of this index, and out of `search` unless you pass `--all`._", ""]


def history_view(c, hist, V):
    """HISTORY.md of one project: a line per note in history/, the most recently
    reviewed first and the undated last. The past at a glance, without opening it."""
    dated = sorted((n for n in hist if as_date(n["reviewed"])),
                   key=lambda n: (as_date(n["reviewed"]), n["id"]), reverse=True)
    undated = sorted((n for n in hist if not as_date(n["reviewed"])), key=lambda n: n["id"])
    out = ["# " + c.name + " - history", "",
           "Generated on " + str(TODAY) + ". **Do not edit by hand.**", "",
           "What already happened in this project, most recent first: "
           + plural(len(hist), "note") + " in `" + HISTORY + "/`. "
           + ("It stays" if len(hist) == 1 else "They stay") + " out of "
           + V["index"] + ", and out of `search` unless you pass `--all`.", ""]
    for n in dated + undated:
        mark = "" if n["status"] == V["statuses"][0] else " `" + n["status"] + "`"
        out.append("- " + (n["reviewed"] if as_date(n["reviewed"]) else "undated") + " · "
                   + (n["type"] or "?") + " · [" + (n["title"] or n["id"]) + "]("
                   + in_project(n) + ")" + mark)
    return out


def in_project(n):
    """A note's file relative to its project: notes/x.md, todo/x.md, ideas/x.md
    or history/x.md."""
    return n["path"].parent.name + "/" + n["id"] + ".md"


def link_to(n, folder_ref):
    """Path to a note's file, relative to wherever the view is written."""
    if folder_ref is None:                      # OPEN.md at the base
        return n["folder"].name + "/" + in_project(n)
    if n["folder"] == folder_ref:               # OPEN.md inside the project
        return in_project(n)
    return "../" + n["folder"].name + "/" + in_project(n)


def blocking_graph(everything, V):
    """children: blocker -> blocked. roots: where each chain starts."""
    CURRENT, UNVERIFIED, BLOCKS = V["statuses"][0], V["statuses"][3], V["edges"][2]
    children, blocked = {}, set()
    for i, n in everything.items():
        # An unverified blocker has not closed; it keeps holding the chain.
        # History holds no open work, so it draws no chain.
        if n["status"] not in (CURRENT, UNVERIFIED) or n["history"]:
            continue
        targets = sorted(d for d in n["links"][BLOCKS] if d in everything)
        if targets:
            children[i] = targets
            blocked.update(targets)
    roots = sorted(i for i in children if i not in blocked)
    return children, blocked, roots


def branch(i, children, everything, folder_ref, level, seen, out):
    """Draw one chain depth-first. `seen` breaks cycles."""
    n = everything[i]
    away = "" if (folder_ref is None or n["folder"] == folder_ref) \
        else " _(" + n["folder"].name + ")_"
    tail = "  <- start here" if level == 0 else ""
    if i in seen:
        out.append("  " * level + "- (cycle) `" + i + "` already appears above")
        return
    seen.add(i)
    out.append("  " * level + "- [" + n["title"] + "](" + link_to(n, folder_ref) + ")"
               + away + tail)
    for c in children.get(i, []):
        branch(c, children, everything, folder_ref, level + 1, seen, out)


def open_block(group, everything, folder_ref, V):
    CURRENT = V["statuses"][0]
    UNVERIFIED = V["statuses"][3]
    TODO = V["types"][2]

    group_ids = {n["id"] for n in group}
    todo = [n for n in group if n["type"] == TODO and n["status"] == CURRENT]
    children, blocked, roots = blocking_graph(everything, V)
    free = sorted([n for n in todo if n["id"] not in blocked], key=lambda n: n["id"])
    doubt = sorted([n for n in group if n["status"] == UNVERIFIED], key=lambda n: n["id"])

    out = ["## Ready to do (" + str(len(free)) + ")", ""]
    for n in free:
        out.append("- [" + n["title"] + "](" + link_to(n, folder_ref) + ")")

    # Chains: the real order of the work, not a flat list of blocked items.
    chains, reached = [], set()
    for r in roots:
        drawing, seen = [], set()
        branch(r, children, everything, folder_ref, 0, seen, drawing)
        if seen & group_ids:                    # this chain touches this project
            chains.append(drawing)
            reached |= (seen & blocked)
    out += ["", "## Work chains (" + str(len(chains)) + ")", "",
            "Each level waits on the one above it. Close a link and the next run",
            "reports the one below as unblocked.", ""]
    for drawing in chains:
        out += drawing + [""]

    # A cycle leaves blocked notes with no root. They must not vanish silently.
    orphans = sorted(i for i in (blocked & group_ids) if i not in reached)
    if orphans:
        out += ["## Blocked inside a cycle (" + str(len(orphans)) + ")", "",
                "These block each other, so none of them can start. Break the cycle.", ""]
        for i in orphans:
            out.append("- [" + everything[i]["title"] + "]("
                       + link_to(everything[i], folder_ref) + ")")
        out.append("")

    out += ["## Unverified, needs checking (" + str(len(doubt)) + ")", ""]
    for n in doubt:
        out.append("- [" + n["title"] + "](" + link_to(n, folder_ref) + ")")
    return out


HOWTO = [
    "## How to use this", "",
    "- One note = one claim with a status. When something changes, **fix the note**;",
    "  stacking a new one on top is how a 115 KB backlog file gets made.",
    "- Before trusting a current note, read its **How to verify** section.",
    "- `OPEN.md` is the work list; this is the content list.", "",
]


def write_view(path, text, force):
    """Write a generated view, unless the file on disk is the user's own.

    The marker common to every view is "**Do not edit by hand", and it is
    independent of --lang because that line is hardcoded in English.
    """
    if path.exists() and not force:
        head = path.read_text(encoding="utf-8-sig", errors="replace")[:400]
        if "**Do not edit by hand" not in head:
            print("  " + path.name + " already exists and was not generated here;"
                  " leaving it alone. Use --force to replace it.")
            return
    # open(), not Path.write_text(newline=...): that argument is 3.10+ and the
    # floor here is 3.8. Without it the views come out CRLF on Windows, against
    # what .gitattributes declares.
    with open(str(path), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def write_views(notes, folders, base, V, force=False):
    out = ["# Knowledge base index", "",
           "Generated by `notelint` on " + str(TODAY) + ". **Do not edit by hand.**",
           ""] + HOWTO
    op = ["# Open work - all projects", "",
          "Generated on " + str(TODAY) + ". **Do not edit by hand** - edit the note's status.",
          ""]
    for c in folders:
        group = [n for n in notes.values() if n["folder"] == c and not n["history"]]
        hist = [n for n in notes.values() if n["folder"] == c and n["history"]]
        out += ["## " + c.name + "  (" + plural(len(group), "note") + ")", ""]
        out += history_line(hist, c.name + "/", V)
        out += index_block(group, c.name + "/", V)
        op += ["# " + c.name, ""] + open_block(group, notes, None, V) + [""]

        pi = ["# " + c.name + " - index", "",
              "Generated on " + str(TODAY) + ". **Do not edit by hand.**", ""] + HOWTO
        pi += history_line(hist, "", V)
        pi += index_block(group, "", V)
        write_view(c / V["index"], "\n".join(pi) + "\n", force)
        po = ["# " + c.name + " - open", "",
              "Generated on " + str(TODAY) + ". **Do not edit by hand.**", ""]
        po += open_block(group, notes, c, V)
        write_view(c / V["open"], "\n".join(po) + "\n", force)
        if hist:
            write_view(c / V["history"], "\n".join(history_view(c, hist, V)) + "\n", force)

    out += oldest_block(notes, V)

    write_view(base / V["index"], "\n".join(out) + "\n", force)
    write_view(base / V["open"], "\n".join(op) + "\n", force)


# ---------------------------------------------------------------------------
# search / open: the cheap lookup. They load the notes and answer; they do not
# lint and do not write the views. They exist so that a question costs one
# command instead of a read of INDEX.md from top to bottom.
# ---------------------------------------------------------------------------
STOP = {"the", "of", "an", "and", "to", "in", "on", "for", "is", "it",
        "de", "del", "la", "el", "los", "las", "en", "y", "a", "por", "que", "un",
        "una", "para", "no", "es", "se", "al", "con", "lo", "su", "sus", "sin", "sobre"}


def terms(words):
    """Search terms: accents folded, filler words dropped. 'pc' is kept."""
    out = []
    for w in words:
        out += [t for t in re.findall(r"[a-z0-9]+", fold(w)) if t not in STOP]
    return out


def matches(t, text):
    """Up to three letters a term must match a whole word ('app' is not
    'happy'); from four on, any part does ('instal' finds 'installer')."""
    if len(t) <= 3:
        return re.search(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])", text) is not None
    return t in text


def search(notes, words, V, project=None, type_=None, status=None, everything=False):
    """The notes that contain EVERY term, best first: hits in the title, then
    current notes, then todos, then the most recently reviewed, and history
    last. Closed notes are left out unless `everything` is set or a status asks
    for them; history, unless `everything` is set."""
    CURRENT, SUPERSEDED, DROPPED = V["statuses"][:3]
    TODO = V["types"][2]
    ts = terms(words)
    hits = []
    for n in notes.values():
        if project and fold(project) not in (fold(n["folder"].name), fold(n["project"])):
            continue
        if type_ and n["type"] != type_:
            continue
        if status and n["status"] != status:
            continue
        if not status and not everything and n["status"] in (SUPERSEDED, DROPPED):
            continue
        if n["history"] and not everything:
            continue
        title = fold(n["title"] + " " + n["id"].replace("-", " "))
        body = fold(n["body"])        # code included: `POLL_INTERVAL` is what gets searched
        if any(not matches(t, title) and not matches(t, body) for t in ts):
            continue
        in_title = sum(1 for t in ts if matches(t, title))
        d = days_unreviewed(n)
        key = (n["history"], -in_title, n["status"] != CURRENT, n["type"] != TODO,
               9999 if d is None else d, n["id"])
        hits.append((key, n))
    hits.sort(key=lambda x: x[0])
    return [n for _, n in hits]


def print_search(hits, words, filters, base, most=15, hidden=0):
    what = " ".join(words) if words else "(no words)"
    label = " · ".join([what] + [k + "=" + v for k, v in filters if v])
    print("")
    print("  " + plural(len(hits), "note") + " · " + label)
    for n in hits[:most]:
        d = days_unreviewed(n)
        # The age of a note in history says nothing: the past is not reviewed.
        age_txt = HISTORY if n["history"] else ("" if d is None else str(d) + "d")
        print("  " + n["type"].ljust(10) + " " + n["status"].ljust(10)
              + age_txt.rjust(8) + "   " + n["path"].relative_to(base).as_posix())
        print(" " * 35 + n["title"])
    if len(hits) > most:
        print("  ... and " + str(len(hits) - most) + " more: narrow the words or the filters.")
    if hidden:
        print("  + " + str(hidden) + " in history or closed: --all shows them.")
    print("")


def launch(target):
    """Hand a path or a URI to whatever the system opens it with."""
    import os, subprocess
    if os.name == "nt":
        os.startfile(target)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", target])
    else:
        subprocess.Popen(["xdg-open", target])


def open_note(notes, ident, V, base, with_=None):
    """Open a note by id. If no note has that id, search its words and open
    only when exactly one matches. The path is always printed, for whoever
    cannot open a window."""
    import shutil, subprocess, urllib.parse
    n = notes.get(ident)
    if n is None:
        same = [m for m in notes.values() if m["id"] == ident]     # a collided name
        hits = same or search(notes, ident.split("-"), V, everything=True)
        if not hits:
            print("No note matches '" + ident + "'.")
            return 1
        if len(hits) > 1:
            print_search(hits, ident.split("-"), [], base)
            print("  More than one: give the exact id.")
            return 1
        n = hits[0]
    p = n["path"]
    print(str(p))
    try:
        if with_ == "code":
            exe = shutil.which("code") or shutil.which("code.cmd")
            if not exe:
                print("'code' is not on the PATH.")
                return 1
            subprocess.Popen([exe, "-g", str(p)])
        elif with_ == "obsidian":
            launch("obsidian://open?path=" + urllib.parse.quote(str(p)))
        else:
            launch(str(p))
    except OSError as e:
        print("Could not open it: " + str(e))
        return 1
    return 0


def query(cmd, argv):
    ap = argparse.ArgumentParser(prog="notelint " + cmd)
    if cmd == "search":
        ap.description = ("Find notes by words (accents ignored; title, id and body) "
                          "and filters. Lints nothing, writes nothing.")
        ap.add_argument("words", nargs="*")
        ap.add_argument("--project", help="only this project")
        ap.add_argument("--type", dest="type_", metavar="TYPE", help="only this type")
        ap.add_argument("--status", help="only this status")
        ap.add_argument("--all", action="store_true",
                        help="include superseded and dropped notes, and history")
    else:
        ap.description = ("Open a note with the system's program, or with Obsidian or "
                          "VS Code, and print its path.")
        ap.add_argument("id", help="the note's id, or words that match only one note")
        ap.add_argument("--with", dest="with_", choices=["obsidian", "code"])
    ap.add_argument("--base", default=".", help="base directory (default: .)")
    ap.add_argument("--lang", choices=sorted(VOCAB), help="field vocabulary (default: detect)")
    a = ap.parse_args(argv)

    base = Path(a.base).resolve()
    if not base.is_dir():
        print("Not a directory: " + str(base))
        return 2
    V = VOCAB[a.lang or detect_lang(base)]
    everything = projects(base)
    if not everything:
        print("No projects found: no directory under " + str(base)
              + " has a notes/, todo/ or ideas/ folder.")
        return 2
    notes = load(everything, V)[0]

    if cmd == "open":
        return open_note(notes, a.id, V, base, a.with_)

    if a.project and fold(a.project) not in {fold(c.name) for c in everything}:
        print("No such project. Available: " + ", ".join(c.name for c in everything))
        return 2
    if a.type_ and a.type_ not in V["types"]:
        print("--type takes: " + ", ".join(V["types"]))
        return 2
    if a.status and a.status not in V["statuses"]:
        print("--status takes: " + ", ".join(V["statuses"]))
        return 2
    if not a.words and not (a.project or a.type_ or a.status):
        print("search needs words or a filter (--project, --type, --status)")
        return 2
    hits = search(notes, a.words, V, a.project, a.type_, a.status, a.all)
    # What --all would add, so that the past is known to exist without opening it.
    hidden = 0 if a.all else len(search(notes, a.words, V, a.project, a.type_,
                                        a.status, True)) - len(hits)
    print_search(hits, a.words, [("project", a.project), ("type", a.type_),
                                 ("status", a.status), ("all", "yes" if a.all else "")],
                 base, hidden=hidden)
    return 0 if hits else 1


# ---------------------------------------------------------------------------
# new / review / close: the three writes a routine needs. They put the
# template and today's date where they belong, so that nobody copies a note
# from memory and gets its format wrong. They decide nothing: what a note says
# is still up to whoever writes it.
# ---------------------------------------------------------------------------
RE_ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def read_raw(path):
    """(text, bom, eol) of a file as it is, so it can be written back the same way."""
    data = path.read_bytes()
    bom = data.startswith(b"\xef\xbb\xbf")
    text = (data[3:] if bom else data).decode("utf-8")
    eol = "\r\n" if "\r\n" in text else "\n"
    return text.replace("\r\n", "\n"), bom, eol


def write_raw(path, text, bom, eol):
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.replace("\n", eol).encode("utf-8"))


def set_fields(text, fields):
    """Change top-level frontmatter fields ('key: value'). A field that is not
    there is added at the end of the header."""
    if not text.startswith("---") or "\n---" not in text[3:]:
        raise ValueError("no closed frontmatter")
    end = text.index("\n---", 3)
    lines, rest = text[:end].split("\n"), text[end:]
    for key, value in fields.items():
        new = key + ": " + value if value else key + ":"
        for k, line in enumerate(lines):
            if k and re.match(re.escape(key) + r"\s*:", line):
                lines[k] = new
                break
        else:
            lines.append(new)
    return "\n".join(lines) + rest


def writer_args(prog, description):
    ap = argparse.ArgumentParser(prog="notelint " + prog, description=description)
    ap.add_argument("--base", default=".", help="base directory (default: .)")
    ap.add_argument("--lang", choices=sorted(VOCAB), help="field vocabulary (default: detect)")
    return ap


def open_base(a):
    """(base, V, projects), or an exit code when there is nothing to work on."""
    base = Path(a.base).resolve()
    if not base.is_dir():
        print("Not a directory: " + str(base))
        return 2
    V = VOCAB[a.lang or detect_lang(base)]
    return base, V, projects(base)


def rel(path, base):
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return str(path)


def cmd_new(argv):
    ap = writer_args("new", "Create a note from the template, dated today, in the folder "
                            "its type belongs to (a todo in todo/, an idea in ideas/, the "
                            "rest in notes/), and print its path.")
    ap.add_argument("project")
    ap.add_argument("type")
    ap.add_argument("id", help="lowercase words joined by hyphens: the file name")
    ap.add_argument("--title", required=True, help="the claim, in one line")
    ap.add_argument("--folder", choices=LIVE_FOLDERS, help="file it somewhere else")
    a = ap.parse_args(argv)
    got = open_base(a)
    if isinstance(got, int):
        return got
    base, V, everything = got
    c = next((d for d in everything if fold(d.name) == fold(a.project)), None)
    if c is None:
        print("No such project" + (". Available: " + ", ".join(d.name for d in everything)
                                   if everything else "") + ".")
        print("To start one, create " + rel(base / a.project / NOTES, base) + "/ first.")
        return 2
    if a.type not in V["types"]:
        print("The type is one of: " + ", ".join(V["types"]))
        return 2
    if not RE_ID.match(a.id):
        print("An id is lowercase letters, digits and hyphens: " + a.id)
        return 2
    if len(a.title) > MAX_TITLE:
        print("The title has " + str(len(a.title)) + " characters (limit " + str(MAX_TITLE)
              + "): the title says what it is, the detail goes in the body.")
        return 2
    notes = load(everything, V)[0]
    same = [n for n in notes.values() if n["id"] == a.id]
    if same:
        print("That id already exists: " + rel(same[0]["path"], base))
        return 2
    TODO, IDEA = V["types"][2], V["types"][3]
    sub = a.folder or {TODO: TODO_DIR, IDEA: IDEAS_DIR}.get(a.type, NOTES)
    dest = c / sub / (a.id + ".md")
    F, today = V["fields"], str(TODAY)
    head = (["---", F["title"] + ": " + a.title, F["type"] + ": " + a.type,
             F["project"] + ": " + c.name, F["status"] + ": " + V["statuses"][0],
             F["created"] + ": " + today, F["reviewed"] + ": " + today,
             F["expires"] + ":", F["evidence"] + ":", F["links"] + ":"]
            + ["  " + e + ": []" for e in V["edges"]] + ["---", ""])
    body = (["## " + V["the_idea"], ""] if a.type == IDEA
            else ["## " + V["what"], "", "## " + V["verify"], ""])
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(str(dest), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(head + body))
    print(rel(dest, base))
    if a.type == IDEA:
        print("  Fill in '" + V["the_idea"] + "'.")
    else:
        print("  Fill in '" + V["what"] + "' and '" + V["verify"]
              + "'; the linter reports the note until the second one says something.")
    return 0


def cmd_review(argv):
    ap = writer_args("review", "Set 'reviewed' to today on notes you have just confirmed, "
                               "and keep a fingerprint of what they depend on, so that "
                               "confirming a dependency unchanged fires no propagation.")
    ap.add_argument("ids", nargs="+", metavar="id")
    a = ap.parse_args(argv)
    got = open_base(a)
    if isinstance(got, int):
        return got
    base, V, everything = got
    notes = load(everything, V)[0]
    missing = [i for i in a.ids if i not in notes]
    if missing:
        print("No such note: " + ", ".join(missing))
        return 2
    done = []
    for i in a.ids:
        n = notes[i]
        try:
            text, bom, eol = read_raw(n["path"])
            text = set_fields(text, {V["fields"]["reviewed"]: str(TODAY)})
        except (OSError, UnicodeDecodeError, ValueError) as e:
            print("  " + i + ": left alone (" + str(e) + ")")
            continue
        write_raw(n["path"], text, bom, eol)
        done.append(i)
        print("  reviewed " + str(TODAY) + "  " + rel(n["path"], base))
    if done:
        save_fingerprints(base, notes, done, V)
    return 0 if len(done) == len(a.ids) else 1


def cmd_close(argv):
    ap = writer_args("close", "Close a todo that is done: it becomes a fact in its own "
                              "note, with the line that says until when it was a todo. "
                              "If no live note depends on it, it goes to history/; if "
                              "one does, or with --keep, to notes/.")
    ap.add_argument("id")
    ap.add_argument("--title", help="the new title, as a claim of what is now true")
    ap.add_argument("--keep", action="store_true", help="file it in notes/, not history/")
    a = ap.parse_args(argv)
    got = open_base(a)
    if isinstance(got, int):
        return got
    base, V, everything = got
    notes = load(everything, V)[0]
    n = notes.get(a.id)
    if n is None:
        print("No such note: " + a.id)
        return 2
    CURRENT, SUPERSEDED, DROPPED, UNVERIFIED = V["statuses"]
    FACT, TODO = V["types"][1], V["types"][2]
    DEPENDS, BLOCKS = V["edges"][0], V["edges"][2]
    if n["unreadable"] or n["type"] != TODO or n["status"] not in (CURRENT, UNVERIFIED):
        print(a.id + " is '" + n["type"] + "' '" + n["status"] + "': close is for a "
              + TODO + " that is " + CURRENT + " or " + UNVERIFIED + ".")
        return 2
    if n["links"][BLOCKS]:
        print(a.id + " blocks " + ", ".join(n["links"][BLOCKS]) + ". A " + FACT + " cannot "
              "block: empty '" + BLOCKS + "' first if they no longer wait on it, or "
              "supersede it with a new note.")
        return 2
    if a.title and len(a.title) > MAX_TITLE:
        print("The title has " + str(len(a.title)) + " characters (limit " + str(MAX_TITLE) + ").")
        return 2
    F, today = V["fields"], str(TODAY)
    try:
        text, bom, eol = read_raw(n["path"])
        fields = {F["type"]: FACT, F["reviewed"]: today}
        if a.title:
            fields[F["title"]] = a.title
        text = set_fields(text, fields)
    except (OSError, UnicodeDecodeError, ValueError) as e:
        print(a.id + ": left alone (" + str(e) + ")")
        return 2
    end = text.index("\n---", 3) + 4
    end = text.index("\n", end) + 1 if "\n" in text[end:] else len(text)
    text = (text[:end] + "\n**" + V["was_todo"].format(date=today) + "**\n\n"
            + text[end:].lstrip("\n"))
    write_raw(n["path"], text, bom, eol)
    # Where it ends up: if something live rests on it, it is still part of the
    # present and stays in notes/; if nothing does, it is the past.
    live = [o for o in notes.values() if o is not n and not o["history"]
            and o["status"] not in (SUPERSEDED, DROPPED)]
    resting = sorted(o["id"] for o in live if a.id in o["links"][DEPENDS])
    holding = sorted(o["id"] for o in live if a.id in o["links"][BLOCKS])
    sub = NOTES if (resting or holding or a.keep) else HISTORY
    dest = n["folder"] / sub / n["path"].name
    if dest != n["path"]:
        if dest.exists():
            print("There is already a " + rel(dest, base) + ": it stays where it was.")
            dest = n["path"]
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            os.replace(str(n["path"]), str(dest))
    closed = parse(dest, n["folder"], V)
    closed["history"] = dest.parent.name == HISTORY
    notes[a.id] = closed
    save_fingerprints(base, notes, [a.id], V)
    print(rel(dest, base))
    if dest.parent.name == HISTORY:
        print("  Filed in " + HISTORY + "/: nothing live depends on it.")
    elif resting or holding:
        # Two different reasons, and only the first is "rests on it": a note
        # that still names this one under 'blocks' does not depend on it.
        why = []
        if resting:
            why.append(", ".join(resting)
                       + (" rests" if len(resting) == 1 else " rest") + " on it")
        if holding:
            why.append(", ".join(holding)
                       + (" still lists" if len(holding) == 1 else " still list")
                       + " it under '" + BLOCKS + "'")
        print("  Stays in " + NOTES + "/: " + " and ".join(why) + ".")
    print("  It is a " + FACT + " now. Rewrite the title as a claim"
          + (" (the new one is in)" if a.title else "")
          + " and '" + V["verify"] + "' so it checks that the work is done.")
    return 0


WRITERS = {"new": cmd_new, "review": cmd_review, "close": cmd_close}

# The id column of the findings when nothing wraps them, and the narrowest a
# wrapped message may get: below that it reads worse than a line that runs over.
ID_COLUMN, NARROWEST = 42, 24


def report_width(asked):
    """How wide the findings may run, or None for one line each. --width says
    so outright (0: never wrap). Without it a terminal gets its own width, and
    anything else - a pipe, a file, a CI log - gets whole lines, so that grep
    and diff see one finding per line."""
    if asked is not None:
        return asked or None
    try:
        if sys.stdout.isatty():
            return shutil.get_terminal_size().columns
    except (AttributeError, ValueError, OSError):
        pass
    return None


def finding_lines(rows, width, column):
    """The printed lines of one category. Unwrapped, the layout the report
    has always had. Wrapped, the id column shrinks to `column` - the longest
    id in the report - and a message that runs past `width` continues under
    its own start. Words are never split, so a path stays in one piece even
    when that leaves a line too long."""
    if not width:
        return ["    " + i.ljust(ID_COLUMN) + " " + d for i, d in rows]
    start = 4 + column
    lines = []
    for i, d in rows:
        # A wide character (the hourglass of a hidden todo) takes two cells.
        wide = sum(1 for ch in d if unicodedata.east_asian_width(ch) in "WF")
        room = max(width - start - wide, NARROWEST)
        parts = textwrap.wrap(d, room, break_long_words=False,
                              break_on_hyphens=False) or [""]
        lines.append(("    " + (i + "  ").ljust(column) + parts[0]).rstrip())
        lines.extend(" " * start + more for more in parts[1:])
    return lines


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv and argv[0] in ("search", "open"):
        return query(argv[0], argv[1:])
    if argv and argv[0] in WRITERS:
        return WRITERS[argv[0]](argv[1:])

    ap = argparse.ArgumentParser(
        prog="notelint", description="A linter for a knowledge base of project notes.",
        epilog="Lookups that lint nothing: 'notelint search -h' and 'notelint open -h'. "
               "Writes: 'notelint new -h', 'notelint review -h', 'notelint close -h'.")
    ap.add_argument("base", nargs="?", default=".", help="base directory (default: .)")
    ap.add_argument("--project", action="append", default=[],
                    help="report on this project only (repeatable)")
    ap.add_argument("--lang", choices=sorted(VOCAB), help="field vocabulary (default: detect)")
    ap.add_argument("--report-only", action="store_true",
                    help="do not write INDEX.md / OPEN.md / HISTORY.md")
    ap.add_argument("--force", action="store_true",
                    help="overwrite INDEX.md / OPEN.md / HISTORY.md even if this tool "
                         "did not write them")
    ap.add_argument("--exit-zero", action="store_true", help="always exit 0")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 on reviews too, not only on errors")
    ap.add_argument("--verify", nargs="?", type=int, const=-1, metavar="DAYS",
                    help="print every 'How to verify' section, dependencies first; "
                         "with DAYS, only notes unreviewed for longer than that")
    ap.add_argument("--width", type=int, metavar="N",
                    help="wrap the findings at N columns (default: the terminal's width; "
                         "one line each when piped or redirected). 0 never wraps")
    ap.add_argument("--version", action="version", version="notelint " + __version__)
    a = ap.parse_args(argv)
    if a.width is not None and a.width < 0:
        ap.error("--width takes 0 or a positive number of columns")

    base = Path(a.base).resolve()
    if not base.is_dir():
        print("Not a directory: " + str(base))
        return 2
    V = VOCAB[a.lang or detect_lang(base)]

    everything = projects(base)
    if not everything:
        print("No projects found: no directory under " + str(base)
              + " has a notes/, todo/ or ideas/ folder.")
        return 2
    folders = everything
    if a.project:
        want = {fold(p) for p in a.project}
        folders = [c for c in everything if fold(c.name) in want]
        if not folders:
            print("No such project. Available: " + ", ".join(c.name for c in everything))
            return 2

    # Every project is loaded even under --project: links cross project
    # boundaries, so a dependency living in an unselected project is not a
    # broken link. The selection narrows the report, not the graph.
    everything_notes, clashes, ambiguous = load(everything, V)

    if a.verify is not None:
        print_verifications(everything_notes, folders, V, None if a.verify < 0 else a.verify)
        return 0

    findings = check(everything_notes, clashes, base, V, ambiguous)
    notes = everything_notes
    if folders is not everything:
        names = {c.name for c in folders}
        notes = {i: n for i, n in everything_notes.items() if n["folder"].name in names}
        # The inbox belongs to the whole base, so it shows under any selection.
        mine = (set(notes) | names | {V["inbox"]}
                | {i for i, p, q in clashes if p in names or q in names})
        findings = [f for f in findings if f[1] in mine]

    past = sum(1 for n in notes.values() if n["history"])
    print("")
    print("  notelint - " + plural(len(notes) - past, "note") + " in "
          + plural(len(folders), "project")
          + (", " + str(past) + " in history" if past else "")
          + "   (" + str(TODAY) + ")")
    print("  " + "-" * 66)
    for c in folders:
        g = [n for n in notes.values() if n["folder"] == c and not n["history"]]
        todo = sum(1 for n in g if n["type"] == V["types"][2]
                   and n["status"] == V["statuses"][0])
        doubt = sum(1 for n in g if n["status"] == V["statuses"][3])
        gone = sum(1 for n in notes.values() if n["folder"] == c and n["history"])
        print("  " + c.name.ljust(20) + str(len(g)).rjust(4)
              + (" note    " if len(g) == 1 else " notes   ")
              + str(todo).rjust(3) + " open   " + str(doubt).rjust(3) + " unverified"
              + ("   " + str(gone).rjust(3) + " in history" if past else ""))
    print("  " + "-" * 66)

    buckets = {}
    for cat, i, d in findings:
        buckets.setdefault(cat, []).append((i, d))
    known = set(ERRORS) | set(REVIEWS)
    # A category missing from both lists still prints, under errors, rather than vanish.
    error_cats = ERRORS + sorted(k for k in buckets if k not in known)
    n_err = sum(len(buckets[c]) for c in error_cats if c in buckets)
    n_rev = sum(len(buckets[c]) for c in REVIEWS if c in buckets)
    if not findings:
        print("")
        print("  No findings. Every link resolves, every claim has live evidence.")
        print("")
    else:
        pos = topo_order(everything_notes, V)
        width = report_width(a.width)
        # One column for the whole report, so every category lines up.
        column = min(max(len(i) for _, i, _ in findings), ID_COLUMN) + 3
        for level, total, cats, hint in (
                ("ERRORS", n_err, error_cats, "written wrong or broken: these go to zero"),
                ("REVIEWS", n_rev, REVIEWS, "a queue: work down a few each session, oldest first")):
            if not total:
                continue
            print("")
            print("  " + "=" * 66)
            print("  " + level + " (" + str(total) + ")  - " + hint)
            for cat in cats:
                if cat not in buckets:
                    continue
                print("")
                print("  " + cat.upper() + "  (" + str(len(buckets[cat])) + ")")
                if cat in ("unreviewed", "propagation"):
                    # Dependencies first: reviewed in this order, they do not
                    # fire propagation findings at each other.
                    rows = sorted(buckets[cat], key=lambda x: (pos.get(x[0], 0), x[0]))
                else:
                    rows = sorted(buckets[cat])
                for line in finding_lines(rows, width, column):
                    print(line)
        print("")
        print("  errors: " + str(n_err) + " · reviews: " + str(n_rev))
        print("")

    if not a.report_only:
        write_views(everything_notes, everything, base, V, a.force)
        print("  " + V["index"] + " and " + V["open"] + " regenerated, and " + V["history"]
              + " in each project with a history.")
        print("")

    failing = n_err + (n_rev if a.strict else 0)
    return 0 if (a.exit_zero or not failing) else 1


if __name__ == "__main__":
    sys.exit(main())
