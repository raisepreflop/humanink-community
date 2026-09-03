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

# QUIÉN HABLA. Ojo con las llaves: `«$QUIEN»` se lee como la variable `QUIEN»` cuando la
# localización no es UTF-8 —el contenedor de Cowork y CI, por ejemplo—, y con `set -u` eso MATA el
# portero después de la primera línea. Pasó el 3-sep-2026 y solo se vio al mirar el stderr, que
# nadie leía. Toda variable pegada a un carácter no ASCII va entre llaves.
# QUIÉN HABLA. Con dos ediciones instaladas se imprimen dos veredictos seguidos, y hasta hoy
# ninguno decía de cuál venía. Es la diferencia entre «mi producto está roto» y «este otro
# paquete no es el mío».
QUIEN="$(hi_nombre_local 2>/dev/null || true)"
QUIEN="${QUIEN:-humanink}$( [ -n "$(hi_version_local 2>/dev/null || true)" ] && printf " %s" "$(hi_version_local)" )"

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
    echo "HUMANINK_LICENSE [${QUIEN}]: valid tier=$(hi_json "$HI_LIC" tier)"
    ;;
  offline)
    # Se avisa pero no se cierra: la última validación buena sigue dentro de la gracia.
    echo "HUMANINK_LICENSE [${QUIEN}]: valid (sin conexión — validada por última vez hace menos de 7 días)"
    ;;
  tier_no_valido)
    echo "HUMANINK_LICENSE [${QUIEN}]: tier_no_valido (tu tier: $(hi_json "$HI_LIC" tier) · este paquete abre: $TIERS_OK)"
    echo "HUMANINK_GATE: 🔑 Tu clave no abre «${QUIEN}» — es de otro producto de HumanInk. Los demás plugins de HumanInk que tengas instalados siguen funcionando con normalidad. Si no reconoces este paquete, quítalo desde Plugins → Gestionar plugins; si lo quieres, mira en humanink.io qué licencia le corresponde."
    ;;
  desconocido)
    # No se ha podido averiguar nada. Ante la duda NO se cierra: el fallo es nuestro, no del autor.
    echo "HUMANINK_LICENSE [${QUIEN}]: desconocido (no se pudo comprobar; se continúa con normalidad)"
    ;;
  *)
    echo "HUMANINK_LICENSE [${QUIEN}]: $ESTADO"
    echo "HUMANINK_GATE: $(hi_mensaje "$ESTADO")"
    ;;
esac

# ── Y si va atrasado, se le dice ────────────────────────────────────────────────────────────────
# Va DESPUÉS del veredicto de licencia y es independiente de él: alguien sin activar también
# merece saber que su copia es vieja, y de hecho es el caso más probable —el fallo que le impide
# activar puede estar corregido en la versión que no tiene—. Envuelto para que un fallo aquí no
# arrastre al portero: esto es un aviso, no una puerta.
{
  LOCAL="$(hi_version_local 2>/dev/null || true)"
  ULTIMA="$(hi_ultima_plugin 2>/dev/null || true)"
  if [ -n "${LOCAL:-}" ] && [ -n "${ULTIMA:-}" ] && hi_atrasado "$LOCAL" "$ULTIMA"; then
    echo "HUMANINK_VERSION: instalada=$LOCAL publicada=$ULTIMA"
    echo "HUMANINK_AVISO: 🔄 Tienes HumanInk $LOCAL y ya está publicada la $ULTIMA. Claude no actualiza los plugins solo: entra en Plugins → Gestionar plugins y vuelve a instalarlo. Merece la pena — los arreglos de licencia y de los correctores van ahí."
  fi
} 2>/dev/null || true

# LA CLAVE NO SE ENSEÑA. Hoy, diagnosticando un bloqueo, el modelo leyó license.json y escribió la
# clave y el email del autor en la conversación, que es un sitio del que se copian capturas. El
# portero ya publica todo lo que hace falta para diagnosticar; el secreto, no.
echo "HUMANINK_PRIVADO: no muestres nunca la clave de licencia ni el contenido de ~/.humanink/license.json en la conversación; para diagnosticar basta con estas líneas."

exit 0
