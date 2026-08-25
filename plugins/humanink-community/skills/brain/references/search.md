---
name: search
description: Literal "where did I write X" search across the brain — mechanical, returns file:line, used before synthesizing an answer.
version: "1.0.0"
---

# Literal search

When the writer asks *"where did I write about X"* (location, not synthesis),
search the actual files first. The script counts; you interpret.

## How

1. Run `scripts/brain-search.sh <root> "<term>"` (or grep directly). It returns
   `path:line: matching text` across `raw/`, `wiki/` and `outputs/`, skipping
   `.snapshots/`.
2. Group hits by scope (author / book / whole-writer) and by raw-vs-wiki.
3. Present the **literal hits with their location**, then offer to synthesize via
   `ask.md` if the writer wants the meaning, not just the where.

## Why search before answer

- Phrasing drifts: the writer may have written "the inspector" once and "the
  detective" elsewhere. A literal sweep catches what a wiki lookup alone misses.
- It grounds the negative answer: "I searched raw + wiki in <scope> for these
  terms and found nothing" is trustworthy; a vague "I don't think so" is not.

## Tips

- Try synonyms and name variants (the writer's, not invented ones).
- Respect scope: a search "for this book" stays inside that book's folders unless
  the writer asks to widen it.
- Report counts honestly ("4 hits, all in raw/, none in the wiki yet" tells the
  writer the material exists but isn't organized — offer to build the wiki).
