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
         blocks="", related="", body="Body.", verify="Read it again.", where="notes"):
    d = base / project / where
    d.mkdir(parents=True, exist_ok=True)
    # Every current note owes a 'How to verify'; pass verify=None to leave it out.
    if verify is not None:
        body += "\n\n## How to verify\n\n" + verify
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
    notes, clashes, ambiguous = notelint.load(folders, V)
    return {(c, i) for c, i, _ in
            notelint.check(notes, clashes, base, V, ambiguous)}


def loaded(base, lang="en"):
    """Return (notes, V) for tests that call something other than check()."""
    V = notelint.VOCAB[lang]
    return notelint.load(notelint.projects(base), V)[0], V


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
    note(base, "Alpha", "alive", title="Totally other wording", depends="dead")
    assert ("zombie", "alive") in run(base)


@case
def related_may_point_at_a_dropped_note(base):
    note(base, "Alpha", "dead", status="dropped")
    note(base, "Alpha", "alive", title="Totally other wording", related="dead")
    assert not any(c == "zombie" for c, _ in run(base)), \
        "a dropped note is kept so it can be pointed at; related is the cheap way"


@case
def related_to_a_superseded_note_is_a_zombie(base):
    note(base, "Alpha", "old", status="superseded")
    note(base, "Alpha", "alive", title="Totally other wording", related="old")
    assert ("zombie", "alive") in run(base), "link to whatever superseded it instead"


@case
def a_reference_gets_the_long_clock(base):
    mid = str(TODAY - datetime.timedelta(days=notelint.DAYS_UNREVIEWED + 5))
    note(base, "Alpha", "where", title="Where the configs live", type="reference",
         reviewed=mid)
    note(base, "Alpha", "fact", title="Something measured once", reviewed=mid)
    found = run(base)
    assert ("unreviewed", "fact") in found
    assert ("unreviewed", "where") not in found, \
        "a reference describes; it is re-confirmed every 180 days, not 60"


@case
def an_idea_never_ages(base):
    old = str(TODAY - datetime.timedelta(days=notelint.DAYS_UNREVIEWED_LONG + 5))
    note(base, "Alpha", "maybe", type="idea", reviewed=old)
    assert ("unreviewed", "maybe") not in run(base), "an idea asserts nothing to re-confirm"


@case
def a_reviewed_date_in_the_future_is_a_format_error(base):
    note(base, "Alpha", "one", reviewed=str(TODAY + datetime.timedelta(days=3)))
    assert ("format", "one") in run(base), \
        "a future date would silence the unreviewed warning for good"


@case
def a_malformed_date_is_a_format_error(base):
    note(base, "Alpha", "one", expires="next spring")
    assert ("format", "one") in run(base)


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
def build_junk_is_not_unclaimed_material(base):
    note(base, "Alpha", "one")
    for junk in ("__pycache__", "node_modules", "target"):
        (base / "Alpha" / junk).mkdir(parents=True, exist_ok=True)
        (base / "Alpha" / junk / "x.bin").write_text("x", encoding="utf-8")
    assert not any(c == "unclaimed" for c, _ in run(base)), \
        "regenerable junk must not be reported as material needing a note"


@case
def naming_a_directory_does_not_claim_it(base):
    # The word "tests" appears in the prose for an unrelated reason. That must
    # not silence a real tests/ directory nobody has documented.
    (base / "Alpha" / "tests").mkdir(parents=True, exist_ok=True)
    (base / "Alpha" / "tests" / "x.md").write_text("x", encoding="utf-8")
    note(base, "Alpha", "one",
         body="We ran tests against the staging box and they passed.")
    assert ("unclaimed", "Alpha") in run(base), \
        "material is claimed by citing its path, not by using the word"


@case
def verifications_come_out_dependencies_first(base):
    note(base, "Alpha", "leaf", title="Built on top", depends="ground")
    note(base, "Alpha", "ground", title="The thing underneath")
    notes, V = loaded(base)
    pos = notelint.topo_order(notes, V)
    assert pos["ground"] < pos["leaf"], \
        "reviewing bottom-up is what stops spurious propagation findings"


@case
def a_dependency_cycle_still_produces_an_order(base):
    note(base, "Alpha", "one", depends="two")
    note(base, "Alpha", "two", title="Other wording entirely", depends="one")
    notes, V = loaded(base)
    pos = notelint.topo_order(notes, V)
    assert set(pos) == {"one", "two"}, "a cycle must not drop notes from the order"


@case
def the_verify_section_is_found_by_either_heading(base):
    for heading in ("How to verify", "How to check", "Cómo se comprueba"):
        assert notelint.is_verification(heading), heading
    assert not notelint.is_verification("What it is")


@case
def oldest_unreviewed_lists_the_stalest_first(base):
    old = str(TODAY - datetime.timedelta(days=40))
    note(base, "Alpha", "stale", title="Nobody has looked at this", reviewed=old)
    note(base, "Alpha", "fresh", title="Confirmed today")
    notes, V = loaded(base)
    lines = "\n".join(notelint.oldest_block(notes, V))
    assert lines.index("stale") < lines.index("fresh"), \
        "the longest unreviewed must come first"


@case
def citing_a_path_claims_it_and_its_parents(base):
    deep = base / "Alpha" / "evidence" / "shots"
    deep.mkdir(parents=True, exist_ok=True)
    (deep / "panel.md").write_text("x", encoding="utf-8")
    note(base, "Alpha", "one", body="See `evidence/shots/panel.md` for the run.")
    assert not any(c == "unclaimed" for c, _ in run(base)), \
        "citing something deep must also claim the directories above it"


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
def the_shipped_example_reports_its_five_planted_faults(base):
    repo = Path(__file__).resolve().parent.parent
    found = run(repo / "example")
    for expected in [("dead evidence", "mystery-benchmark"),
                     ("format", "sqlite-over-postgres"),
                     ("propagation", "feed-poll-interval"),
                     ("hidden todo", "retry-storm-incident"),
                     ("unclaimed", "Kestrel")]:
        assert expected in found, "example lost its planted fault: " + str(expected)


def open_view(base, lang="en"):
    """Render OPEN.md for the first project and return it as text."""
    V = notelint.VOCAB[lang]
    folders = notelint.projects(base)
    notes = notelint.load(folders, V)[0]
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


# --------------------------------------------------------------------------
# Encoding and frontmatter shapes the parser used to swallow or die on.
# --------------------------------------------------------------------------


@case
def a_utf8_bom_does_not_break_a_valid_note(base):
    note(base, "Alpha", "one")
    p = base / "Alpha" / "notes" / "one.md"
    p.write_bytes(b"\xef\xbb\xbf" + p.read_bytes())
    assert run(base) == set(), \
        "a BOM is what PowerShell 5.1 writes; the note is still valid"


@case
def a_note_that_is_not_utf8_is_reported_not_fatal(base):
    note(base, "Alpha", "one")
    p = base / "Alpha" / "notes" / "one.md"
    p.write_bytes(p.read_text(encoding="utf-8").replace(
        "Body.", "Caf\u00e9").encode("latin-1"))
    found = run(base)
    assert any(c == "format" for c, _ in found), \
        "a non-UTF-8 note must be a finding, not an unhandled exception"


