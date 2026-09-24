#!/usr/bin/env bash
# HumanInk — calcula dónde guardar el resultado, en la convención que ya use el autor.
# Usage: next-output.sh <project_folder> [numero_de_capitulo]
# Imprime tres líneas:  MODE=builds|chapters   SOURCE=<fichero actual o vacío>   OUT=<fichero a crear>
#
# BUILDS (recomendada): el manuscrito entero por fichero, numerado ascendente.
#   …/MiNovela-b28.docx  →  OUT=…/MiNovela-b29.docx
#   El capítulo se edita DENTRO del manuscrito y se guarda el build siguiente: así la coherencia
#   se revisa siempre contra el texto completo, que es para lo que sirve este sistema.
# CHAPTERS: un fichero por capítulo versionado.
#   …/capitulos/cap-07-v2.docx  →  OUT=…/capitulos/cap-07-v3.docx
set -u
CARPETA="${1:-.}"
CARPETA="${CARPETA/#\~/$HOME}"
CAP="${2:-}"
ROOT="$(cd "$(dirname "$0")" && pwd)"

CURRENT=$(bash "$ROOT/latest-chapters.sh" "$CARPETA" 2>/dev/null | grep -vF '(no previous chapters)' | tail -1)

# ── Modo capítulos ──
if [ -d "$CARPETA/capitulos" ]; then
  CAP_NUM=$(printf '%s' "$CAP" | grep -oE '[0-9]+' | head -1)
  [ -z "$CAP_NUM" ] && CAP_NUM=1
  BASE="$CARPETA/capitulos/cap-$(printf '%02d' "$CAP_NUM")"
  CUR=$(ls "${BASE}"-v*.docx 2>/dev/null | sort -V | tail -1 || true)
  if [ -n "$CUR" ]; then
    V=$(printf '%s' "$CUR" | grep -oE 'v[0-9]+' | tail -1 | tr -d 'v')
    NEXT=$((V + 1))
  else
    NEXT=1
  fi
  echo "MODE=chapters"
  echo "SOURCE=${CUR:-}"
  echo "OUT=${BASE}-v${NEXT}.docx"
  exit 0
fi

# ── Modo manuscrito (m01-v01: manuscrito y versión, la convención recomendada desde el
#    Studio, 13-sep-2026). El número de MANUSCRITO se conserva tal cual venga (casi todos
#    tendrán un solo m01); solo la VERSIÓN avanza. ──
if [ -n "$CURRENT" ] && printf '%s' "$CURRENT" | grep -qiE '\-m[0-9]+-v[0-9]+'; then
  dir=$(dirname "$CURRENT")
  file=$(basename "$CURRENT")
  slug=$(printf '%s' "$file" | sed -E 's/(.*)-[mM][0-9]+-[vV][0-9]+.*/\1/')
  mparte=$(printf '%s' "$file" | sed -E 's/.*-([mM][0-9]+)-[vV][0-9]+.*/\1/' | tr '[:upper:]' '[:lower:]')
  num=$(printf '%s' "$file" | sed -E 's/.*-[vV]0*([0-9]+).*/\1/')
  width=$(printf '%s' "$file" | sed -E 's/.*-[vV]([0-9]+).*/\1/' | awk '{print length($0)}')
  next=$((num + 1))
  echo "MODE=manuscrito"
  echo "SOURCE=$CURRENT"
  printf 'OUT=%s/%s-%s-v%0*d.docx\n' "$dir" "$slug" "$mparte" "$width" "$next"
  exit 0
fi

# ── Modo builds (la convención antigua: -bNN) ──
# CASE-INSENSITIVE (13-sep-2026): un fichero real de autor llega como «LDDLL-1-B32-…», con B
# mayúscula. Sin -i esta rama no lo reconocía y trataba una novela con 32 builds como si fuera
# un proyecto nuevo, reiniciando en b01 al lado del b32 real. latest-chapters.sh ya elegía bien
# el CURRENT con -i; esta rama, que decide qué escribir a partir de él, se había quedado atrás.
if [ -n "$CURRENT" ] && printf '%s' "$CURRENT" | grep -qiE '\-b[0-9]+'; then
  dir=$(dirname "$CURRENT")
  file=$(basename "$CURRENT")
  # slug = todo lo anterior a "-b<NN>"; se conserva el ancho del número (b09 → b10, b28 → b29)
  slug=$(printf '%s' "$file" | sed -E 's/(.*)-[bB][0-9]+.*/\1/')
  num=$(printf '%s' "$file" | sed -E 's/.*-[bB]0*([0-9]+).*/\1/')
  width=$(printf '%s' "$file" | sed -E 's/.*-[bB]([0-9]+).*/\1/' | awk '{print length($0)}')
  next=$((num + 1))
  echo "MODE=builds"
  echo "SOURCE=$CURRENT"
  printf 'OUT=%s/%s-b%0*d.docx\n' "$dir" "$slug" "$width" "$next"
  exit 0
fi

# ── Proyecto nuevo: se estrena con el sistema recomendado (m01-v01 desde el 13-sep-2026) ──
name=$(basename "$CARPETA" | tr ' ' '-')
echo "MODE=manuscrito"
echo "SOURCE="
echo "OUT=$CARPETA/${name}-m01-v01.docx"
