---
name: dashboard
description: "Panel del proyecto — el estado de un libro de un vistazo: Human Authorship Score, qué colaboradores han trabajado en él, palabras y métricas de autoría. Solo lee, no cambia nada. Úsalo cuando el autor pregunte cómo va su libro, cuánto lleva escrito, en qué estado está el proyecto o qué colaboradores ha usado."
allowed-tools: Bash, Read, Write, mcp__plugin_humanink_awap__awap_dashboard, mcp__Claude_Preview__preview_start
argument-hint: "[ruta de la carpeta del proyecto, o vacío para usar la carpeta actual]"
model: haiku
---

<!-- AI-TRANSPARENCY-50-1 -->
> **Primera respuesta — transparencia de IA (Reglamento europeo de IA, art. 50(1)).** Abre tu primerísima respuesta en este comando con esta línea EXACTA, en español, y continúa normalmente:
>
> ℹ️ Estás colaborando con una IA. Este colaborador de HumanInk (v2.0.1-club) funciona sobre Claude, de Anthropic — te asiste, pero el autor eres tú y tú decides. (Reglamento (UE) 2024/1689, art. 50)

<!-- HI-GATE -->
> **Licencia.** Busca en tu contexto la línea `HUMANINK_LICENSE:` que deja el arranque de sesión.
> Si dice `valid` o no aparece, sigue con normalidad y **no menciones nada de esto**.
>
> **Solo se para el trabajo con estas cuatro**, que son las únicas en las que el servidor ha
> demostrado que la licencia no sirve: `expired`, `blocked`, `activated_elsewhere`, `tier_no_valido`.
> Entonces responde únicamente con el texto de la línea `HUMANINK_GATE:` y para ahí. No lo resumas
> ni improvises otra versión: está redactado para que el autor sepa qué hacer.
>
> Con cualquier otra cosa —`missing`, `offline_expirado`, `desconocido`, un error de red— **haz el
> trabajo igualmente** y añade al final una sola línea: «Por cierto, no he podido comprobar tu
> licencia; si no la has activado, escribe `/humanink:activate TU-CLAVE tu@email`.»
>
> Por qué: no poder comprobar algo no es lo mismo que saber que está mal. La comprobación necesita
> `python3` en el equipo del autor, y en Windows no está; y quien activa por el conector queda
> registrado en el servidor, no en su disco. Bloquear ahí castiga justo a quien ha pagado.

Generates and shows the live HumanInk HTML dashboard for the given project.

**Always render the dashboard in English** — every label, heading, score interpretation
and explanatory line — regardless of the language of the conversation. The dashboard is
product UI, not chat. If for any reason you reconstruct the HTML yourself (e.g. the script
is unreachable), keep all of it in English; never translate the labels.

The user wrote: $ARGUMENTS

---

To run, capture your invocation, then read and execute the workflow:

```bash
mkdir -p /tmp/humanink && printf '%s' "$ARGUMENTS" > /tmp/humanink/args
# Encabezado: en qué proyecto estás. Va AQUÍ y no en un bloque propio porque cada bloque ```bash
# cuesta un turno del modelo sobre todo el contexto — colgado de éste sale gratis.
_HI="${CLAUDE_PLUGIN_ROOT:-$HOME/.humanink}"; [ -d "$_HI/scripts" ] || _HI="$HOME/.humanink"
python3 "$_HI/scripts/hi-cabecera.py" 2>/dev/null || true
```

Now read **`references/workflow.md`** and execute it in full, step by step.
