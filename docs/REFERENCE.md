# Reference

The fine print behind the [README](../README.md): rules you only need once you
are keeping a base with notelint. The routine that surrounds the linter is in
[PROTOCOL.md](PROTOCOL.md).

## How material is claimed

Material is claimed by **citing its path** — in `evidence:`, or between backticks
in the body — not by mentioning its name. Citing something deep also claims the
directories above it, so quoting `evidence/shots/panel.md` does not leave
`evidence` looking unclaimed. And citing a directory by name claims what it
holds — but only a directory you actually named: a parent that is merely
implied by a deeper citation does not claim its other children, or one file
would claim every sibling. Matching on the bare name was the earlier
behaviour and it had a hole you could drive a project through: a new directory
called `legal`, `src` or `tests` never showed up, because those words were
already written somewhere in the notes for an unrelated reason.

### A comment after the path

You can write a comment after the path, and it does not have to be a bare
path on its own line. The comment starts at ` —` (em dash), ` (` or ` §`:

```yaml
evidence:
  - evidence/bench-2026-08-20.md — the p95 numbers
  - docs/HANDOFF.md §4
  - reports/Q3 Report - final.pdf
```

A plain hyphen is **not** a delimiter, deliberately: too many real file names
contain one, and `Q3 Report - final.pdf` has to stay citable as itself.

### Source code: `(existence only)`

Source code is the one kind of evidence that is *supposed* to change. Cite
`src/poller.go` and every build would report `evidence changed` until nobody
reads the report. End the line with `(existence only)` and the linter checks
only that the file is still there; the note still ages like any other, and that
is what gets it re-checked:

```yaml
evidence:
  - src/poller.go (existence only)
  - evidence/bench-2026-08-20.md
```

Keep the mark for code. A spec, a benchmark or a contract changing under a note
is exactly what `evidence changed` is for. Spanish notes write it
`(sólo que exista)`.

### A path with a space

One limit to know before it puzzles you: **between backticks in the body, the
first segment of a path cannot contain a space.** A backticked span may be a
shell command, and that guard is what stops one from claiming half the project.
So a file sitting loose at the top of a project with a space in its name, like
`Q3 Report.pdf`, is claimed from `evidence:`, where every line is a path and the
guard does not apply.

## `search` and `open`

`search` folds accents and looks in the title, the id and the body. Words of
three letters or fewer match whole (`app` does not find `happy`); longer ones
match inside a word (`instal` finds `installer`). Hits in the title come first,
then current notes, then todos, then the most recently reviewed.
`superseded` and `dropped` notes stay out unless you pass `--all` or ask for
that `--status`, and notes in `history/` unless you pass `--all`; a last line
says how many were left out. Exit code `1` means nothing matched.

`open` takes an id, or words that match exactly one note, and hands the file to
whatever your system opens it with — or `--with obsidian`, `--with code`. It
always prints the path too, so an agent without a screen gets the answer.
`--base` defaults to the current directory, so from a base made by the
installer it is just `python tools/notelint.py search …`.

## What the linter does with `history/`

The linter still loads it, so every link into it resolves, and checks its
format and its links. Nothing else: it does not age, its evidence is not
watched, and it is left out of `INDEX.md` (one line says how many and where),
`OPEN.md`, `--verify` and `search` without `--all`. The one new finding is
`depends on history`: a live note that rests on one of these. To see the past at
a glance, each project with a history gets a generated `HISTORY.md`: one line
per note, most recently reviewed first.
