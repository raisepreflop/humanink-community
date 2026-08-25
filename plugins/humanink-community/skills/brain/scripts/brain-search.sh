#!/usr/bin/env bash
# brain-search.sh <root> "<term>" — búsqueda literal con file:line (salta .snapshots).
set -e
ROOT="${1:?uso: brain-search.sh <root> \"<term>\"}"; TERM="${2:?falta término}"
grep -rin --include='*.md' --exclude-dir='.snapshots' -- "$TERM" "$ROOT" 2>/dev/null \
  | sed "s#^$ROOT/##" || echo "(sin coincidencias)"
