#!/usr/bin/env bash
# AWAP local — después de que la IA ejecute una orden o escriba un fichero.
#
# PostToolUse sobre Bash|Write|Edit. Los colaboradores abren y cierran su sesión con hi-args.py y
# hi-log.sh, pero lo que el modelo escribe FUERA de un colaborador (un «alárgalo un poco» en el
# turno siguiente) no pasa por ahí. Aquí se anota como de la IA lo que haya cambiado desde el gancho
# de antes (awap-antes.sh), también lo que escribe con un guion: un Word no se puede escribir con
# Write ni Edit (UAT, 2-oct-2026). Dentro de un colaborador es solo una señal de vida. Sin registro
# en la carpeta no hace nada. No imprime nada y sale SIEMPRE con 0: nunca estorba.
set -u
PYTHON=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || true)
[ -n "$PYTHON" ] || exit 0
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
AW="$PLUGIN_ROOT/scripts/awap_local.py"
[ -f "$AW" ] || exit 0
# El JSON del evento llega por la entrada estándar.
"$PYTHON" "$AW" despues - >/dev/null 2>&1 || true
exit 0
