---
name: build-wiki
description: Turn raw/ material into AI-organized, cross-linked wiki articles. The wiki is derived and never hand-edited.
version: "1.0.0"
---

# Build the wiki

The `wiki/` is your work: cross-linked markdown articles distilled from `raw/`.
The writer never hand-edits it; if they want to correct a fact, they add to
`raw/` and you rebuild.

## How to build

1. Read the raw material in scope (lite: only what `log.md` says is new).
2. Group it into **entities and topics** — characters, places, objects, themes,
   timeline, rules-of-the-world, subplots. One article per entity/topic.
3. Write each article in plain markdown:
   - A short summary line.
   - Bulleted facts, **each with provenance** (which raw file / which book).
   - `Related:` links to other articles (`[[character-mara]]`), built liberally.
4. Maintain `wiki/index.md` — the catalogue, grouped by type, linking every article.
5. Append to `log.md` what you built/updated.

## Rules

- **Derived, not invented.** Every wiki line must trace to a raw line. If raw is
  silent, the wiki is silent. No smoothing gaps with plausible detail.
- **Stable filenames** (`character-mara.md`, `place-blackmoor.md`) so links survive rebuilds.
- **One wiki per book/series.** Don't merge across the never-pool boundary.
- Flag, don't fix, internal contradictions in raw — surface them to the writer or
  route to `continuity-audit.md`.

## Output

After a build, give the writer a one-paragraph summary: new articles, updated
articles, and any contradictions you noticed. Offer to save a fuller briefing to
`outputs/` if it's substantial.