@case
def frontmatter_never_closed_is_reported(base):
    note(base, "Alpha", "one")
    p = base / "Alpha" / "notes" / "one.md"
    head = p.read_text(encoding="utf-8").split("\n---", 1)[0]
    p.write_text(head + "\n", encoding="utf-8")
    assert ("format", "one") in run(base), \
        "without the closing --- the body is empty and nothing in it is checked"


@case
def links_written_as_a_block_list_are_not_swallowed(base):
    note(base, "Alpha", "one")
    p = base / "Alpha" / "notes" / "one.md"
    p.write_text(p.read_text(encoding="utf-8").replace(
        "  depends-on: []", "  depends-on:\n    - ghost"), encoding="utf-8")
    assert ("broken link", "one") in run(base), \
        "the block form is what YAML suggests; losing it silently loses blocks:"


@case
def quoted_values_read_like_bare_ones(base):
    note(base, "Alpha", "one", title='"Postmortem: the outage"', related='"two"')
    note(base, "Alpha", "two", title="A different unrelated claim")
    p = base / "Alpha" / "notes" / "one.md"
    p.write_text(p.read_text(encoding="utf-8").replace(
        "type: fact", 'type: "fact"').replace("status: current", "status: 'current'"),
        encoding="utf-8")
    assert run(base) == set(), \
        "YAML allows quotes, and a title with a colon needs them: \"fact\" is fact"
    notes, V = loaded(base)
    assert notes["one"]["title"] == "Postmortem: the outage", "the quotes are not the title"


@case
def a_note_that_cannot_be_read_is_a_finding_not_a_crash(base):
    import os
    note(base, "Alpha", "one")
    (base / "Alpha" / "notes" / "folder.md").mkdir()
    try:
        os.symlink(str(base / "nowhere.md"), str(base / "Alpha" / "notes" / "gone.md"))
        linked = True
    except (OSError, NotImplementedError):
        linked = False          # Windows without the right to make links
    found = run(base)
    assert ("format", "folder") in found, "a folder named x.md is reported, not raised"
    assert ("wrong project", "folder") not in found, \
        "one fault, one finding: its empty fields are not five more"
    if linked:
        assert ("format", "gone") in found, "and so is a link that leads nowhere"
    rc, out = quiet(notelint.main, [str(base), "--report-only"])
    assert rc == 1 and "cannot be read" in out, \
        "exit 1 means 'there are findings'; a traceback must not borrow it"


@case
def a_view_the_tool_did_not_write_is_left_alone(base):
    note(base, "Alpha", "one")
    mine = base / "INDEX.md"
    mine.write_text("# My own index\n\nHand written, and not by notelint.\n",
                    encoding="utf-8")
    V = notelint.VOCAB["en"]
    folders = notelint.projects(base)
    notes = notelint.load(folders, V)[0]
    notelint.write_views(notes, folders, base, V)
    assert "Hand written" in mine.read_text(encoding="utf-8"), \
        "the installer promises existing files are untouched; honour it"


@case
def force_replaces_a_view_the_tool_did_not_write(base):
    note(base, "Alpha", "one")
    mine = base / "INDEX.md"
    mine.write_text("# My own index\n", encoding="utf-8")
    V = notelint.VOCAB["en"]
    folders = notelint.projects(base)
    notes = notelint.load(folders, V)[0]
    notelint.write_views(notes, folders, base, V, force=True)
    assert "Do not edit by hand" in mine.read_text(encoding="utf-8"), \
        "--force is the documented way out"


# --------------------------------------------------------------------------
# Citations, and names that collide across projects.
# --------------------------------------------------------------------------


@case
def a_comment_after_a_path_does_not_break_the_claim(base):
    note(base, "Alpha", "one", evidence=["evidence/bench.md — the p95 numbers"])
    (base / "Alpha" / "evidence").mkdir(parents=True, exist_ok=True)
    (base / "Alpha" / "evidence" / "bench.md").write_text("x\n", encoding="utf-8")
    found = run(base)
    assert not any(c == "dead evidence" for c, _ in found), "the file is right there"
    assert not any(c == "unclaimed" for c, _ in found), \
        "the same line cannot be live evidence and unclaimed at once"


@case
def a_hyphen_in_a_file_name_is_part_of_the_name(base):
    note(base, "Alpha", "one", evidence=["evidence/Q3 Report - final.pdf"])
    (base / "Alpha" / "evidence").mkdir(parents=True, exist_ok=True)
    (base / "Alpha" / "evidence" / "Q3 Report - final.pdf").write_text("x", encoding="utf-8")
    found = run(base)
    assert not any(c in ("dead evidence", "unclaimed") for c, _ in found), \
        "a plain hyphen is not a comment delimiter; the file must stay citable"


@case
def both_notes_survive_a_name_collision(base):
    note(base, "Alpha", "decisions", title="Decisions of Alpha")
    note(base, "Beta", "decisions", title="Decisions of Beta")
    notes = notelint.load(notelint.projects(base), notelint.VOCAB["en"])[0]
    assert len(notes) == 2, "both must be loaded, not one discarded"
    titles = {n["title"] for n in notes.values()}
    assert titles == {"Decisions of Alpha", "Decisions of Beta"}


@case
def a_collision_is_still_reported(base):
    note(base, "Alpha", "decisions", title="Decisions of Alpha")
    note(base, "Beta", "decisions", title="Decisions of Beta")
    assert any(c == "duplicate id" for c, _ in run(base))


@case
def a_link_to_a_collided_name_is_ambiguous_not_broken(base):
    note(base, "Alpha", "decisions", title="Decisions of Alpha")
    note(base, "Beta", "decisions", title="Decisions of Beta")
    note(base, "Alpha", "other", title="Another claim entirely", related="decisions")
    found = run(base)
    assert ("ambiguous link", "other") in found, \
        "the name points at neither note, and saying 'broken' would be wrong"
    assert not any(c == "broken link" for c, _ in found)


@case
def evidence_claims_a_top_level_name_with_a_space(base):
    note(base, "Alpha", "one", evidence=["Q3 Report.pdf"])
    (base / "Alpha" / "Q3 Report.pdf").write_text("x", encoding="utf-8")
    found = run(base)
    assert not any(c in ("dead evidence", "unclaimed") for c, _ in found), \
        "evidence: is one path per line; a space in the name is just part of it"


@case
def a_space_in_the_first_segment_still_blocks_a_claim_from_the_body(base):
    note(base, "Alpha", "one", body="The numbers come from `Q3 Report.pdf`.")
    (base / "Alpha" / "Q3 Report.pdf").write_text("x", encoding="utf-8")
    assert ("unclaimed", "Alpha") in run(base), \
        "a backticked span may be a shell command: there the guard stays"


# --------------------------------------------------------------------------
# Second pass, 2026-09-08: what --project, an unverified blocker and a
# cited directory actually mean.
# --------------------------------------------------------------------------


