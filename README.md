# notelint

**A linter for the notes you keep about a project.**

Documentation doesn't rot because people are lazy. It rots because nothing ever
checks whether it is still true. A fact gets written down once, the thing it
described changes six weeks later, and the file keeps asserting the old version
with total confidence — while its modification date says "yesterday", because
someone fixed a typo.

`notelint` treats a folder of markdown notes the way a linter treats source
code: it reads the whole graph and reports what no longer holds together.

```
  notelint - 9 notes in 1 project(s)   (2026-09-03)
  ------------------------------------------------------------------
  Kestrel                9 notes     2 open     0 unverified
  ------------------------------------------------------------------

  DEAD EVIDENCE  (1)
    mystery-benchmark      evidence/fts-benchmark-2026-08-26.csv

  PROPAGATION  (1)
    feed-poll-interval     sqlite-over-postgres was reviewed 2026-09-01,
                           this is still at 2026-08-20

  UNCLAIMED  (1)
    Kestrel                evidence/screenshots
```

## Try it in thirty seconds

```bash
git clone https://github.com/johan-socarras/notelint
cd notelint
python notelint.py example
```

No dependencies, Python 3.8+. The bundled example ships with **three deliberate
faults** so the first run shows you what a finding looks like. Exit code is `1`
when there are findings, so it drops straight into CI.

> If you clone this repo months from now, the example will also report
> `UNREVIEWED` notes. That is not rot in the example — that is the tool working.

## The idea

A note is **one claim with a status**, not a document. "SQLite, not Postgres" is
a note. "Architecture" is forty notes in a trench coat.

Every note carries a small header, and — this is the part that does the real
work — a section saying **how to check whether it is still true**:

```markdown
---
title: Feeds are polled every 5 minutes, not every minute
type: fact             # decision | fact | todo | idea | incident | reference
project: Kestrel
status: current        # current | superseded | dropped | unverified
created: 2026-08-20
reviewed: 2026-08-20
expires:               # optional: re-verify after this date
evidence:
  - evidence/bench-2026-08-20.md
  - https://example.com/rfc
links:
  depends-on: [sqlite-over-postgres]
  supersedes: []
  blocks: []
  related: [retry-storm-incident]
---

## What it is

One minute was tried and abandoned: on 300 feeds on 1 vCPU, p95 write latency
went from 41 ms to 340 ms, because every poll opens a write transaction.

## How to verify

`grep -n "pollInterval" internal/poller/poller.go`
```

Without that last section, in two months nobody can tell a fact from folklore,
and the only way to find out is to audit everything from scratch. With it,
verifying a claim costs one command.

## The links are typed, and that is the point

`related:` is cheap and says nothing. The other three carry consequences the
linter can act on:

| Link | Means |
|---|---|
| `depends-on` | If that note changes, **this one needs re-reading**. |
| `supersedes` | This note replaces that one, which becomes `superseded`. |
| `blocks` | That work can't start until this closes. `OPEN.md` is built from it. |
| `related` | No direction, no consequence. |

## What it checks

| Check | Fires when |
|---|---|
| `broken link` | `[[name]]` points at a note that doesn't exist (code spans are ignored) |
| `dead evidence` | A cited file is gone from disk |
| `expired` | `expires` has passed and the note still says `current` |
| `unreviewed` | A `current` note hasn't been confirmed in 60 days |
| `zombie` | A `superseded`/`dropped` note is still treated as live by a current one |
| `unblocked` | A blocker closed, so blocked work is free and nobody noticed |
| **`propagation`** | A note was reviewed **after** something that declared a dependency on it |
| **`unclaimed`** | A file or folder is in the project and **no note explains why it exists** |
| `duplicate?` | Two current notes in one project have near-identical titles |
| `duplicate id`, `wrong project`, `format` | Structural mistakes |

The last two in bold are the ones I haven't seen packaged elsewhere, and they
are the ones that make the base behave like a system instead of a folder:

- **`propagation`** is the nerve. You correct one note, and the linter tells you
  which notes downstream just became suspect. Rot spreads; so should the alarm.
- **`unclaimed`** is inventory. Drop a folder of screenshots into a project and
  you have thirty seconds of context and two months of "what is this, and can I
  delete it?". The linter refuses to let material sit there unexplained.

## Generated views, never hand-edited

Each run rewrites `INDEX.md` (everything, by project and type) and `OPEN.md`
(`todo` notes split into ready / blocked-by-another-note / unverified). Delete
them and they come back identical. You change what's in them by editing a note's
`status`, not by editing the list — which is exactly why the list can't drift
from reality.

## Multi-project, multi-language

Any directory containing a `notes/` folder is a project. There is nothing to
register: create the folder and it's picked up. Links cross project boundaries,
so a lesson learned in one project can be a dependency of another.

Field names come from a vocabulary, so notes can be kept in the language the
team actually thinks in. English and Spanish ship in the box (`--lang`, or let
it auto-detect); adding another is a dictionary entry in `VOCAB`.

## Working with an AI agent

This is where it started. If you hand an agent a folder of project docs, it will
read stale ones with the same confidence as fresh ones — and a confident wrong
answer costs more than no answer. Three properties matter here more than they do
for a human reader:

1. **`How to verify` gives the agent a cheap action** instead of an expensive
   re-derivation from source.
2. **`unclaimed` stops silent accumulation.** Agents generate files. Every one of
   them should have to justify itself.
3. **Exit code 1** means "the knowledge base is inconsistent" is a condition you
   can gate on, not a judgment call.

`docs/PROTOCOL.md` is the routine I use: run the linter before writing anything,
fix notes rather than stack new ones, propagate, then run it again until clean.

## Design notes

- **No dependencies, one file.** The parser reads a deliberately small subset of
  YAML. If the format ever needs real YAML, the format is too complicated.
- **Flat `notes/`, on purpose.** Folders by topic reintroduce "where does this
  go?", and that question is what produces the same fact filed in two places.
- **Nothing is deleted.** Wrong turns become `dropped` with the reason, so nobody
  proposes them again in six months believing they're new.
- **It checks structure, not truth.** It knows a note hasn't been reviewed in 60
  days. It cannot know whether it's still correct — that's what `How to verify`
  is for, and why a human or an agent still has to do the reading.

## Tests

```bash
python tests/test_notelint.py
```

Nineteen tests, no framework. Every check plants its own fault and asserts it
fires — a linter that never reports anything looks identical to a clean
codebase, so each check has to be proven capable of failing.

## License

MIT. Offered as a reference implementation: use it, fork it, copy the idea. No
support promised.
