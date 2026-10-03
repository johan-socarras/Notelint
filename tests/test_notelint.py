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
         blocks="", related="", body="Body.", verify="Read it again."):
    d = base / project / "notes"
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


# --------------------------------------------------------------------------
# tools/power.py. Not the linter, but it turns machines off, so the guard
# that keeps a countdown cancellable is worth a test.
# --------------------------------------------------------------------------


@case
def a_negative_countdown_is_refused(base):
    import subprocess
    root = Path(__file__).resolve().parent.parent
    r = subprocess.run([sys.executable, str(root / "tools" / "power.py"),
                        "shutdown", "--in", "-5", "--dry-run"],
                       capture_output=True, text=True)
    assert r.returncode != 0, "--in -5 must not reach the shutdown command"
    assert "negative" in (r.stderr + r.stdout),         "and it has to say why, not just fail"


@case
def zero_still_means_act_at_once(base):
    import subprocess
    root = Path(__file__).resolve().parent.parent
    r = subprocess.run([sys.executable, str(root / "tools" / "power.py"),
                        "shutdown", "--in", "0", "--dry-run"],
                       capture_output=True, text=True)
    assert r.returncode == 0, "--in 0 is documented and must keep working"


@case
def a_space_in_the_first_segment_still_blocks_the_claim(base):
    note(base, "Alpha", "one", evidence=["Q3 Report.pdf"])
    (base / "Alpha" / "Q3 Report.pdf").write_text("x", encoding="utf-8")
    assert any(c == "unclaimed" for c, _ in run(base)),         "documented limit: the guard that stops a backticked command from "         "claiming half the project also costs top-level names with spaces"


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
