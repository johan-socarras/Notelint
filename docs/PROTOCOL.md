# The update routine

`notelint` reports. It does not decide, and it does not write notes. This is the
routine that surrounds it — written for a person, and equally for an AI agent
asked to "update the notes".

## The knowledge base is an organism

Nothing here is static, and **a change in one place usually forces another**.
Editing a note without checking who depended on it is how a knowledge base rots
quietly. Same for material: **if something enters a project — images, an
installer, a folder of code, a PDF — a note has to say what it is and why it is
there.** Unexplained material is material nobody dares delete in six months.

## Eight steps

1. **Run the linter before writing anything.**
   ```bash
   python tools/notelint.py .    # a base made by the installer
   python notelint.py <base>     # a clone of the repository
   ```
   Start from what it reports, not from what you remember.

2. **Walk what actually happened.** For every new fact, decision or open item:
   is there already a note? Then **fix that one**. If not, create one from
   `templates/note.md`.

   And for every note you touch, one more question: **does this note leave work
   undone?** Then create or fix a `todo` note, and leave a single line here
   linking to it. A fix described inside a `fact` or an `incident` never reaches
   `OPEN.md`, and work that is not in `OPEN.md` is work you will forget.

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

   Confirming many at once? Go **dependencies first**, or one project per
   session, oldest first. Working bottom-up stops you from firing spurious
   propagation findings at yourself.

7. **Run the linter until it's clean.** If a finding is left on purpose, say
   which and why rather than leaving it silent.

8. **Report what changed** in a few lines: notes touched, closed, opened.

## Three rules the steps rest on

1. **A fact lives in exactly one file.** Everything else links to it.
2. **Correcting a note beats adding one on top.** The instinct to record
   everything is what produces a 2,000-line backlog file where "done" and
   "todo" are interleaved beyond recovery.
3. **Every `current` note carries its "How to verify".** Without it, in two
   months you cannot tell which claims still hold, and the only remedy is to
   audit everything from scratch.

## Someone else may be editing right now

Another session — another person, another agent, or you on another machine — can
be working in the same base at the same time. It happens: eleven new notes
appearing in the middle of a review is a real thing that has occurred.

Before editing a note you did not write in this session, look at its `reviewed`
date and its modification time on disk. If someone just touched it, do not write
over it. And if the change you were about to make is already made, say so and
move on instead of redoing it.

If you work from more than one machine, `tools/syncguard.py` turns this from
vigilance into a check — see [SYNC.md](SYNC.md). It is optional and off unless
you set it up.

## What the linter cannot do

It finds broken links, vanished evidence, expired notes, zombies, pending
propagation and unclaimed material. **It does not know whether a note is true,
and it does not write notes.** That stays human — or agent — work. What the tool
guarantees is that the mess cannot be left in silence.
