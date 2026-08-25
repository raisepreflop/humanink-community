#!/usr/bin/env bash
# snapshot.sh <root> <folder-rel> — copia de seguridad pre-pase en .snapshots/.
set -e
ROOT="${1:?uso: snapshot.sh <root> <folder-rel>}"; REL="${2:?falta carpeta}"
TS=$(date +%Y%m%d-%H%M%S 2>/dev/null || echo snapshot)
DEST="$ROOT/.snapshots/$TS-$(echo "$REL" | tr '/' '_')"
mkdir -p "$DEST"
cp -R "$ROOT/$REL/." "$DEST/" 2>/dev/null || true
echo "snapshot: $DEST"