@case
def project_filter_keeps_cross_project_links_whole(base):
    import io, contextlib
    note(base, "Alpha", "lesson", title="A lesson learned in Alpha")
    note(base, "Beta", "uses-lesson", title="Beta rests on the Alpha lesson",
         depends="lesson")
    with contextlib.redirect_stdout(io.StringIO()) as out:
        rc = notelint.main([str(base), "--project", "Beta", "--report-only"])
    assert rc == 0 and "BROKEN LINK" not in out.getvalue(), \
        "links cross project boundaries; narrowing the report must not break them"


@case
def an_unverified_blocker_still_blocks(base):
    note(base, "Alpha", "gate", title="Decide the auth model first",
         type="todo", status="unverified", blocks="work")
    note(base, "Alpha", "work", title="Expose the port", type="todo")
    assert not any(c == "unblocked" for c, _ in run(base)), \
        "unverified is not closed: the protocol says it keeps blocking"
    text = open_view(base)
    assert "Expose the port" not in text.split("## Work chains")[0], \
        "and what it blocks must not look ready to do"
    assert "## Work chains (1)" in text


@case
def citing_a_directory_claims_what_it_holds(base):
    shots = base / "Alpha" / "screenshots"
    shots.mkdir(parents=True, exist_ok=True)
    (shots / "panel.png").write_bytes(b"x")
    note(base, "Alpha", "one", body="The captures live in `screenshots`.")
    assert not any(c == "unclaimed" for c, _ in run(base)), \
        "a directory cited by name claims its files"


@case
def a_cited_file_does_not_claim_its_siblings(base):
    ev = base / "Alpha" / "evidence"
    (ev / "shots").mkdir(parents=True, exist_ok=True)
    (ev / "bench.md").write_text("x", encoding="utf-8")
    (ev / "shots" / "panel.png").write_bytes(b"x")
    note(base, "Alpha", "one", evidence=["evidence/bench.md"])
    assert ("unclaimed", "Alpha") in run(base), \
        "the parent is implied, not cited: it must not claim the other children"


# --------------------------------------------------------------------------
# Checks carried over from the knowledge base notelint grew out of.
# --------------------------------------------------------------------------


INBOX = """# Inbox

Changed something by hand? Say what and why, one line each.

## To process

- Renamed the staging host to {name}, the old one is gone.

## Processed

- Moved the screenshots into evidence/.
"""


@case
def an_unprocessed_inbox_line_is_a_finding(base):
    note(base, "Alpha", "one")
    (base / "INBOX.md").write_text(INBOX.format(name="kite"), encoding="utf-8")
    found = notelint.check(*notelint.load(notelint.projects(base), EN)[:2], base, EN)
    lines = [d for c, _, d in found if c == "inbox"]
    assert len(lines) == 1 and "kite" in lines[0], \
        "only what is under 'To process' is pending; 'Processed' is history"


@case
def the_inbox_shows_under_a_project_filter(base):
    import io, contextlib
    note(base, "Alpha", "one")
    (base / "INBOX.md").write_text(INBOX.format(name="kite"), encoding="utf-8")
    with contextlib.redirect_stdout(io.StringIO()) as out:
        rc = notelint.main([str(base), "--project", "Alpha", "--report-only"])
    assert rc == 1 and "INBOX" in out.getvalue(), \
        "the inbox belongs to the whole base, so narrowing the report keeps it"


@case
def evidence_edited_after_the_review_is_reported(base):
    week_ago = str(TODAY - datetime.timedelta(days=7))
    (base / "Alpha" / "evidence").mkdir(parents=True, exist_ok=True)
    (base / "Alpha" / "evidence" / "bench.md").write_text("p95 41 ms\n", encoding="utf-8")
    note(base, "Alpha", "one", reviewed=week_ago, evidence=["evidence/bench.md"])
    assert ("evidence changed", "one") in run(base), \
        "the file the claim rests on changed after the claim was last confirmed"


@case
def a_note_edited_without_bumping_reviewed_is_reported(base):
    week_ago = str(TODAY - datetime.timedelta(days=7))
    note(base, "Alpha", "one", reviewed=week_ago)
    assert ("touched unreviewed", "one") in run(base), \
        "written today, confirmed a week ago: someone edited it outside the routine"


@case
def a_reviewed_bump_settles_both_modification_checks(base):
    (base / "Alpha" / "evidence").mkdir(parents=True, exist_ok=True)
    (base / "Alpha" / "evidence" / "bench.md").write_text("x\n", encoding="utf-8")
    note(base, "Alpha", "one", evidence=["evidence/bench.md"])
    found = run(base)
    assert not any(c in ("evidence changed", "touched unreviewed") for c, _ in found), \
        "confirming the note today is exactly what clears them"


@case
def modification_times_are_ignored_inside_git(base):
    week_ago = str(TODAY - datetime.timedelta(days=7))
    (base / ".git").mkdir()
    (base / "Alpha" / "evidence").mkdir(parents=True, exist_ok=True)
    (base / "Alpha" / "evidence" / "bench.md").write_text("x\n", encoding="utf-8")
    note(base, "Alpha", "one", reviewed=week_ago, evidence=["evidence/bench.md"])
    found = run(base)
    assert not any(c in ("evidence changed", "touched unreviewed") for c, _ in found), \
        "a clone rewrites every modification time; it would report every note"


@case
def code_marked_existence_only_is_not_reported_when_it_changes(base):
    week_ago = str(TODAY - datetime.timedelta(days=7))
    (base / "Alpha" / "src").mkdir(parents=True, exist_ok=True)
    (base / "Alpha" / "src" / "app.py").write_text("print(1)\n", encoding="utf-8")
    note(base, "Alpha", "marked", reviewed=week_ago,
         evidence=["src/app.py (existence only)"])
    note(base, "Alpha", "unmarked", title="Some unrelated other claim", reviewed=week_ago,
         evidence=["src/app.py"])
    found = run(base)
    assert ("evidence changed", "marked") not in found, \
        "the mark says the file changing is expected; only its absence matters"
    assert ("evidence changed", "unmarked") in found, \
        "and the same file without the mark is still reported"
    assert not any(c in ("dead evidence", "unclaimed") for c, _ in found), \
        "the mark is not part of the path: the file is found and claimed"


@case
def a_marked_file_that_is_gone_is_still_dead_evidence(base):
    note(base, "Alpha", "one", evidence=["src/gone.py (existence only)"])
    assert ("dead evidence", "one") in run(base), \
        "existence is exactly what the mark still checks"


@case
def the_spanish_mark_and_a_comment_before_it_are_understood(base):
    week_ago = str(TODAY - datetime.timedelta(days=7))
    (base / "Alpha" / "src").mkdir(parents=True, exist_ok=True)
    (base / "Alpha" / "src" / "app.py").write_text("print(1)\n", encoding="utf-8")
    d = base / "Alpha" / "notes"
    d.mkdir(parents=True, exist_ok=True)
    (d / "una.md").write_text(
        "---\ntitulo: Una afirmacion\ntipo: hecho\nproyecto: Alpha\n"
        "estado: vigente\ncreada: 2026-01-01\nrevisada: " + week_ago + "\n"
        "caduca:\nevidencia:\n  - src/app.py — el bucle (sólo que exista)\n"
        "  - src/app.py(solo que exista)\nenlaces:\n  depende-de: []\n"
        "  supera-a: []\n  bloquea: []\n  relacionada: []\n---\n\nCuerpo.\n"
        "\n## Cómo se comprueba\n\n`ls src`\n",
        encoding="utf-8")
    found = run(base, lang="es")
    assert not any(c in ("evidence changed", "dead evidence", "unclaimed")
                   for c, _ in found), \
        "with or without the accent or the space, after a comment or not"


