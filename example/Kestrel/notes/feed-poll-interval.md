---
title: Feeds are polled every 5 minutes, not every minute
type: fact
project: Kestrel
status: current
created: 2026-08-20
reviewed: 2026-08-20
expires:
evidence:
  - evidence/bench-2026-08-20.md
links:
  depends-on: [sqlite-over-postgres]
  supersedes: []
  blocks: []
  related: [retry-storm-incident]
---

## What it is

The poller runs every 5 minutes. One minute was tried and abandoned: measured
on 300 feeds on 1 vCPU, p95 write latency went from 41 ms to 340 ms and six
polls timed out, because every poll opens a write transaction against the
single SQLite file.

## How to verify

`grep -n "pollInterval" internal/poller/poller.go`.
