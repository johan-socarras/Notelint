#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for notelint.

Every test plants a specific fault in a temporary knowledge base and asserts
that the matching check fires. A linter that never reports anything looks
exactly like a clean codebase, so each check is proven to fail when it should.

    python tests/test_notelint.py
"""
import sys, shutil, tempfile, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import notelint  # noqa: E402

TODAY = datetime.date.today()
EN = notelint.VOCAB["en"]

NOTE = """---
title: {title}
type: {type}
project: {project}
status: {status}
created: 2026-01-01
reviewed: {reviewed}
expires: {expires}
evidence:
{evidence}
links:
  depends-on: [{depends}]
  supersedes: [{supersedes}]
  blocks: [{blocks}]
  related: [{related}]
---

{body}
"""


def note(base, project, name, title="A claim", type="fact", status="current",
         reviewed=None, expires="", evidence=(), depends="", supersedes="",
         blocks="", related="", body="Body."):
    d = base / project / "notes"
    d.mkdir(parents=True, exist_ok=True)
    ev = "\n".join("  - " + e for e in evidence)
    (d / (name + ".md")).write_text(NOTE.format(
        title=title, type=type, project=project, status=status,
        reviewed=reviewed or str(TODAY), expires=expires, evidence=ev,
        depends=depends, supersedes=supersedes, blocks=blocks, related=related,
        body=body), encoding="utf-8")


def run(base, lang="en"):
    """Return the findings as a set of (category, subject) pairs."""
    V = notelint.VOCAB[lang]
    folders = notelint.projects(base)
    notes, clashes = notelint.load(folders, V)
    return {(c, i) for c, i, _ in notelint.check(notes, clashes, base, V)}


CASES = []


def case(fn):
    CASES.append(fn)
    return fn


@case
def clean_base_reports_nothing(base):
    note(base, "Alpha", "one", related="two")
    note(base, "Alpha", "two", title="A different unrelated claim")
    assert run(base) == set(), "a clean base must produce no findings"


@case
def broken_link_in_frontmatter(base):
    note(base, "Alpha", "one", depends="ghost")
    assert ("broken link", "one") in run(base)


@case
def broken_link_in_body(base):
    note(base, "Alpha", "one", body="See [[ghost]] for details.")
    assert ("broken link", "one") in run(base)


@case
def code_spans_are_not_links(base):
    note(base, "Alpha", "one", body="The TOML key is `[[ratelimits]]`, not a link.")
    assert not any(c == "broken link" for c, _ in run(base)), \
        "[[x]] inside backticks is code, not a wiki link"


@case
def dead_evidence(base):
    note(base, "Alpha", "one", evidence=["evidence/gone.md"])
    assert ("dead evidence", "one") in run(base)


@case
def live_evidence_and_urls_pass(base):
    (base / "Alpha").mkdir(parents=True, exist_ok=True)
    (base / "Alpha" / "here.md").write_text("here", encoding="utf-8")
    note(base, "Alpha", "one", evidence=["here.md", "https://example.com"],
         body="Mentions here.md so it is not unclaimed.")
    assert not any(c == "dead evidence" for c, _ in run(base))


@case
def expired_note_still_current(base):
    note(base, "Alpha", "one", expires=str(TODAY - datetime.timedelta(days=1)))
    assert ("expired", "one") in run(base)


@case
def unreviewed_for_too_long(base):
    old = TODAY - datetime.timedelta(days=notelint.DAYS_UNREVIEWED + 5)
    note(base, "Alpha", "one", reviewed=str(old))
    assert ("unreviewed", "one") in run(base)


@case
def zombie_reference(base):
    note(base, "Alpha", "dead", status="dropped")
    note(base, "Alpha", "alive", title="Totally other wording", related="dead")
    assert ("zombie", "alive") in run(base)


@case
def supersedes_a_dead_note_is_not_a_zombie(base):
    note(base, "Alpha", "dead", status="superseded")
    note(base, "Alpha", "alive", title="Totally other wording", supersedes="dead")
    assert not any(c == "zombie" for c, _ in run(base)), \
        "pointing at what you replaced is the correct use of supersedes"


@case
def stale_blocker_frees_the_blocked_note(base):
    note(base, "Alpha", "blocker", status="dropped", blocks="work")
    note(base, "Alpha", "work", title="Something entirely different", type="todo")
    assert ("unblocked", "work") in run(base)


@case
def propagation_when_a_dependency_moved_on(base):
    older = str(TODAY - datetime.timedelta(days=10))
    note(base, "Alpha", "base", title="The underlying decision")
    note(base, "Alpha", "leaf", title="Something built on top",
         reviewed=older, depends="base")
    assert ("propagation", "leaf") in run(base)


@case
def unclaimed_material(base):
    note(base, "Alpha", "one")
    (base / "Alpha" / "photos").mkdir(parents=True, exist_ok=True)
    (base / "Alpha" / "photos" / "a.md").write_text("x", encoding="utf-8")
    assert ("unclaimed", "Alpha") in run(base)


@case
def note_filed_in_the_wrong_project(base):
    note(base, "Alpha", "one")
    d = base / "Beta" / "notes"
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy(base / "Alpha" / "notes" / "one.md", d / "two.md")
    assert ("wrong project", "two") in run(base)


@case
def duplicate_id_across_projects(base):
    note(base, "Alpha", "same")
    note(base, "Beta", "same")
    assert any(c == "duplicate id" for c, _ in run(base))


@case
def probable_duplicate_titles(base):
    note(base, "Alpha", "one", title="Poll every five minutes not every minute")
    note(base, "Alpha", "two", title="Poll every minute not every five minutes")
    assert any(c == "duplicate?" for c, _ in run(base))


@case
def invalid_status_is_a_format_error(base):
    note(base, "Alpha", "one", status="kind-of-true")
    assert ("format", "one") in run(base)


@case
def spanish_vocabulary_is_understood(base):
    d = base / "Alpha" / "notes"
    d.mkdir(parents=True, exist_ok=True)
    (d / "una.md").write_text(
        "---\ntitulo: Una afirmacion\ntipo: hecho\nproyecto: Alpha\n"
        "estado: vigente\ncreada: 2026-01-01\nrevisada: " + str(TODAY) + "\n"
        "caduca:\nevidencia:\nenlaces:\n  depende-de: [fantasma]\n"
        "  supera-a: []\n  bloquea: []\n  relacionada: []\n---\n\nCuerpo.\n",
        encoding="utf-8")
    assert notelint.detect_lang(base) == "es", "the Spanish vocabulary must be detected"
    assert ("broken link", "una") in run(base, lang="es")


@case
def the_shipped_example_reports_its_three_planted_faults(base):
    repo = Path(__file__).resolve().parent.parent
    found = run(repo / "example")
    for expected in [("dead evidence", "mystery-benchmark"),
                     ("propagation", "feed-poll-interval"),
                     ("unclaimed", "Kestrel")]:
        assert expected in found, "example lost its planted fault: " + str(expected)


def open_view(base, lang="en"):
    """Render OPEN.md for the first project and return it as text."""
    V = notelint.VOCAB[lang]
    folders = notelint.projects(base)
    notes, _ = notelint.load(folders, V)
    group = [n for n in notes.values() if n["folder"] == folders[0]]
    return "\n".join(notelint.open_block(group, notes, folders[0], V))


@case
def work_chains_show_the_whole_order(base):
    note(base, "Alpha", "ship-090", title="Ship version 0.9.0",
         type="todo", blocks="run-tests")
    note(base, "Alpha", "run-tests", title="Run the acceptance suite",
         type="todo", blocks="update-site")
    note(base, "Alpha", "update-site", title="Rewrite the pricing page", type="todo")
    text = open_view(base)

    assert "## Work chains (1)" in text, "the three notes are one chain, not three items"
    assert "- [Ship version 0.9.0]" in text
    assert "  - [Run the acceptance suite]" in text, "second link must be indented once"
    assert "    - [Rewrite the pricing page]" in text, "third link must be indented twice"
    assert "<- start here" in text

    ready = text.split("## Work chains")[0]
    assert "Run the acceptance suite" not in ready, "blocked work must not look ready"
    assert "Ship version 0.9.0" in ready, "the head of the chain is what you can do now"


@case
def closing_a_link_frees_the_next_one(base):
    note(base, "Alpha", "ship-090", title="Ship version 0.9.0",
         status="superseded", blocks="run-tests")
    note(base, "Alpha", "run-tests", title="Run the acceptance suite", type="todo")
    assert ("unblocked", "run-tests") in run(base), \
        "when the blocker closes, the next link must be reported as free"
    assert "Run the acceptance suite" in open_view(base).split("## Work chains")[0], \
        "and it must move into Ready to do"


@case
def a_blocking_cycle_is_reported_not_hidden(base):
    note(base, "Alpha", "first", title="One half of a deadlock",
         type="todo", blocks="second")
    note(base, "Alpha", "second", title="Other half of the same deadlock",
         type="todo", blocks="first")
    text = open_view(base)
    assert "## Blocked inside a cycle (2)" in text, \
        "a cycle has no root, so both notes would silently vanish from the view"


def main():
    passed = failed = 0
    for fn in CASES:
        tmp = Path(tempfile.mkdtemp(prefix="notelint-test-"))
        try:
            fn(tmp)
            print("  ok    " + fn.__name__.replace("_", " "))
            passed += 1
        except AssertionError as e:
            print("  FAIL  " + fn.__name__.replace("_", " ") + "\n          " + str(e))
            failed += 1
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    print("\n  " + str(passed) + " passed, " + str(failed) + " failed\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
