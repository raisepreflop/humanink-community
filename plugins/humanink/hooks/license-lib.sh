#!/usr/bin/env bash
# Estado de licencia de HumanInk — funciones compartidas.
#
# Existe porque el plugin va a distribuirse desde un marketplace PÚBLICO de GitHub: es la única
# forma de que Cowork instale de un clic y actualice solo, y Cowork solo sincroniza repositorios
# públicos. Eso significa que el código estará a la vista, así que quien decide si se puede usar
# no es el fichero: es la clave.
#
# Reglas que no se negocian:
#   · Nunca bloquear por un fallo NUESTRO. Sin red, con el servidor caído o con el fichero de
#     estado corrupto, el autor sigue trabajando. Se cierra por caducidad comprobada, no por duda.
#   · Siete días de gracia sin red, contados desde la última validación BUENA — misma regla que el
#     companion de Word (humanink-word/companion/license.mjs), que lleva meses en producción.
#   · El texto del manuscrito no entra aquí para nada. Solo viajan la clave y el email.
set -u

HI_DIR="${HOME}/.humanink"
HI_LIC="${HI_DIR}/license.json"
HI_ESTADO="${HI_DIR}/license-state"
HI_VERIFY="${HUMANINK_VERIFY_URL:-https://verify.humanink.io}"

HI_REVALIDA_H=24          # cada cuánto se vuelve a preguntar al servidor
HI_GRACIA_D=7             # días sin red antes de cerrar

# ── json: leer un campo, sin jq y SIN python3 ────────────────────────────────────────────────
# Por qué a mano: en Windows no hay `python3`, y cuando falta, TODO esto devolvía vacío. El
# síntoma era «no se puede conectar con el servidor de licencias» con el servidor perfectamente
# sano — un cliente pasó dos días atascado por esto. Aquí solo se usa lo que trae cualquier shell.
#
# El JSON que se lee es nuestro y es plano: cadenas, números, booleanos y null. No hay anidamiento,
# así que un extractor por campo es suficiente y no hay que arrastrar un parser.
hi_campo() {   # hi_campo <texto-json> <campo>
  printf '%s' "$1" | tr -d '\n' | sed -n \
    "s/.*\"$2\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" | head -1
}

hi_campo_crudo() {   # hi_campo_crudo <texto-json> <campo> — para true/false/null/números
  printf '%s' "$1" | tr -d '\n' | sed -n \
    "s/.*\"$2\"[[:space:]]*:[[:space:]]*\([^,}\"]*\).*/\1/p" | head -1 | tr -d ' '
}

hi_json() {   # hi_json <fichero> <campo>
  [ -f "$1" ] || { printf ''; return; }
  local t v
  t="$(cat "$1" 2>/dev/null)"
  v="$(hi_campo "$t" "$2")"
  [ -n "$v" ] || v="$(hi_campo_crudo "$t" "$2")"
  case "$v" in null) v="";; esac
  printf '%s' "$v"
}

hi_guardar() {   # hi_guardar <clave> <email> <tier> <expira> <valida:0|1> <error>
  mkdir -p "$HI_DIR" 2>/dev/null || return 0
  local tmp="$HI_LIC.tmp" val="false" exp="null" err="null"
  [ "$5" = "1" ] && val="true"
  [ -n "${4:-}" ] && exp="\"$4\""
  [ -n "${6:-}" ] && err="\"$6\""
  {
    printf '{\n'
    printf ' "key": "%s",\n' "$(hi_escapa "$1")"
    printf ' "email": "%s",\n' "$(hi_escapa "$2")"
    printf ' "tier": "%s",\n' "$(hi_escapa "$3")"
    printf ' "expires_at": %s,\n' "$exp"
    printf ' "checked_at": %s,\n' "$(date +%s)"
    printf ' "last_valid": %s,\n' "$val"
    printf ' "last_error": %s\n' "$err"
    printf '}\n'
  } > "$tmp" 2>/dev/null && mv -f "$tmp" "$HI_LIC" 2>/dev/null   # atómico: un corte no deja el estado a medias
}

# Comillas y barras, lo único que puede romper el JSON de una clave o un email.
hi_escapa() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }

# ── El servidor ─────────────────────────────────────────────────────────────────────────────
hi_preguntar() {   # hi_preguntar <clave> <email> → imprime el JSON de /activate, o vacío sin red
  curl -sS -m 6 -X POST "${HI_VERIFY}/activate" \
    -H "content-type: application/json" \
    -d "{\"key\":\"$(hi_escapa "$1")\",\"email\":\"$(hi_escapa "$2")\"}" \
    2>/dev/null
}

