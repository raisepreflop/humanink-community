#!/usr/bin/env bash
# SessionStart — comprueba la licencia una vez por sesión y deja el resultado donde el modelo lo ve.
#
# Dónde va esto importa. El Bash de las skills dentro de Cowork corre en una máquina aislada sin red
# garantizada; los HOOKS, en cambio, corren en el equipo del autor y sí tienen red y disco — es lo
# que hace funcionar el espejo de scripts desde la 1.0.118. Así que la validación vive aquí.
#
# Deja el resultado por dos vías, porque ninguna es fiable sola:
#   1. Por su salida, que entra en el contexto del modelo. Es la que siempre llega.
#   2. En ~/.humanink/license-state, para las skills que puedan leer disco.
#
# Sale con 0 SIEMPRE. Un hook que aborta una sesión por un problema de licencia deja al autor sin
# su herramienta de escribir, y eso es peor que cualquier uso indebido que pudiera evitar.
set -u

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
. "$DIR/license-lib.sh" 2>/dev/null || exit 0

ESTADO="$(hi_estado 2>/dev/null || echo desconocido)"

# gate.conf lo escribe el build con los tiers que abre este paquete: una clave de Reescritura no
# tiene por qué abrir el Writers' Room.
TIERS_OK=""
[ -f "$DIR/gate.conf" ] && . "$DIR/gate.conf" 2>/dev/null

if [ "$ESTADO" = "valid" ] || [ "$ESTADO" = "offline" ]; then
  TIER="$(hi_json "$HI_LIC" tier 2>/dev/null)"
  if [ -n "$TIERS_OK" ] && [ -n "$TIER" ] && ! printf '%s' " $TIERS_OK " | grep -q " $TIER "; then
    ESTADO="tier_no_valido"
  fi
fi

mkdir -p "$HI_DIR" 2>/dev/null && printf '%s\n' "$ESTADO" > "$HI_ESTADO" 2>/dev/null

case "$ESTADO" in
  valid)
    echo "HUMANINK_LICENSE: valid tier=$(hi_json "$HI_LIC" tier)"
    ;;
  offline)
    # Se avisa pero no se cierra: la última validación buena sigue dentro de la gracia.
    echo "HUMANINK_LICENSE: valid (sin conexión — validada por última vez hace menos de 7 días)"
    ;;
  tier_no_valido)
    echo "HUMANINK_LICENSE: tier_no_valido"
    echo "HUMANINK_GATE: 🔑 Tu clave es de otro producto de HumanInk. Esta edición necesita su propia licencia — mira en humanink.io cuál te corresponde."
    ;;
  desconocido)
    # No se ha podido averiguar nada. Ante la duda NO se cierra: el fallo es nuestro, no del autor.
    echo "HUMANINK_LICENSE: desconocido (no se pudo comprobar; se continúa con normalidad)"
    ;;
  *)
    echo "HUMANINK_LICENSE: $ESTADO"
    echo "HUMANINK_GATE: $(hi_mensaje "$ESTADO")"
    ;;
esac

exit 0