@case
def a_doubt_left_for_weeks_is_reported(base):
    old = str(TODAY - datetime.timedelta(days=notelint.DAYS_UNVERIFIED + 3))
    fresh = str(TODAY - datetime.timedelta(days=notelint.DAYS_UNVERIFIED - 3))
    note(base, "Alpha", "stale", title="Nobody came back to check this", status="unverified",
         reviewed=old)
    note(base, "Alpha", "fresh", title="Raised this week, still open", status="unverified",
         reviewed=fresh)
    found = run(base)
    assert ("stale unverified", "stale") in found, "two weeks in doubt is abandonment"
    assert ("stale unverified", "fresh") not in found


@case
def superseding_a_note_that_is_still_current_is_reported(base):
    note(base, "Alpha", "old", title="Poll every minute")
    note(base, "Alpha", "new", title="Five minutes between polls", supersedes="old")
    assert ("supersedes a live note", "new") in run(base), \
        "either the old note becomes superseded, or the link is wrong"


@case
def a_superseded_note_needs_a_successor(base):
    note(base, "Alpha", "old", title="Poll every minute", status="superseded")
    note(base, "Alpha", "other", title="Something unrelated entirely")
    assert ("no successor", "old") in run(base), \
        "superseded by what? Without the link the reader is left guessing"


@case
def a_proper_supersession_is_quiet(base):
    note(base, "Alpha", "old", title="Poll every minute", status="superseded")
    note(base, "Alpha", "new", title="Five minutes between polls", supersedes="old")
    found = run(base)
    assert not any(c in ("supersedes a live note", "no successor") for c, _ in found)


@case
def only_a_todo_may_block(base):
    note(base, "Alpha", "measured", title="The cache hit rate is 92 percent",
         blocks="work")
    note(base, "Alpha", "gate", title="Pick the cache backend", type="todo",
         blocks="work")
    note(base, "Alpha", "work", title="Remove the warmup job", type="todo")
    found = run(base)
    assert ("permanent block", "measured") in found, \
        "a fact never closes, so whatever it blocks waits forever"
    assert ("permanent block", "gate") not in found


@case
def a_task_marked_inside_a_fact_is_hidden_work(base):
    note(base, "Alpha", "fact", title="The importer drops empty titles",
         body="Measured on the March dump.\n\n⏳ Patch the importer to keep them.")
    note(base, "Alpha", "todo", title="Ship the new importer", type="todo",
         body="⏳ Wire the flag.")
    found = run(base)
    assert ("hidden todo", "fact") in found, "OPEN.md lists todo notes, not marks in facts"
    assert ("hidden todo", "todo") not in found


def with_installed(base, project, name, version):
    """Add `installed-version: <version>` to an existing note's frontmatter."""
    p = base / project / "notes" / (name + ".md")
    p.write_text(p.read_text(encoding="utf-8").replace(
        "expires:", "installed-version: " + version + "\nexpires:", 1), encoding="utf-8")


@case
def a_todo_named_after_an_old_build_is_reported(base):
    note(base, "Alpha", "what-alpha-is", title="Alpha is a desktop app")
    with_installed(base, "Alpha", "what-alpha-is", "62")
    note(base, "Alpha", "verify-v58-on-the-laptop", title="Check sign-in on the laptop",
         type="todo")
    note(base, "Alpha", "check-sync", title="Check sync after v58 and v60", type="todo")
    note(base, "Alpha", "port-to-v2-protocol", title="Move the client to the new wire format",
         type="todo")
    found = run(base)
    assert ("past version", "verify-v58-on-the-laptop") in found, \
        "the title was corrected but the file name still says v58"
    assert ("past version", "check-sync") in found, "v60 is the highest it names, and v62 is out"
    assert ("past version", "port-to-v2-protocol") not in found, \
        "v2 has fewer digits than v62: a protocol version, not a build"


@case
def no_installed_version_means_no_version_check(base):
    note(base, "Alpha", "verify-v58-on-the-laptop", title="Check sign-in", type="todo")
    assert not any(c == "past version" for c, _ in run(base)), \
        "a project that does not number its builds is never checked"


@case
def an_installed_version_that_is_not_a_number_is_a_format_error(base):
    note(base, "Alpha", "what-alpha-is", title="Alpha is a desktop app")
    with_installed(base, "Alpha", "what-alpha-is", "latest")
    assert ("format", "what-alpha-is") in run(base)


@case
def a_current_note_without_how_to_verify_is_reported(base):
    note(base, "Alpha", "bare", title="Something claimed with no way to check it",
         verify=None)
    note(base, "Alpha", "empty", title="A heading with nothing under it", verify="")
    note(base, "Alpha", "notion", title="Maybe cache the feed list", type="idea",
         verify=None)
    found = run(base)
    assert ("no verification", "bare") in found, "the third rule, enforced"
    assert ("no verification", "empty") in found, "an empty section checks nothing"
    assert ("no verification", "notion") not in found, "an idea asserts nothing to check"


@case
def a_rule_of_conduct_is_checked_by_how_to_apply(base):
    note(base, "Alpha", "rule", title="Never deploy on a Friday", type="decision",
         verify=None, body="Body.\n\n## How to apply\n\nA Friday tag in the release log.")
    assert not any(c == "no verification" for c, _ in run(base))


@case
def how_to_verify_goes_last(base):
    note(base, "Alpha", "one", verify="Run it.\n\n## Background\n\nLong story.")
    assert ("format", "one") in run(base), \
        "a section after the verification hides it from whoever reads to the end"


@case
def unreviewed_notes_print_dependencies_first(base):
    import io, contextlib
    old = str(TODAY - datetime.timedelta(days=notelint.DAYS_UNREVIEWED + 5))
    note(base, "Alpha", "aaa-leaf", title="Built on top of the ground", reviewed=old,
         depends="zzz-ground")
    note(base, "Alpha", "zzz-ground", title="The thing underneath", reviewed=old)
    with contextlib.redirect_stdout(io.StringIO()) as out:
        notelint.main([str(base), "--report-only"])
    text = out.getvalue().split("\n  UNREVIEWED")[1].split("\n\n")[0]
    assert text.index("zzz-ground") < text.index("aaa-leaf"), \
        "confirm what a note rests on before the note, not alphabetically"


# --------------------------------------------------------------------------
# search and open: the lookups that lint nothing.
# --------------------------------------------------------------------------


def quiet(fn, *args):
    import io, contextlib
    with contextlib.redirect_stdout(io.StringIO()) as out:
        rc = fn(*args)
    return rc, out.getvalue()