hi_activar() {   # hi_activar <clave> <email> → 0 si quedó activada
  local r; r="$(hi_preguntar "$1" "$2")"
  [ -z "$r" ] && { echo "network"; return 1; }
  local valida tier expira err
  valida="$([ "$(hi_campo_crudo "$r" valid)" = "true" ] && echo 1 || echo 0)"
  tier="$(hi_campo "$r" tier)"
  expira="$(hi_campo "$r" expires_at)"
  err="$(hi_campo "$r" error)"
  hi_guardar "$1" "$2" "$tier" "$expira" "${valida:-0}" "$err"
  [ "$valida" = "1" ] && return 0
  echo "${err:-invalid}"; return 1
}

# ── El estado ───────────────────────────────────────────────────────────────────────────────
# Imprime una palabra: valid · missing · offline · expired · <error del servidor>
# ¿Se puede hablar con nuestro servidor desde aquí?
#
# Hace falta para distinguir dos cosas que se veían iguales y no lo son: «este autor no ha
# activado» y «no puedo comprobar si ha activado». Una barata y sin cabeceras: si el dominio está
# bloqueado, curl falla y ya está.
hi_alcanzable() {
  curl -sS -m 4 -o /dev/null "${HI_VERIFY}/latest?product=word" 2>/dev/null
}

hi_estado() {
  # SIN FICHERO. Hasta el 2-sep-2026 esto contestaba «missing» directamente, y eso rompía la
  # primera regla de este fichero —«nunca bloquear por un fallo NUESTRO»— sin que nadie lo notara,
  # porque en un ordenador normal las dos cosas coinciden.
  #
  # Donde no coinciden es en un entorno con la salida de red restringida: la sesión arranca sin
  # fichero (el contenedor es nuevo), el portero dice «activa tu licencia»… y la activación no
  # puede llegar al servidor porque el dominio está fuera de la lista permitida. Bucle cerrado:
  # el producto te pide una llave y tapia la cerradura. Le pasó a un cliente el 2-sep-2026.
  #
  # Ahora se pregunta primero si el servidor es alcanzable. Si no lo es, el estado es
  # «desconocido», que la puerta ya trata como «se continúa con normalidad»: ante la duda no se
  # cierra. Si SÍ es alcanzable y no hay fichero, entonces sí es que no ha activado.
  if [ ! -f "$HI_LIC" ] || [ -z "$(hi_json "$HI_LIC" key)" ]; then
    if hi_alcanzable; then echo missing; else echo desconocido; fi
    return
  fi
  local clave email valida edad
  clave="$(hi_json "$HI_LIC" key)"
  email="$(hi_json "$HI_LIC" email)"

  valida="$(hi_json "$HI_LIC" last_valid)"
  edad=$(( $(date +%s) - $(hi_json "$HI_LIC" checked_at 2>/dev/null || echo 0) ))

  # Dentro de la ventana de revalidación: se cree lo que se sabe y no se molesta al servidor.
  # El fichero puede venir de una versión vieja (Python escribía True) o de esta (true).
  case "$valida" in true|True) valida="si";; *) valida="no";; esac
  if [ "$valida" = "si" ] && [ "$edad" -lt $((HI_REVALIDA_H * 3600)) ]; then
    echo valid; return
  fi

  local r; r="$(hi_preguntar "$clave" "$email")"
  if [ -z "$r" ]; then
    # Sin red: se respeta la última validación buena durante la gracia. Un autor de viaje o con
    # el wifi caído no puede quedarse fuera de su propio libro.
    if [ "$valida" = "si" ] && [ "$edad" -lt $((HI_GRACIA_D * 86400)) ]; then echo offline; else echo offline_expirado; fi
    return
  fi
  local ok tier expira err
  ok="$([ "$(hi_campo_crudo "$r" valid)" = "true" ] && echo 1 || echo 0)"
  tier="$(hi_campo "$r" tier)"
  expira="$(hi_campo "$r" expires_at)"
  err="$(hi_campo "$r" error)"
  hi_guardar "$clave" "$email" "$tier" "$expira" "${ok:-0}" "$err"
  if [ "$ok" = "1" ]; then echo valid; else echo "${err:-invalid}"; fi
}

