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

# ── json: leer un campo sin depender de jq ──────────────────────────────────────────────────
hi_json() {   # hi_json <fichero> <campo>
  python3 - "$1" "$2" 2>/dev/null <<'PY'
import json, sys
try:
    with open(sys.argv[1], encoding="utf-8") as f:
        d = json.load(f)
    v = d.get(sys.argv[2])
    print("" if v is None else v)
except Exception:
    print("")
PY
}

hi_guardar() {   # hi_guardar <clave> <email> <tier> <expira> <valida:0|1> <error>
  mkdir -p "$HI_DIR" 2>/dev/null || return 0
  python3 - "$HI_LIC" "$@" 2>/dev/null <<'PY'
import json, os, sys, time
ruta, clave, email, tier, expira, valida, err = sys.argv[1:8]
d = {
    "key": clave, "email": email, "tier": tier,
    "expires_at": expira or None,
    "checked_at": int(time.time()),
    "last_valid": valida == "1",
    "last_error": err or None,
}
tmp = ruta + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(d, f, ensure_ascii=False, indent=1)
os.replace(tmp, ruta)   # atómico: un corte a media escritura no deja el estado a medias
PY
}

# ── El servidor ─────────────────────────────────────────────────────────────────────────────
hi_preguntar() {   # hi_preguntar <clave> <email> → imprime el JSON de /activate, o vacío sin red
  curl -sS -m 6 -X POST "${HI_VERIFY}/activate" \
    -H "content-type: application/json" \
    -d "{\"key\":$(printf '%s' "$1" | python3 -c 'import json,sys;print(json.dumps(sys.stdin.read()))'),\"email\":$(printf '%s' "$2" | python3 -c 'import json,sys;print(json.dumps(sys.stdin.read()))')}" \
    2>/dev/null
}

hi_activar() {   # hi_activar <clave> <email> → 0 si quedó activada
  local r; r="$(hi_preguntar "$1" "$2")"
  [ -z "$r" ] && { echo "network"; return 1; }
  local valida tier expira err
  valida="$(printf '%s' "$r" | python3 -c 'import json,sys;print("1" if json.load(sys.stdin).get("valid") else "0")' 2>/dev/null)"
  tier="$(printf '%s' "$r" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("tier") or "")' 2>/dev/null)"
  expira="$(printf '%s' "$r" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("expires_at") or "")' 2>/dev/null)"
  err="$(printf '%s' "$r" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("error") or "")' 2>/dev/null)"
  hi_guardar "$1" "$2" "$tier" "$expira" "${valida:-0}" "$err"
  [ "$valida" = "1" ] && return 0
  echo "${err:-invalid}"; return 1
}

# ── El estado ───────────────────────────────────────────────────────────────────────────────
# Imprime una palabra: valid · missing · offline · expired · <error del servidor>
hi_estado() {
  [ -f "$HI_LIC" ] || { echo missing; return; }
  local clave email valida edad
  clave="$(hi_json "$HI_LIC" key)"
  email="$(hi_json "$HI_LIC" email)"
  [ -z "$clave" ] && { echo missing; return; }

  valida="$(hi_json "$HI_LIC" last_valid)"
  edad=$(( $(date +%s) - $(hi_json "$HI_LIC" checked_at 2>/dev/null || echo 0) ))

  # Dentro de la ventana de revalidación: se cree lo que se sabe y no se molesta al servidor.
  if [ "$valida" = "True" ] && [ "$edad" -lt $((HI_REVALIDA_H * 3600)) ]; then
    echo valid; return
  fi

  local r; r="$(hi_preguntar "$clave" "$email")"
  if [ -z "$r" ]; then
    # Sin red: se respeta la última validación buena durante la gracia. Un autor de viaje o con
    # el wifi caído no puede quedarse fuera de su propio libro.
    if [ "$valida" = "True" ] && [ "$edad" -lt $((HI_GRACIA_D * 86400)) ]; then echo offline; else echo offline_expirado; fi
    return
  fi
  local ok tier expira err
  ok="$(printf '%s' "$r" | python3 -c 'import json,sys;print("1" if json.load(sys.stdin).get("valid") else "0")' 2>/dev/null)"
  tier="$(printf '%s' "$r" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("tier") or "")' 2>/dev/null)"
  expira="$(printf '%s' "$r" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("expires_at") or "")' 2>/dev/null)"
  err="$(printf '%s' "$r" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("error") or "")' 2>/dev/null)"
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
