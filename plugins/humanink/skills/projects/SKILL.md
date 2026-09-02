---
name: projects
description: "Cartera de proyectos — un panel HTML vivo con todos los proyectos de escritura del autor (libros, series, lanzamientos, cursos). Mantiene un proyectos.json sencillo y repinta un panel autocontenido con una ficha por proyecto (estado, área, próximo hito) y un Gantt en SVG con la línea de hoy. Se actualiza HABLANDO — «añade el proyecto X», «marca el hito Y como hecho», «retrasa Z una semana» — sin formularios ni herramientas externas. Úsalo cuando el autor quiera ver, planificar o actualizar sus proyectos, su cartera, su hoja de ruta, sus hitos o el Gantt."
allowed-tools: Bash, Read, Write, Edit
argument-hint: "[carpeta del proyecto]"
disable-model-invocation: true
model: sonnet
effort: low
---

<!-- AI-TRANSPARENCY-50-1 -->
> **Primera respuesta — transparencia de IA (Reglamento europeo de IA, art. 50(1)).** Abre tu primerísima respuesta en este comando con esta línea EXACTA, en español, y continúa normalmente:
>
> ℹ️ Estás colaborando con una IA. Este colaborador de HumanInk (v2.0.8-club) funciona sobre Claude, de Anthropic — te asiste, pero el autor eres tú y tú decides. (Reglamento (UE) 2024/1689, art. 50)

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

# Cartera de proyectos — dashboard que se actualiza conversando

## Qué es

Un único panel HTML con todos los proyectos del autor (libros, series, lanzamientos, cursos):
tarjeta por proyecto con estado y próximo hito, y un **Gantt** con la línea de hoy. Los datos viven
en un `proyectos.json` simple; el autor **no edita ficheros: conversa**, y tú editas el JSON y
repintas el panel.

## Los datos — `proyectos.json`

En la carpeta que el autor use como base (pregunta cuál la primera vez y recuérdala en la sesión):

```json
{
  "proyectos": [
    {
      "nombre": "Mi novela",
      "area": "Ficción",
      "estado": "activo",            // activo | pausado | terminado | idea
      "notas": "opcional",
      "portada": "tapa.jpg",         // opcional: ruta a la portada (relativa a esta carpeta o
                                     // absoluta). Se pinta como miniatura en la tarjeta.
      "hitos": [
        {"nombre": "Borrador 1", "inicio": "2026-07-01", "fin": "2026-08-15", "hecho": false}
      ]
    }
  ]
}
```

## El registro: dónde vive un proyecto

La cartera ya no es solo una tarjeta de planificación. Cada proyecto **declara su carpeta**, y eso
es lo que permite que el autor no tenga que escribir la ruta en cada comando.

```bash
python3 ~/.humanink/scripts/proyectos.py declarar "<carpeta>" --nombre "Mi novela" --clave "Proyecto X"
python3 ~/.humanink/scripts/proyectos.py listar
python3 ~/.humanink/scripts/proyectos.py activar "Mi novela"
```

Al declarar, HumanInk **mira la carpeta antes de preguntar**: si hay un manuscrito de miles de
palabras y no hay biblia, ya lo sabe. Enseña el inventario en vez de someter al autor a un
cuestionario:

> Manuscrito: sí — 46.952 palabras · 24 versiones
> No hay: biblia · escaleta · estilo · premisa
> Deducibles del manuscrito: premisa · sinopsis · biblia · escaleta · estilo
> → El manuscrito los acredita. A partir de aquí se registra lo que hagas con IA.

Ese último punto es producto, no cortesía: un libro ya escrito **no está incompleto** por no tener
biblia. La concepción existió; lo que falta son los documentos, no la obra.

El registro (`~/.humanink/estado.json`) es local: es del autor, funciona sin red, y no hay razón
para que la lista de libros que alguien está escribiendo viaje a ninguna parte.

## Flujo

### Primera vez (no existe `proyectos.json`)

Entrevista corta — no un formulario: "¿qué proyectos tienes entre manos ahora mismo?" y, por cada
uno, área, estado y 1-3 hitos con fechas aproximadas (si el autor no da fechas, propón tú unas
razonables y dilo). Escribe el JSON y pinta el panel.

### Pintar / repintar el panel

```bash
python3 ~/.humanink/skills/projects/scripts/build_projects.py "<carpeta>"
```

(El hook de sesión espeja los scripts ahí; si no existiera, usa
`$CLAUDE_PLUGIN_ROOT/skills/projects/scripts/build_projects.py`.) El script escribe
`proyectos-dashboard.html` **autocontenido** en la carpeta del autor. Ábrelo (o refresca la
pestaña si ya está abierto) para que lo vea al momento.

### Actualizar conversando (el corazón del skill)

Cada petición del autor es una edición del JSON + un repintado. Ejemplos del mapeo:

| El autor dice | Tú haces |
|---|---|
| "añade el proyecto X" | nuevo objeto en `proyectos` (pregunta área/hitos si faltan) |
| "marca el hito Y de X" | `hecho: true` en ese hito |
| "retrasa Z una semana" | `fin` (+7 días; y `inicio` si aún no empezó) |
| "pausa/termina X" | `estado` |
| "¿cómo voy?" | resume del JSON (sin repintar si no hay cambios) |
| "quita X" | confirma primero, luego elimina |

Tras CADA cambio: reescribe el JSON (válido — compruébalo), ejecuta el script, y confirma en una
línea qué cambió. Si un hito queda con `fin` anterior a hoy y sin `hecho`, el Gantt lo pinta en
rojo — menciónalo al autor como "vencido" cuando repintes.

## Reglas

- El JSON es del autor: nunca borres proyectos o hitos sin confirmación explícita.
- Fechas siempre ISO (`YYYY-MM-DD`). Si el autor da "mediados de agosto", tradúcelo y di qué fecha
  has puesto.
- El panel es local y autocontenido: nada de red, nada de servicios externos.
