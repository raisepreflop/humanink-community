#!/usr/bin/env bash
# HumanInk shared manuscript lister — autodetecta cómo organiza el autor su novela.
# Usage: latest-chapters.sh <project_folder>
# Imprime, una por línea, la(s) ruta(s) .docx que hay que leer para tener el manuscrito al día.
#
# Soporta DOS convenciones, porque los autores reales usan las dos:
#
#   A) VERSIONES (recomendada) — un fichero = el manuscrito ENTERO, numerado ascendente:
#      DUOC-m10-v01.docx, DUOC-m10-v02.docx … (m = manuscrito, v = versión)
#      Se acepta también la nomenclatura antigua -b01 y, en AMBAS, mayúscula o minúscula:
#      los ficheros reales del autor venían como LDDLL-1-B32-… y el patrón sólo-minúsculas
#      no casaba con ninguno.
#      Cada sesión o intervención genera el build siguiente. Es el sistema con el que Rais ha
#      escrito sus novelas: para una reescritura quirúrgica tienes todo el texto delante en un
#      solo fichero, los placeholders se buscan de una vez y la coherencia no depende de juntar
#      trozos. Devuelve UN solo fichero: el build más alto.
#
#   B) CAPÍTULOS — un fichero por capítulo, versionado: capitulos/cap-NN-vK.docx
#      Devuelve el último v de cada capítulo, uno por línea.
#
# Si no encuentra ninguna de las dos, AVISA por stderr (nunca en silencio: que un colaborador
# escriba sin el manuscrito y no lo diga es el peor fallo posible para la coherencia).
set -u
CARPETA="${1:-.}"
CARPETA="${CARPETA/#\~/$HOME}"
CAPS_DIR="$CARPETA/capitulos"

# ── B) Capítulos: convención explícita, tiene prioridad si existe la carpeta ──
if [ -d "$CAPS_DIR" ] && ls "$CAPS_DIR"/*.docx >/dev/null 2>&1; then
  ls "$CAPS_DIR"/*.docx 2>/dev/null | sed 's/-v[0-9]*\.docx$//' | sort -u | while read -r base; do
    latest=$(ls "${base}"-v*.docx 2>/dev/null | sort -V | tail -1)
    [ -z "$latest" ] && latest=$(ls "${base}".docx 2>/dev/null)
    [ -n "$latest" ] && echo "$latest"
  done
  exit 0
fi

# ── A) Versiones: <lo-que-sea>-v<NN>[-sufijo].docx (o -b<NN>, y en cualquier caja), hasta 2 niveles de profundidad ──
# Se descartan: ficheros de bloqueo de Word (~$…), duplicados del Finder (" copia"/" copy"/"(1)")
# y las carpetas de salida del plugin.
builds=$(find "$CARPETA" -maxdepth 2 -type f -name '*.docx' 2>/dev/null \
  | grep -Ev '/~\$|/\.|/entregables/|/informes/|/deliverables/' \
  | grep -Ev ' cop(ia|y)|\([0-9]+\)\.docx$' \
  | grep -Ei '\-[vb][0-9]+([^/]*)?\.docx$')

if [ -n "$builds" ]; then
  # Ordena por número de build (no alfabéticamente: b9 < b10) y coge el más alto.
  # Empate dentro del mismo número (b05.docx vs b05-reescrito.docx) → el más reciente en disco.
  top=$(printf '%s\n' "$builds" | while IFS= read -r f; do
          n=$(basename "$f" | sed -E 's/.*-[vVbB]0*([0-9]+).*/\1/')
          printf '%s\t%s\n' "$n" "$f"
        done | sort -n -k1,1 | tail -1 | cut -f1)
  printf '%s\n' "$builds" | while IFS= read -r f; do
    n=$(basename "$f" | sed -E 's/.*-[vVbB]0*([0-9]+).*/\1/')
    [ "$n" = "$top" ] && printf '%s\n' "$f"
  done | while IFS= read -r f; do
    [ -f "$f" ] && printf '%s\t%s\n' "$(stat -f %m "$f" 2>/dev/null || stat -c %Y "$f" 2>/dev/null)" "$f"
  done | sort -n -k1,1 | tail -1 | cut -f2-
  exit 0
fi

# ── Ninguna convención reconocida: avisar fuerte, nunca seguir en silencio ──
echo "(no previous chapters)"
alt=$(find "$CARPETA" -maxdepth 2 -type f -name '*.docx' 2>/dev/null | grep -Ev '/~\$|/\.' | head -5)
if [ -n "$alt" ]; then
  echo "⚠️  ATENCIÓN: hay .docx en el proyecto pero no siguen ninguna convención reconocida:" >&2
  printf '%s\n' "$alt" | sed 's/^/     /' >&2
  echo "     EL MANUSCRITO NO SE HA CARGADO. Díselo al autor antes de escribir una sola línea." >&2
  echo "     Recomiéndale el sistema de builds: <MiNovela>-b01.docx, -b02.docx… (el manuscrito" >&2
  echo "     entero en cada fichero, numerado ascendente en cada intervención)." >&2
else
  echo "⚠️  No hay manuscrito en '$CARPETA' — proyecto nuevo, o la ruta es otra." >&2
fi
exit 0
