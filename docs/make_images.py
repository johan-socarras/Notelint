#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Draws the two pictures in the README from the bundled example.

    python docs/make_images.py            # rewrites docs/report.svg and docs/graph.svg
    python docs/make_images.py --check    # exit 1 if either file would change

Nothing in them is typed by hand. `report.svg` is what `notelint.py` prints
for `example/` at 80 columns; `graph.svg` is the notes, the links and the
findings that `notelint.py` itself loads and reports. The one thing chosen
here is where each box of the graph sits (LAYOUT, below): if the example
gains or loses a note, this script stops and says so instead of drawing a
picture that is no longer the example.

The date is pinned. The report prints today's date and ages the notes from
it, so without a fixed day the picture would change every morning and, two
months on, fill with `unreviewed` findings that are not planted faults.

No dependencies, Python 3.8+, like the linter.
"""
import io, sys, datetime, contextlib
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import notelint  # noqa: E402

DAY = datetime.date(2026, 11, 10)   # the day the example was last brought up to date
WIDTH = 80                          # columns of the report, as in the README
EXAMPLE = ROOT / "example"
PROJECT = "Kestrel"

MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'DejaVu Sans Mono', monospace"
SANS = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
BG, PANEL, LINE = "#0d1117", "#161b22", "#30363d"
TEXT, MUTED, FAINT = "#e6edf3", "#8b949e", "#6e7681"
ERROR, REVIEW = "#f85149", "#d29922"


# ---------------------------------------------------------------- the report

def report():
    """The linter's own output for the example, on DAY, at WIDTH columns."""
    notelint.TODAY = DAY
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        notelint.main([str(EXAMPLE), "--report-only", "--width", str(WIDTH)])
    return out.getvalue().strip("\n").split("\n")


