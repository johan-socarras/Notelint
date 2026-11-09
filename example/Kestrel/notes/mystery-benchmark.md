---
title: Full-text search costs about 90 MB of RAM at 10k articles
type: fact
project: Kestrel
status: current
created: 2026-08-26
reviewed: 2026-08-30
expires:
evidence:
  - evidence/fts-benchmark-2026-08-26.csv
links:
  depends-on: []
  supersedes: []
  blocks: []
  related: [full-text-search]
---

## What it is

An FTS5 index over 10,000 articles measured at roughly 90 MB resident. That is
the number the search decision would rest on.

**This note is one of the example's deliberate faults:** the CSV it cites is
not in the repository, so `notelint` reports dead evidence. A claim whose
evidence has vanished is exactly the kind of thing that quietly turns into
folklore.

## How to verify

Re-run the benchmark and commit the CSV, or downgrade this note to unverified.
