---
name: comparar
description: "Comparador de versiones — el antes y el después de un manuscrito a lo largo de sus versiones numeradas. Mide qué cambió de verdad entre dos versiones (palabras, capítulos, párrafos, cortes de escena, longitud de frase, porcentaje de diálogo, adverbios) y dónde, listando los pasajes añadidos, cortados y reescritos. Produce un informe en Word con la tabla de evolución y, sobre una serie entera, el historial versión a versión. Úsalo cuando el autor pregunte qué cambió entre dos versiones, cuánto ha crecido el libro, qué hizo realmente una pasada, o quiera el registro de la reescritura."
allowed-tools: Bash, Read, Write, mcp__plugin_humanink_awap__awap_log_telemetry
argument-hint: "<version-nueva.docx> [version-anterior.docx] [--serie] [--informe]"
model: sonnet
effort: low
context: fork
background: false
---

<!-- AI-TRANSPARENCY-50-1 -->
> **Primera respuesta — transparencia de IA (Reglamento europeo de IA, art. 50(1)).** Abre tu primerísima respuesta en este comando con esta línea EXACTA, en español, y continúa normalmente:
>
> ℹ️ Estás colaborando con una IA. Este colaborador de HumanInk (v1.9.7-club) funciona sobre Claude, de Anthropic — te asiste, pero el autor eres tú y tú decides. (Reglamento (UE) 2024/1689, art. 50)

<!-- HI-GATE -->
> **Licencia.** Antes de nada, busca en tu contexto la línea `HUMANINK_LICENSE:` que deja el arranque
> de sesión. Si dice `valid`, sigue con normalidad y **no menciones nada de esto**.
>
> Si dice otra cosa —`missing`, `expired`, `tier_no_valido`…—, **no ejecutes el trabajo**: responde
> únicamente con el texto de la línea `HUMANINK_GATE:` y para ahí. No resumas ni improvises una
> versión propia del mensaje: está redactado para que el autor sepa qué hacer.
>
> Si la línea `HUMANINK_LICENSE:` **no aparece**, comprueba en disco y sigue si no puedes:
>
> ```bash
> cat "$HOME/.humanink/license-state" 2>/dev/null || echo desconocido
> ```
>
> `valid` o `desconocido` → adelante. Ante la duda se trabaja: un fallo nuestro no puede dejar a un
> autor sin su herramienta de escribir.

# Comparador de builds

## Qué es

El antes y el después, con números medidos y pasajes concretos. Un autor que lleva treinta
versiones no recuerda qué hizo en la doce, y "he ampliado el libro" no es un dato: +13.311
palabras y +104 cortes de escena sí lo son.

Dos modos:

- **Par** (por defecto): dos builds concretos. Qué cambió y dónde.
- **Serie** (`--serie`): toda la cadena de builds del proyecto, build a build. Es el registro de
  la reescritura completa.

El usuario ha indicado: $ARGUMENTS

## 1. Medir y localizar — un bloque, un turno

```bash
[ -z "${ARGUMENTS:-}" ] && ARGUMENTS="$(cat /tmp/humanink/args 2>/dev/null)"
ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../.." 2>/dev/null && pwd)}"; [ -d "$ROOT/scripts" ] || ROOT="$HOME/.humanink"
eval "$(python3 "$ROOT/scripts/hi-args.py" "$ARGUMENTS")"
mkdir -p /tmp/humanink && printf '%s' "$ARGUMENTS" > /tmp/humanink/args
# Encabezado: en qué proyecto estás. Va AQUÍ y no en un bloque propio porque cada bloque ```bash
# cuesta un turno del modelo sobre todo el contexto — colgado de éste sale gratis.
_HI="${CLAUDE_PLUGIN_ROOT:-$HOME/.humanink}"; [ -d "$_HI/scripts" ] || _HI="$HOME/.humanink"
python3 "$_HI/scripts/hi-cabecera.py" 2>/dev/null || true

if echo "$FLAGS" | grep -qi -- "--serie"; then
  python3 "$ROOT/scripts/ooxml/comparar.py" --serie "$FOLDER"
