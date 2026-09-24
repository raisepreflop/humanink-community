"""De qué libro es un build, y dónde se guarda su telemetría.

Revisión del 17-sep-2026: en una carpeta con varios libros (Descargas), la telemetría se guardaba
como telemetria/v48.json para todos, así que medir un libro pisaba la curva de otro y le pasaba su
nota. Desde la 1.6.5 cada libro tiene su carpeta, telemetria/libros/<libro>/; el fichero de siempre
(telemetria/v48.json) se sigue escribiendo SOLO si en la carpeta hay un único libro, para no romper
a quien ya lo lee (el dashboard del plugin).

`companion/pasadas.mjs` aplica exactamente las mismas reglas (`libroDe`, `carpetaDeLibro`), y
qa/pasadas.test.mjs lo comprueba contra este módulo.
"""
import os
import re
import unicodedata

RE_VERSION = re.compile(r"-[vb]0*(\d+)", re.I)


def libro_de(f):
    """«DUOC-10-b48 VF.docx» → «duoc-10»; «Mi novela-m01-v03.docx» → «mi novela-m01»."""
    nombre = os.path.basename(f)
    if nombre.lower().endswith(".docx"):
        nombre = nombre[:-5]
    m = RE_VERSION.search(nombre)
    base = nombre[:m.start()] if m else nombre
    return " ".join(base.split()).lower()


def carpeta_de_libro(libro):
    """El nombre de la carpeta de un libro: sin tildes ni signos. «Él y la mar» → «el-y-la-mar»."""
    s = unicodedata.normalize("NFKD", str(libro))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "libro"


def es_build(nombre):
    n = os.path.basename(nombre)
    return (n.lower().endswith(".docx") and bool(RE_VERSION.search(n)) and not n.startswith("~$")
            and "copia" not in n.lower() and "copy" not in n.lower())


def libros_en(carpeta):
    try:
        return sorted({libro_de(f) for f in os.listdir(carpeta) if es_build(f)})
    except OSError:
        return []


def destinos(carpeta, build):
    """Dónde se escribe la telemetría de ESTE build: la de su libro y, si es el único, la de siempre."""
    base = os.path.join(carpeta, "telemetria")
    fuera = [os.path.join(base, "libros", carpeta_de_libro(libro_de(build)))]
    if len(libros_en(carpeta)) <= 1:
        fuera.append(base)
    return fuera
