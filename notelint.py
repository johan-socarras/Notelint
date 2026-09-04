#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
notelint - a linter for a knowledge base of project notes.

Documentation does not rot because people are lazy. It rots because nothing
ever checks whether it is still true. notelint checks.

Point it at a directory. Every subdirectory that contains a `notes/` folder is
a project. Notes are global across projects (links may cross), but each project
also gets its own index and its own list of open work.

    python notelint.py                 # lint the current directory, write indexes
    python notelint.py path/to/base    # lint somewhere else
    python notelint.py --report-only   # do not write INDEX.md / OPEN.md
    python notelint.py --lang es       # Spanish field names
    python notelint.py --project Alpha # report on one project only

Exit code is 1 when there are findings, so it works in CI. Use --exit-zero to
always exit 0.

No dependencies. Python 3.8+.
"""
import sys, re, datetime, unicodedata, argparse
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

TODAY = datetime.date.today()
DAYS_UNREVIEWED = 60

# Directories at the base that are never projects.
NEVER_A_PROJECT = {"templates", "tools", "docs", ".git", ".github", "node_modules"}

# Regenerable junk: not material that anyone should have to claim with a note.
GENERATED = {"__pycache__", ".pytest_cache", ".mypy_cache", "node_modules",
             "target", ".venv", "venv"}

# ---------------------------------------------------------------------------
# Vocabulary. The note format is the same in every language; only the field
# names change, so a team can keep notes in its own language.
# ---------------------------------------------------------------------------
VOCAB = {
    "en": {
        "fields": {"title": "title", "type": "type", "project": "project",
                   "status": "status", "created": "created", "reviewed": "reviewed",
                   "expires": "expires", "evidence": "evidence", "links": "links"},
        "types": ["decision", "fact", "todo", "idea", "incident", "reference"],
        "statuses": ["current", "superseded", "dropped", "unverified"],
        "edges": ["depends-on", "supersedes", "blocks", "related"],
        "index": "INDEX.md", "open": "OPEN.md",
    },
    "es": {
        "fields": {"title": "titulo", "type": "tipo", "project": "proyecto",
                   "status": "estado", "created": "creada", "reviewed": "revisada",
                   "expires": "caduca", "evidence": "evidencia", "links": "enlaces"},
        "types": ["decision", "hecho", "pendiente", "idea", "incidente", "referencia"],
        "statuses": ["vigente", "superado", "descartado", "en-duda"],
        "edges": ["depende-de", "supera-a", "bloquea", "relacionada"],
        "index": "INDICE.md", "open": "ABIERTO.md",
    },
}

RE_WIKI = re.compile(r"\[\[([^\]|#]+)")
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


def detect_lang(base):
    """Pick the vocabulary whose status field appears in the notes."""
    for note in base.glob("*/notes/*.md"):
        head = note.read_text(encoding="utf-8", errors="replace")[:600]
        for lang, v in VOCAB.items():
            if re.search(r"^" + v["fields"]["status"] + r"\s*:", head, re.M):
                return lang
    return "en"


def projects(base):
    out = []
    for d in sorted(base.iterdir()):
        if (d.is_dir() and d.name not in NEVER_A_PROJECT
                and not d.name.startswith(".") and (d / "notes").is_dir()):
            out.append(d)
    return out


# ---------------------------------------------------------------------------
# Parsing. A deliberately small YAML subset, so the tool stays dependency-free
# and the format stays simple enough to write by hand.
# ---------------------------------------------------------------------------
def parse(path, folder, V):
    F, E = V["fields"], V["edges"]
    txt = path.read_text(encoding="utf-8")
    n = {"id": path.stem, "path": path, "folder": folder, "body": "", "errors": []}
    for k in ("title", "type", "project", "status", "created", "reviewed", "expires"):
        n[k] = ""
    n["evidence"] = []
    n["links"] = {e: [] for e in E}
    back = {v: k for k, v in F.items()}

    if not txt.startswith("---"):
        n["errors"].append("no frontmatter")
        n["body"] = txt
        return n
    parts = txt.split("\n---", 1)
    head = parts[0][3:]
    n["body"] = parts[1] if len(parts) > 1 else ""

    section = None
    for line in head.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        s = line.strip()
        if indent == 0 and ":" in s:
            key, _, val = s.partition(":")
            key, val = key.strip(), val.strip()
            section = None
            if key == F["evidence"] or key == F["links"]:
                section = back[key]
                if val:
                    n["errors"].append("'" + key + ":' takes a list on following lines")
            elif key in back:
                n[back[key]] = val
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
            n["links"][key] = [x.strip() for x in val.split(",") if x.strip()]
    return n


def load(folders, V):
    notes, clashes = {}, []
    for c in folders:
        for p in sorted((c / "notes").glob("*.md")):
            n = parse(p, c, V)
            if n["id"] in notes:
                clashes.append((n["id"], notes[n["id"]]["folder"].name, c.name))
                continue
            notes[n["id"]] = n
    return notes, clashes


def keywords(t):
    stop = {"the", "and", "for", "with", "that", "this", "from", "into", "not",
            "los", "las", "del", "para", "por", "que", "una", "con", "sin", "mas"}
    return {w for w in re.findall(r"[a-z0-9]+", fold(t)) if w not in stop and len(w) > 3}


def evidence_exists(e, folder, base):
    if e.startswith("http://") or e.startswith("https://"):
        return True
    raw = e.split(" §")[0].split(" (")[0].split(" —")[0].strip().replace("\\", "/")
    p = Path(raw)
    if p.is_absolute():
        return p.exists()
    return (folder / raw).exists() or (base / raw).exists()


# ---------------------------------------------------------------------------
# The checks.
# ---------------------------------------------------------------------------
def check(notes, clashes, base, V):
    out = []
    CURRENT, SUPERSEDED, DROPPED, UNVERIFIED = V["statuses"]
    DEPENDS, SUPERSEDES, BLOCKS, RELATED = V["edges"]
    ids = set(notes)

    for i, a, b in clashes:
        out.append(("duplicate id", i, "exists in " + a + " and in " + b))

    for i, n in sorted(notes.items()):
        for e in n["errors"]:
            out.append(("format", i, e))
        if n["type"] not in V["types"]:
            out.append(("format", i, "invalid type: " + repr(n["type"])))
        if n["status"] not in V["statuses"]:
            out.append(("format", i, "invalid status: " + repr(n["status"])))
        if not n["title"]:
            out.append(("format", i, "no title"))
        if fold(n["project"]) != fold(n["folder"].name):
            out.append(("wrong project", i,
                        "says '" + n["project"] + "' but lives in " + n["folder"].name))

        # 1. broken links
        targets = set()
        for e in V["edges"]:
            targets |= set(n["links"][e])
        targets |= set(m.strip() for m in RE_WIKI.findall(strip_code(n["body"])))
        for d in sorted(targets):
            if d not in ids:
                out.append(("broken link", i, "[[" + d + "]] does not exist"))

        # 2. evidence that no longer exists on disk
        for e in n["evidence"]:
            if not evidence_exists(e, n["folder"], base):
                out.append(("dead evidence", i, e))

        # 3. expired, or unreviewed for too long
        if n["status"] == CURRENT:
            x = as_date(n["expires"])
            if x and x < TODAY:
                out.append(("expired", i, "expired on " + str(x) + " and still current"))
            r = as_date(n["reviewed"])
            if r and (TODAY - r).days > DAYS_UNREVIEWED:
                out.append(("unreviewed", i, str((TODAY - r).days) + " days since last review"))
            if not r:
                out.append(("format", i, "'reviewed' missing or malformed"))

    # 4. zombies: a closed note still treated as alive by a current one
    for i, n in sorted(notes.items()):
        if n["status"] != CURRENT:
            continue
        for e in V["edges"]:
            if e == SUPERSEDES:
                continue
            for d in n["links"][e]:
                o = notes.get(d)
                if o and o["status"] in (SUPERSEDED, DROPPED):
                    out.append(("zombie", i, e + ": " + d + " points at a " + o["status"] + " note"))

    # 5. stale blocker: A blocks B, but A is closed - B is free now
    for i, n in sorted(notes.items()):
        if n["status"] == CURRENT:
            continue
        for d in n["links"][BLOCKS]:
            if d in notes and notes[d]["status"] == CURRENT:
                out.append(("unblocked", d, "was blocked by " + i + ", now " + n["status"]))

    # 6. propagation: B was reviewed after A, and A said it depends on B
    for i, n in sorted(notes.items()):
        ra = as_date(n["reviewed"])
        if not ra or n["status"] != CURRENT:
            continue
        for d in n["links"][DEPENDS]:
            o = notes.get(d)
            if not o:
                continue
            rb = as_date(o["reviewed"])
            if rb and rb > ra:
                out.append(("propagation", i,
                            d + " was reviewed " + str(rb) + ", this is still at " + str(ra)))

    # 7. unclaimed material: something is in the project and no note mentions it
    for c in {n["folder"] for n in notes.values()}:
        blob = "\n".join(n["title"] + "\n" + n["body"] + "\n" + "\n".join(n["evidence"])
                         for n in notes.values() if n["folder"] == c)
        for entry in sorted(c.iterdir()):
            if (entry.name in ("notes", V["index"], V["open"])
                    or entry.name in GENERATED or entry.name.startswith(".")):
                continue
            children = sorted(entry.iterdir()) if entry.is_dir() else []
            for cand in [entry] + children:
                if cand.name.startswith("."):
                    continue
                if cand.name not in blob:
                    out.append(("unclaimed", c.name,
                                str(cand.relative_to(c)).replace("\\", "/")))

    # 8. probable duplicates, within one project
    live = [(i, keywords(n["title"]), n["folder"].name)
            for i, n in notes.items() if n["status"] == CURRENT]
    for x in range(len(live)):
        for y in range(x + 1, len(live)):
            a, b = live[x], live[y]
            if a[2] != b[2] or not a[1] or not b[1]:
                continue
            j = len(a[1] & b[1]) / len(a[1] | b[1])
            if j >= 0.6:
                out.append(("duplicate?", a[0],
                            "looks like " + b[0] + " (" + str(int(j * 100)) + "%)"))
    return out


ORDER = ["duplicate id", "format", "wrong project", "broken link", "dead evidence",
         "expired", "unreviewed", "zombie", "unblocked", "propagation",
         "unclaimed", "duplicate?"]


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
            out.append("- [" + n["title"] + "](" + prefix + "notes/" + n["id"] + ".md)" + mark)
        out.append("")
    return out


def link_to(n, folder_ref):
    """Path to a note's file, relative to wherever the view is written."""
    if folder_ref is None:                      # OPEN.md at the base
        return n["folder"].name + "/notes/" + n["id"] + ".md"
    if n["folder"] == folder_ref:               # OPEN.md inside the project
        return "notes/" + n["id"] + ".md"
    return "../" + n["folder"].name + "/notes/" + n["id"] + ".md"