@case
def search_needs_every_word_and_ranks_title_hits_first(base):
    note(base, "Alpha", "poll-interval", title="Feeds are polled every five minutes")
    note(base, "Alpha", "bench", title="A benchmark run",
         body="The poll loop held at five minutes under load.")
    note(base, "Alpha", "other", title="Something else", body="Five apples.")
    notes, V = loaded(base)
    hits = [n["id"] for n in notelint.search(notes, ["poll", "five"], V)]
    assert hits == ["poll-interval", "bench"], hits


@case
def search_ignores_accents_and_short_words_match_whole(base):
    note(base, "Alpha", "una", title="Configuración del instalador")
    note(base, "Alpha", "dos", title="Happy path for the agent")
    notes, V = loaded(base)
    assert [n["id"] for n in notelint.search(notes, ["configuracion"], V)] == ["una"]
    assert [n["id"] for n in notelint.search(notes, ["instal"], V)] == ["una"], \
        "four letters or more match inside a word"
    assert notelint.search(notes, ["app"], V) == [], "'app' is not 'happy'"


@case
def search_leaves_closed_notes_out_unless_asked(base):
    note(base, "Alpha", "old", title="Poll every minute", status="dropped")
    note(base, "Alpha", "new", title="Poll every five minutes")
    notes, V = loaded(base)
    assert [n["id"] for n in notelint.search(notes, ["poll"], V)] == ["new"]
    assert len(notelint.search(notes, ["poll"], V, everything=True)) == 2
    assert [n["id"] for n in notelint.search(notes, ["poll"], V, status="dropped")] == ["old"]


@case
def search_filters_by_project_and_type(base):
    note(base, "Alpha", "a-todo", title="Fix the importer", type="todo")
    note(base, "Alpha", "a-fact", title="The importer drops titles")
    note(base, "Beta", "b-todo", title="Fix the exporter", type="todo")
    rc, out = quiet(notelint.main, ["search", "--base", str(base),
                                    "--project", "Alpha", "--type", "todo"])
    assert rc == 0 and "a-todo" in out and "a-fact" not in out and "b-todo" not in out


@case
def search_writes_nothing(base):
    note(base, "Alpha", "one", title="Feeds are polled")
    quiet(notelint.main, ["search", "polled", "--base", str(base)])
    assert not (base / "INDEX.md").exists(), "a lookup must not regenerate the views"


@case
def open_prints_the_path_and_hands_it_to_the_system(base):
    note(base, "Alpha", "feed-poll-interval", title="Feeds are polled every five minutes")
    opened = []
    real = notelint.launch
    notelint.launch = opened.append
    try:
        rc, out = quiet(notelint.main, ["open", "feed-poll-interval", "--base", str(base)])
        rc2, _ = quiet(notelint.main, ["open", "five-minutes", "--base", str(base),
                                       "--with", "obsidian"])
    finally:
        notelint.launch = real
    assert rc == 0 and out.strip().endswith("feed-poll-interval.md")
    assert rc2 == 0, "words that match one note are enough"
    assert opened[0].endswith("feed-poll-interval.md")
    assert opened[1].startswith("obsidian://open?path=")


@case
def open_refuses_to_guess_between_several(base):
    note(base, "Alpha", "poll-a", title="Poll the feeds")
    note(base, "Alpha", "poll-b", title="Poll the mirrors")
    opened = []
    real = notelint.launch
    notelint.launch = opened.append
    try:
        rc, out = quiet(notelint.main, ["open", "poll", "--base", str(base)])
        rc2, _ = quiet(notelint.main, ["open", "nothing-like-this", "--base", str(base)])
    finally:
        notelint.launch = real
    assert rc == 1 and "exact id" in out and opened == []
    assert rc2 == 1


# --------------------------------------------------------------------------
# Size caps: one claim fits in a title and a page.
# --------------------------------------------------------------------------


@case
def a_title_past_the_cap_is_reported(base):
    note(base, "Alpha", "long", title="x" * (notelint.MAX_TITLE + 1))
    note(base, "Alpha", "fits", title="y" * notelint.MAX_TITLE)
    found = run(base)
    assert ("long title", "long") in found
    assert ("long title", "fits") not in found, "the cap itself is allowed"


@case
def a_note_past_the_cap_is_reported_unless_closed(base):
    many = "\n".join("Line " + str(k) for k in range(notelint.MAX_LINES + 10))
    note(base, "Alpha", "long", body=many)
    note(base, "Alpha", "old", title="An old and closed claim", status="dropped",
         body=many, verify=None)
    note(base, "Alpha", "short", title="A short and current claim",
         body="\n".join("Line " + str(k) for k in range(notelint.MAX_LINES - 20)))
    found = run(base)
    assert ("long note", "long") in found
    assert ("long note", "old") not in found, "nobody is meant to keep reading a closed note"
    assert ("long note", "short") not in found


# --------------------------------------------------------------------------
# history/: the notes that no longer describe the present.
# --------------------------------------------------------------------------


@case
def a_link_into_history_still_resolves(base):
    note(base, "Alpha", "old-plan", title="The first plan", status="dropped",
         where="history", verify=None)
    note(base, "Alpha", "plan", title="The plan in force", related="old-plan",
         body="It replaced [[old-plan]].")
    assert run(base) == set(), "moving a note to history must not break a link to it"


@case
def history_does_not_age_nor_watch_its_evidence(base):
    ancient = str(TODAY - datetime.timedelta(days=notelint.DAYS_UNREVIEWED + 60))
    note(base, "Alpha", "launch", title="The launch went out late", reviewed=ancient,
         evidence=["evidence/gone.md"], verify=None, where="history",
         body="\n".join("Line " + str(k) for k in range(notelint.MAX_LINES + 10)))
    note(base, "Alpha", "now", title="What is true today")
    assert run(base) == set(), \
        "no unreviewed, no dead evidence, no missing verification, no size: the past is not re-verified"


@case
def only_the_past_belongs_in_history(base):
    note(base, "Alpha", "a-todo", title="Still to do", type="todo", where="history")
    note(base, "Alpha", "a-rule", title="A decision in force", type="decision", where="history")
    note(base, "Alpha", "a-doubt", title="Not sure yet", status="unverified", where="history")
    note(base, "Alpha", "an-incident", title="The outage of last spring", type="incident",
         where="history")
    note(base, "Alpha", "an-idea", title="Something to try someday", type="idea",
         where="history")
    note(base, "Alpha", "a-dropped", title="A road not taken", type="decision",
         status="dropped", where="history")
    found = run(base)
    for wrong in ("a-todo", "a-rule", "a-doubt"):
        assert ("format", wrong) in found, wrong + " is present work, not history"
    for right in ("an-incident", "an-idea", "a-dropped"):
        assert ("format", right) not in found, right + " belongs there"


@case
def a_project_left_with_only_history_is_still_loaded(base):
    note(base, "Retired", "what-it-was", title="A tool we no longer run",
         where="history")
    note(base, "Alpha", "lesson", title="What Alpha learned from it",
         related="what-it-was")
    assert run(base) == set(), "its notes are still link targets"


