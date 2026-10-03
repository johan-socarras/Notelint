---
name: notelint
description: Maintain a notelint knowledge base — a folder of linked markdown notes that holds the real state of one or more projects. Use when asked to update, review or clean up the notes or the knowledge base; to record a decision, a measured fact, an incident or an open item; to say what work is open, blocked or unverified; or to recall what was decided earlier and why. Also use it when new material lands in a project and something has to account for it.
---

# Maintaining a notelint knowledge base

A note is **one claim with a status**, not a document. The linter reads the whole
graph and reports what no longer holds together. Your job is the judgment it
cannot do: deciding what is true, and writing it down.

## 1. Find the base

A knowledge base is a directory whose subdirectories contain a `notes/` folder:

```
<base>/
  ProjectA/notes/*.md
  ProjectB/notes/*.md
```

Look for `notelint.py` near it, or for that `*/notes/*.md` shape. If several
candidates exist, or none, **ask once** and use that answer for the rest of the
session rather than guessing each time.

## 2. Run the linter before reading or writing anything

```bash
cd <base> && python tools/notelint.py . --project <name>    # a base made by the installer
python notelint.py <base> --project <name>                # a clone of the repository
```

With the project the conversation is about (see "Scope" below); without
`--project` only when no project is in view. The whole report mixes every
project's findings, and the one that matters gets buried. The views are
regenerated whole either way, and links into other projects still resolve.

Its report is the starting point — not memory, and not whatever looks urgent.
Exit code `1` means there are findings. Read them first, and let them tell you
what the base needs before you decide what to add.

Lines under `INBOX` are what someone changed by hand and why, left in
`INBOX.md` at the base. Do not ask them what they touched: it is written
there. Account for each line like any other fact, then move it under
`## Processed`.

## 3. Follow the protocol

Eight steps and three rules. In a base made by the installer it is
`<base>/PROTOCOL.md`; in a clone of the repository it is `docs/PROTOCOL.md`.
**Read it and obey it**; do not improvise a shortened version. In particular it is what tells you to *fix* an
existing note rather than stack a new one on top, and to propagate a change to
whatever declared a dependency on it.

For the shape of a note and what each field means, use `templates/note.md`,
which sits beside the protocol in both layouts.
`OPEN.md` shows the work (with blocking chains in order) and `INDEX.md` shows the
content. Both are generated — never edit them by hand.

## 4. If you are only asked a question

"What is open in X?", "what did we decide about Y?": **search first, not the
index.**

```bash
python tools/notelint.py search <words> [--project P] [--type T] [--status S] [--all]
python notelint.py search <words> --base <base>     # from a clone
```

It answers in a few lines with the notes that contain every word, best first.
Read only the ones you need (it prints their paths) and answer **without
running the linter, without reading `INDEX.md` or `OPEN.md` whole, and without
opening the protocol**. If the person wants to see a note, `open <id>` opens it
in their program and prints the path as well.

A full `--report-only` run is for questions about the base as a whole ("what
is open?" with no project, "are there findings?"). If that report has
findings, say so: they are part of the answer.

**A mechanical operation — moving, renaming, deleting — needs no audit
first.** Do it; one search for the old path, limited to the `notes/` folders
and any scripts, fixes the citations; and run the linter **once at the end**,
`--report-only`, on the project you touched. If something mechanical runs past
five minutes, stop and say so in one line.

## 5. Scope

- If the conversation is about one project, "update the notes" means **that
  project**.
- With no project in view, it means **all of them**.
- Explicit instructions about what to update always win over this default.

## What the files do not say, and you need to know

- **Someone else may be editing the same base right now** — another session, or a
  colleague. Before touching a note you did not write in this session, check its
  `reviewed` date and the file's modification time. Do not overwrite recent work,
  and if the change you were about to make is already there, say so and move on
  instead of redoing it.
- **Never invent a "How to verify".** If you cannot name the command, path or
  screen where someone could check the claim, the note is not `current` — it is
  `unverified`. A verification step that does not work is worse than none,
  because the next reader will trust it.
- **Never delete a note to tidy up.** A wrong turn becomes `dropped` **with the
  reason**, so nobody proposes it again in six months believing it is new. A
  replaced note becomes `superseded`, and the note replacing it says so.
- **The date you write in `reviewed` is the one the linter prints** in its
  header — the machine's local date — not your own clock, which may run on UTC
  and turn the day over hours early. A future `reviewed` is a format error.
- **Report what changed** when you finish: notes touched, closed, opened. A
  silent update is indistinguishable from no update.

## Why this skill is short

The procedure lives in the protocol file, the format in `templates/note.md`, and
the facts live in the notes. **If this skill restated them it would become a
fourth document that drifts out of sync** — exactly what the knowledge base
exists to prevent.

Do not add project state, file paths, versions or open items here. All of that is
a note. When something seems to be missing from this skill, the right fix is
almost always to write or correct a note instead.
