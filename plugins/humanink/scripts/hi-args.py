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


m = re.search(r'(~?/[^\s"]+|~[^\s"]*)', raw)
folder = m.group(1) if m else (_proyecto_activo() or os.getcwd())
folder = os.path.expanduser(folder)

# --- goal: quoted text after an intent flag -----------------------------
# Covers the quoted argument across collaborators: --goal/--section
# (ghostwriter), --ask (coach), --genre/--amazon/--topic/--about (analyst).
goal = ""
g = re.search(r'--(?:goal|section|ask|genre|amazon|topic|about|on)\s+"([^"]+)"', raw)
if g:
    goal = g.group(1)

# --- all flags (e.g. --rewrite --report) --------------------------------
flags = " ".join(re.findall(r'--\w[\w-]*', raw))

# --- chapter: leftover after stripping flags, paths and quoted spans ----
chapter = raw
chapter = re.sub(r'--\w[\w-]*(\s+"[^"]*")?', " ", chapter)  # flags + their quoted value
chapter = re.sub(r'~?/[^\s"]+', " ", chapter)               # paths
chapter = re.sub(r'"[^"]*"', " ", chapter)                  # any remaining quotes
chapter = re.sub(r'\s+', " ", chapter).strip()

for k, v in (("MODE", mode), ("FOLDER", folder), ("CHAPTER", chapter),
             ("GOAL", goal), ("FLAGS", flags)):
    print(f"{k}={shlex.quote(v)}")