def report_svg(lines):
    size, lead, cell, pad, bar = 14, 20, 8.6, 24, 38
    w = round(WIDTH * cell + 2 * pad)
    h = bar + pad + len(lines) * lead + pad - 6
    o = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" '
         'height="%d" role="img" aria-label="The report notelint prints for the '
         'bundled example: four errors and one review">' % (w, h, w, h),
         '<rect width="%d" height="%d" rx="10" fill="%s" stroke="%s"/>' % (w, h, BG, LINE),
         '<path d="M0 %d V10 A10 10 0 0 1 10 0 H%d A10 10 0 0 1 %d 10 V%d Z" fill="%s"/>'
         % (bar, w - 10, w, bar, PANEL),
         '<path d="M0 %d H%d" stroke="%s"/>' % (bar, w, LINE)]
    for k in range(3):
        o.append('<circle cx="%d" cy="%d" r="6" fill="%s"/>' % (22 + 20 * k, bar // 2, LINE))
    o.append('<text x="%d" y="%d" text-anchor="middle" font-family="%s" font-size="13" '
             'fill="%s">python notelint.py example --report-only --width 80</text>'
             % (w // 2, bar // 2 + 5, MONO, MUTED))
    o.append('<g font-family="%s" font-size="%d" fill="%s">' % (MONO, size, TEXT))
    y = bar + pad + size - 4
    for line in lines:
        if line.strip():
            # Both spellings of "keep my spaces": the columns of the report
            # are made of them.
            o.append('<text x="%d" y="%d" xml:space="preserve" style="white-space: pre">'
                     '%s</text>' % (pad, y, escape(line)))
        y += lead
    o += ['</g>', '</svg>']
    return "\n".join(o) + "\n"


# ----------------------------------------------------------------- the graph

# Column and row of each box. Notes by id; material by its path in the project.
LAYOUT = {
    "evidence/bench-2026-08-20.md": (0, 0),
    "evidence/screenshots": (1, 0),
    "evidence/fts-benchmark-2026-08-26.csv": (2, 0),
    "feed-poll-interval": (0, 1),
    "sqlite-over-postgres": (1, 1),
    "mystery-benchmark": (2, 1),
    "retry-storm-incident": (0, 2),
    "what-kestrel-is": (1, 2),
    "full-text-search": (2, 2),
    "auth-model-undecided": (0, 3),
    "opml-import": (1, 3),
    "drop-native-mobile-app": (2, 3),
}
BW, BH, GX, GY, MX, MY = 236, 62, 104, 62, 34, 34  # box, gaps, margins


def example():
    """What the linter knows about the example: notes, findings, material."""
    notelint.TODAY = DAY
    V = notelint.VOCAB["en"]
    notes, clashes, ambiguous = notelint.load(notelint.projects(EXAMPLE), V)
    findings = notelint.check(notes, clashes, EXAMPLE, V, ambiguous)
    folder = EXAMPLE / PROJECT
    material = {}                                   # path -> is it on disk
    cites = []                                      # (note id, path)
    for i, n in notes.items():
        for e in n["evidence"]:
            if "://" in e:
                continue
            # The planted absolute path is drawn as the file it points at.
            path = notelint.inside_base(e, folder, EXAMPLE) or notelint.cite_path(e)
            if path.startswith(PROJECT + "/"):
                path = path[len(PROJECT) + 1:]
            material[path] = notelint.evidence_exists(path, folder, EXAMPLE)
            cites.append((i, path))
    for cat, who, what in findings:
        if cat == "unclaimed":
            material[what] = True
    return V, notes, findings, material, cites


def centre(key):
    c, r = LAYOUT[key]
    return MX + c * (BW + GX) + BW / 2, MY + r * (BH + GY) + BH / 2


def edge_points(a, b):
    """The segment between two boxes, from border to border."""
    (ax, ay), (bx, by) = centre(a), centre(b)
    dx, dy = bx - ax, by - ay
    t = min((BW / 2) / abs(dx) if dx else 9, (BH / 2) / abs(dy) if dy else 9)
    return ax + dx * t, ay + dy * t, bx - dx * t, by - dy * t


def graph_svg():
    V, notes, findings, material, cites = example()
    drawn = set(notes) | set(material)
    if drawn != set(LAYOUT):
        sys.exit("The example changed and LAYOUT did not.\n  not placed: "
                 + ", ".join(sorted(drawn - set(LAYOUT)) or ["-"])
                 + "\n  no longer there: " + ", ".join(sorted(set(LAYOUT) - drawn) or ["-"]))
    DEPENDS, SUPERSEDES, BLOCKS, RELATED = V["edges"]
    level = {c: ERROR for c in notelint.ERRORS}
    level.update({c: REVIEW for c in notelint.REVIEWS})
    marks = {}
    for cat, who, what in findings:
        marks.setdefault(what if cat == "unclaimed" else who, []).append(cat)

    cols = 1 + max(c for c, _ in LAYOUT.values())
    rows = 1 + max(r for _, r in LAYOUT.values())
    w = 2 * MX + cols * BW + (cols - 1) * GX
    legend_y = MY + rows * BH + (rows - 1) * GY + 40
    h = legend_y + 34
    o = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" '
         'height="%d" role="img" aria-label="The bundled example as notelint reads it: '
         'nine notes, the typed links between them, the files they cite, and the five '
         'planted faults">' % (w, h, w, h),
         '<defs><marker id="tip" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
         'markerHeight="7" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="%s"/>'
         '</marker></defs>' % TEXT,
         '<rect width="%d" height="%d" rx="10" fill="%s" stroke="%s"/>' % (w, h, BG, LINE)]

    def line(a, b, kind):
        x1, y1, x2, y2 = edge_points(a, b)
        if kind in (DEPENDS, BLOCKS):
            o.append('<path d="M%.1f %.1f L%.1f %.1f" stroke="%s" stroke-width="1.6" '
                     'marker-end="url(#tip)"/>' % (x1, y1, x2, y2, TEXT))
            o.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-family="%s" '
                     'font-size="11.5" fill="%s">%s</text>'
                     % ((x1 + x2) / 2, (y1 + y2) / 2 - 7, MONO, TEXT, escape(kind)))
        elif kind == "evidence":
            o.append('<path d="M%.1f %.1f L%.1f %.1f" stroke="%s" stroke-width="1.2" '
                     'stroke-dasharray="2 5" stroke-linecap="round"/>' % (x1, y1, x2, y2, MUTED))
        else:
            o.append('<path d="M%.1f %.1f L%.1f %.1f" stroke="%s" stroke-width="1.2"/>'
                     % (x1, y1, x2, y2, FAINT))

    # Links first, so the boxes sit on top of them. A pair joined by a link
    # that carries a consequence is not drawn again as 'related'.
    strong = set()
    for i, n in sorted(notes.items()):
        for kind in (DEPENDS, SUPERSEDES, BLOCKS):
            for j in n["links"][kind]:
                strong.add(frozenset((i, j)))
    seen = set()
    for i, n in sorted(notes.items()):
        for j in n["links"][RELATED]:
            pair = frozenset((i, j))
            if pair not in strong and pair not in seen:
                seen.add(pair)
                line(i, j, RELATED)
    for i, path in sorted(cites):
        line(i, path, "evidence")
    for i, n in sorted(notes.items()):
        for kind in (DEPENDS, SUPERSEDES, BLOCKS):
            for j in n["links"][kind]:
                line(i, j, kind)

    for key in sorted(LAYOUT):
        cx, cy = centre(key)
        x, y = cx - BW / 2, cy - BH / 2
        found = marks.get(key, [])
        edge = level[found[0]] if found else LINE
        if key in notes:
            n = notes[key]
            where = "history/" if n["history"] else n["path"].parent.name + "/"
            dim = n["history"]
            name, sub = key, n["type"] + " · " + where
            dash = ""
        else:
            dim = False
            name = key.rsplit("/", 1)[-1] + ("/" if "." not in key.rsplit("/", 1)[-1] else "")
            sub = "evidence/ · " + ("on disk" if material[key] else "not on disk")
            dash = "" if material[key] else ' stroke-dasharray="6 4"'
        o.append('<rect x="%.1f" y="%.1f" width="%d" height="%d" rx="8" fill="%s" '
                 'stroke="%s" stroke-width="%s"%s/>'
                 % (x, y, BW, BH, PANEL, edge, "1.8" if found else "1", dash))
        # A long file name gets smaller letters rather than a wider box.
        size = min(13.5, (BW - 28) / (0.62 * len(name)))
        o.append('<text x="%.1f" y="%.1f" font-family="%s" font-size="%.1f" '
                 'font-weight="600" fill="%s">%s</text>'
                 % (x + 14, y + 26, MONO, size, MUTED if dim else TEXT, escape(name)))
        o.append('<text x="%.1f" y="%.1f" font-family="%s" font-size="12" fill="%s">%s</text>'
                 % (x + 14, y + 46, SANS, MUTED, escape(sub)))
        for k, cat in enumerate(found):
            label = cat.upper()
            tw = 7.2 * len(label) + 16
            tx, ty = x + BW - tw - 10, y - 11 + k * 24
            o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="22" rx="11" fill="%s" '
                     'stroke="%s" stroke-width="1.4"/>' % (tx, ty, tw, BG, level[cat]))
            o.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-family="%s" '
                     'font-size="11" font-weight="600" fill="%s">%s</text>'
                     % (tx + tw / 2, ty + 15, MONO, level[cat], escape(label)))

    # The legend: what each kind of line means.
    x = MX
    for kind, text in ((DEPENDS, "depends-on, blocks: a link with a consequence"),
                       (RELATED, "related"), ("evidence", "cites as evidence")):
        if kind == DEPENDS:
            o.append('<path d="M%d %d h34" stroke="%s" stroke-width="1.6" '
                     'marker-end="url(#tip)"/>' % (x, legend_y, TEXT))
        elif kind == "evidence":
            o.append('<path d="M%d %d h34" stroke="%s" stroke-width="1.2" '
                     'stroke-dasharray="2 5" stroke-linecap="round"/>' % (x, legend_y, MUTED))
        else:
            o.append('<path d="M%d %d h34" stroke="%s" stroke-width="1.2"/>'
                     % (x, legend_y, FAINT))
        o.append('<text x="%d" y="%d" font-family="%s" font-size="12" fill="%s">%s</text>'
                 % (x + 44, legend_y + 4, SANS, MUTED, escape(text)))
        x += 44 + round(6.4 * len(text)) + 30
    o.append('</svg>')
    return "\n".join(o) + "\n"


def main(argv):
    wanted = {"report.svg": report_svg(report()), "graph.svg": graph_svg()}
    stale = []
    for name, svg in wanted.items():
        path = ROOT / "docs" / name
        if path.is_file() and path.read_text(encoding="utf-8") == svg:
            continue
        stale.append(name)
        if "--check" not in argv:
            with open(str(path), "w", encoding="utf-8", newline="\n") as f:
                f.write(svg)
    if "--check" in argv:
        print("up to date" if not stale else "would change: " + ", ".join(stale))
        return 1 if stale else 0
    print("docs/report.svg and docs/graph.svg: "
          + ("rewritten " + ", ".join(stale) if stale else "already up to date"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
