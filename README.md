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

## Install

One command. It creates a knowledge base, puts the tools inside it, installs the
agent skill, and runs the linter once so you can see what it does.

**Linux and macOS**

```bash
curl -fsSL https://raw.githubusercontent.com/johan-socarras/notelint/main/install.sh | sh
```

**Windows (PowerShell)**

```powershell
irm https://raw.githubusercontent.com/johan-socarras/notelint/main/install.ps1 | iex
```

The base goes in `~/knowledge-base` unless you say otherwise:

```bash
curl -fsSL https://raw.githubusercontent.com/johan-socarras/notelint/main/install.sh | sh -s -- ~/my-brain
```

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/johan-socarras/notelint/main/install.ps1))) -Base C:\my-brain
```

The base is **self-contained**: the tools are installed inside it, so if you
later move it into a synced folder, they travel with it. Re-running the
installer is safe — it adds what is missing and leaves your files alone.

Piping a script from the internet into a shell is a thing you should only do
after reading the script. `install.sh` and `install.ps1` are in this repo for
exactly that reason.

## Or try it without installing anything

```bash
git clone https://github.com/johan-socarras/notelint
cd notelint
python notelint.py example --report-only
```

`--report-only` leaves the tree alone. Drop it and the run also rewrites
`INDEX.md` and `OPEN.md`, which are committed here so you can read them without
running anything.

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
# type:   decision | fact | todo | idea | incident | reference
# status: current | superseded | dropped | unverified
# expires: optional, re-verify after this date
title: Feeds are polled every 5 minutes, not every minute
type: fact
project: Kestrel
status: current
created: 2026-08-20
reviewed: 2026-08-20
expires:
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

And you can get them all at once, ordered so you check what something rests on
before you check it:

```bash
python notelint.py example --verify        # every "How to verify", dependencies first
python notelint.py example --verify 15     # only notes unreviewed for over 15 days
```

It runs nothing — that judgment stays yours. You run each one and touch
`reviewed` only where the result matched what the note predicted. A different
result is not a failed command, it's a finding: the note is wrong, fix it.

## The links are typed, and that is the point

`related:` is cheap and says nothing. The other three carry consequences the
linter can act on:

| Link | Means |
|---|---|
| `depends-on` | If that note changes, **this one needs re-reading**. |
| `supersedes` | This note replaces that one, which becomes `superseded`. |
| `blocks` | That work can't start until this closes. The chains in `OPEN.md` are built from it. |
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
| **`unclaimed`** | A file or folder is in the project and **no note explains why it exists** (build junk like `__pycache__`, `node_modules` and `target` is skipped) |
| `duplicate?` | Two current notes in one project have near-identical titles |
| `ambiguous link` | `[[name]]` matches notes in two projects, so it points at neither |
| `duplicate id`, `wrong project`, `format` | Structural mistakes |

The last two in bold are the ones I haven't seen packaged elsewhere, and they
are the ones that make the base behave like a system instead of a folder:

- **`propagation`** is the nerve. You correct one note, and the linter tells you
  which notes downstream just became suspect. Rot spreads; so should the alarm.
- **`unclaimed`** is inventory. Drop a folder of screenshots into a project and
  you have thirty seconds of context and two months of "what is this, and can I
  delete it?". The linter refuses to let material sit there unexplained.

Material is claimed by **citing its path** — in `evidence:`, or between backticks
in the body — not by mentioning its name. Citing something deep also claims the
directories above it, so quoting `evidence/shots/panel.md` does not leave
`evidence` looking unclaimed. Matching on the bare name was the earlier
behaviour and it had a hole you could drive a project through: a new directory
called `legal`, `src` or `tests` never showed up, because those words were
already written somewhere in the notes for an unrelated reason.

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

One limit to know before it puzzles you: **the first segment of the path cannot
contain a space.** That guard is what stops a shell command written in backticks
from claiming half the project, and the price is that a file sitting loose at the
top of a project with spaces in its name can never be claimed - it keeps showing
up under `unclaimed` however you cite it. Move it into a folder, as above, or
rename it.

## Flags

| Flag | What it does |
|---|---|
| `--report-only` | Report, but do not write `INDEX.md` / `OPEN.md` |
| `--force` | Rewrite a view even if this tool did not write it |
| `--project NAME` | Report on one project only (repeatable) |
| `--lang en\|es` | Field vocabulary (default: detect) |
| `--verify [DAYS]` | Print every "How to verify", dependencies first |
| `--exit-zero` | Always exit 0, for when you do not want CI to fail |

## Generated views, never hand-edited

Each run rewrites `INDEX.md` (everything, by project and type) and `OPEN.md`
(the work list). Delete them and they come back identical. A file of your own
already sitting under either name is left alone — the linter only replaces what
it wrote itself, unless you pass `--force`. You change what's in
them by editing a note's `status`, not by editing the list — which is exactly
why the list can't drift from reality.

`INDEX.md` ends with **the eight longest unreviewed**, across every project.
That turns the 60-day cliff into a trickle: confirm a few each session and the
`unreviewed` warning never arrives as an avalanche you have to ignore.

### Work chains

`blocks` is transitive, so `OPEN.md` doesn't print a flat list of blocked items —
it draws the order the work actually has to happen in:

```markdown
## Work chains (1)

