#!/usr/bin/env bash
# HumanInk shared "record this invocation" tail.
# Usage: hi-log.sh <collab-slug> <display-name> <project-folder> [mode] [tokens_in] [tokens_out] [docs_up]
# Does two things, silently (never fails the skill):
#   1) appends a usage event via ~/.awos/awos-log.py
#   2) writes a project checkpoint via the ai-parser quickcheck
#   3) closes the collaborator's session in the local authorship log (AWAP), if the book has one
# Replaces the ~26-line log/checkpoint block repeated at the end of every collaborator.
set -u
COLLAB="${1:-awos-unknown}"
NAME="${2:-$COLLAB}"
CARPETA="${3:-}"; CARPETA="${CARPETA/#\~/$HOME}"
MODE="${4:---default}"
TOK_IN="${5:-0}"
TOK_OUT="${6:-0}"
DOCS_UP="${7:-0}"

PY=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo python3)
SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
# El bloque de cierre de varios colaboradores pasa «$CARPETA», que se definió en un bloque anterior:
# cada bloque es un shell nuevo y llega vacía. Antes se tomaba el directorio de trabajo, así que la
# invocación se apuntaba a otro «proyecto» y el registro de autoría del libro se quedaba con la sesión
# abierta (UAT, 2-oct-2026). Se recupera de la orden con la que se llamó al colaborador.
if [ -z "$CARPETA" ]; then
  _ARGS="${ARGUMENTS:-$(cat /tmp/humanink/args 2>/dev/null)}"
  FOLDER=""
  eval "$(HI_SIN_AWAP=1 "$PY" "$SELF_DIR/hi-args.py" "$_ARGS" 2>/dev/null | grep '^FOLDER=')" 2>/dev/null || true
  CARPETA="${FOLDER:-$(pwd)}"
  [ -f "$CARPETA" ] && CARPETA="$(dirname "$CARPETA")"
fi
PROJECT=$(basename "$CARPETA")
ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$SELF_DIR/.." && pwd)}"

# docs produced since the logger was last touched (best-effort)
DOCS_PROD=$(find "$CARPETA" -newer ~/.awos/awos-log.py \
  \( -name "*.docx" -o -name "*.xlsx" -o -name "*.html" -o -name "*.pdf" \) 2>/dev/null | wc -l | tr -d " ")
[ -z "$DOCS_PROD" ] && DOCS_PROD=0

# 1) usage log
if [ -f ~/.awos/awos-log.py ]; then
  "$PY" ~/.awos/awos-log.py log \
    --collaborator "$COLLAB" --name "$NAME" --project "$PROJECT" --mode "$MODE" \
    --tokens-in "$TOK_IN" --tokens-out "$TOK_OUT" \
    --docs-up "$DOCS_UP" --docs-prod "$DOCS_PROD" 2>/dev/null || true
fi

# 2) project checkpoint (silent ledger)
QC=$(ls ~/.awos/ai-parser/quickcheck.py 2>/dev/null || ls "$ROOT/scripts/ai-parser/quickcheck.py" 2>/dev/null | head -1)
[ -n "$QC" ] && "$PY" "$QC" --checkpoint "$COLLAB" "${MODE:---}" "" --root "$CARPETA" --quiet 2>/dev/null || true

# 3) AWAP local: si la carpeta del libro lleva registro de autoría, aquí TERMINA de trabajar este
#    colaborador, y lo que haya cambiado desde que empezó (hi-args.py) se anota como suyo. Sin
#    registro no hace nada. Con `=`: el modo empieza por «--» y si no argparse lo toma por opción.
AW="$SELF_DIR/awap_local.py"
[ -f "$AW" ] && "$PY" "$AW" fin "$CARPETA" --colab="$COLLAB" --nombre="$NAME" --modo="$MODE" >/dev/null 2>&1 || true

echo "logged: $COLLAB ($MODE) · $PROJECT"
