#!/usr/bin/env python3
"""Inventario y cartera de proyectos.

Lo que se protege aquí, en una frase: que el autor **no tenga que escribir la ruta en cada comando**
y que HumanInk **mire la carpeta antes de preguntar**.

Antes de esto, la ruta del proyecto no se guardaba en ningún sitio persistente —ni en la cartera, ni
en la base, ni en el servidor MCP, que la perdía al reiniciarse— y los ficheros del proyecto no se
declaraban: se adivinaban con un barrido ciego del árbol.

    python3 scripts/test_proyectos.py
"""
import json
import os
import subprocess
import sys
import tempfile
import zipfile

AQUI = os.path.dirname(os.path.abspath(__file__))
FALLOS = []


def check(nombre, ok, extra=""):
    print(f"  {'✓' if ok else '✗'} {nombre}{'  ' + str(extra) if extra else ''}")
    if not ok:
        FALLOS.append(nombre)


def correr(script, *args, entorno=None):
    e = dict(os.environ, **(entorno or {}))
    r = subprocess.run([sys.executable, os.path.join(AQUI, script), *args],
                       capture_output=True, text=True, env=e)
    return r.stdout, r.returncode


def docx_falso(ruta, palabras):
    """Un .docx mínimo pero real: el inventario lo lee descomprimiéndolo."""
    texto = " ".join(["palabra"] * palabras)
    with zipfile.ZipFile(ruta, "w") as z:
        z.writestr("word/document.xml", f"<w:document><w:t>{texto}</w:t></w:document>")


print("Inventario\n")

with tempfile.TemporaryDirectory() as d:
    # Una novela terminada sin ningún documento de apoyo: EL CASO NORMAL.
    docx_falso(os.path.join(d, "Novela-v03.docx"), 50000)
    docx_falso(os.path.join(d, "Novela-v01.docx"), 40000)
    out, _ = correr("inventario.py", d, "--json")
    inv = json.loads(out)
    check("reconoce el manuscrito", inv["manuscrito"] is not None,
          inv["manuscrito"]["fichero"] if inv["manuscrito"] else "")
    check("elige la ÚLTIMA versión, no la más larga", inv["manuscrito"]["fichero"] == "Novela-v03.docx")
    check("cuenta las versiones", inv["versiones"] == 2, inv["versiones"])
    check("el tipo por defecto es 'traigo un manuscrito'", inv["tipo"] == "manuscript_first")
    check("dice qué falta", "biblia" in inv["faltan"])
    check("y qué acredita el manuscrito", "biblia" in inv["deducibles"] and "premisa" in inv["deducibles"])

with tempfile.TemporaryDirectory() as d:
    # Una carpeta con biblia pero sin novela: se empieza de cero.
    open(os.path.join(d, "biblia.md"), "w").write("# Biblia\n" + "x " * 500)
    out, _ = correr("inventario.py", d, "--json")
    inv = json.loads(out)
    check("sin manuscrito, tipo 'desde cero'", inv["tipo"] == "from_scratch")
    check("la biblia se reconoce", "biblia" in inv["documentos"])
    check("no deduce nada sin manuscrito", inv["deducibles"] == [])

with tempfile.TemporaryDirectory() as d:
    # Los ficheros que Word y macOS dejan por medio no son del autor.
    docx_falso(os.path.join(d, "~$Novela.docx"), 90000)
    docx_falso(os.path.join(d, "._Novela.docx"), 90000)
    out, _ = correr("inventario.py", d, "--json")
    check("ignora los temporales de Word y macOS", json.loads(out)["manuscrito"] is None)

with tempfile.TemporaryDirectory() as d:
    open(os.path.join(d, "nota.md"), "w").write("una nota corta")
    out, _ = correr("inventario.py", d, "--json")
    check("una nota corta no es un manuscrito", json.loads(out)["manuscrito"] is None)

out, code = correr("inventario.py", "/no/existe/nada")
check("una carpeta inexistente da error limpio", code == 1 and "No existe" in out)

print("\nCartera y proyecto activo\n")

with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
    ENT = {"HOME": home}
    docx_falso(os.path.join(a, "Novela-v02.docx"), 50000)

    correr("proyectos.py", "declarar", a, "--nombre", "Uno", entorno=ENT)
    correr("proyectos.py", "declarar", b, "--nombre", "Dos", entorno=ENT)
    out, _ = correr("proyectos.py", "listar", "--json", entorno=ENT)
    d = json.loads(out)
    check("guarda los dos proyectos", len(d["proyectos"]) == 2, len(d["proyectos"]))
    check("guarda la RUTA, que antes no se guardaba en ningún sitio",
          all(p.get("ruta") for p in d["proyectos"]))
    check("el último declarado queda activo", d["activo"]["nombre"] == "Dos")

    correr("proyectos.py", "activar", "Uno", entorno=ENT)
    out, _ = correr("proyectos.py", "activo", "--json", entorno=ENT)
    check("se cambia de proyecto por nombre", json.loads(out)["nombre"] == "Uno")

    # LA prueba: un comando SIN ruta resuelve al proyecto activo.
    r = subprocess.run([sys.executable, os.path.join(AQUI, "hi-args.py"), "reescribe el capítulo 7"],
                       capture_output=True, text=True, env=dict(os.environ, **ENT))
    folder = next((l.split("=", 1)[1].strip("'") for l in r.stdout.split("\n") if l.startswith("FOLDER=")), "")
    check("un comando sin ruta usa el proyecto activo", os.path.realpath(folder) == os.path.realpath(a))

    # Y una ruta explícita sigue mandando sobre el activo.
    r = subprocess.run([sys.executable, os.path.join(AQUI, "hi-args.py"), f"{b} --rewrite"],
                       capture_output=True, text=True, env=dict(os.environ, **ENT))
    folder = next((l.split("=", 1)[1].strip("'") for l in r.stdout.split("\n") if l.startswith("FOLDER=")), "")
    check("una ruta escrita a mano manda sobre el activo", os.path.realpath(folder) == os.path.realpath(b))

    # Volver a declarar el mismo proyecto no lo duplica.
    correr("proyectos.py", "declarar", a, "--nombre", "Uno otra vez", entorno=ENT)
    out, _ = correr("proyectos.py", "listar", "--json", entorno=ENT)
    check("redeclarar no duplica", len(json.loads(out)["proyectos"]) == 2)

    out, code = correr("proyectos.py", "activar", "no-existe-esto", entorno=ENT)
    check("activar algo inexistente da error limpio", code == 1 and "No tengo" in out)

if FALLOS:
    print("\n".join(["", "FALLOS:"] + [f"  - {f}" for f in FALLOS]))
    sys.exit(1)
print("\nproyectos: todo en verde")
