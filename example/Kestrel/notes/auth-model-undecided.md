---
title: Decide the auth model before anything exposes a port
type: todo
project: Kestrel
status: current
created: 2026-08-22
reviewed: 2026-08-30
expires:
evidence:
links:
  depends-on: []
  supersedes: []
  blocks: [opml-import]
  related: []
---

## What is missing

Three options, none chosen: no auth at all (bind to localhost only), a single
password in the config file, or a reverse proxy's business.

It blocks [[opml-import]] because import needs an upload endpoint, and an
upload endpoint on an unauthenticated service is a file drop for anyone on the
network.

## How to verify

When a decision exists it becomes a `decision` note and this one is superseded.
