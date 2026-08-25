---
name: durability
description: Protect the writer's brain — pre-pass snapshots for undo, and an optional mirror backup to a second location. Local-first, the writer owns everything.
version: "1.0.0"
---

# Durability — undo and backup

The brain is the writer's irreplaceable work. Two safety nets: snapshots (undo)
and a mirror (offsite copy). Both local-first; nothing leaves the writer's control.

## Snapshots (undo)

- Before any wide or destructive change (a big ingest, a wiki rebuild, a
  continuity fix that rewrites articles), run `scripts/snapshot.sh <root> <folder>`.
  It copies the target into `.snapshots/{timestamp}-{folder}/`.
- `.snapshots/` is hidden, never scanned by ingest, and excluded from backups.
- To undo: restore the relevant snapshot over the folder. Always confirm before restoring.
- Keep the last few snapshots; offer to prune old ones during a health check.

## Backup (mirror)

- `config.yaml: backup_targets` lists one or more destinations (a synced folder, an
  external drive path).
- `scripts/backup-mirror.sh <root> <target>` mirrors the brain (excluding
  `.snapshots/`) to a target. Run it on request, or remind gently during a health
  check if no backup exists.
- Recommend the target be a **different physical location/service** than the brain
  itself, so one failure doesn't take both.

## Rules

- **Confirm before restoring or overwriting** — a restore can lose recent work.
- **Snapshot before risk** — never run a wide change without one.
- **Local-first** — the writer owns the files; the brain never ships their canon
  anywhere they didn't choose.