- [Ship version 0.9.0](notes/ship-090.md)  <- start here
  - [Run the acceptance suite](notes/run-tests.md)
    - [Rewrite the pricing page](notes/update-site.md)
```

This is how a conditional plan gets recorded without turning the knowledge base
into a workflow engine. "When 0.9.0 ships we run the tests, and if they pass we
update the site" becomes three notes and two `blocks` edges. Only the head of the
chain shows under **Ready to do**; the rest stay out of your way until they're
actually actionable.

The branch — *if* they pass — is deliberately **not** modelled. You record what
happened after the fact: a `fact` note with the numbers and the next link frees
up, or an `incident` note with the cause and the chain stays put. Encoding
hypothetical branches ahead of time is how a note system turns into a bad issue
tracker.

Two details that took a test each to get right: a chain that spans projects
renders with the foreign project named beside the note, and a **cycle** — notes
that block each other, so nothing can start — gets its own section instead of
silently vanishing from the view for lack of a root.

## Multi-project, multi-language

Any directory **directly under the base** containing a `notes/` folder is a
project. There is nothing to register: create the folder and it's picked up.
Nesting is not searched, and a handful of names (`tools`, `templates`, `docs`,
`.git` and friends) never count as projects. Links cross project boundaries,
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

### The agent skill

`skills/notelint/SKILL.md` is a [Claude Code](https://claude.com/claude-code)
skill that teaches an agent to maintain a base by these rules. Install it by
copying the folder:

```bash
cp -r skills/notelint ~/.claude/skills/
```

After that, "update the notes" reaches for it from any working directory, not
just from inside the base.

It is deliberately short — it *locates* the procedure instead of restating it, so
it cannot drift out of sync with `docs/PROTOCOL.md`. What it adds is the handful
of things no file in the repo says: that someone else may be editing the same
base right now, that you must never invent a "How to verify" you haven't run,
that a note is `dropped` with a reason rather than deleted, and that a silent
update is indistinguishable from no update at all.

`docs/PROTOCOL.md` is the routine I use: run the linter before writing anything,
fix notes rather than stack new ones, propagate, then run it again until clean.

## Optional tools

Two extras live in `tools/`. Both are standalone — `notelint.py` does not import
either one, and if you delete them nothing breaks. They are here because a
knowledge base you actually use every day ends up needing them.

### `syncguard.py` — for working from more than one machine

Keep the base in a synced folder and you will eventually open the laptop and
start writing before the sync finished pulling what you did on the desktop. The
sync client resolves that by leaving two files with `conflicted copy` in the
name, and your base quietly grows a second truth.

```sh
python tools/syncguard.py . --status    # what every machine last reported
python tools/syncguard.py . --wait 180  # block until the sync lands
python tools/syncguard.py . --stamp     # "I finished here" - run when done
```

It hashes every note, and each machine stamps that hash when it finishes. The
check runs on the **receiving** side: you never have to prove the other machine
finished uploading — the machine you sit down at tells you whether it all
arrived.

It does not care which sync tool you use. OneDrive, Dropbox, Drive, Syncthing, a
git remote, rsync, a NAS — it compares content, so anything that eventually makes
two folders match will do. Configure it in `.sync/config.json`: turn it off
entirely with `"enabled": false`, or list `"machines"` when you have three
computers and only want two of them to count.

Full guide, including the traps: [`docs/SYNC.md`](docs/SYNC.md).

### `power.py` — shut down or suspend when the work is done

For telling an agent "when you finish, shut the machine down". One file, same
behaviour on Windows, Linux and macOS.

```sh
python tools/power.py shutdown --in 60          # countdown you can still cancel
python tools/power.py suspend --in 30
python tools/power.py shutdown --close code     # close apps first
python tools/power.py shutdown --dry-run        # say what it would do
```

The countdown runs inside the process, which is what makes cancelling always the
same gesture — Ctrl+C — regardless of platform.

## Make it yours

Everything here is small on purpose. The linter is one file; the guard is
another; the power script is a third. No dependencies, no build step, no
framework to learn before you can change a line.

That is deliberate. The point of a knowledge base is that it fits the way *you*
work, and the moment a tool is too big to read in a sitting, you stop adapting
it and start working around it.

So: fork it, rewrite the checks, add your own, change the vocabulary, wire it
into whatever you already use. If you would rather not do it by hand, hand a file
to whichever AI assistant you use and describe what you want — each one is small
enough to pass whole, and `tests/` will tell you if you broke something.

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

Forty-three tests, no framework. Every check plants its own fault and asserts it
fires — a linter that never reports anything looks identical to a clean
codebase, so each check has to be proven capable of failing.

## License

MIT. Offered as a reference implementation: use it, fork it, copy the idea. No
support promised.
