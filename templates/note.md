---
title: One claim, not a topic. If it needs subheadings, it is two notes. On a todo, the next step in the imperative, with its size in brackets if it is trivial.
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

**Required on every `current` note** (an `idea` is the only exemption), and it
comes last. It says **what to look at and what you must see** for the note to
stay current: the command, the path or the screen, and the result that confirms
it (`→ 0`, `→ empty`, `→ 200`, `→ 0 failed`). If you cannot name the method or
say which result confirms it, the note is not `current`: it is `unverified`. If
the note is a rule of conduct, the section is titled "How to apply" and says how
you notice the rule was broken. A todo that someone closes by decision says so,
and that is its verification.

Four more rules, each learned from a verification that did not work:

- **Commands use the same anchors as `evidence:`** — paths relative to the
  project or to the base, or absolute — and the file or folder a command reads
  goes **in `evidence:` as well**. Then, when that path moves, the linter tells
  you for free.
- **If the verification is "path X exists", it is not a command: it is a line
  in `evidence:`.** The linter already checks it on every run.
- **A measured number lives in exactly one note.** Here the expected result is
  an invariant; if all you can give is today's figure, date it **and** say what
  getting a different one would mean.
- **Verifying is looking, not changing.** If the method writes to production,
  deletes something or changes a device, it is not a verification: it is a test.
  It goes in the body, with a link to the note that says who has to agree first.

---

_Everything from here down is guidance. Delete it in the real note: "How to
verify" has to be the last section, and the linter says so if it is not._

## Filling in the fields

- **type** — `decision` (something was chosen, and why) · `fact` (something
  checked: measured or observed; if the note explains HOW something is done or
  WHERE it lives, it is a `reference`) · `todo` (not done yet) · `idea` (no
  commitment; the only type exempt from "How to verify", and it never appears in
  `OPEN.md`) · `incident` (it went wrong, with the lesson) · `reference` (where
  something lives, or how it is done).
- **id** — the file name without `.md`. Keep it to lowercase letters, digits and
  hyphens. It is global to the whole base, so if the name would fit another
  project just as well (`build-the-app`, `code-signing`…), put the project's
  name in front. In the body, `[[id]]` is a link and the linter checks it;
  anything between backticks is not a link.
- **format** — `evidence:` takes one path per line, each with a hyphen; links
  go in brackets on one line (`[a, b]`).
- **status** — `current` · `superseded` (another note replaced it, and says so
  with `supersedes`) · `dropped` (decided against, with the reason) ·
  `unverified` (needs checking; it **keeps blocking** whatever it blocked, and
  checking it is the first job, not treating it as closed).
  **A todo that got done is closed in its own note**, without creating another:
  `type` becomes `fact`, the title is rewritten as a statement, "How to verify"
  now checks that it is done, and one line says "Was a todo until YYYY-MM-DD".
  The file is not renamed (links go by id). Two exceptions: if it has a
  non-empty `blocks`, clear that first or close it as `superseded` plus a new
  note; and if the outcome carries more than the todo note can hold, also
  `superseded` plus a new note.
- **expires** — optional. After this date the claim must be re-verified.
- **reviewed** — bump it whenever someone confirms the note still holds, even if
  not a word changes. After 60 days the linter flags it (180 for a `reference`,
  an `incident`, or a `decision` with `depends-on`; an `idea` never ages). An
  `unverified` note left more than 14 days is reported too. Write the date the
  linter prints in its header.
- **installed-version** — optional, and only on the one note that says which
  build of the project is installed, as `N` or `vN`. With it, a current todo
  whose name or title stayed on an older build is reported.
- **evidence** — paths relative to the project or the base, absolute paths, or
  URLs. It is also what **claims** material: for something to stop showing under
  `UNCLAIMED`, cite its path here (or between backticks in the body); naming it
  is not enough. The linter checks that **paths** exist on disk, and reports
  one that changed after the note was last reviewed; it **does not check
  URLs** — any address passes, a dead one included.
- **⏳** in the body marks a loose task in a note that is not a `todo`. The
  linter reports it, because written that way it never reaches `OPEN.md` and the
  work drops out of sight. If there is a task, it gets a `todo` note of its own.
  The mark is not the real signal, though: a section called "The fix" or "What
  is missing" inside a `fact`, an `incident` or a `decision` is hidden work just
  the same. The right shape is one line — `what is missing has its own note:
  [[its-id]]` — with the detail living in the `todo`.

### The four link types, and the evidence field

| Link | Means |
|---|---|
| `depends-on` | If that note **is reviewed or changes**, this one needs re-reading. The linter reports it as `PROPAGATION`. |
| `supersedes` | This note makes that one obsolete, and that one becomes `superseded` (or was already `dropped`). Pointing `supersedes` at a note that is still open is an error. |
| `blocks` | That work **cannot start** until this closes. Not "better afterwards", not "same topic": that is `related`. It is written on the blocking note; if, while writing a todo, you see it waits on another, go to that other note and put the link there instead of leaving it in prose. **Only `todo` notes block**: a `fact` or a `decision` that blocks holds its target forever. `OPEN.md` is built from it. |
| `evidence` | Not a link: it has its own field, above, and the linter checks that its paths exist. |
| `related` | No direction, no consequence. The cheap link, and the right one towards a `dropped` note (towards a `superseded` one it is a zombie: link to whatever superseded it). |

Field names can be Spanish instead (`titulo`, `tipo`, `estado`, `enlaces`,
`version-instalada`…) — see `VOCAB` in `notelint.py`. Keep one vocabulary per
knowledge base.
