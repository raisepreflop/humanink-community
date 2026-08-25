---
name: schema
description: The on-disk shape of the HumanInk Brain — three levels, the same four internals everywhere, and the never-pool rule.
version: "1.0.0"
---

# Brain schema — how the brain is organized

The filesystem IS the database; you are the librarian. Everything is plain
markdown the writer owns. The brain is organized by **author (pen name)** over
**three levels**.

```
~/HumanInk-Brain/
  brain.md                      ← how the brain works + the writer's personal rules
  config.yaml                   ← location, default author, pen-name list, prefs, backup_targets
  .snapshots/                   ← HIDDEN pre-pass backups for undo (durability.md); never scanned

  inbox/                        ← UNIVERSAL DROP POINT. Dump anything, unsorted. Flat, no wiki.
                                  Triaged into the folders below. A synced folder (Drive/iCloud/
                                  Dropbox) makes this your phone-capture pipe with zero setup.

  authors/                      ← the organizing axis (one folder per pen name / brand)
    {author}/
      profile.md                ← bio / persona / genre for this brand
      voice/   raw/ wiki/ outputs/ log.md     ← this brand's voice exemplars
      market/  raw/ wiki/ outputs/ log.md     ← this brand's comps / audience / positioning
      books/
        {book-or-series}/       ← one wiki per book or series — canon NEVER pooled
          raw/ wiki/ outputs/ log.md
          feedback/ raw/ wiki/ outputs/       ← editor / beta-reader notes

  craft/      raw/ wiki/ outputs/ log.md      ← WHOLE-WRITER: lessons about your own writing
  ideas/      raw/ wiki/ outputs/ log.md      ← WHOLE-WRITER: seeds not yet assigned to a book
  fragments/  raw/ wiki/ outputs/ log.md      ← WHOLE-WRITER: lines, snippets, "use someday"
  reference/  raw/ wiki/ outputs/ log.md      ← WHOLE-WRITER: general research, reused
```

## The three levels

| Level | Folders | Holds |
|---|---|---|
| **Whole-writer** | `inbox/`, `craft/`, `ideas/`, `fragments/`, `reference/` | Knowledge that belongs to the *person*, across every pen name. |
| **Author (pen name)** | `authors/{author}/voice/`, `…/market/`, `…/profile.md` | Brand-specific: voice and market genuinely differ per pen name. |
| **Book** | `authors/{author}/books/{book}/` | One book or series: research, characters, world, canon. |

## The four internals (everywhere except inbox)

- `raw/` — the junk drawer. The writer dumps anything here; you NEVER tidy it by hand.
- `wiki/` — your AI-organized, cross-linked articles. **Never hand-edited.** `wiki/index.md` is the catalogue.
- `outputs/` — answers / briefings / reports you generate; they feed back in.
- `log.md` — memory: what was processed when. The cursor the lite scans read so they only touch what changed.

`inbox/` is the exception: a flat holding pen, emptied into the others by triage.

## The never-pool rule (load-bearing)

- **One wiki per series (or standalone book).** A series is one continuous world,
  so its books' canon pools *within* the series. Every fact carries which-book provenance.
- **Canon never crosses series, and never crosses pen names.** Answer within the
  relevant scope; ask which book / author if ambiguous; never blend one brand's
  character into another's answer.
- **Voice and market are per author.** Craft, ideas, fragments, reference are whole-writer.

## Adding folders (writer-shaped)

The writer creates folders in one sentence — *"make me a tropes folder under
[author]"*, *"a map-sketches folder for this book"*. Ask only "for this book,
this author, or all your writing?" to place it at the right level, then create it
with the standard internals via `scripts/brain-tree.sh`. The seeded set is a
starting point, never a cage.
