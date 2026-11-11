#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Draws the three pictures in the README.

    python docs/make_images.py            # rewrites the three files in docs/
    python docs/make_images.py --check    # exit 1 if any of them would change

Two come from the bundled example, and nothing in them is typed by hand.
`report.svg` is what `notelint.py` prints for `example/` at 80 columns;
`graph.svg` is the notes, the links and the findings that `notelint.py`
itself loads and reports. The one thing chosen here is where each box of the
graph sits (LAYOUT, below): if the example gains or loses a note, this script
stops and says so instead of drawing a picture that is no longer the example.

`how-it-works.svg` is a diagram, not output: who gives the task, who edits
the notes, what the linter does with them. Its words are written here and say
no more than the README does. All it takes from the example is the three file
names in the middle, and the script stops if one of them is gone. Its icons
are drawn here, stroke by stroke; none of them is anybody's logo.

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


# ---------------------------------------------------------------- the loop

# The three notes named in the middle box, as paths inside the example project.
SHOWN = ["notes/feed-poll-interval.md", "todo/opml-import.md", "ideas/full-text-search.md"]

# Title and second line of each way into the notes.
AGENT = ("Your AI agent", "Claude Code, or any other")
EDITOR = ("Obsidian", "or any Markdown editor")
FILES = ("File manager", "Windows or Ubuntu, any editor")

ICONS = {
    "person": '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7"/>',
    "robot": '<rect x="4" y="8" width="16" height="12" rx="3"/><path d="M12 8V4.6"/>'
             '<circle cx="12" cy="3.4" r="1.2"/><path d="M9 13.2v1.8M15 13.2v1.8"/>',
    "notebook": '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 3v18"/>'
                '<path d="M12 8h4M12 12h4"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1'
              '-2-2z"/>',
    "terminal": '<rect x="3" y="4" width="18" height="16" rx="2.5"/>'
                '<path d="M7 10l3 2.5L7 15M12.5 15H17"/>',
}