@case
def a_live_note_resting_on_history_is_reported(base):
    note(base, "Alpha", "measured", title="The poller held at 41 ms", where="history")
    note(base, "Alpha", "rests", title="The interval stays at five minutes",
         depends="measured")
    note(base, "Alpha", "mentions", title="Some other claim entirely", related="measured")
    found = run(base)
    assert ("depends on history", "rests") in found, \
        "what a live note depends on cannot be past: move it back, or make the link related"
    assert ("depends on history", "mentions") not in found, "related carries no consequence"


@case
def the_same_name_in_notes_and_history_is_a_clash_not_a_loss(base):
    note(base, "Alpha", "plan", title="The plan in force")
    note(base, "Alpha", "plan", title="The first plan", status="dropped",
         where="history", verify=None)
    notes, V = loaded(base)
    assert {n["title"] for n in notes.values()} == {"The plan in force", "The first plan"}
    assert ("duplicate id", "plan") in run(base)


@case
def history_is_not_unclaimed_material(base):
    note(base, "Alpha", "old", title="An old claim", status="dropped",
         where="history", verify=None)
    note(base, "Alpha", "new", title="A new claim")
    assert not any(c == "unclaimed" for c, _ in run(base))


@case
def history_stays_out_of_the_views(base):
    note(base, "Alpha", "old-fact", title="Version one shipped on a Tuesday",
         where="history")
    note(base, "Alpha", "now", title="Version two is what runs")
    notes, V = loaded(base)
    notelint.write_views(notes, notelint.projects(base), base, V)
    index = (base / "Alpha" / "INDEX.md").read_text(encoding="utf-8")
    root = (base / "INDEX.md").read_text(encoding="utf-8")
    assert "Version two is what runs" in index
    assert "Version one" not in index and "Version one" not in root, \
        "a note in history is not part of the present"
    assert "`history/`: 1 note that" in index and "`Alpha/history/`: 1 note that" in root, \
        "but the index says it exists, and where"


@case
def search_leaves_history_out_unless_all(base):
    note(base, "Alpha", "poll-old", title="Poll every minute", where="history")
    note(base, "Alpha", "poll-new", title="Poll every five minutes")
    notes, V = loaded(base)
    assert [n["id"] for n in notelint.search(notes, ["poll"], V)] == ["poll-new"]
    assert [n["id"] for n in notelint.search(notes, ["poll"], V, everything=True)] \
        == ["poll-new", "poll-old"], "with --all it comes back, after the present"
    rc, out = quiet(notelint.main, ["search", "poll", "--base", str(base)])
    assert "+ 1 in history or closed" in out, "the past is known to exist without opening it"


@case
def verify_and_the_header_leave_history_aside(base):
    note(base, "Alpha", "old", title="An old fact", where="history",
         verify="ls old-thing")
    note(base, "Alpha", "now", title="A fact of today", verify="ls new-thing")
    rc, out = quiet(notelint.main, [str(base), "--verify"])
    assert "new-thing" in out and "old-thing" not in out
    rc, out = quiet(notelint.main, [str(base), "--report-only"])
    assert "1 note in 1 project, 1 in history" in out


@case
def the_header_counts_in_singular_and_plural(base):
    note(base, "Alpha", "one")
    rc, out = quiet(notelint.main, [str(base), "--report-only"])
    assert "1 note in 1 project " in out and "1 notes" not in out, \
        "the first line a new user reads must not say '1 notes'"
    note(base, "Beta", "two", title="A different unrelated claim")
    rc, out = quiet(notelint.main, [str(base), "--report-only"])
    assert "2 notes in 2 projects " in out


@case
def version_prints_and_exits_zero(base):
    import io, contextlib
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            notelint.main(["--version"])
    except SystemExit as e:
        assert e.code == 0, "--version is an answer, not an error"
    else:
        raise AssertionError("--version has to print the version and stop")
    assert buf.getvalue().strip() == "notelint " + notelint.__version__


# --------------------------------------------------------------------------
# Two levels: errors fail the run, reviews are a queue.
# --------------------------------------------------------------------------


@case
def every_category_belongs_to_exactly_one_level(base):
    assert not set(notelint.ERRORS) & set(notelint.REVIEWS), "a category in both levels"
    src = Path(notelint.__file__).read_text(encoding="utf-8")
    import re
    emitted = set(re.findall(r'out\.append\(\("([a-z ?]+)"', src))
    emitted |= {"inbox", "duplicate id"}
    missing = emitted - set(notelint.ERRORS) - set(notelint.REVIEWS)
    assert not missing, "categories with no level: " + ", ".join(sorted(missing))


@case
def reviews_alone_do_not_fail_the_run(base):
    old = str(TODAY - datetime.timedelta(days=notelint.DAYS_UNREVIEWED + 5))
    note(base, "Alpha", "one", reviewed=old)
    rc, out = quiet(notelint.main, [str(base), "--report-only"])
    assert rc == 0, "an unreviewed note is a queue, not a failure"
    assert "REVIEWS (" in out and "ERRORS" not in out


@case
def strict_fails_on_reviews_too(base):
    old = str(TODAY - datetime.timedelta(days=notelint.DAYS_UNREVIEWED + 5))
    note(base, "Alpha", "one", reviewed=old)
    rc, _ = quiet(notelint.main, [str(base), "--report-only", "--strict"])
    assert rc == 1


@case
def an_error_fails_the_run_and_prints_first(base):
    old = str(TODAY - datetime.timedelta(days=notelint.DAYS_UNREVIEWED + 5))
    note(base, "Alpha", "one", reviewed=old, depends="ghost")
    rc, out = quiet(notelint.main, [str(base), "--report-only"])
    assert rc == 1
    assert out.index("ERRORS (") < out.index("BROKEN LINK") < out.index("REVIEWS (") \
        < out.index("UNREVIEWED"), "errors first, each under its own level"
    assert "errors: 1 · reviews: " in out
    rc, _ = quiet(notelint.main, [str(base), "--report-only", "--exit-zero"])
    assert rc == 0


# --------------------------------------------------------------------------
# todo/ and ideas/ beside notes/, and HISTORY.md.
# --------------------------------------------------------------------------


@case
def todo_and_ideas_are_read_like_notes(base):
    note(base, "Alpha", "work", title="Ship the importer", type="todo", where="todo")
    note(base, "Alpha", "maybe", title="A plugin system some day", type="idea",
         where="ideas", depends="work")
    note(base, "Alpha", "fact", title="What it is today", related="maybe")
    assert run(base) == set(), "a todo in todo/ and an idea in ideas/ are ordinary notes"
    text = open_view(base)
    assert "todo/work.md" in text, "OPEN.md links the todo where it lives"


@case
def a_project_with_only_todo_is_a_project(base):
    note(base, "Alpha", "work", title="Start the project", type="todo", where="todo")
    assert [c.name for c in notelint.projects(base)] == ["Alpha"]


@case
def the_same_id_in_notes_and_todo_is_a_clash(base):
    note(base, "Alpha", "one")
    note(base, "Alpha", "one", title="Another claim", type="todo", where="todo")
    notes, V = loaded(base)
    assert len([n for n in notes.values() if n["id"] == "one"]) == 2, "both survive"
    assert ("duplicate id", "one") in run(base)


