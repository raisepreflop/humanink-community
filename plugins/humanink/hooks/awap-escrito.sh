#!/usr/bin/env bash
# AWAP local — avisa al registro de autoría de que la IA acaba de escribir un fichero.
#
# PostToolUse sobre Write|Edit. Los colaboradores abren y cierran su sesión con hi-args.py y
# hi-log.sh, pero lo que el modelo escribe DESPUÉS de cerrar (un «alárgalo un poco» en el turno
# siguiente) no pasa por ahí, y sin este aviso contaba como escrito por el autor (equipo rojo,
# 1-oct-2026). Si la carpeta del fichero no lleva registro (`.awap/local/project.json`), no hace
# nada. No imprime nada y sale SIEMPRE con 0: nunca estorba a una escritura.
set -u
PYTHON=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || true)
[ -n "$PYTHON" ] || exit 0
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
AW="$PLUGIN_ROOT/scripts/awap_local.py"
[ -f "$AW" ] || exit 0
# El JSON del evento llega por la entrada estándar; `escrito -` lo lee de ahí.
"$PYTHON" "$AW" escrito - >/dev/null 2>&1 || true
exit 0
