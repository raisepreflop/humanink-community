#!/usr/bin/env bash
# brain-tree.sh <root> [author] [book] — crea/extiende la estructura del HumanInk Brain.
set -e
ROOT="${1:?uso: brain-tree.sh <root> [author] [book]}"
AUTHOR="$2"; BOOK="$3"
mkdir -p "$ROOT"/{inbox,.snapshots}
mkdir -p "$ROOT"/{craft,ideas,fragments,reference}
internals(){ for d in "$@"; do mkdir -p "$d"/{raw,wiki,outputs}; [ -f "$d/wiki/index.md" ] || echo "# Index" > "$d/wiki/index.md"; [ -f "$d/log.md" ] || echo "# Log" > "$d/log.md"; done; }
internals "$ROOT/craft" "$ROOT/ideas" "$ROOT/fragments" "$ROOT/reference"
[ -f "$ROOT/brain.md" ] || printf '# This is your HumanInk Brain\nDrop anything into inbox/ and ask: "process my inbox".\nwiki/ is AI-built — do not hand-edit. Ask your brain anything.\n\n## My rules\n' > "$ROOT/brain.md"
[ -f "$ROOT/config.yaml" ] || printf 'brain_version: "1.0.0"\nlocation: "%s"\nauthors: []\npreferences:\n  ask_before_delete: true\nbackup_targets: []\nawap:\n  log_events: true\n' "$ROOT" > "$ROOT/config.yaml"
if [ -n "$AUTHOR" ]; then
  A="$ROOT/authors/$AUTHOR"
  mkdir -p "$A"
  [ -f "$A/profile.md" ] || echo "# $AUTHOR — profile" > "$A/profile.md"
  internals "$A/voice" "$A/market"
  if [ -n "$BOOK" ]; then
    B="$A/books/$BOOK"; internals "$B"; internals "$B/feedback"
  fi
fi
echo "OK: estructura creada/actualizada en $ROOT"