@case
def history_md_lists_the_past_most_recent_first(base):
    note(base, "Alpha", "live", title="Still true")
    note(base, "Alpha", "older", title="Gone long ago", status="dropped",
         reviewed=str(TODAY - datetime.timedelta(days=30)), where="history")
    note(base, "Alpha", "newer", title="Gone last week", status="dropped",
         reviewed=str(TODAY - datetime.timedelta(days=7)), where="history")
    quiet(notelint.main, [str(base)])
    text = (base / "Alpha" / "HISTORY.md").read_text(encoding="utf-8")
    assert "**Do not edit by hand" in text
    assert text.index("Gone last week") < text.index("Gone long ago")
    assert ("unclaimed", "Alpha") not in run(base), "HISTORY.md is a view, not material"


@case
def no_history_md_without_history(base):
    note(base, "Alpha", "live", title="Still true")
    quiet(notelint.main, [str(base)])
    assert not (base / "Alpha" / "HISTORY.md").exists()


# --------------------------------------------------------------------------
# Absolute paths into the base.
# --------------------------------------------------------------------------


@case
def an_absolute_path_into_the_base_is_a_format_error(base):
    (base / "Alpha" / "evidence").mkdir(parents=True)
    target = base / "Alpha" / "evidence" / "x.md"
    target.write_text("x", encoding="utf-8")
    note(base, "Alpha", "one", evidence=[str(target)])
    found = run(base)
    assert ("format", "one") in found
    assert ("dead evidence", "one") not in found, "one finding for one fault"


@case
def an_absolute_path_from_another_machine_is_recognised(base):
    (base / "Alpha" / "evidence").mkdir(parents=True)
    (base / "Alpha" / "evidence" / "x.md").write_text("x", encoding="utf-8")
    note(base, "Alpha", "one", evidence=["C:\\Users\\dana\\notes\\Alpha\\evidence\\x.md"])
    V = EN
    notes = notelint.load(notelint.projects(base), V)[0]
    msgs = [d for c, i, d in notelint.check(notes, [], base, V) if c == "format"]
    assert msgs and "`evidence/x.md`" in msgs[0], "it says what to write instead"


@case
def an_absolute_path_outside_the_base_is_left_alone(base):
    outside = Path(tempfile.mkdtemp(prefix="notelint-outside-"))
    try:
        (outside / "y.md").write_text("y", encoding="utf-8")
        note(base, "Alpha", "one", evidence=[str(outside / "y.md")])
        assert run(base) == set(), "outside the base, an absolute path is the only way"
    finally:
        shutil.rmtree(outside, ignore_errors=True)


# --------------------------------------------------------------------------
# new / review / close, and the fingerprints behind propagation.
# --------------------------------------------------------------------------


def cli(base, *args):
    return quiet(notelint.main, list(args) + ["--base", str(base)])


@case
def new_files_each_type_where_it_belongs(base):
    note(base, "Alpha", "seed")
    for t, i, where in (("todo", "do-it", "todo"), ("idea", "maybe", "ideas"),
                        ("fact", "it-is", "notes")):
        rc, out = cli(base, "new", "alpha", t, i, "--title", "A " + t)
        assert rc == 0, out
        assert (base / "Alpha" / where / (i + ".md")).is_file(), t + " goes to " + where
    found = run(base)
    assert not any(c == "format" for c, _ in found), "the template is valid as written"
    assert ("no verification", "it-is") in found, "until someone says how to verify it"
    assert ("no verification", "maybe") not in found


@case
def new_writes_the_spanish_vocabulary(base):
    d = base / "Alfa" / "notes"
    d.mkdir(parents=True)
    (d / "semilla.md").write_text("---\ntitulo: X\ntipo: hecho\nproyecto: Alfa\n"
                                  "estado: vigente\n---\n", encoding="utf-8")
    rc, out = cli(base, "new", "Alfa", "pendiente", "hacerlo", "--title", "Hacerlo")
    assert rc == 0, out
    text = (base / "Alfa" / "todo" / "hacerlo.md").read_text(encoding="utf-8")
    assert "estado: vigente" in text and "## Cómo se comprueba" in text


@case
def new_refuses_a_taken_or_malformed_id(base):
    note(base, "Alpha", "one")
    assert cli(base, "new", "Alpha", "fact", "one", "--title", "X")[0] == 2
    assert cli(base, "new", "Alpha", "fact", "Bad Id", "--title", "X")[0] == 2
    assert cli(base, "new", "Alpha", "nonsense", "fine", "--title", "X")[0] == 2
    assert cli(base, "new", "Nowhere", "fact", "fine", "--title", "X")[0] == 2
    assert cli(base, "new", "Alpha", "fact", "fine", "--title", "x" * 200)[0] == 2


@case
def review_dates_today_and_keeps_bom_and_crlf(base):
    old = str(TODAY - datetime.timedelta(days=90))
    note(base, "Alpha", "one", reviewed=old)
    p = base / "Alpha" / "notes" / "one.md"
    p.write_bytes(b"\xef\xbb\xbf" + p.read_bytes().replace(b"\n", b"\r\n"))
    rc, out = cli(base, "review", "one")
    assert rc == 0, out
    raw = p.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf") and b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"")
    assert ("reviewed: " + str(TODAY)).encode() in raw
    assert run(base) == set()


@case
def review_refuses_an_unknown_id(base):
    note(base, "Alpha", "one")
    assert cli(base, "review", "one", "ghost")[0] == 2


def redate(base, project, name, when, folder="notes"):
    p = base / project / folder / (name + ".md")
    text = p.read_text(encoding="utf-8")
    import re
    p.write_text(re.sub(r"(?m)^reviewed: .*$", "reviewed: " + when, text), encoding="utf-8")


@case
def a_dependency_confirmed_unchanged_fires_no_propagation(base):
    older = str(TODAY - datetime.timedelta(days=20))
    note(base, "Alpha", "ground", title="The underlying decision", reviewed=older)
    note(base, "Alpha", "leaf", title="Something built on top", reviewed=older,
         depends="ground")
    notes, V = loaded(base)
    notelint.save_fingerprints(base, notes, ["leaf"], V)
    redate(base, "Alpha", "ground", str(TODAY))       # confirmed, not a word changed
    assert ("propagation", "leaf") not in run(base)


@case
def a_dependency_whose_body_changed_still_fires(base):
    older = str(TODAY - datetime.timedelta(days=20))
    note(base, "Alpha", "ground", title="The underlying decision", reviewed=older)
    note(base, "Alpha", "leaf", title="Something built on top", reviewed=older,
         depends="ground")
    notes, V = loaded(base)
    notelint.save_fingerprints(base, notes, ["leaf"], V)
    note(base, "Alpha", "ground", title="The underlying decision", body="It changed.")
    assert ("propagation", "leaf") in run(base)


