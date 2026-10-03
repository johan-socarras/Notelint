# The update routine

`notelint` reports. It does not decide, and it does not write notes. This is the
routine that surrounds it — written for a person, and equally for an AI agent
asked to "update the notes".

The commands below are written for a base made by the installer, run from the
base: `python tools/notelint.py …`. In a clone of the repository it is
`python notelint.py <base> …` for a lint, and `--base <base>` for `search`.

## Which part of the base

- **"Update the notes" while talking about one project** → that project.
- **"Update the notes" with no project in view** → all of them.
- Explicit instructions about what to update win over both; the rest of the
  routine applies to whatever they touch.

## The knowledge base is an organism

Nothing here is static, and **a change in one place usually forces another**.
Editing a note without checking who depended on it is how a knowledge base rots
quietly. Same for material: **if something enters a project — images, an
installer, a folder of code, a PDF — a note has to say what it is and why it is
there.** Unexplained material is material nobody dares delete in six months.

## Eight steps

1. **Run the linter before writing anything.**
   ```bash
   python tools/notelint.py . --project <name>    # a base made by the installer
   python notelint.py <base> --project <name>     # a clone of the repository
   ```
   Start from what it reports, not from what you remember.

   Name the project the update is about; leave `--project` out only when it
   covers the whole base. A report of every project buries the finding that
   matters under the others. The views are regenerated whole either way.

   Lines it prints under `INBOX` come from `INBOX.md` at the base: someone
   changed something by hand, outside this routine, and left one line saying
   what and why. They are facts like any other, handled in step 2 — there is
   no need to ask what was touched, it is written there. Once a line is
   accounted for, move it from `## To process` to `## Processed`.

2. **Walk what actually happened.** For every new fact, decision or open item:
   is there already a note? Then **fix that one**. If not, create one from
   `templates/note.md`.

   And for every note you touch, one more question: **does this note leave work
   undone?** Then create or fix a `todo` note, and leave a single line here
   linking to it. A fix described inside a `fact` or an `incident` never reaches
   `OPEN.md`, and work that is not in `OPEN.md` is work you will forget. The
   linter reports the ⏳ mark in a note that is not a `todo` as `HIDDEN TODO`.

   If a note asserts something you cannot check today — no command, no path, no
   screen, no result that would confirm it — it is not `current`. It is
   `unverified`.

3. **Propagate.** For every note you touched, look at who links to it with
   `depends-on` and review those too. The linter lists this under
   `PROPAGATION`: it fires when a note was reviewed *after* something that
   declared a dependency on it.

4. **Claim new material.** Anything that entered the project needs its note. The
   linter lists these under `UNCLAIMED`. Closing those is part of the update,
   not an extra.

   **Material is claimed by citing its path, not by naming it.** What counts is
   the `evidence:` field and paths written between backticks in the body,
   relative to the project or to the base. Citing something deep also claims the
   directories above it. Mentioning a bare name in a sentence is not enough —
   that was the earlier rule, and it meant a new directory called `legal`, `src`
   or `tests` never surfaced, because those words were already written somewhere
   for an unrelated reason.

   One limit worth knowing: the linter only looks at the **first two levels** of
   each project. That is deliberate — walking an entire source tree would bury
   the report in noise — but it means "it did not appear under `UNCLAIMED`" is
   not the same as "it is claimed". For material buried deeper, look by hand.

   And when you move material, search for the old path inside `notes/` and inside
   any scripts too, not just in `evidence:` fields. The linter checks paths in
   frontmatter; it cannot see a path hardcoded in a shell script.