def how_svg():
    missing = [f for f in SHOWN if not (EXAMPLE / PROJECT / f).is_file()]
    if missing:
        sys.exit("The example changed and SHOWN did not.\n  no longer there: "
                 + ", ".join(missing))

    def icon(kind, x, y):
        return ('<g transform="translate(%.1f %.1f)" fill="none" stroke="%s" '
                'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">%s</g>'
                % (x, y, TEXT, ICONS[kind]))

    def text(x, y, s, font=SANS, size=12, fill=MUTED, bold=False, middle=False):
        return ('<text x="%.1f" y="%.1f" font-family="%s" font-size="%s" fill="%s"%s%s>'
                '%s</text>' % (x, y, font, size, fill,
                               ' font-weight="600"' if bold else "",
                               ' text-anchor="middle"' if middle else "", escape(s)))

    def box(x, y, w, h, strong=False):
        return ('<rect x="%.1f" y="%.1f" width="%d" height="%d" rx="8" fill="%s" '
                'stroke="%s" stroke-width="%s"/>'
                % (x, y, w, h, PANEL, TEXT if strong else LINE, "1.4" if strong else "1"))

    def arrow(d, strong=True):
        return ('<path d="%s" fill="none" stroke="%s" stroke-width="%s" '
                'marker-end="url(#%s)"/>' % (d, TEXT if strong else FAINT,
                                             "1.6" if strong else "1.2",
                                             "tip" if strong else "faint-tip"))

    def step(x, y, n):
        return ('<circle cx="%.1f" cy="%.1f" r="10" fill="%s" stroke="%s" '
                'stroke-width="1.4"/>' % (x, y, BG, TEXT)
                + text(x, y + 4, str(n), MONO, 11.5, TEXT, True, True))

    def way_in(y, kind, names, strong=False):
        return [box(lx, y, lw, dh, strong), icon(kind, lx + 14, y + dh / 2 - 12),
                text(lx + 50, y + dh / 2 - 4, names[0], MONO, 13.5, TEXT, True),
                text(lx + 50, y + dh / 2 + 15, names[1])]

    def level(y, label, colour, says):
        tw = 7.2 * len(label) + 16
        return ['<rect x="%.1f" y="%.1f" width="%.1f" height="22" rx="11" fill="%s" '
                'stroke="%s" stroke-width="1.4"/>' % (rx + 16, y, tw, BG, colour),
                text(rx + 16 + tw / 2, y + 15, label, MONO, 11, colour, True, True),
                text(rx + 100, y + 15, says, SANS, 12.5, TEXT)]

    w, h, top, colh = 984, 424, 166, 224
    lx, lw, dh, dgap = 34, 250, 64, 16          # the ways in, on the left
    cx, cw = 384, 216                           # the notes, in the middle
    rx, rw = 700, 250                           # the linter, on the right
    yx, yw, yy, yh = 367, 250, 30, 58           # you, on top
    o = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" '
         'height="%d" role="img" aria-label="How notelint fits in: you give the task, '
         'your AI agent updates the notes, notelint reads them all and reports, and you '
         'review. The notes are plain Markdown files that Obsidian, any Markdown editor '
         'or the file manager can open too">' % (w, h, w, h),
         '<defs>']
    for name, colour in (("tip", TEXT), ("faint-tip", FAINT)):
        o.append('<marker id="%s" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
                 'markerHeight="7" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="%s"/>'
                 '</marker>' % (name, colour))
    o += ['</defs>',
          '<rect width="%d" height="%d" rx="10" fill="%s" stroke="%s"/>' % (w, h, BG, LINE)]

    # You, and the two ends of the loop: the task goes down, the result comes back.
    down, up = lx + lw / 2, rx + rw / 2
    o += [box(yx, yy, yw, yh, True), icon("person", yx + 16, yy + 17),
          text(yx + 52, yy + 26, "You", MONO, 13.5, TEXT, True),
          text(yx + 52, yy + 45, "give the task, then review"),
          arrow("M%d %d H%.1f a12 12 0 0 0 -12 12 V%d" % (yx, yy + yh / 2, down + 12, top - 3)),
          arrow("M%.1f %d V%.1f a12 12 0 0 0 -12 -12 H%d"
                % (up, top, yy + yh / 2 + 12, yx + yw + 3)),
          step(down, 118, 1), text(down + 18, 122, "give the task", MONO, 11.5, TEXT),
          step(up, 118, 4), text(up + 18, 122, "review", MONO, 11.5, TEXT)]

    # The ways in. The agent is part of the loop; the other two are by hand.
    y1, y2, y3 = top, top + dh + dgap, top + 2 * (dh + dgap)
    o += way_in(y1, "robot", AGENT, True)
    o += way_in(y2, "notebook", EDITOR)
    o += way_in(y3, "folder", FILES)
    mid = (lx + lw + cx) / 2
    o += [arrow("M%d %.1f H%d" % (lx + lw, y1 + dh / 2, cx - 3)), step(mid, y1 + dh / 2, 2),
          text(mid, y1 + dh / 2 + 25, "updates", MONO, 11.5, TEXT, False, True),
          arrow("M%d %.1f H%d" % (lx + lw, y2 + dh / 2, cx - 3), False),
          arrow("M%d %.1f H%d" % (lx + lw, y3 + dh / 2, cx - 3), False),
          text(mid, (y2 + y3 + dh) / 2 + 4, "by hand", MONO, 11.5, MUTED, False, True)]

    # The notes.
    o += [box(cx, top, cw, colh), icon("folder", cx + 16, top + 16),
          text(cx + 52, top + 33, "Your notes", MONO, 13.5, TEXT, True),
          text(cx + 16, top + 62, "plain Markdown files in folders"),
          '<path d="M%d %d h%d" stroke="%s"/>' % (cx + 16, top + 78, cw - 32, LINE),
          text(cx + 16, top + 104, PROJECT + "/", MONO, 11)]
    for k, f in enumerate(SHOWN):
        o.append(text(cx + 22, top + 126 + 21 * k, f, MONO, 11))
    o.append(text(cx + 16, top + 204, "the example in this repo", SANS, 11, FAINT))

    # The linter.
    mid = (cx + cw + rx) / 2
    o += [arrow("M%d %.1f H%d" % (cx + cw, top + colh / 2, rx - 3)),
          step(mid, top + colh / 2, 3),
          text(mid, top + colh / 2 + 25, "reads all", MONO, 11.5, TEXT, False, True),
          box(rx, top, rw, colh, True), icon("terminal", rx + 16, top + 16),
          text(rx + 52, top + 33, "notelint", MONO, 13.5, TEXT, True),
          text(rx + 16, top + 62, "lints the whole base and reports"),
          '<path d="M%d %d h%d" stroke="%s"/>' % (rx + 16, top + 78, rw - 32, LINE)]
    o += level(top + 96, "ERRORS", ERROR, "go to zero")
    o += level(top + 130, "REVIEWS", REVIEW, "are a queue")
    o += [text(rx + 16, top + 204, "It checks structure, not truth.", SANS, 11, FAINT),
          '</svg>']
    return "\n".join(o) + "\n"


def main(argv):
    wanted = {"report.svg": report_svg(report()), "graph.svg": graph_svg(),
              "how-it-works.svg": how_svg()}
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
    print("docs/: " + ("rewritten " + ", ".join(stale) if stale
                       else "the three pictures are already up to date"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
