---
name: authors
description: Manage multiple pen names / brands — capture, add, and keep them cleanly separated so voice, market and canon never bleed between brands.
version: "1.0.0"
---

# Authors (pen names)

The pen name is the unit writers think in, and the organizing axis of the brain.
Many writers run several brands; the brain keeps them cleanly apart.

## Capture / add

- Add a pen name in one sentence: *"add a new pen name, Jack Reeve, thrillers."*
  Create `authors/{slug}/` with `profile.md`, `voice/`, `market/`, `books/` (each
  with standard internals), and add it to `config.yaml: authors`.
- `profile.md` holds the bio/persona/genre for that brand.

## The separation that matters

- **Voice and market are per pen name** — they genuinely differ per brand, so they
  live under the author, not the whole-writer level.
- **Canon never crosses pen names.** A character, place or fact under one brand
  never enters another brand's answer. If a question is ambiguous across brands,
  **ask which one**.
- **Whole-writer stays shared.** Craft lessons, loose ideas, fragments and general
  reference belong to the person and are available across all pen names.

## One name only

If the writer uses a single name (their own), there's just one author folder and
the layer adds no friction — don't over-explain it. The structure is ready if they
ever add a second brand.

## Default author

`config.yaml: default_author` resolves unscoped actions. When the writer is
clearly working within one brand this session, treat that as the active scope, but
still confirm before doing anything that crosses into another.
