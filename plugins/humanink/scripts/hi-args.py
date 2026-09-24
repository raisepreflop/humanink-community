#!/usr/bin/env python3
"""HumanInk shared arg parser.

Usage:  eval "$(python3 hi-args.py "$ARGUMENTS")"
Emits shell-quoted assignments: MODE, FOLDER, CHAPTER, GOAL, FLAGS

Replaces the per-skill arg-parsing bash block and removes the macOS
`grep -oP` dependency (BSD grep has no -P), which previously broke
--goal / --section extraction on macOS.
"""
import json
import sys
import os
import re
import shlex

raw = sys.argv[1] if len(sys.argv) > 1 else ""

# --- mode ---------------------------------------------------------------
low = raw.lower()
mode = "nuevo"
if "--rewrite" in low:
    mode = "reescribir"
elif "--section" in low:
    mode = "seccion"
elif "--insert" in low:
    mode = "insertar"

# --- project folder ------------------------------------------------------
# Orden: (1) una ruta escrita en el comando, (2) el PROYECTO ACTIVO, (3) el directorio actual.
#
# El (2) es la novedad y la razón de ser de esto: hasta ahora el autor tenía que escribir la ruta
# del proyecto en CADA comando —21 de 31 argument-hint empiezan por «[ruta del proyecto]»— porque el
# único «activo» que existía vivía dentro del proceso del servidor MCP, se perdía al reiniciarlo, y
# los skills de Bash ni lo veían. El fichero de estado lo leen las dos capas.
def _proyecto_activo():
    try:
        with open(os.path.expanduser("~/.humanink/estado.json"), encoding="utf-8") as f:
            d = json.load(f)
        ruta = (d.get("activo") or {}).get("ruta")
        return ruta if ruta and os.path.isdir(os.path.expanduser(ruta)) else None
    except Exception:
        return None


# LA RUTA (24-sep-2026). Antes era «hasta el primer espacio», y en castellano casi toda carpeta lleva
# espacios: «/Users/ana/Mi novela/cap-03.docx» se quedaba en «/Users/ana/Mi». Y cualquier barra
# suelta («3/4», «a/b») contaba como ruta. Ahora, por este orden:
#   1. una ruta entre comillas ("…", '…' o «…»);
#   2. sin comillas, la ruta MÁS LARGA que existe en el disco, añadiendo palabra a palabra;
#   3. sin comillas y sin disco a la vista (la VM de Cowork no siempre lo ve), hasta la primera
#      extensión de documento (.docx, .md, .txt, .pdf, .odt), aunque haya espacios en medio;
#   4. si no, el primer tramo sin espacios, como antes.
# Una ruta tiene que empezar por «/» o «~/» al principio o tras un espacio: «3/4» no es una ruta.
EXT = r'\.(?:docx|md|txt|pdf|odt|rtf)'

def _ruta_escrita(texto):
    # La PRIMERA ruta del texto, venga entre comillas o no: es la del manuscrito o el proyecto. Una
    # ruta que va detrás de un flag («--style "/x/estilo.docx"») es el valor de ese flag, no el
    # proyecto (equipo rojo, 24-sep: el reader leía la guía de estilo como si fuera el manuscrito).
    cands = []
    for q in re.finditer(r'(?:^|\s)["«]((?:~|/)[^"»\n]*)["»]', texto):
        if not re.search(r'--[\w-]+\s*$', texto[:q.start(1) - 1]):
            cands.append((q.start(1), q.group(1).strip()))
    for ini in re.finditer(r'(?:^|\s)((?:~/|/)\S)', texto):
        if re.search(r'--[\w-]+\s*$', texto[:ini.start(1)]):
            continue
        resto = texto[ini.start(1):]
        palabras = resto.split(" ")
        hallada = None
        for n in range(len(palabras), 0, -1):
            cand = " ".join(palabras[:n]).rstrip(" ,;:)")
            if os.path.exists(os.path.expanduser(cand)):
                hallada = cand
                break
        if not hallada:
            e = re.match(r'(.*?' + EXT + r')(?=[\s,;:)]|$)', resto, flags=re.I)
            hallada = e.group(1) if e and "--" not in e.group(1) else palabras[0].rstrip(",;:)")
        cands.append((ini.start(1), hallada))
        break
    return min(cands)[1] if cands else None

ruta = _ruta_escrita(raw)
folder = ruta if ruta else (_proyecto_activo() or os.getcwd())
folder = os.path.expanduser(folder)

# --- goal: quoted text after an intent flag -----------------------------
# Covers the quoted argument across collaborators: --goal/--section
# (ghostwriter), --ask (coach), --genre/--amazon/--topic/--about (analyst).
goal = ""
g = re.search(r'--(?:goal|section|ask|genre|amazon|topic|about|on)\s+"([^"]+)"', raw)
if g:
    goal = g.group(1)

# --- base: la versión anterior para /verificar --base (antes se perdía: FLAGS solo lleva nombres) --
b = re.search(r'--base\s+(?:"([^"]+)"|«([^»]+)»|(\S+(?:\s\S+)*?' + EXT + r')|(\S+))', raw, flags=re.I)
base = os.path.expanduser(next(x for x in b.groups() if x)) if b else ""

# --- all flags (e.g. --rewrite --report) --------------------------------
flags = " ".join(re.findall(r'--\w[\w-]*', raw))

# --- chapter: leftover after stripping flags, paths and quoted spans ----
chapter = raw
chapter = re.sub(r'--\w[\w-]*(\s+"[^"]*")?', " ", chapter)  # flags + their quoted value
if ruta:
    chapter = chapter.replace(ruta, " ")                        # la ruta, entera, con sus espacios
chapter = re.sub(r'«[^»]*»', " ", chapter)                     # comillas españolas
chapter = re.sub(r'(?:^|(?<=\s))~?/[^\s"]+', " ", chapter)      # rutas sueltas que queden (valores de flags)
chapter = re.sub(r'"[^"]*"', " ", chapter)                  # any remaining quotes
chapter = re.sub(r'\s+', " ", chapter).strip()

for k, v in (("MODE", mode), ("FOLDER", folder), ("CHAPTER", chapter),
             ("GOAL", goal), ("FLAGS", flags), ("BASE", base)):
    print(f"{k}={shlex.quote(v)}")