else
  python3 "$ROOT/scripts/ooxml/comparar.py" $ARGUMENTS
fi
```

El script mide; tú interpretas. **No recalcules a mano ninguna cifra que él ya dé** — sus números
salen del XML resolviendo el control de cambios, y son los que hay que citar.

## 2. Leer lo que significan los números

No basta con listar deltas. Cada magnitud dice algo del oficio:

| Si sube… | Suele significar |
|---|---|
| Palabras sin subir párrafos | Los párrafos existentes se han ensanchado: más subtexto o más paja |
| Párrafos sin subir palabras | Se ha troceado: mejor ritmo, o fragmentación |
| Cortes de escena | El libro ha ganado señalización: el lector se orienta |
| Frase media | Prosa más reflexiva; si sube mucho, riesgo de densidad |
| % de diálogo | Más escena y menos resumen (o al revés si baja) |
| Adverbios en -mente por mil | Suele ser mala señal: el verbo exacto pesa menos |

Y una regla: **el percentil 90 de longitud de párrafo bajando es casi siempre buena noticia** —
significa que los párrafos-ladrillo se han partido.

## 3. Los pasajes

El script imprime los tramos añadidos, cortados y reescritos con su posición. Selecciona los
**más significativos, no todos**: si hay 34 escenas nuevas, agrúpalas y nombra las cinco mayores.
Cita las primeras palabras de cada una para que el autor las reconozca.

## 4. Informe (si el autor lo pide, o con `--informe`)

Escribe el markdown y conviértelo:

```bash
[ -z "${ARGUMENTS:-}" ] && ARGUMENTS="$(cat /tmp/humanink/args 2>/dev/null)"
ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../.." 2>/dev/null && pwd)}"; [ -d "$ROOT/scripts" ] || ROOT="$HOME/.humanink"
python3 ~/.awos/md2docx.py "$OUT_MD" "$OUT_DOCX" "Comparativa de builds"
rm -f "$OUT_MD"
bash "$ROOT/scripts/hi-log.sh" awos-comparador "Comparador de builds" "$(dirname "$OUT_DOCX")" "${MODE:---par}" "${_AWOS_TOK_IN:-0}" "${_AWOS_TOK_OUT:-0}"
```

Estructura del informe:

```
# Comparativa — [libro], build [A] → build [B]
## Resultado en una tabla   (la magnitud · antes · después · diferencia)
## Qué se hizo              (los pasajes, agrupados por tipo)
## Lectura de los números   (qué significan para el libro)
## Fase por fase            (sólo en modo --serie)
```

## Subir la telemetría (solo en `--serie`)

Al terminar una serie, el script deja `telemetria/v*.json` y `telemetria/global.json` en la carpeta.
Esos ficheros son lo que alimenta el panel — pero el panel de Cowork corre en la nube y **no tiene
acceso al disco del autor**, así que hasta que no se suben, todo lo medido es invisible desde ahí.

Léelos y pásalos por MCP:

```
mcp__plugin_humanink_awap__awap_log_telemetry({
  versions: [ …contenido de cada telemetria/v<N>.json… ],
  global:   { …contenido de telemetria/global.json… }
})
```

Si el conector AWAP no está disponible, no pares ni des un error: el informe ya está hecho y los
ficheros siguen en su carpeta. Di en una línea que la telemetría no se ha subido y sigue.

**Viajan métricas y posiciones, nunca texto.** El servidor recorta las primeras palabras de cada
pasaje y reduce los nombres de fichero a su marca de versión, porque llevan las siglas del libro.

## Reglas

- Cifras del script, siempre. Si una cifra no la ha dado el script, di de dónde sale.
- Compara **estados equivalentes**: si un build tiene cambios sin aceptar, dilo y aclara si
  comparas aceptando o rechazando. Mezclarlos da diferencias falsas.
- Nunca presentes como hallazgo tuyo una decisión deliberada del autor.
- Si los dos builds son idénticos, dilo en una línea y no adornes.
