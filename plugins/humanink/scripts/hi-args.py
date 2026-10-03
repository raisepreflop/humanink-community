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

# La salida, siempre en UTF-8: Windows la escribe en cp1252 y un «→» tumba el script (ver scripts/ooxml/_utf8.py).
for _flujo in (sys.stdin, sys.stdout, sys.stderr):
    getattr(_flujo, "reconfigure", lambda **_: None)(encoding="utf-8", errors="backslashreplace")

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
    # Cada comilla se cierra con LA SUYA (2.3.3): «"/x/Mi novela — «Ángel» (año 2026)"» se cortaba en el
    # » del nombre, y la skill contestaba que no veía la carpeta. Con comillas españolas, que no se
    # distinguen de las del propio nombre, vale el cierre que deja una ruta que EXISTE (el más largo);
    # si ninguna existe, el primero, como antes.
    # Y las tipográficas “…” y ‘…’, que el Mac pone solo al escribir (UAT, 3-oct-2026).
    for q in re.finditer(r"""(?:^|\s)(?:"((?:~|/)[^"\n]*)"|'((?:~|/)[^'\n]*)'|“((?:~|/)[^”\n]*)”|‘((?:~|/)[^’\n]*)’)""", texto):
        g = next(i for i in range(1, 5) if q.group(i) is not None)
        if not re.search(r'--[\w-]+\s*$', texto[:q.start(g) - 1]):
            cands.append((q.start(g), q.group(g).strip()))
    # El resto de la línea se mira SIN consumirlo (lookahead): si este « es el valor de una opción y se
    # salta, la ruta del libro que viene detrás entre « » tiene que seguir a la vista (equipo rojo, 3-oct).
    for q in re.finditer(r'(?:^|\s)«(?=((?:~|/)[^\n]*))', texto):
        if re.search(r'--[\w-]+\s*$', texto[:q.start(1) - 1]):
            continue
        cierres = [m.start() for m in re.finditer(r'»(?=[\s,;:.)]|$)', q.group(1))] or \
                  [m.start() for m in re.finditer('»', q.group(1))]
        if not cierres:
            continue
        rutas = [q.group(1)[:c].strip() for c in cierres]
        vivas = [r for r in rutas if os.path.exists(os.path.expanduser(r))]
        # Sin el disco a la vista no se puede preguntar cuál existe: vale el primer cierre que deja
        # emparejadas las comillas de DENTRO («…— «Ángel» (año 2026)» tiene una abierta y una cerrada).
        parejas = [r for r in rutas if r.count("«") == r.count("»")]
        cands.append((q.start(1), vivas[-1] if vivas else (parejas[0] if parejas else rutas[0])))
        break
    for ini in re.finditer(r'(?:^|\s)((?:~/|/)\S)', texto):
        if re.search(r'--[\w-]+\s*$', texto[:ini.start(1)]):
            continue
        resto = texto[ini.start(1):]
        palabras = resto.split(" ")
        hallada = None
        for n in range(len(palabras), 0, -1):
            # Primero tal cual, con su paréntesis: «Mi novela (2)» es una carpeta, no «Mi novela» seguida
            # de un paréntesis de cierre (UAT, 2-oct-2026: el registro se abría en otro libro).
            for cand in (" ".join(palabras[:n]).rstrip(" ,;:"), " ".join(palabras[:n]).rstrip(" ,;:)")):
                if os.path.exists(os.path.expanduser(cand)):
                    hallada = cand
                    break
            if hallada:
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
# El valor entre comillas de una opción: rectas, “tipográficas” (las pone el Mac solo), ‘simples’ o
# «españolas», que pueden llevar otras « » dentro (3-oct-2026: con “…” el objetivo se perdía).
VALOR = r'(?:"([^"]+)"|“([^”]+)”|‘([^’]+)’|«((?:[^«»\n]|«[^«»\n]*»)+)»)'
QUITAR_VALOR = r'(?:"[^"]*"|“[^”]*”|‘[^’]*’|«(?:[^«»\n]|«[^«»\n]*»)*»)'
primero = lambda m: next((x for x in m.groups() if x), "") if m else ""

g = re.search(r'--(?:goal|section|ask|amazon|topic|about|on)\s+' + VALOR, raw)
if g:
    goal = primero(g)

# --- genre: su propia variable (27-sep). Hasta hoy iba a GOAL, y el coach o el fantasma lo tomaban por su
# pregunta u objetivo; y sin comillas, o con «», se perdía. Con él se elige la lente de estructura.
gm = re.search(r'--(?:genre|genero|género)\s+(?:' + VALOR + r'|(\S+))', raw, flags=re.I)
genre = primero(gm)

# --- base: la versión anterior para /verificar --base (antes se perdía: FLAGS solo lleva nombres) --
b = re.search(r'--base\s+(?:' + VALOR + r'|(\S+(?:\s\S+)*?' + EXT + r')|(\S+))', raw, flags=re.I)
base = os.path.expanduser(primero(b)) if b else ""

# --- all flags (e.g. --rewrite --report) --------------------------------
flags = " ".join(re.findall(r'--\w[\w-]*', raw))

# --- chapter: leftover after stripping flags, paths and quoted spans ----
chapter = raw
chapter = re.sub(r'--(?:genre|genero|género)\s+(?:' + QUITAR_VALOR + r'|\S+)', " ", chapter, flags=re.I)  # el género, con su valor
chapter = re.sub(r'--\w[\w-]*(\s+' + QUITAR_VALOR + r')?', " ", chapter)  # flags + their quoted value
if ruta:
    chapter = chapter.replace(ruta, " ")                        # la ruta, entera, con sus espacios
    chapter = re.sub(r'(^|\s)["\'“‘«]\s*["\'”’»](?=\s|$)', " ", chapter)   # las comillas que la rodeaban
chapter = re.sub(r'«[^»]*»', " ", chapter)                     # comillas españolas
chapter = re.sub(r'(?:^|(?<=\s))~?/[^\s"]+', " ", chapter)      # rutas sueltas que queden (valores de flags)
chapter = re.sub(r'"[^"]*"|“[^”]*”', " ", chapter)       # any remaining quotes
chapter = re.sub(r'\s+', " ", chapter).strip()

for k, v in (("MODE", mode), ("FOLDER", folder), ("CHAPTER", chapter),
             ("GOAL", goal), ("GENRE", genre), ("FLAGS", flags), ("BASE", base)):
    print(f"{k}={shlex.quote(v)}")


# --- AWAP local (1-oct-2026) ---------------------------------------------
# Si la carpeta del libro lleva registro de autoría (`.awap/local/project.json`, lo crea
# `/humanink:auditor --init`), aquí EMPIEZA a trabajar un colaborador: lo que haya cambiado desde la
# última vez se anota como del autor, y desde ahora lo que cambie es del colaborador hasta que
# `hi-log.sh` lo cierre. Esto se evalúa con `eval`, así que no escribe nada en la salida; y no puede
# romper a ningún colaborador: sin registro no hace nada, y si falla, calla.
def _con_registro(ruta):
    p = os.path.abspath(ruta)
    if os.path.isfile(p):
        p = os.path.dirname(p)
    for _ in range(8):
        if os.path.isfile(os.path.join(p, ".awap", "local", "project.json")):
            return True
        if os.path.dirname(p) == p:
            break
        p = os.path.dirname(p)
    return False


try:
    if not os.environ.get("HI_SIN_AWAP") and _con_registro(folder):
        import subprocess
        subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "awap_local.py"),
                        "inicio", folder], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=180)
except Exception:
    pass