@case
def review_records_the_fingerprints_inside_the_base(base):
    note(base, "Alpha", "ground", title="The underlying decision")
    note(base, "Alpha", "leaf", title="Something built on top", depends="ground")
    cli(base, "review", "leaf")
    import json
    data = json.loads((base / ".notelint" / "fingerprints.json").read_text(encoding="utf-8"))
    assert "ground" in data["fingerprints"]["leaf"]
    assert ("unclaimed", "Alpha") not in run(base)


@case
def an_unreadable_fingerprint_file_is_noisy_not_silent(base):
    older = str(TODAY - datetime.timedelta(days=20))
    note(base, "Alpha", "ground", title="The underlying decision")
    note(base, "Alpha", "leaf", title="Something built on top", reviewed=older,
         depends="ground")
    (base / ".notelint").mkdir()
    (base / ".notelint" / "fingerprints.json").write_text("{not json", encoding="utf-8")
    assert ("propagation", "leaf") in run(base)


@case
def close_turns_a_todo_into_a_fact_in_history(base):
    note(base, "Alpha", "work", title="Ship the importer", type="todo", where="todo")
    rc, out = cli(base, "close", "work", "--title", "The importer shipped")
    assert rc == 0, out
    p = base / "Alpha" / "history" / "work.md"
    assert p.is_file() and not (base / "Alpha" / "todo" / "work.md").exists()
    text = p.read_text(encoding="utf-8")
    assert "type: fact" in text and "title: The importer shipped" in text
    assert "**Was a todo until " + str(TODAY) + ".**" in text
    assert run(base) == set()


@case
def close_keeps_it_in_notes_while_something_rests_on_it(base):
    note(base, "Alpha", "work", title="Ship the importer", type="todo", where="todo")
    note(base, "Alpha", "next", title="Document the importer", type="todo",
         where="todo", depends="work")
    rc, out = cli(base, "close", "work")
    assert rc == 0, out
    assert (base / "Alpha" / "notes" / "work.md").is_file()
    assert ("depends on history", "next") not in run(base)


@case
def close_with_keep_files_it_in_notes(base):
    note(base, "Alpha", "work", title="Ship the importer", type="todo", where="todo")
    assert cli(base, "close", "work", "--keep")[0] == 0
    assert (base / "Alpha" / "notes" / "work.md").is_file()


@case
def close_refuses_what_is_not_an_open_todo_or_still_blocks(base):
    note(base, "Alpha", "fact", title="A fact")
    note(base, "Alpha", "later", title="Then this", type="todo", where="todo")
    note(base, "Alpha", "first", title="First this", type="todo", where="todo",
         blocks="later")
    assert cli(base, "close", "fact")[0] == 2
    assert cli(base, "close", "first")[0] == 2, "a fact cannot block"
    assert (base / "Alpha" / "todo" / "first.md").is_file(), "refused means untouched"


@case
def close_says_why_a_blocked_todo_stays_in_notes(base):
    note(base, "Alpha", "first", title="First this", type="todo", where="todo",
         blocks="later")
    note(base, "Alpha", "later", title="Then this", type="todo", where="todo")
    note(base, "Alpha", "after", title="And this after", type="todo", where="todo",
         depends="later")
    rc, out = cli(base, "close", "later")
    assert rc == 0, out
    assert (base / "Alpha" / "notes" / "later.md").is_file()
    assert "after rests on it" in out, "a note that depends on it does rest on it"
    assert "first still lists it under 'blocks'" in out, \
        "the note that blocks it does not rest on it, and the message must not say so"
    assert "first rests" not in out and "after, first" not in out


# --------------------------------------------------------------------------
# The width of the report.
# --------------------------------------------------------------------------


def a_long_finding(base):
    old = str(TODAY - datetime.timedelta(days=10))
    note(base, "Alpha", "one", reviewed=old, depends="two")
    note(base, "Alpha", "two", title="A different unrelated claim")


@case
def a_finding_stays_on_one_line_when_the_report_is_piped(base):
    a_long_finding(base)
    rc, out = quiet(notelint.main, [str(base), "--report-only"])
    rows = [l for l in out.splitlines() if "two was reviewed" in l]
    assert len(rows) == 1 and rows[0].endswith("this is still at " + str(
        TODAY - datetime.timedelta(days=10))), \
        "captured output is not a terminal: grep and diff must see the finding whole"
    assert quiet(notelint.main, [str(base), "--report-only", "--width", "0"])[1] == out, \
        "--width 0 never wraps, whatever the output is"


@case
def width_wraps_a_finding_under_its_own_start(base):
    a_long_finding(base)
    whole = quiet(notelint.main, [str(base), "--report-only"])[1]
    message = next(l for l in whole.splitlines()
                   if "two was reviewed" in l).split(None, 1)[1]
    rc, out = quiet(notelint.main, [str(base), "--report-only", "--width", "50"])
    assert rc == 0, "wrapping changes the layout, never the exit code"
    lines = out.splitlines()
    at = next(k for k, l in enumerate(lines) if "two was reviewed" in l)
    col = lines[at].index("two was reviewed")
    got = [lines[at]]
    while lines[at + len(got)].startswith(" " * col) and lines[at + len(got)].strip():
        got.append(lines[at + len(got)])
    assert len(got) > 1, "a message longer than the width has to wrap"
    assert all(len(l) <= 50 for l in got), "no line runs past the width asked for"
    assert all(l[:col].strip() == "" for l in got[1:]), \
        "a continuation starts where the message started"
    assert " ".join(l[col:] for l in got) == message, "wrapping loses no word"


@case
def width_never_splits_a_path(base):
    long_path = "evidence/" + "a-very-long-directory-name/" * 3 + "gone.md"
    note(base, "Alpha", "one", evidence=[long_path])
    rc, out = quiet(notelint.main, [str(base), "--report-only", "--width", "40"])
    assert long_path in out, "a path cut in two can no longer be copied or found"


@case
def the_readme_shows_what_the_linter_prints(base):
    """The report in the README is not typed by hand: it is this run, on the
    day it names, at the width it names. Only inside a clone, where the two
    checks that read modification times stay quiet (see `under_git`)."""
    import re
    root = Path(notelint.__file__).resolve().parent
    readme, example = root / "README.md", root / "example"
    if not (readme.is_file() and example.is_dir() and notelint.under_git(example)):
        return
    shown = re.search(r"```\n(  notelint - .*?)\n```",
                      readme.read_text(encoding="utf-8"), re.S)
    assert shown, "the README no longer carries a sample report"
    day = re.search(r"\((\d{4})-(\d\d)-(\d\d)\)", shown.group(1))
    real = notelint.TODAY
    notelint.TODAY = datetime.date(*map(int, day.groups()))
    try:
        rc, out = quiet(notelint.main, [str(example), "--report-only", "--width", "80"])
    finally:
        notelint.TODAY = real
    assert rc == 1, "the example ships errors on purpose"
    assert out.strip("\n") == shown.group(1), \
        "the README's sample report is not what the linter prints for example/"


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


def test_suite():
    """For pytest, which only collects test_* functions: the same cases, run
    by the same loop, so `python -m pytest` and this script agree."""
    assert main() == 0, "a case failed: see its FAIL line in the captured output"


if __name__ == "__main__":
    sys.exit(main())
