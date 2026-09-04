---
title: A dead feed took the poller down for 40 minutes
type: incident
project: Kestrel
status: current
created: 2026-08-24
reviewed: 2026-08-30
expires:
evidence:
links:
  depends-on: []
  supersedes: []
  blocks: []
  related: [feed-poll-interval]
---

## What happened

One feed started returning 503. The poller retried it three times per cycle
with no backoff, and because polls are serial, every other feed queued behind
it. Nothing crashed, so nothing alerted - the reader just silently stopped
updating for 40 minutes.

## The lesson

The bug was not the retry count. It was that a per-feed failure could consume
the shared budget of a serial loop. Fixed with a per-feed deadline, not by
lowering the retries.

## How to verify

`grep -n "context.WithTimeout" internal/poller/poller.go` - one per feed.
