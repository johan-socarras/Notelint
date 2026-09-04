---
title: SQLite, not Postgres
type: decision
project: Kestrel
status: current
created: 2026-08-18
reviewed: 2026-09-01
expires:
evidence:
  - evidence/bench-2026-08-20.md
links:
  depends-on: []
  supersedes: []
  blocks: []
  related: [what-kestrel-is, feed-poll-interval]
---

## What was decided

Storage is one SQLite file. Postgres was considered and rejected.

## Why

The product is single-user by definition, so the only thing Postgres buys is
concurrent writes we will never have. What it costs is a second process to
install, back up and upgrade - which breaks the one promise the project makes.

Revisit only if Kestrel ever becomes multi-user. That would be a different
product, not a new storage backend.

## How to verify

`ls *.db` next to the binary. If a connection string ever appears in the
config, this note is wrong.
