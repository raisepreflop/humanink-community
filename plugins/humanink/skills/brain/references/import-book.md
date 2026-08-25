---
name: import-book
description: Backfill the brain from an already-finished manuscript — extract characters, places, world and timeline into a book wiki without altering the prose.
version: "1.0.0"
---

# Import a finished book

A writer arriving with a finished manuscript should get an instant wiki of their
own book. You read the prose and build the canon record; you never rewrite the prose.

## Steps

1. **Place it.** Create/confirm `authors/{author}/books/{book}/` and drop a copy
   of the manuscript into its `raw/` (verbatim — the source of truth).
2. **Extract entities.** Read through and build wiki articles for characters,
   places, objects, world rules, timeline and subplots — each fact with
   provenance (chapter/scene).
3. **Coverage check.** Report what you captured and where coverage is thin
   ("only 2 of ~9 named characters have notes yet — want a deeper pass?"). Don't
   pretend a one-pass extraction is exhaustive.
4. **Continuity audit.** Run `continuity-audit.md` over the freshly built wiki —
   imports are a great time to catch contradictions the writer never noticed.
5. **Hand off.** The book is now queryable (`ask.md`) and ready for the Desk
   Editor or the next book in the series.

## Rules

- **Never alter the manuscript.** Import reads; it does not edit prose.
- **Derived only.** Every wiki fact traces to a line in the manuscript — no
  invented backstory, no "it's implied that…".
- **Big jobs are honest about scope.** State what was a sample vs a full pass; a
  silent partial import reads as complete when it isn't.

Importing a finished book is also an authorship moment: log it (`awap-evidence.md`)
and, if the writer wants to certify the book, hand to the Auditor (17).
