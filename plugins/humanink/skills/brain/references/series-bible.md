---
name: series-bible
description: Maintain a continuity bible for a series — one wiki where canon pools across the books of that series, with per-book provenance, kept current as new books are written.
version: "1.0.0"
---

# Series bible

A series is one continuous world, so its books' canon pools *within* the series —
this is the one place pooling is allowed, and only here. The series bible is the
living wiki of that shared world.

## Structure

The series lives at `authors/{author}/books/{series}/`. Its `wiki/` is the series
bible: characters, places, world rules, timeline, arcs — every fact tagged with
**which book** it was established in (provenance).

## Keeping it current (bible delta)

When the writer finishes or revises a book in the series:

1. Read the new/changed material (lite scan via `log.md`).
2. Update the series wiki: add new facts (with this book's provenance), extend
   existing entities, note new relationships.
3. **Run a continuity audit** (`continuity-audit.md`) across the series — new
   books are where contradictions creep in. Report, don't auto-fix.
4. Maintain a short `outputs/series-status.md`: what's locked across all books,
   what's open, dangling threads (a planted gun not yet fired).

## Carry-forward discipline (for Book N)

When planning the next book, classify each relevant prior fact:

- **locked** — established canon; cite the book.
- **carry-forward** — continues unchanged into this book.
- **open** — deliberately unresolved; a candidate to pay off here.

Surface these so the writer builds on canon instead of contradicting it. This is
where the brain quietly becomes the Coach's series memory (`collaborators.md`).

## Rules

- Provenance on every fact — without it the bible can't answer "in which book".
- Pool **within** the series only; never across series or pen names.
- The writer owns canon decisions; you maintain the record.
