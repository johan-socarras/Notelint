# Changelog

What changes in each version of notelint. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the versions
follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- A third picture in the README, at the top of "Working with an AI agent": the
  loop between you, your agent and the linter, and the other ways into the notes
  (Obsidian or any Markdown editor, the file manager). Drawn by
  [docs/make_images.py](docs/make_images.py), whose `--check` now covers it.

## [2.0.0] - 2026-11-11

The report now tells apart what is broken from what only asks for a look, and
the linter writes the parts of a note that nobody should type from memory.

### Changed

- **Findings come in two levels, and only errors fail the exit code.** `ERRORS`
  are things written wrong or broken: a dead link, a missing file, a malformed
  date. `REVIEWS` are a queue: a note nobody has confirmed in two months, a
  dependency that moved on. In 1.0.0 every finding returned exit code `1`, so a
  note turning sixty days old broke CI; now it does not. `--strict` brings the
  old behaviour back.
- **Open work and loose ideas have their own folders.** A project keeps its
  claims in `notes/`, its todos in `todo/` and its ideas in `ideas/`. The three
  are read alike, so a base that keeps everything in `notes/` still works, and a
  directory with any of them is a project.
- **`propagation` fires for a real change, not for a date.** With a fingerprint
  on record, a dependency confirmed later without a word changed fires nothing.
  Without one it still fires on the dates alone.
- **An absolute evidence path into the base is a `format` error** that names
  the relative path to write instead. It worked on the machine that wrote it
  and was dead in every clone.
- **On a terminal, findings wrap to its width.** Piped or redirected, each one
  stays on a single line, as before, so `grep` and `diff` see whole findings.

### Added

- `new <project> <type> <id> --title "…"` writes a note from the template, dated
  today, in the folder its type belongs to.
- `review <id> …` sets `reviewed` to today and records a fingerprint of each
  note the reviewed ones depend on, in `.notelint/fingerprints.json`.
- `close <id>` turns a todo that is done into a fact in its own file, and moves
  it to `history/` when no live note rests on it.
- `HISTORY.md`, a generated view of the past for each project with a
  `history/` folder.
- `--strict`, to fail on reviews too, and `--width N`, to wrap the findings at
  a fixed number of columns (`0` never wraps).
- [docs/REFERENCE.md](docs/REFERENCE.md), with the fine print that used to sit
  in the README, and two pictures in the README drawn from the bundled example
  by [docs/make_images.py](docs/make_images.py).
- A test that the sample report in the README is what the linter prints.

### Upgrading from 1.0.0

Nothing in a base has to change: notes in `notes/` are read as before. A CI job
that relied on exit code `1` for every finding needs `--strict`. To replace the
linter inside an existing base, delete `tools/notelint.py` and run the installer
again; it leaves notes, `PROTOCOL.md` and the templates alone.

## [1.0.0] - 2026-11-09

The first public release.

### Added

- 26 checks over a folder of markdown notes read as one graph, from broken
  links and dead evidence to `propagation` (a note reviewed after something that
  depends on it) and `unclaimed` (a file no note explains).
- `search` and `open`, the lookups that lint nothing.
- Generated `INDEX.md` and `OPEN.md`, with blocking chains drawn in the order
  the work has to happen.
- A `history/` folder per project for the notes that no longer describe the
  present.
- English and Spanish field vocabularies, detected automatically.
- One file, no dependencies, Python 3.8+; exit code `1` on findings.
- A one-command installer for Linux, macOS and Windows, and an agent skill for
  Claude Code.

[Unreleased]: https://github.com/johan-socarras/notelint/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/johan-socarras/notelint/releases/tag/v2.0.0
[1.0.0]: https://github.com/johan-socarras/notelint/releases/tag/v1.0.0
