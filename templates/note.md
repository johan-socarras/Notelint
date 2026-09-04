---
title: One claim, not a topic. If it needs subheadings, it is two notes.
type: fact
project: YourProject
status: current
created: 2026-01-01
reviewed: 2026-01-01
expires:
evidence:
  - evidence/some-file.md §3
  - https://example.com/spec
links:
  depends-on: []
  supersedes: []
  blocks: []
  related: []
---

## What it is

Five to thirty lines. If it doesn't fit, it's two notes with a link between them.

## Why it matters

Optional. Include it when the consequence isn't obvious from the claim itself.

## How to verify

**Required on every `current` note.** The exact command, path or screen where
someone can see whether this still holds. Without it, in two months nobody can
tell this from folklore, and the only remedy is to re-audit everything.

---

## Filling in the fields

- **type** — `decision` (something was chosen, and why) · `fact` (something
  measured) · `todo` (not done yet) · `idea` (no commitment) · `incident` (it
  went wrong, with the lesson) · `reference` (where something lives).
- **status** — `current` · `superseded` (another note replaced it) · `dropped`
  (decided against, keep the reason) · `unverified` (needs checking).
- **expires** — optional. After this date the claim must be re-verified.
- **reviewed** — bump it whenever someone confirms the note still holds, even if
  not a word changes. After 60 days the linter flags it.
- **evidence** — paths relative to the project or the base, absolute paths, or
  URLs. The linter checks that they exist.

### The four link types

| Link | Means |
|---|---|
| `depends-on` | If that note changes, **this one needs re-reading**. |
| `supersedes` | This note replaces that one, which becomes `superseded`. |
| `blocks` | That work can't start until this closes. `OPEN.md` is built from it. |
| `related` | No direction, no consequence. The cheap link. |

Field names can be Spanish instead (`titulo`, `tipo`, `estado`, `enlaces`…) —
see `VOCAB` in `notelint.py`. Keep one vocabulary per knowledge base.
