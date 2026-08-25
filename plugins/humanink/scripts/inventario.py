#!/usr/bin/env python3
"""Qué hay en la carpeta de un libro — el inventario de partida.

    python3 scripts/inventario.py <carpeta> [--json]

Existe porque HumanInk daba por hecho que el libro se construye con él desde la premisa, y el caso
normal es el contrario: casi todo el que llega trae una novela terminada que quiere reescribir. A
ese autor había que preguntarle qué tenía, cuando la carpeta ya lo dice.

Y porque los ficheros del proyecto no se declaraban en ningún sitio: se adivinaban con un barrido
ciego de todo el árbol y con nombres escritos a fuego en un script de shell. Aquí se miran una vez,
se dice qué hay y qué falta, y se registra.

La distinción que ordena la salida: el manuscrito ACREDITA la concepción —quien escribió la novela
tuvo premisa, biblia y escaleta, aunque nunca los pusiera en documentos aparte— y la reescritura SE
REGISTRA. Por eso un proyecto con manuscrito y sin biblia no está «incompleto»: está en su sitio.
"""
import json
import os
import re
import sys
import zipfile

# Los papeles que HumanInk conoce. Cada uno con los nombres que puede tener, en el orden en que se
# buscan. La lista vive aquí y no repartida por los skills, que era el problema.
PAPELES = {
    "manuscrito":  ["*.docx", "*.md"],          # se filtra por tamaño más abajo
    "biblia":      ["biblia.md", "bible.md"],
    "escaleta":    ["escaleta.md", "outline.md", "estructura.md"],
    "estilo":      ["estilo.md", "style.md", "voz.md"],
    "premisa":     ["premisa.md", "premise.md"],
    "sinopsis":    ["sinopsis.md", "synopsis.md"],
    "perfil":      ["perfil-autor.md", "author.md"],
    "plan":        ["plan.json"],
}

# Un manuscrito es un documento largo. Por debajo de esto es una nota, una carta o un capítulo
# suelto — no la obra. El umbral es generoso a propósito: más vale preguntar que decidir mal.
MINIMO_MANUSCRITO = 3000

RE_VERSION = re.compile(r"-[vb]0*(\d+)", re.I)


def palabras_docx(ruta):
    """Palabras de un .docx sin dependencias: se lee el XML y se quitan las etiquetas."""
    try:
        with zipfile.ZipFile(ruta) as z:
            xml = z.read("word/document.xml").decode("utf-8", "replace")
        texto = re.sub(r"<[^>]+>", " ", xml)
        texto = re.sub(r"&[a-z]+;|&#\d+;", " ", texto)
        return len(texto.split())
    except Exception:
        return 0


def palabras_texto(ruta):
    try:
        with open(ruta, encoding="utf-8", errors="replace") as f:
            return len(f.read().split())
    except OSError:
        return 0


def palabras(ruta):
    return palabras_docx(ruta) if ruta.lower().endswith(".docx") else palabras_texto(ruta)


def util(nombre):
    """Los ficheros que Word y macOS dejan por medio no son del autor."""
    base = os.path.basename(nombre)
    return not (base.startswith("~$") or base.startswith("._") or base.startswith("."))


def inventariar(carpeta):
    carpeta = os.path.expanduser(carpeta)
    if not os.path.isdir(carpeta):
        return {"error": f"No existe la carpeta: {carpeta}"}

    sueltos = [f for f in os.listdir(carpeta) if util(f) and os.path.isfile(os.path.join(carpeta, f))]
    encontrado, faltan = {}, []

    for papel, patrones in PAPELES.items():
        if papel == "manuscrito":
            continue
        for p in patrones:
            hit = next((f for f in sueltos if f.lower() == p.lower()), None)
            if hit:
                encontrado[papel] = {"fichero": hit, "palabras": palabras(os.path.join(carpeta, hit))}
                break
        else:
            faltan.append(papel)

    # El manuscrito: el documento largo. Si hay varios numerados, es una serie de versiones.
    candidatos = []
    for f in sueltos:
        if not f.lower().endswith((".docx", ".md", ".txt")):
            continue
        if any(f.lower() == n.lower() for ns in PAPELES.values() for n in ns):
            continue
        n = palabras(os.path.join(carpeta, f))
        if n >= MINIMO_MANUSCRITO:
            m = RE_VERSION.search(f)
            candidatos.append({"fichero": f, "palabras": n, "version": int(m.group(1)) if m else None})

    candidatos.sort(key=lambda c: (c["version"] is None, c["version"] or 0, c["palabras"]))
    versiones = [c for c in candidatos if c["version"] is not None]

    manuscrito = None
    if candidatos:
        # El último por número de versión, o el más largo si no están numerados.
        manuscrito = versiones[-1] if versiones else max(candidatos, key=lambda c: c["palabras"])
    else:
        faltan.insert(0, "manuscrito")

    tiene_telemetria = os.path.isdir(os.path.join(carpeta, "telemetria"))

    return {
        "carpeta": carpeta,
        # 'manuscript_first' es el caso NORMAL, no la excepción: casi todo el que llega a HumanInk
        # trae una novela terminada. Empezar de cero es la variante.
        "tipo": "manuscript_first" if manuscrito else "from_scratch",
        "manuscrito": manuscrito,
        "versiones": len(versiones),
        "documentos": encontrado,
        "faltan": faltan,
        # Lo que el manuscrito ACREDITA. No es que haya que crearlos: es que ya existieron, en la
        # cabeza del autor y en el texto, aunque nunca se escribieran aparte.
        "deducibles": [p for p in ("premisa", "sinopsis", "biblia", "escaleta", "estilo") if p in faltan]
        if manuscrito else [],
        "telemetria": tiene_telemetria,
    }


def imprimir(inv):
    if "error" in inv:
        print("  " + inv["error"])
        return
    m = inv["manuscrito"]
    print(f"\n  Carpeta: {inv['carpeta']}")
    if m:
        v = f" · {inv['versiones']} versiones" if inv["versiones"] > 1 else ""
        print(f"  Manuscrito: sí — {m['fichero']} · {m['palabras']:,} palabras{v}".replace(",", "."))
    else:
        print("  Manuscrito: no")
    if inv["documentos"]:
        print("  Documentos: " + " · ".join(f"{k} ({v['fichero']})" for k, v in inv["documentos"].items()))
    if inv["faltan"]:
        print("  No hay: " + " · ".join(inv["faltan"]))
    if inv["deducibles"]:
        print("  Deducibles del manuscrito: " + " · ".join(inv["deducibles"]))
        print("  → El manuscrito los acredita. A partir de aquí se registra lo que se haga con IA.")
    if inv["telemetria"]:
        print("  Telemetría de reescritura: sí")
    print()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    inv = inventariar(args[0] if args else ".")
    if "--json" in sys.argv:
        print(json.dumps(inv, ensure_ascii=False, indent=1))
    else:
        imprimir(inv)
    sys.exit(1 if "error" in inv else 0)