5. **Move statuses, don't delete.** Anything **replaced** becomes `superseded`,
   and the note replacing it declares `supersedes`.

   A **`todo` that got done** is closed *in its own note*: set `type` to `fact`,
   rewrite the title as a statement of what is now true, make "How to verify"
   check that it is done, and add one line — "Was a todo until YYYY-MM-DD". Do
   not rename the file and do not create a second note. Two exceptions: if it
   has a non-empty `blocks`, clear that first (or use `superseded` plus a new
   note); and if the outcome does not fit in the note, `superseded` plus a new
   note is right.

   Abandoned work becomes `dropped` *with the reason*, so nobody proposes it
   again believing it's new. Anything you can no longer vouch for becomes
   `unverified` — it keeps blocking whatever it blocked, and checking it is the
   first job.

6. **Touch `reviewed`** on every note you confirmed, even when not a word
   changed. That field is the whole difference between "still true" and "nobody
   has looked at this since July".

   Confirming many at once? Go in the order the linter lists them —
   **dependencies first** — or one project per session, oldest first. Working
   bottom-up stops you from firing spurious propagation findings at yourself.

   The date is the one the linter prints in its header: the machine's local
   date. An agent's own clock may run on UTC and turn the day over hours early,
   and a `reviewed` in the future is a format error.

7. **Run the linter until it's clean.** If a finding is left on purpose, say
   which and why rather than leaving it silent.

   For the checks inside the notes, `python tools/notelint.py . --verify
   --project <name>` prints every "How to verify", dependencies first. Run them
   with judgment — never one that writes, deletes or changes something outside
   the base — and touch `reviewed` only where the result matched what the note
   predicted. A different result is a finding of this step: fix the note, do
   not stay quiet about it.

8. **Report what changed** in a few lines: notes touched, closed, opened.

## Three rules the steps rest on

1. **A fact lives in exactly one file.** Everything else links to it.
2. **Correcting a note beats adding one on top.** The instinct to record
   everything is what produces a 2,000-line backlog file where "done" and
   "todo" are interleaved beyond recovery.
3. **Every `current` note carries its "How to verify".** Without it, in two
   months you cannot tell which claims still hold, and the only remedy is to
   audit everything from scratch. The linter reports a missing or empty one as
   `NO VERIFICATION`.

## What is not done from memory

A decision changes, the main note gets fixed, and three others keep saying the
old thing — in a title, in a file name — until someone is handed a list of open
work that still talks about the old plan. Four habits close that gap:

- **When a decision changes, before answering anyone,** run
  `python tools/notelint.py search <words of the old state>` — the old
  version, the old approach, the name of what was abandoned — and fix every
  current note that still states it as present, **titles and file names
  included**. Notes that tell it as history ("since v58") stay as they are.
  It is a search, not an audit.
- **If the project numbers its builds `vN`**, its main note carries
  `installed-version: N` in the frontmatter, bumped whenever a new one is
  installed. The linter then reports, under `PAST VERSION`, the current todos
  whose file name or title stayed on an older one.
- **A todo is named after the work, never after the version**
  (`check-sign-in-on-the-laptop`, not `verify-v58-sign-in`): the version moves
  and the name does not. A fact about one specific build may carry it.
- **Before handing anyone a list of what is left,** run
  `python tools/notelint.py search --project <name> --type todo` and read those
  notes: the list comes from there, not from the conversation and not from
  file names.

## Someone else may be editing right now

Another session — another person, or another agent — can be working in the
same base at the same time. It happens: eleven new notes
appearing in the middle of a review is a real thing that has occurred.

Before editing a note you did not write in this session, look at its `reviewed`
date and its modification time on disk. If someone just touched it, do not write
over it. And if the change you were about to make is already made, say so and
move on instead of redoing it. The linter flags a note modified after its
`reviewed` date as `TOUCHED UNREVIEWED` — outside a git work tree, where
modification times can be trusted.

## What the linter cannot do

It finds broken links, evidence that vanished or changed, expired and
unreviewed notes, doubts left unresolved, zombies, blocks that can never lift,
pending propagation, todos named after a past version, notes without a way to
verify them, and unclaimed material. **It does not know whether a note is true,
and it does not write notes.** That stays human — or agent — work. What the tool
guarantees is that the mess cannot be left in silence.
