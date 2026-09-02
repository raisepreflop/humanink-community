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

# El prompt llega por stdin, en JSON. Se lee sin python3: en Windows no está, y depender de él
# era justo lo que dejaba a un cliente dos días sin poder activar.
PROMPT="$(cat | tr -d '\n' | sed -n 's/.*"prompt"[[:space:]]*:[[:space:]]*"\(.*\)"[^"]*}.*/\1/p')"

[ -z "$PROMPT" ] && exit 0

# LA CLAVE Y EL EMAIL, ESTÉN DONDE ESTÉN EN EL MENSAJE.
#
# Antes esto solo miraba el patrón exacto `/x:activate CLAVE EMAIL`, con los tres trozos juntos en
# el mismo mensaje. Y esa NO es la conversación real: lo normal es escribir `/humanink:activate`,
# que el colaborador pregunte «¿con qué email compraste?» y contestar con el email suelto. Por ahí
# el hook no se enteraba, así que este fichero no se escribía nunca.
#
# El resultado era el peor posible, porque no se notaba: la activación SÍ ocurría —en el servidor,
# por el conector, o dentro del recinto aislado de Cowork, que se tira al terminar— y el autor veía
# «activado». Pero la puerta solo mira ESTE fichero del equipo, así que en la siguiente sesión
# volvía a pedir la clave. Trabajaba, se le cerraba, activaba, trabajaba, se le cerraba.
#
# Se acepta la clave venga como venga; lo que se cuida es no activar con un email equivocado.
# Cuatro grupos separados por guiones, de 2 a 8 caracteres cada uno.
#
# La primera versión exigía grupos de EXACTAMENTE cinco para no confundirse con un trozo de UUID
# —8-4-4-4-12—, pero eso habría dejado fuera claves con otra forma: las hay como HK-1111-2222-3333.
# Rechazar la clave buena de un cliente por proteger de un falso positivo es el peor intercambio.
#
# Lo que separa una clave de un trozo de UUID no es la longitud de los grupos: es que la clave está
# SUELTA. Dentro de un UUID, cualquier tramo de cuatro grupos lleva un guion pegado a un lado. Así
# que se exige que lo que hay alrededor no sea ni guion ni alfanumérico, y después se recorta.
CLAVE="$(printf '%s' "$PROMPT" \
  | grep -oE '(^|[^A-Za-z0-9-])[A-Za-z0-9]{2,8}(-[A-Za-z0-9]{2,8}){3}([^A-Za-z0-9-]|$)' \
  | head -1 | grep -oE '[A-Za-z0-9]{2,8}(-[A-Za-z0-9]{2,8}){3}')"
# Permisivo a propósito: aquí NO se valida un email, solo se detecta. Exigir un dominio de dos o
# más letras rechazaba direcciones que el hook anterior aceptaba, y quien decide si el email vale
# es el servidor. Un patrón nuestro más severo que el suyo solo sirve para rechazar clientes buenos.
EMAIL="$(printf '%s' "$PROMPT" | grep -oE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]+' | head -1)"

PEND="$HI_DIR/.clave-pendiente"

# Si escribió el comando ENTERO y el tercer trozo no es un email, se le dice. Guardar la clave en
# silencio y quedarse esperando sería peor que el error: escribió los tres datos y no recibe nada.
if [ -n "$CLAVE" ] && [ -z "$EMAIL" ]; then
  TERCERO="$(printf '%s' "$PROMPT" \
    | grep -oE '/[a-z-]+:activate[[:space:]]+[^[:space:]]+[[:space:]]+[^[:space:]]+' \
    | head -1 | awk '{print $3}')"
  if [ -n "$TERCERO" ]; then
    echo "HUMANINK_ACTIVACION: error=email_invalido"
    exit 0
  fi
fi

if [ -n "$CLAVE" ] && [ -z "$EMAIL" ]; then
  # La clave sin email: se guarda un momento a la espera de la respuesta a «¿con qué email
  # compraste?». Con permisos de solo-dueño, junto a la licencia, y con fecha para caducarla.
  mkdir -p "$HI_DIR" 2>/dev/null || exit 0
  ( umask 077; printf '%s %s\n' "$(date +%s)" "$CLAVE" > "$PEND" 2>/dev/null ) || true
  exit 0
fi

if [ -z "$CLAVE" ] && [ -n "$EMAIL" ] && [ -f "$PEND" ]; then
  # Un email suelto contestando a la pregunta. DOS CANDADOS, porque atar una clave al email
  # equivocado es de las pocas cosas aquí que no tienen marcha atrás —una clave, una cuenta—:
  #
  #   · el mensaje tiene que ser poco más que el email (contestar una pregunta, no escribir un
  #     párrafo que de paso menciona una dirección de correo), y
  #   · la clave no puede llevar ahí más de quince minutos.
  PALABRAS="$(printf '%s' "$PROMPT" | wc -w | tr -d ' ')"
  GUARDADA="$(cat "$PEND" 2>/dev/null)"
  CUANDO="$(printf '%s' "$GUARDADA" | awk '{print $1}')"
  CLAVE="$(printf '%s' "$GUARDADA" | awk '{print $2}')"
  EDAD=$(( $(date +%s) - ${CUANDO:-0} ))
  if [ "${PALABRAS:-99}" -gt 5 ] || [ "$EDAD" -gt 900 ] || [ -z "$CLAVE" ]; then
    [ "$EDAD" -gt 900 ] && rm -f "$PEND" 2>/dev/null
    exit 0
  fi
fi

[ -z "$CLAVE" ] || [ -z "$EMAIL" ] && exit 0
rm -f "$PEND" 2>/dev/null

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
