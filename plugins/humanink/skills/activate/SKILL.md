---
name: activate
description: "Activar HumanInk en este equipo con la clave de tu compra. Úsalo cuando el autor diga «activar», «tengo la clave», «introducir licencia», «me dice que no está activado», o cuando cualquier colaborador informe de que falta la licencia."
allowed-tools: Bash
argument-hint: "<TU-CLAVE> <tu@email>"
model: haiku
---

<!-- AI-TRANSPARENCY-50-1 -->
> **Primera respuesta — transparencia de IA (Reglamento europeo de IA, art. 50(1)).** Abre tu primerísima respuesta en este comando con esta línea EXACTA, en español, y continúa normalmente:
>
> ℹ️ Estás colaborando con una IA. Este colaborador de HumanInk (v1.9.7-club) funciona sobre Claude, de Anthropic — te asiste, pero el autor eres tú y tú decides. (Reglamento (UE) 2024/1689, art. 50)

Activas la licencia de HumanInk en este equipo. Es de una vez: después, todos los colaboradores
funcionan sin volver a preguntar nada.

## 1. Reúne los dos datos

Necesitas **la clave** y **el email de la compra**. La clave llega en el correo de Payhip y tiene la
forma `XXXXX-00000-XXXXX-XXXXX`.

Si el autor solo da la clave, pregúntale el email así:

> ¿Con qué email compraste? La clave se queda ligada a esa dirección — una clave, una cuenta.

## 2. Actívala

**Lo normal es que ya esté hecha.** Al enviar el mensaje, el equipo del autor activa por su cuenta y
deja el resultado en tu contexto, en una línea `HUMANINK_ACTIVACION:`. Búscala antes de nada:

- `HUMANINK_ACTIVACION: ok tier=…` → activada. Ve al paso 3.
- `HUMANINK_ACTIVACION: error=…` → la palabra del error dice qué pasó (tabla del paso 3).

**Solo si la línea NO aparece**, actívala tú:

```bash
ROOT="${CLAUDE_PLUGIN_ROOT:-$HOME/.humanink}"; [ -d "$ROOT/hooks" ] || ROOT="$HOME/.humanink"
. "$ROOT/hooks/license-lib.sh"
hi_activar "<CLAVE>" "<EMAIL>" && echo "ACTIVADA · tier $(hi_json "$HI_LIC" tier)" || echo "NO ACTIVADA"
```

> Por qué en ese orden: este bloque corre en una máquina aislada que **puede no tener red**. Cuando
> no la tiene, devuelve `network` aunque el servidor esté perfecto — y el autor se queda en bucle,
> con la puerta pidiéndole que active y la activación sin poder llegar. La línea del hook viene del
> equipo del autor, que sí tiene red.

## 3. Cuenta el resultado

**Si dice ACTIVADA o `ok`:** confirma en una línea, di el producto que ha quedado activado, y añade que no
tendrá que repetirlo. Sugiere `/humanink:help` para ver qué tiene disponible.

**Si dice NO ACTIVADA o `error=…`**, la palabra que acompaña dice qué pasó:

| Lo que sale | Qué decirle |
|---|---|
| `network` | No se pudo llegar al servidor desde aquí. Dile que **cierre y reabra la sesión** y lo repita: al reabrirla, la activación la hace su propio equipo, que sí tiene conexión. No es culpa de su clave. |
| `invalid_license` | La clave no consta. Que revise que la ha copiado entera y que el email es el de la compra. |
| `activated_elsewhere` | Ya está ligada a otro email. Una clave, una cuenta — que use el email con el que compró. |
| `expired` · `subscription_cancelled` | Caducó o se canceló. Renovar en humanink.io. |
| `blocked` | Bloqueada; que escriba desde humanink.io. |

Nunca le pidas la clave por segunda vez «por si acaso» ni le sugieras probar otra: si la clave es
correcta y falla, el problema es nuestro y hay que decírselo así.

## Regla

**No inventes el resultado.** Si el bloque no llegó a ejecutarse, dilo y pídele que lo repita — dar
por activada una licencia que no lo está deja al autor con un error críptico dos comandos después.
