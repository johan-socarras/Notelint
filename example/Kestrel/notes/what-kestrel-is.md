---
title: What Kestrel is, in five lines
type: reference
project: Kestrel
status: current
created: 2026-08-18
reviewed: 2026-08-30
expires:
evidence:
links:
  depends-on: []
  supersedes: []
  blocks: []
  related: [sqlite-over-postgres]
---

## What it is

A self-hosted feed reader for one person. Single Go binary, SQLite file, no
container, no daemon zoo. It is deliberately not a multi-tenant service: every
design call in this knowledge base follows from that.

## How to verify

`./kestrel --version` and check the binary is still a single file.
