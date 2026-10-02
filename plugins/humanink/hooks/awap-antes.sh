#!/usr/bin/env bash
# AWAP local — antes de que la IA ejecute una orden o escriba un fichero.
#
# PreToolUse sobre Bash|Write|Edit. Si la carpeta a la que toca la orden lleva registro de autoría
# (`.awap/local/project.json`), lo que el autor haya cambiado hasta este momento se anota como suyo,
# para que no se lo lleve lo que la IA escriba a continuación. Dentro de un colaborador es solo una
# señal de vida. Sin registro no hace nada. No imprime nada y sale SIEMPRE con 0.
set -u
PYTHON=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || true)
[ -n "$PYTHON" ] || exit 0
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
AW="$PLUGIN_ROOT/scripts/awap_local.py"
[ -f "$AW" ] || exit 0
"$PYTHON" "$AW" antes - >/dev/null 2>&1 || true
exit 0
