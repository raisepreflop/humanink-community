#!/usr/bin/env bash
# brain-status.sh <root> — conteos para el health check (los scripts cuentan, el agente juzga).
set -e
ROOT="${1:?uso: brain-status.sh <root>}"
cd "$ROOT"
inbox=$(find inbox -type f 2>/dev/null | grep -v '/\.' | wc -l | tr -d ' ')
raw=$(find . -path ./.snapshots -prune -o -type f -path '*/raw/*' -print 2>/dev/null | wc -l | tr -d ' ')
wiki=$(find . -path ./.snapshots -prune -o -type f -path '*/wiki/*' -name '*.md' -print 2>/dev/null | wc -l | tr -d ' ')
outputs=$(find . -path ./.snapshots -prune -o -type f -path '*/outputs/*' -print 2>/dev/null | wc -l | tr -d ' ')
snaps=$(find .snapshots -maxdepth 1 -type d 2>/dev/null | tail +2 | wc -l | tr -d ' ')
authors=$(find authors -maxdepth 1 -type d 2>/dev/null | tail +2 | wc -l | tr -d ' ')
echo "inbox_pending=$inbox"
echo "raw_files=$raw"
echo "wiki_articles=$wiki"
echo "outputs=$outputs"
echo "authors=$authors"
echo "snapshots=$snaps"
# carpetas con raw más nuevo que su log.md (wiki potencialmente stale) — portable BSD/GNU
mtime(){ stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null || echo 0; }
echo "stale_candidates:"
find . -path ./.snapshots -prune -o -type d -name raw -print 2>/dev/null | while read -r r; do
  d=$(dirname "$r"); log="$d/log.md"; newest=0
  while IFS= read -r f; do m=$(mtime "$f"); [ "$m" -gt "$newest" ] && newest=$m; done \
    < <(find "$r" -type f 2>/dev/null)
  [ "$newest" -eq 0 ] && continue
  if [ -f "$log" ]; then lt=$(mtime "$log"); else lt=0; fi
  [ "$newest" -gt "$lt" ] && echo "  $d"
done
