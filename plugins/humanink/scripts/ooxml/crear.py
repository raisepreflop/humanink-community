#!/usr/bin/env python3
"""Crea un .docx desde Markdown, sin pandoc y sin nada instalado en el equipo.

POR QUÉ EXISTE. La ayuda del panel promete, para catorce colaboradores, que «el documento aparece
en tu carpeta de proyecto y se abre en Word». `report.mjs` lo hacía con el `pandoc` del sistema y,
si no estaba, renombraba el .md y lo devolvía como si tal cosa — y el panel confirmaba igual:
«Entregable guardado (abierto en Word)». En el .pkg no viaja ningún pandoc, así que a un cliente
normal le pasaba en CADA encargo: pedía un .docx y recibía otra cosa sin que nadie se lo dijera.

Aquí no se pretende igualar a pandoc. Se pretende cumplir lo prometido con lo que un informe
lleva de verdad: títulos, párrafos, listas, negrita y cursiva. Un .docx que Word abre.

Uso:  crear.py <entrada.md> <salida.docx> [--titulo "Título"]
"""
import argparse
import re
import sys
import zipfile
from xml.sax.saxutils import escape

# El esqueleto mínimo que Word acepta. Cada parte está aquí porque sin ella Word se queja al abrir:
# los tipos de contenido, la relación raíz que apunta al documento, y los estilos de encabezado.
TIPOS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""

RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

RELS_DOC = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _estilo(ident, nombre, tam, negrita, espacio_antes):
    return (
        f'<w:style w:type="paragraph" w:styleId="{ident}"><w:name w:val="{nombre}"/>'
        f'<w:basedOn w:val="Normal"/><w:qFormat/>'
        f'<w:pPr><w:spacing w:before="{espacio_antes}" w:after="120"/><w:keepNext/></w:pPr>'
        f'<w:rPr>{"<w:b/>" if negrita else ""}<w:sz w:val="{tam}"/></w:rPr></w:style>'
    )


ESTILOS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<w:styles {W}>'
    '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/>'
    '<w:pPr><w:spacing w:after="140" w:line="276" w:lineRule="auto"/></w:pPr>'
    '<w:rPr><w:sz w:val="22"/></w:rPr></w:style>'
    + _estilo("Heading1", "heading 1", 40, True, 360)
    + _estilo("Heading2", "heading 2", 30, True, 300)
    + _estilo("Heading3", "heading 3", 25, True, 240)
    + '<w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/>'
      '<w:basedOn w:val="Normal"/><w:pPr><w:ind w:left="720"/><w:spacing w:after="60"/></w:pPr></w:style>'
    + "</w:styles>"
)

# Negrita, cursiva y `código`. Se resuelven en este orden para que **`a`** no se rompa.
MARCAS = [
    (re.compile(r"\*\*(.+?)\*\*", re.S), "b"),
    (re.compile(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", re.S), "i"),
    (re.compile(r"`([^`]+)`", re.S), "c"),
]


def _tramos(texto):
    """Parte una línea en tramos (texto, marca). Sin árbol: los informes no anidan estilos."""
    tramos = [(texto, "")]
    for patron, marca in MARCAS:
        nuevos = []
        for trozo, ya in tramos:
            if ya:
                nuevos.append((trozo, ya))
                continue
            pos = 0
            for m in patron.finditer(trozo):
                if m.start() > pos:
                    nuevos.append((trozo[pos:m.start()], ""))
                nuevos.append((m.group(1), marca))
                pos = m.end()
            if pos < len(trozo):
                nuevos.append((trozo[pos:], ""))
        tramos = nuevos
    return [(t, m) for t, m in tramos if t]


def _runs(texto):
    fuera = []
    for trozo, marca in _tramos(texto):
        props = ""
        if marca == "b":
            props = "<w:b/>"
        elif marca == "i":
            props = "<w:i/>"
        elif marca == "c":
            props = '<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/>'
        rpr = f"<w:rPr>{props}</w:rPr>" if props else ""
        # xml:space="preserve" o Word se come los espacios de los bordes y las palabras se pegan.
        fuera.append(f'<w:r>{rpr}<w:t xml:space="preserve">{escape(trozo)}</w:t></w:r>')
    return "".join(fuera) or '<w:r><w:t xml:space="preserve"></w:t></w:r>'


def _parrafo(texto, estilo=None):
    ppr = f'<w:pPr><w:pStyle w:val="{estilo}"/></w:pPr>' if estilo else ""
    return f"<w:p>{ppr}{_runs(texto)}</w:p>"


def markdown_a_parrafos(md):
    salida = []
    for linea in md.replace("\r\n", "\n").split("\n"):
        t = linea.rstrip()
        if not t.strip():
            continue
        enc = re.match(r"^(#{1,3})\s+(.*)$", t)
        if enc:
            salida.append(_parrafo(enc.group(2), f"Heading{len(enc.group(1))}"))
            continue
        vin = re.match(r"^\s*[-*+•]\s+(.*)$", t)
        if vin:
            salida.append(_parrafo("• " + vin.group(1), "ListParagraph"))
            continue
        num = re.match(r"^\s*(\d+)[.)]\s+(.*)$", t)
        if num:
            salida.append(_parrafo(f"{num.group(1)}. {num.group(2)}", "ListParagraph"))
            continue
        if re.match(r"^\s*([-*_])\s*\1\s*\1[\s\-*_]*$", t):
            continue                                   # una regla horizontal no pinta nada aquí
        salida.append(_parrafo(t))
    return salida or [_parrafo("")]


def crear(md, destino):
    cuerpo = "".join(markdown_a_parrafos(md))
    documento = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document {W}><w:body>{cuerpo}'
        '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1418" w:right="1418" w:bottom="1418" w:left="1418"/></w:sectPr>'
        "</w:body></w:document>"
    )
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", TIPOS)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/_rels/document.xml.rels", RELS_DOC)
        z.writestr("word/styles.xml", ESTILOS)
        z.writestr("word/document.xml", documento)
    return destino


def main(argv=None):
    p = argparse.ArgumentParser(description="Markdown → .docx, sin pandoc")
    p.add_argument("entrada")
    p.add_argument("salida")
    p.add_argument("--titulo", default=None, help="Se antepone como H1 si el texto no trae uno")
    a = p.parse_args(argv)
    md = open(a.entrada, encoding="utf-8").read()
    if a.titulo and not md.lstrip().startswith("# "):
        md = f"# {a.titulo}\n\n{md}"
    crear(md, a.salida)
    print(a.salida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
