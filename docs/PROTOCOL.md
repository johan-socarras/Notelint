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
   python notelint.py
   ```
   Start from what it reports, not from what you remember.

2. **Walk what actually happened.** For every new fact, decision or open item:
   is there already a note? Then **fix that one**. If not, create one from
   `templates/note.md`.

3. **Propagate.** For every note you touched, look at who links to it with
   `depends-on` and review those too. The linter lists this under
   `PROPAGATION`: it fires when a note was reviewed *after* something that
   declared a dependency on it.

4. **Claim new material.** Anything that entered the project needs its note. The
   linter lists these under `UNCLAIMED`. Closing those is part of the update,
   not an extra.

5. **Move statuses, don't delete.** Resolved work becomes `superseded` (and the
   note replacing it declares `supersedes`). Abandoned work becomes `dropped`
   *with the reason*, so nobody proposes it again believing it's new. Anything
   you can no longer vouch for becomes `unverified`.

6. **Touch `reviewed`** on every note you confirmed, even when not a word
   changed. That field is the whole difference between "still true" and "nobody
   has looked at this since July".

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

## What the linter cannot do

It finds broken links, vanished evidence, expired notes, zombies, pending
propagation and unclaimed material. **It does not know whether a note is true,
and it does not write notes.** That stays human — or agent — work. What the tool
guarantees is that the mess cannot be left in silence.
