#!/usr/bin/env bash
# Presencia — quién usa la edición libre. NUNCA cierra nada.
#
# POR QUÉ EXISTE. El 10-sep-2026 se retiró la comprobación de licencia de la edición del Club:
# daba más problemas que resolvía (dos licencias envenenadas desde mensajes ajenos, un cliente
# tres rondas sin poder trabajar). A cambio, Rais pidió saber quién la usa: «que pida el email o
# lo que sea». Esto es ese «lo que sea», con una regla por encima de todas: este hook no puede
# dejar a nadie sin su herramienta. Sale con 0 SIEMPRE.
#
# Dos modos, según cómo lo llame hooks.json:
#
#   presencia.sh sesion    (SessionStart)  — si hay email guardado, avisa al servidor como mucho
#                                            una vez al día; si no lo hay, deja UNA línea en el
#                                            contexto para que el colaborador lo pida.
#   presencia.sh mensaje   (UserPromptSubmit) — recoge el email cuando el autor lo escribe.
#
# CÓMO SE RECOGE EL EMAIL, y por qué con tanto cuidado. El Bash de las skills no tiene disco en
# Cowork, así que guardarlo tiene que hacerse aquí, en un hook — y un hook que lee prosa es
# exactamente lo que envenenó dos licencias. Aquí no hay clave ni servidor que ate nada, así que
# un falso positivo no cuesta nada (se cambia escribiendo «presencia tu@email»), pero aun así se
# exige: que NO haya ya un email guardado, que el mensaje sea poco más que el email (≤ 8 palabras)
# y que lleve exactamente uno. Una captura de WhatsApp de un cliente no cumple ninguna de las tres.
set -u

MODO="${1:-sesion}"
# Sin HOME —pasa en algún lanzador— `set -u` mataría el hook en la primera línea. El equipo rojo
# lo vio el 10-sep-2026: era el único hueco entre «sale con 0 SIEMPRE» y el código.
HOME="${HOME:-/tmp}"
HI_DIR="$HOME/.humanink"
FICH="$HI_DIR/presencia.json"
URL="${HUMANINK_VERIFY_URL:-https://verify.humanink.io}"
ROOT="${CLAUDE_PLUGIN_ROOT:-}"

campo() {   # campo <fichero> <clave>  → el valor de una clave de cadena, sin python
  [ -f "$1" ] || return 0
  sed -n "s/.*\"$2\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" "$1" | head -1
}

EMAIL_GUARDADO="$(campo "$FICH" email)"
HOY="$(date +%Y-%m-%d)"

guardar() {   # guardar <email> <dia>  — el email solo tiene los caracteres del patrón: sin comillas
  # Devuelve 1 si no ha podido escribir: entonces NO se dice «ok» ni se avisa al servidor, porque
  # el autor lo vería pedir el email en cada sesión creyendo que ya lo dio.
  mkdir -p "$HI_DIR" 2>/dev/null || return 1
  ( umask 077; printf '{"email":"%s","dia":"%s"}\n' "$1" "$2" > "$FICH.tmp" 2>/dev/null \
      && mv -f "$FICH.tmp" "$FICH" 2>/dev/null ) || return 1
  [ -f "$FICH" ]
}

avisar() {   # avisar <email> — una llamada corta; el resultado no importa para el autor
  local ver="" nombre="" so=""
  [ -n "$ROOT" ] && ver="$(campo "$ROOT/.claude-plugin/plugin.json" version)" \
                 && nombre="$(campo "$ROOT/.claude-plugin/plugin.json" name)"
  so="$(uname -s 2>/dev/null || echo desconocido)"
  curl -s -m 4 -X POST "$URL/presencia" -H 'content-type: application/json' \
    -d "{\"email\":\"$1\",\"edicion\":\"${nombre:-humanink}\",\"version\":\"${ver:-?}\",\"so\":\"$so\"}" \
    >/dev/null 2>&1 || true
}

case "$MODO" in
  sesion)
    if [ -z "$EMAIL_GUARDADO" ]; then
      echo "HUMANINK_PRESENCIA: falta_email"
      exit 0
    fi
    # Como mucho una vez al día, tenga red o no: se sella el día ANTES de llamar, para que una
    # máquina sin salida no lo intente en cada sesión.
    [ "$(campo "$FICH" dia)" = "$HOY" ] && exit 0
    guardar "$EMAIL_GUARDADO" "$HOY"
    avisar "$EMAIL_GUARDADO"
    exit 0
    ;;
  mensaje)
    # El prompt, hasta la primera comilla sin escapar: no se supone que sea el último campo del
    # JSON (el sed viejo lo suponía, y con «cwd» detrás no sacaba nada).
    PROMPT="$(cat | tr -d '\n' | sed -En 's/.*"prompt"[[:space:]]*:[[:space:]]*"(([^"\\]|\\.)*)".*/\1/p')"
    [ -z "$PROMPT" ] && exit 0
    PALABRAS="$(printf '%s' "$PROMPT" | wc -w | tr -d ' ')"
    [ "${PALABRAS:-99}" -le 8 ] || exit 0
    CUANTOS="$(printf '%s' "$PROMPT" | grep -oE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]+' | wc -l | tr -d ' ')"
    [ "${CUANTOS:-0}" = "1" ] || exit 0
    EMAIL="$(printf '%s' "$PROMPT" | grep -oE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]+' | head -1 | tr 'A-Z' 'a-z')"
    # Y LO QUE RODEA AL EMAIL TIENE QUE SER NADA, O CASI. «escribe a cesar@gmail.com sobre el
    # capítulo de hoy» son ocho palabras con un email y NO es el autor dándonos el suyo: es una
    # orden a un colaborador. Quitado el email, lo que quede solo puede ser relleno de contestar
    # («mi email es», «presencia», «aquí tienes»…). Cualquier otra palabra —un verbo, un nombre—
    # y no se guarda.
    RESTO="$(printf '%s' "$PROMPT" | sed -E 's/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]+/ /g' \
      | tr 'A-Z' 'a-z' | tr -c 'a-z0-9áéíóúñü\n' ' ')"
    for w in $RESTO; do
      case "$w" in
        mi|email|e-mail|mail|correo|es|el|la|presencia|aqui|aquí|tienes|este|esta|direccion|dirección|soy|ok|vale|de|mío|mio) ;;
        *) exit 0 ;;
      esac
    done
    if [ -n "$EMAIL_GUARDADO" ]; then
      # Ya hay uno: solo se cambia si lo pide con la palabra. Un email suelto en una respuesta a
      # otra cosa no puede reescribirlo.
      case "$PROMPT" in *[Pp]resencia*) ;; *) exit 0 ;; esac
    fi
    guardar "$EMAIL" "$HOY" || exit 0
    avisar "$EMAIL"
    echo "HUMANINK_PRESENCIA: ok"
    exit 0
    ;;
esac
exit 0