# El mensaje que ve el autor. Dice qué pasa y qué hacer, sin jerga y sin culpar a nadie.
hi_mensaje() {   # hi_mensaje <estado>
  case "$1" in
    missing)
      echo "🔑 HumanInk todavía no está activado en este equipo. Escribe \`/humanink:activate TU-CLAVE tu@email\` — la clave está en el email de tu compra. ¿Aún no la tienes? humanink.io" ;;
    expired)
      echo "🔑 Tu licencia ha caducado. Renuévala en humanink.io y vuelve a activar con \`/humanink:activate\`." ;;
    subscription_cancelled)
      echo "🔑 Tu suscripción figura como cancelada. Si crees que es un error, escríbenos desde humanink.io." ;;
    activated_elsewhere)
      echo "🔑 Esa clave ya está activada con otro email. Usa el email con el que compraste: una clave, una cuenta." ;;
    offline_expirado)
      echo "🔑 Llevo más de siete días sin poder verificar tu licencia. Conéctate un momento y vuelve a intentarlo." ;;
    blocked)
      echo "🔑 Esta licencia está bloqueada. Escríbenos desde humanink.io y lo miramos." ;;
    *)
      echo "🔑 No he podido validar tu licencia. Prueba \`/humanink:activate TU-CLAVE tu@email\`, y si sigue igual escríbenos desde humanink.io." ;;
  esac
}

# ── El aviso de versión ─────────────────────────────────────────────────────────────────────────
#
# POR QUÉ EXISTE. Claude no actualiza los plugins solo, y el autor no entra a mirar si hay una
# versión nueva: no lo hace y no lo va a hacer. Medido el 3-sep-2026 en el equipo de Rais, que es
# quien los publica: tenía cargada la 2.0.1-club con la 2.0.8 publicada desde hacía días, y el
# fallo que le hacía repetir la clave en cada chat estaba corregido en la 2.0.5. Un cliente activo
# puede ir cinco versiones atrás sin que nada se lo cuente, y cada arreglo que publicamos se queda
# sin llegar.
#
# Así que lo cuenta el propio plugin, una vez al día, y nunca bloquea nada.
HI_VER_CACHE="${HI_DIR}/plugin-ultima"
# `${BASH_SOURCE[0]:-$0}`, con respaldo: esta librería la cargan varios hooks y podría cargarla
# una skill desde `sh` o `zsh`, donde BASH_SOURCE no existe y con `set -u` aborta el fichero
# entero —incluido el portero de licencia—. Un aviso de versión no puede tirar nada.
HI_PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-${0:-.}}")/.." 2>/dev/null && pwd || printf .)"

# La versión de ESTE paquete, leída de su propio manifiesto.
hi_version_local() {
  sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' \
    "$HI_PLUGIN_DIR/.claude-plugin/plugin.json" 2>/dev/null | head -1
}

# El NOMBRE de este paquete. Sin esto, con dos ediciones instaladas el autor lee dos veredictos
# contradictorios y ninguno dice quién habla: el 3-sep-2026 Rais tuvo que rastrear rutas dentro de
# ~/Library para descubrir que quien le bloqueaba era su propio plugin de pruebas.
hi_nombre_local() {
  sed -n 's/.*"name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' \
    "$HI_PLUGIN_DIR/.claude-plugin/plugin.json" 2>/dev/null | head -1
}

# Cada edición se anuncia por separado: la del Club no lleva las mismas skills que la completa.
hi_producto_plugin() {
  case "$(hi_version_local)" in
    *-club) printf 'plugin-club' ;;
    *)      printf 'plugin' ;;
  esac
}

# La última publicada, con caché de un día. Si la caché está fresca no se toca la red: este hook
# corre en CADA arranque de sesión y no puede costar una petición cada vez.
hi_ultima_plugin() {
  local ahora edad r v
  ahora="$(date +%s)"
  if [ -f "$HI_VER_CACHE" ]; then
    edad=$(( ahora - $(cut -f1 "$HI_VER_CACHE" 2>/dev/null || echo 0) ))
    if [ "$edad" -lt 86400 ] && [ "$edad" -ge 0 ]; then
      cut -f2 "$HI_VER_CACHE" 2>/dev/null
      return 0
    fi
  fi
  r="$(curl -sS -m 3 "${HI_VERIFY}/latest?product=$(hi_producto_plugin)" 2>/dev/null)" || return 0
  v="$(hi_campo "$r" version)"
  [ -n "$v" ] || return 0
  mkdir -p "$HI_DIR" 2>/dev/null && printf '%s\t%s\n' "$ahora" "$v" > "$HI_VER_CACHE" 2>/dev/null
  printf '%s' "$v"
}

# ¿Es la primera MENOR que la segunda? Se compara solo la parte numérica: «2.0.8-club» y «2.0.8»
# son la misma versión en ediciones distintas, y ordenar el sufijo daría un aviso falso.
hi_atrasado() {   # hi_atrasado <local> <remota> → 0 si hay que actualizar
  local a="${1%%-*}" b="${2%%-*}"
  [ -n "$a" ] && [ -n "$b" ] || return 1
  [ "$a" = "$b" ] && return 1
  [ "$(printf '%s\n%s\n' "$a" "$b" | sort -V 2>/dev/null | head -1)" = "$a" ]
}
