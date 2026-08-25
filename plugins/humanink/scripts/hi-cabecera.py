#!/usr/bin/env python3
"""Una línea que sitúa al autor: en qué proyecto está y cómo va.

    python3 scripts/hi-cabecera.py [carpeta]

Se imprime al principio de cada colaborador. Dónde va importa tanto como qué dice: se cuelga del
bloque bash que TODOS los skills ejecutan ya (el que guarda `$ARGUMENTS` en /tmp/humanink/args), y
no de un bloque propio. Cada bloque ```bash cuesta un turno del modelo sobre todo el contexto, y el
coste es contexto × turnos: un encabezado con bloque propio se pagaría en cada invocación de cada
colaborador, todos los días. Así sale gratis.

Nunca falla ni entorpece: si no hay proyecto declarado, no imprime nada y el colaborador sigue como
si no existiera. Un encabezado que rompe un comando es peor que no tener encabezado.
"""
import json
import os
import sys

ESTADO = os.path.expanduser("~/.humanink/estado.json")


def leer_json(ruta):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def miles(n):
    try:
        return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return None


def proyecto_de(carpeta):
    """El proyecto de ESTA carpeta. Sin carpeta, el activo.

    Si el autor nombra una carpeta que no está declarada, NO se cae al proyecto activo: enseñar la
    cabecera de otro libro sobre un comando que se ejecuta en otro sitio es peor que no enseñar
    nada. Un encabezado sirve para situar; si sitúa mal, engaña.
    """
    d = leer_json(ESTADO) or {}
    proyectos = d.get("proyectos") or []
    if carpeta:
        real = os.path.realpath(os.path.expanduser(carpeta))
        return next((p for p in proyectos if os.path.realpath(p.get("ruta", "")) == real), None)
    act = d.get("activo") or {}
    return next((p for p in proyectos if p.get("id") == act.get("id")), None)


def pasada_pendiente(ruta):
    """Qué toca según el plan de reescritura, si lo hay."""
    plan = leer_json(os.path.join(ruta, "plan.json"))
    if not isinstance(plan, dict):
        return None
    pasadas = plan.get("pasadas") or plan.get("passes") or []
    for i, p in enumerate(pasadas, 1):
        if isinstance(p, dict) and p.get("estado") not in ("hecha", "done", "completada"):
            return f"pasada {i}/{len(pasadas)}: {p.get('nombre') or p.get('name') or '—'}"
    return f"plan completo ({len(pasadas)} pasadas)" if pasadas else None


def ultima_version(ruta):
    """La última versión medida, del propio registro de telemetría."""
    g = leer_json(os.path.join(ruta, "telemetria", "global.json"))
    if isinstance(g, dict) and g.get("versiones"):
        return f"{g['versiones']} versiones medidas"
    return None


def cabecera(carpeta=None):
    p = proyecto_de(carpeta)
    if not p:
        return ""
    ruta = p.get("ruta", "")
    # El nombre en clave manda sobre el título: es lo que se usa mientras se escribe.
    nombre = p.get("clave") or p.get("nombre") or os.path.basename(ruta)
    partes = []
    pal = miles(p.get("palabras"))
    if pal:
        partes.append(f"{pal} palabras")
    medidas = ultima_version(ruta)
    if medidas:
        partes.append(medidas)          # «24 versiones medidas» ya dice cuántas hay
    elif (p.get("versiones") or 0) > 1:
        partes.append(f"{p['versiones']} versiones")
    pasada = pasada_pendiente(ruta)
    if pasada:
        partes.append(pasada)
    if p.get("tipo") == "manuscript_first" and p.get("deducibles"):
        partes.append("manuscrito preexistente")
    return f"▸ {nombre}" + (" · " + " · ".join(partes) if partes else "")


if __name__ == "__main__":
    try:
        linea = cabecera(sys.argv[1] if len(sys.argv) > 1 else None)
        if linea:
            print(linea)
    except Exception:
        pass   # jamás entorpecer al colaborador
