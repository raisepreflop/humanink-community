#!/usr/bin/env bash
# HumanInk shared context loader.
# Usage: hi-context.sh <project_folder>
# Prints the standard voice/structure documents in one call, so a workflow
# doesn't need seven separate `cat` blocks. Missing docs print a short note.
set -u
CARPETA="${1:-.}"
CARPETA="${CARPETA/#\~/$HOME}"

show() { # <label> <path> <hint-if-missing>
  echo "=== $1 ==="
  if [ -f "$2" ]; then cat "$2"; else echo "$3"; fi
  echo
}

show "STYLE"          "$CARPETA/estilo.md"            "⚠️ No estilo.md — run /humanink:style first"
show "BIBLE"          "$CARPETA/biblia.md"            "⚠️ No biblia.md — run /humanink:coach first"
show "OUTLINE"        "$CARPETA/escaleta.md"          "⚠️ No escaleta.md — run /humanink:coach first"
show "AUTHOR PROFILE" "$CARPETA/perfil-autor.md"      "(no perfil-autor.md)"
show "PROMISES"       "$CARPETA/promesas.md"          "(no promesas.md — maintained by /humanink:coach --bible-delta)"
show "FORBIDDEN WORDS" "$CARPETA/estilo/prohibidas.md" "(no estilo/prohibidas.md)"

echo "=== NAME CANON ==="
if [ -f "$CARPETA/entity-canon.md" ]; then cat "$CARPETA/entity-canon.md"
elif [ -f "$CARPETA/canon.md" ]; then cat "$CARPETA/canon.md"
else echo "(no entity-canon.md — maintained by /humanink:coach --bible-delta)"; fi
