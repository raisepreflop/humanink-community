---
name: health-check
description: Report the brain's integrity — orphaned raw, stale wikis, broken links, oversized inbox, missing provenance — so the writer can keep it trustworthy.
version: "1.0.0"
---

# Health check

A periodic, mechanical-plus-judgment pass that tells the writer whether the brain
is in good shape. Run `scripts/brain-status.sh <root>` for the counts, then interpret.

## What to report

- **Inbox backlog** — items waiting; offer to process.
- **Orphaned raw** — raw notes not yet reflected in any wiki article (material the
  brain "has" but can't yet answer from). Offer to build.
- **Stale wikis** — folders whose raw changed after the wiki was last built
  (`log.md` cursor older than newest raw). Offer a rebuild.
- **Broken links** — `[[article]]` links pointing to nothing; suggest fixes.
- **Missing provenance** — wiki facts with no source tag (weakens grounding).
- **Snapshot/backup status** — last snapshot, whether a backup target is set
  (`durability.md`).

## How to present

A short status table with a health read (Healthy / Needs attention / At risk) and
**one or two concrete offers** ("process the 6 inbox items", "rebuild Book 2's
wiki"), each ignorable. Never a wall of warnings.

## Rules

- Scripts count; you judge. The script output is ground truth for counts.
- Recommend, don't force — the writer can run a messy brain if they want.
- Don't fix anything during a health check without the writer's go-ahead.
