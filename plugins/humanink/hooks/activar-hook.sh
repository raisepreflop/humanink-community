#!/usr/bin/env bash
# UserPromptSubmit — activa la licencia DESDE EL EQUIPO DEL AUTOR.
#
# POR QUÉ EXISTE. La puerta se cerraba y la llave no podía girar.
#
# El `/humanink:activate` llamaba al servidor con curl desde el Bash de la skill. En Claude Code eso
# funciona; en Cowork, no: el Bash de las skills corre en una máquina aislada sin red, así que el
# autor recibía «el servidor de licencias no conecta» una y otra vez —el servidor estaba perfecto— y
# se quedaba en bucle: la puerta le pedía activar y activar no podía llegar al servidor.
#
# Los hooks, en cambio, corren AQUÍ, en el equipo del autor: tienen red y tienen disco. Es el mismo
# motivo por el que la comprobación de licencia vive en un hook desde el principio.
#
# Qué hace: mira lo que el autor acaba de escribir y, si es una activación, la ejecuta él mismo y
# deja el resultado en el contexto. La skill solo tiene que leerlo y contarlo.
#
# Sale con 0 SIEMPRE y en silencio cuando no es asunto suyo: un hook que se cuela en cada mensaje
# del autor es peor que el problema que resuelve.
set -u

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
. "$DIR/license-lib.sh" 2>/dev/null || exit 0

# El prompt llega por stdin, en JSON. Sin python3 no hay nada que hacer: se calla y sale.
PROMPT="$(python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get("prompt") or "")
except Exception:
    print("")
' 2>/dev/null)" || exit 0

[ -z "$PROMPT" ] && exit 0

# /humanink:activate CLAVE EMAIL — y sus primos: /humanink-certificate:activate, /reescritura:activate
LINEA="$(printf '%s' "$PROMPT" | grep -oE '/[a-z-]+:activate[[:space:]]+[^[:space:]]+[[:space:]]+[^[:space:]]+' | head -1)"
[ -z "$LINEA" ] && exit 0

CLAVE="$(printf '%s' "$LINEA" | awk '{print $2}')"
EMAIL="$(printf '%s' "$LINEA" | awk '{print $3}')"
[ -z "$CLAVE" ] || [ -z "$EMAIL" ] && exit 0

# Un email sin arroba es un dedazo, no una activación: mejor decirlo que gastar una llamada.
case "$EMAIL" in
  *@*.*) ;;
  *) echo "HUMANINK_ACTIVACION: error=email_invalido"; exit 0 ;;
esac

if ERR="$(hi_activar "$CLAVE" "$EMAIL" 2>/dev/null)"; then
  echo "HUMANINK_ACTIVACION: ok tier=$(hi_json "$HI_LIC" tier)"
  # La puerta lee este fichero al arrancar la sesión; se deja al día ya, no en la siguiente.
  mkdir -p "$HI_DIR" 2>/dev/null && printf 'valid\n' > "$HI_ESTADO" 2>/dev/null
else
  echo "HUMANINK_ACTIVACION: error=${ERR:-desconocido}"
fi

exit 0
