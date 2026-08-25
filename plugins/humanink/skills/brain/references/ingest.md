---
name: ingest
description: Triage the inbox and raw/ drops into the right scope, then build wiki articles from them. The capture → organize path.
version: "1.0.0"
---

# Ingest — from drop to organized

The writer dumps; you sort and organize. Never lose the original.

## 1. Triage (the inbox)

For each item in `inbox/`:

1. Read it. Decide its **level and scope**: whole-writer (`craft/ ideas/
   fragments/ reference/`), an author's `voice/`/`market/`, or a specific
   `books/{book}/`. If unsure, **ask** — never guess scope (never-pool rule).
2. **Move the original, verbatim, into that folder's `raw/`.** The raw layer is
   the writer's exact words; preserve them. Don't paraphrase the source.
3. Note it in that folder's `log.md` (date · what · where it came from).
4. Snapshot before any wide change (`scripts/snapshot.sh`).

Empty the inbox by moving, not copying. Confirm a summary of where things went.

## 2. Build the wiki from raw

Once raw material is in place, route to `build-wiki.md` to turn it into
cross-linked articles. Rule: **the wiki is derived from raw**, so raw is the
source of truth and is never overwritten.

## 3. Lite vs full scans

- **Lite (default):** read each folder's `log.md` cursor and process only what
  changed since last time. Fast, cheap, runs often.
- **Full:** re-read everything in scope. Offer it when the writer says "rebuild"
  or after a big import.

## 4. Provenance (for series)

When a fact comes from a specific book in a series, tag it with which book, so a
later answer can say *"established in Book 2"*. Provenance is what lets the series
wiki pool canon safely without losing track of where each fact was set.

## What ingest is NOT

- It does not invent connections the raw doesn't support.
- It does not move something across pen names "because it fits" — ask first.
- It does not delete the original. Ever.

Log the ingest as an authorship event (`awap-evidence.md`) — captured research is
part of the writer's authorship trail.
