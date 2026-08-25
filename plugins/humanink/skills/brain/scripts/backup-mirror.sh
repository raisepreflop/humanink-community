#!/usr/bin/env bash
# backup-mirror.sh <root> <target> — espejo del brain (excluye .snapshots) a un destino.
set -e
ROOT="${1:?uso: backup-mirror.sh <root> <target>}"; TARGET="${2:?falta destino}"
mkdir -p "$TARGET"
if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete --exclude '.snapshots' "$ROOT"/ "$TARGET"/
else
  (cd "$ROOT" && find . -path ./.snapshots -prune -o -type f -print | cpio -pdm "$TARGET" 2>/dev/null)
fi
echo "backup OK → $TARGET"