def blocking_graph(everything, V):
    """children: blocker -> blocked. roots: where each chain starts."""
    CURRENT, BLOCKS = V["statuses"][0], V["edges"][2]
    children, blocked = {}, set()
    for i, n in everything.items():
        if n["status"] != CURRENT:
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


def write_views(notes, folders, base, V):
    out = ["# Knowledge base index", "",
           "Generated by `notelint` on " + str(TODAY) + ". **Do not edit by hand.**",
           ""] + HOWTO
    op = ["# Open work - all projects", "",
          "Generated on " + str(TODAY) + ". **Do not edit by hand** - edit the note's status.",
          ""]
    for c in folders:
        group = [n for n in notes.values() if n["folder"] == c]
        out += ["## " + c.name + "  (" + str(len(group)) + " notes)", ""]
        out += index_block(group, c.name + "/", V)
        op += ["# " + c.name, ""] + open_block(group, notes, None, V) + [""]

        pi = ["# " + c.name + " - index", "",
              "Generated on " + str(TODAY) + ". **Do not edit by hand.**", ""] + HOWTO
        pi += index_block(group, "", V)
        (c / V["index"]).write_text("\n".join(pi) + "\n", encoding="utf-8")
        po = ["# " + c.name + " - open", "",
              "Generated on " + str(TODAY) + ". **Do not edit by hand.**", ""]
        po += open_block(group, notes, c, V)
        (c / V["open"]).write_text("\n".join(po) + "\n", encoding="utf-8")

    (base / V["index"]).write_text("\n".join(out) + "\n", encoding="utf-8")
    (base / V["open"]).write_text("\n".join(op) + "\n", encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="notelint", description="A linter for a knowledge base of project notes.")
    ap.add_argument("base", nargs="?", default=".", help="base directory (default: .)")
    ap.add_argument("--project", action="append", default=[],
                    help="report on this project only (repeatable)")
    ap.add_argument("--lang", choices=sorted(VOCAB), help="field vocabulary (default: detect)")
    ap.add_argument("--report-only", action="store_true", help="do not write the indexes")
    ap.add_argument("--exit-zero", action="store_true", help="always exit 0")
    a = ap.parse_args(argv)

    base = Path(a.base).resolve()
    if not base.is_dir():
        print("Not a directory: " + str(base))
        return 2
    V = VOCAB[a.lang or detect_lang(base)]

    everything = projects(base)
    if not everything:
        print("No projects found: no directory under " + str(base) + " has a notes/ folder.")
        return 2
    folders = everything
    if a.project:
        want = {fold(p) for p in a.project}
        folders = [c for c in everything if fold(c.name) in want]
        if not folders:
            print("No such project. Available: " + ", ".join(c.name for c in everything))
            return 2

    notes, clashes = load(folders, V)
    findings = check(notes, clashes, base, V)

    print("")
    print("  notelint - " + str(len(notes)) + " notes in "
          + str(len(folders)) + " project(s)   (" + str(TODAY) + ")")
    print("  " + "-" * 66)
    for c in folders:
        g = [n for n in notes.values() if n["folder"] == c]
        todo = sum(1 for n in g if n["type"] == V["types"][2]
                   and n["status"] == V["statuses"][0])
        doubt = sum(1 for n in g if n["status"] == V["statuses"][3])
        print("  " + c.name.ljust(20) + str(len(g)).rjust(4) + " notes   "
              + str(todo).rjust(3) + " open   " + str(doubt).rjust(3) + " unverified")
    print("  " + "-" * 66)

    if not findings:
        print("")
        print("  No findings. Every link resolves, every claim has live evidence.")
        print("")
    else:
        buckets = {}
        for cat, i, d in findings:
            buckets.setdefault(cat, []).append((i, d))
        for cat in ORDER:
            if cat not in buckets:
                continue
            print("")
            print("  " + cat.upper() + "  (" + str(len(buckets[cat])) + ")")
            for i, d in sorted(buckets[cat]):
                print("    " + i.ljust(42) + " " + d)
        print("")

    if not a.report_only:
        all_notes = load(everything, V)[0]
        write_views(all_notes, everything, base, V)
        print("  " + V["index"] + " and " + V["open"] + " regenerated.")
        print("")

    return 0 if (a.exit_zero or not findings) else 1


if __name__ == "__main__":
    sys.exit(main())
