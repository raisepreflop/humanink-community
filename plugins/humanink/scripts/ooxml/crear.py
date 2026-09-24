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
<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>
</Types>"""

RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

RELS_DOC = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>
</Relationships>"""

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


# EL FORMATO DE LA CASA (Rais, 21-sep-2026: «hay un skill de cómo hay que hacer los ficheros en
# Word»). Es el de `md2docx.py`, el conversor de los plugins, y hasta hoy el Studio no lo aplicaba:
#   · Times New Roman 12, justificado, interlineado 1,5;
#   · Título 1 a 14 pt en negrita y en página nueva, Título 2 a 13 pt en negrita;
#   · páginas SIEMPRE numeradas, en el pie.
# Los títulos se llaman «heading 1/2/…» para que Word los traduzca a «Título 1/2» y salgan en el
# panel de navegación; los párrafos de lista, cita, código y tabla no se justifican ni llevan 1,5,
# que en una lista de una línea solo abre huecos.
FUENTE = '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman" w:eastAsia="Times New Roman"/>'


def _estilo(ident, nombre, tam, negrita, espacio_antes, nivel, pagina_nueva=False, cursiva=False):
    return (
        f'<w:style w:type="paragraph" w:styleId="{ident}"><w:name w:val="{nombre}"/>'
        f'<w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>'
        f'<w:pPr><w:keepNext/>{"<w:pageBreakBefore/>" if pagina_nueva else ""}'
        f'<w:spacing w:before="{espacio_antes}" w:after="120" w:line="240" w:lineRule="auto"/>'
        f'<w:jc w:val="left"/><w:outlineLvl w:val="{nivel}"/></w:pPr>'
        f'<w:rPr>{FUENTE}{"<w:b/>" if negrita else ""}{"<w:i/>" if cursiva else ""}<w:sz w:val="{tam}"/><w:szCs w:val="{tam}"/></w:rPr></w:style>'
    )


SIN_JUSTIFICAR = '<w:jc w:val="left"/>'

ESTILOS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<w:styles {W}>'
    f'<w:docDefaults><w:rPrDefault><w:rPr>{FUENTE}<w:sz w:val="24"/><w:szCs w:val="24"/><w:lang w:val="es-ES"/></w:rPr></w:rPrDefault>'
    '<w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="360" w:lineRule="auto"/><w:jc w:val="both"/></w:pPr></w:pPrDefault></w:docDefaults>'
    '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/>'
    '<w:pPr><w:spacing w:after="120" w:line="360" w:lineRule="auto"/><w:jc w:val="both"/></w:pPr>'
    f'<w:rPr>{FUENTE}<w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr></w:style>'
    + _estilo("Heading1", "heading 1", 28, True, 240, 0, pagina_nueva=True)
    + _estilo("Heading2", "heading 2", 26, True, 240, 1)
    + _estilo("Heading3", "heading 3", 24, True, 200, 2)
    + _estilo("Heading4", "heading 4", 24, True, 160, 3, cursiva=True)
    + '<w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/>'
      f'<w:basedOn w:val="Normal"/><w:pPr><w:ind w:left="720"/><w:spacing w:after="60" w:line="300" w:lineRule="auto"/>{SIN_JUSTIFICAR}</w:pPr></w:style>'
    # Cita: el mismo sangrado que una lista — 720 twips = 36pt, el que ya usaba md2docx.py — para
    # que se distinga del cuerpo sin inventar una medida nueva.
    + '<w:style w:type="paragraph" w:styleId="Quote"><w:name w:val="Quote"/>'
      f'<w:basedOn w:val="Normal"/><w:pPr><w:ind w:left="720"/><w:spacing w:after="80" w:line="300" w:lineRule="auto"/>{SIN_JUSTIFICAR}</w:pPr></w:style>'
    # Código: monoespaciada, sin más adorno — un bloque que antes se descartaba entero (md2docx.py)
    # o salía literal con sus ``` (crear.py sin esto). Ninguna de las dos cumple lo prometido.
    + '<w:style w:type="paragraph" w:styleId="Code"><w:name w:val="Code"/>'
      f'<w:basedOn w:val="Normal"/><w:pPr><w:ind w:left="360"/><w:spacing w:after="0" w:line="240" w:lineRule="auto"/>{SIN_JUSTIFICAR}</w:pPr>'
      '<w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:sz w:val="20"/></w:rPr></w:style>'
    # Tabla: sin justificar y a interlineado sencillo; en una celda estrecha el 1,5 y el justificado
    # abren ríos de blanco.
    + '<w:style w:type="paragraph" w:styleId="Tabla"><w:name w:val="Tabla"/>'
      f'<w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="40" w:after="40" w:line="240" w:lineRule="auto"/>{SIN_JUSTIFICAR}</w:pPr>'
      '<w:rPr><w:sz w:val="22"/><w:szCs w:val="22"/></w:rPr></w:style>'
    + "</w:styles>"
)

# Las páginas SIEMPRE numeradas: un campo PAGE centrado en el pie. Es un campo de Word, así que el
# número es el de verdad aunque el autor añada o quite páginas.
PIE = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<w:ftr {W}><w:p><w:pPr><w:jc w:val="center"/><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
    f'<w:r><w:rPr>{FUENTE}<w:sz w:val="20"/></w:rPr><w:fldChar w:fldCharType="begin"/></w:r>'
    f'<w:r><w:rPr>{FUENTE}<w:sz w:val="20"/></w:rPr><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>'
    f'<w:r><w:rPr>{FUENTE}<w:sz w:val="20"/></w:rPr><w:fldChar w:fldCharType="separate"/></w:r>'
    f'<w:r><w:rPr>{FUENTE}<w:sz w:val="20"/></w:rPr><w:t>1</w:t></w:r>'
    f'<w:r><w:rPr>{FUENTE}<w:sz w:val="20"/></w:rPr><w:fldChar w:fldCharType="end"/></w:r>'
    '</w:p></w:ftr>'
)

# Negrita, cursiva, `código` y ~~tachado~~. Bold y tachado antes que cursiva para que
# **~~a~~** y ~~*a*~~ no se rompan entre sí.
MARCAS = [
    (re.compile(r"\*\*(.+?)\*\*", re.S), "b"),
    (re.compile(r"~~(.+?)~~", re.S), "s"),
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
        elif marca == "s":
            props = "<w:strike/>"
        elif marca == "i":
            props = "<w:i/>"
        elif marca == "c":
            props = '<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/>'
        rpr = f"<w:rPr>{props}</w:rPr>" if props else ""
        # xml:space="preserve" o Word se come los espacios de los bordes y las palabras se pegan.
        fuera.append(f'<w:r>{rpr}<w:t xml:space="preserve">{escape(trozo)}</w:t></w:r>')
    return "".join(fuera) or '<w:r><w:t xml:space="preserve"></w:t></w:r>'


# Las tablas del informe. Sin esto salían como texto con barras —«| Aspecto | Nota |»— y el autor
# recibía un documento que Word abre pero que no se puede leer: justo lo que más usa un informe de
# lectura, que es una tabla por capítulo.
FILA = re.compile(r"^\s*\|(.+)\|\s*$")
SEPARADOR = re.compile(r"^\s*\|[\s:|-]+\|\s*$")


def _celdas(linea):
    return [c.strip() for c in FILA.match(linea).group(1).split("|")]


def _tabla(filas):
    """filas: lista de listas de texto. La primera es la cabecera."""
    ancho = max(len(f) for f in filas)
    # 9026 twips = el ancho útil de un A4 con los márgenes de este documento. Repartido a partes
    # iguales: adivinar el contenido para dar anchos distintos sale peor que una rejilla regular.
    col = 9026 // ancho
    grid = "".join(f'<w:gridCol w:w="{col}"/>' for _ in range(ancho))
    bordes = "".join(
        f'<w:{b} w:val="single" w:sz="4" w:space="0" w:color="BFBFBF"/>'
        for b in ("top", "left", "bottom", "right", "insideH", "insideV")
    )
    fuera = [
        "<w:tbl><w:tblPr>"
        f'<w:tblW w:w="9026" w:type="dxa"/><w:tblBorders>{bordes}</w:tblBorders>'
        '<w:tblLayout w:type="fixed"/></w:tblPr>'
        f"<w:tblGrid>{grid}</w:tblGrid>"
    ]
    for i, fila in enumerate(filas):
        celdas = []
        for j in range(ancho):
            texto = fila[j] if j < len(fila) else ""
            # La cabecera en negrita: se marca en el propio texto para no duplicar la lógica de runs.
            contenido = f"**{texto}**" if i == 0 and texto else texto
            celdas.append(
                f'<w:tc><w:tcPr><w:tcW w:w="{col}" w:type="dxa"/></w:tcPr>'
                f'<w:p><w:pPr><w:pStyle w:val="Tabla"/></w:pPr>{_runs(contenido)}</w:p></w:tc>'
            )
        # tblHeader repite la cabecera si la tabla parte de página, que es lo normal en un informe.
        pr = '<w:trPr><w:tblHeader/></w:trPr>' if i == 0 else ""
        fuera.append(f"<w:tr>{pr}{''.join(celdas)}</w:tr>")
    fuera.append("</w:tbl>")
    # Word necesita un párrafo detrás de una tabla; si no, dos tablas seguidas se funden en una.
    fuera.append('<w:p><w:pPr><w:spacing w:after="0"/></w:pPr></w:p>')
    return "".join(fuera)


def _parrafo(texto, estilo=None):
    ppr = f'<w:pPr><w:pStyle w:val="{estilo}"/></w:pPr>' if estilo else ""
    return f"<w:p>{ppr}{_runs(texto)}</w:p>"


def _cita(texto):
    """Una línea de cita (`> …`), en cursiva forzada — sin pasar por `_runs`/`_tramos`: una cita
    es prosa citada, no lleva marcado propio, y forzar la cursiva aquí evita que un `*` suelto
    dentro de la cita se interprete como énfasis."""
    ppr = '<w:pPr><w:pStyle w:val="Quote"/></w:pPr>'
    return f'<w:p>{ppr}<w:r><w:rPr><w:i/></w:rPr><w:t xml:space="preserve">{escape(texto)}</w:t></w:r></w:p>'


def _bloque_codigo(lineas):
    """Un bloque ```…``` como UN párrafo monoespaciado con saltos de línea manuales (`<w:br/>`):
    un `<w:p>` de Word no admite un salto de línea dentro de su propio texto."""
    ppr = '<w:pPr><w:pStyle w:val="Code"/></w:pPr>'
    runs = []
    for i, linea in enumerate(lineas):
        if i:
            runs.append("<w:br/>")
        runs.append(f'<w:r><w:t xml:space="preserve">{escape(linea)}</w:t></w:r>')
    return f"<w:p>{ppr}{''.join(runs)}</w:p>"


# ── GRÁFICOS NATIVOS DE WORD (21-sep-2026) ────────────────────────────────────────────────────
#
# Rais: «el informe no lleva gráficos». Aquí no se pinta ninguna imagen: se escribe un gráfico de
# Word de verdad (DrawingML), con los datos DENTRO del documento como literales. Word lo dibuja con
# su propio motor, sale nítido a cualquier zoom y se imprime bien; y como no depende de matplotlib
# ni de nada instalado, sale igual en el Mac y en el Windows de cualquiera.
#
# En el Markdown se escribe como un bloque de código con la etiqueta `grafico` y un JSON dentro:
#   {"tipo": "barras" | "radar", "titulo": "…", "categorias": ["…"],
#    "series": [{"nombre": "…", "valores": [7, 8.5, …]}], "max": 10}
C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
COLORES = ["1F4E79", "C55A11", "548235", "7F6000"]


def _lit_str(valores):
    pts = "".join(f'<c:pt idx="{i}"><c:v>{escape(str(v))}</c:v></c:pt>' for i, v in enumerate(valores))
    return f'<c:strLit><c:ptCount val="{len(valores)}"/>{pts}</c:strLit>'


def _lit_num(valores):
    pts = "".join(f'<c:pt idx="{i}"><c:v>{float(v)}</c:v></c:pt>' for i, v in enumerate(valores) if v is not None)
    return f'<c:numLit><c:formatCode>General</c:formatCode><c:ptCount val="{len(valores)}"/>{pts}</c:numLit>'


def _serie(i, s, categorias, radar):
    color = COLORES[i % len(COLORES)]
    relleno = (f'<c:spPr><a:ln w="28575"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill></a:ln></c:spPr>'
               if radar else f'<c:spPr><a:solidFill><a:srgbClr val="{color}"/></a:solidFill></c:spPr>')
    etiquetas = ('' if radar else
                 '<c:dLbls><c:numFmt formatCode="0.0" sourceLinked="0"/><c:spPr><a:noFill/><a:ln><a:noFill/></a:ln></c:spPr>'
                 '<c:showLegendKey val="0"/><c:showVal val="1"/><c:showCatName val="0"/><c:showSerName val="0"/>'
                 '<c:showPercent val="0"/><c:showBubbleSize val="0"/></c:dLbls>')
    marcador = '<c:marker><c:symbol val="circle"/><c:size val="5"/></c:marker>' if radar else ''
    return (f'<c:ser><c:idx val="{i}"/><c:order val="{i}"/><c:tx><c:v>{escape(str(s.get("nombre", "")))}</c:v></c:tx>'
            f'{relleno}{marcador}{etiquetas}<c:cat>{_lit_str(categorias)}</c:cat><c:val>{_lit_num(s.get("valores", []))}</c:val></c:ser>')


def grafico_xml(spec):
    """El chartSpace de un gráfico. Solo barras horizontales y radar: los dos que pide un informe."""
    radar = spec.get("tipo") == "radar"
    categorias = [str(c) for c in spec.get("categorias", [])]
    series = spec.get("series", [])
    maximo = spec.get("max", 10)
    titulo = escape(str(spec.get("titulo", "")))
    cuerpo_series = "".join(_serie(i, s, categorias, radar) for i, s in enumerate(series))
    if radar:
        trazo = (f'<c:radarChart><c:radarStyle val="marker"/><c:varyColors val="0"/>{cuerpo_series}'
                 '<c:axId val="101"/><c:axId val="102"/></c:radarChart>'
                 '<c:catAx><c:axId val="101"/><c:scaling><c:orientation val="minMax"/></c:scaling><c:delete val="0"/>'
                 '<c:axPos val="b"/><c:majorGridlines/><c:numFmt formatCode="General" sourceLinked="0"/><c:tickLblPos val="nextTo"/>'
                 '<c:crossAx val="102"/><c:crosses val="autoZero"/><c:auto val="1"/><c:lblAlgn val="ctr"/><c:lblOffset val="100"/></c:catAx>'
                 f'<c:valAx><c:axId val="102"/><c:scaling><c:orientation val="minMax"/><c:max val="{maximo}"/><c:min val="0"/></c:scaling>'
                 '<c:delete val="0"/><c:axPos val="l"/><c:majorGridlines/><c:numFmt formatCode="0" sourceLinked="0"/>'
                 '<c:majorTickMark val="none"/><c:tickLblPos val="nextTo"/><c:crossAx val="101"/><c:crosses val="autoZero"/>'
                 '<c:crossBetween val="between"/><c:majorUnit val="2"/></c:valAx>')
    else:
        trazo = (f'<c:barChart><c:barDir val="bar"/><c:grouping val="clustered"/><c:varyColors val="0"/>{cuerpo_series}'
                 '<c:gapWidth val="60"/><c:axId val="201"/><c:axId val="202"/></c:barChart>'
                 # Categorías de arriba abajo en el orden en que se escribieron.
                 '<c:catAx><c:axId val="201"/><c:scaling><c:orientation val="maxMin"/></c:scaling><c:delete val="0"/>'
                 '<c:axPos val="l"/><c:numFmt formatCode="General" sourceLinked="0"/><c:tickLblPos val="nextTo"/>'
                 '<c:crossAx val="202"/><c:crosses val="autoZero"/><c:auto val="1"/><c:lblAlgn val="ctr"/><c:lblOffset val="100"/></c:catAx>'
                 f'<c:valAx><c:axId val="202"/><c:scaling><c:orientation val="minMax"/><c:max val="{maximo}"/><c:min val="0"/></c:scaling>'
                 '<c:delete val="0"/><c:axPos val="t"/><c:majorGridlines/><c:numFmt formatCode="0" sourceLinked="0"/>'
                 '<c:majorTickMark val="out"/><c:tickLblPos val="nextTo"/><c:crossAx val="201"/><c:crosses val="max"/>'
                 '<c:crossBetween val="between"/><c:majorUnit val="2"/></c:valAx>')
    leyenda = ('<c:legend><c:legendPos val="b"/><c:overlay val="0"/></c:legend>' if len(series) > 1 else '')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<c:chartSpace xmlns:c="{C_NS}" xmlns:a="{A_NS}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<c:roundedCorners val="0"/><c:chart>'
        f'<c:title><c:tx><c:rich><a:bodyPr/><a:p><a:pPr><a:defRPr sz="1200" b="1"><a:latin typeface="Times New Roman"/></a:defRPr></a:pPr>'
        f'<a:r><a:rPr lang="es-ES" sz="1200" b="1"><a:latin typeface="Times New Roman"/></a:rPr><a:t>{titulo}</a:t></a:r></a:p></c:rich></c:tx>'
        '<c:overlay val="0"/></c:title><c:autoTitleDeleted val="0"/>'
        f'<c:plotArea><c:layout/>{trazo}</c:plotArea>{leyenda}<c:plotVisOnly val="1"/><c:dispBlanksAs val="gap"/></c:chart>'
        '<c:txPr><a:bodyPr/><a:p><a:pPr><a:defRPr sz="1000"><a:latin typeface="Times New Roman"/></a:defRPr></a:pPr><a:endParaRPr lang="es-ES"/></a:p></c:txPr>'
        '</c:chartSpace>'
    )


def _parrafo_grafico(n, rid, radar):
    alto = 4200000 if radar else 3000000                       # EMU: ~11,7 cm el radar, ~8,3 cm las barras
    return (
        '<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="120" w:after="120" w:line="240" w:lineRule="auto"/></w:pPr>'
        '<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">'
        f'<wp:extent cx="5400000" cy="{alto}"/><wp:effectExtent l="0" t="0" r="0" b="0"/>'
        f'<wp:docPr id="{1000 + n}" name="Gráfico {n}"/><wp:cNvGraphicFramePr/>'
        f'<a:graphic xmlns:a="{A_NS}"><a:graphicData uri="{C_NS}">'
        f'<c:chart xmlns:c="{C_NS}" r:id="{rid}"/></a:graphicData></a:graphic>'
        '</wp:inline></w:drawing></w:r></w:p>'
    )


def markdown_a_parrafos(md, graficos=None):
    salida = []
    lineas = md.replace("\r\n", "\n").split("\n")
    i = -1
    while i + 1 < len(lineas):
        i += 1
        t = lineas[i].rstrip()
        if not t.strip():
            continue

        # ¿Empieza una tabla? Una fila de barras seguida de la línea de guiones. Se consume entera
        # aquí: si se dejara al bucle normal, cada fila saldría como un párrafo con barras.
        if FILA.match(t) and i + 1 < len(lineas) and SEPARADOR.match(lineas[i + 1]):
            filas = [_celdas(t)]
            i += 1                                   # la línea de guiones no se pinta
            while i + 1 < len(lineas) and FILA.match(lineas[i + 1]) and not SEPARADOR.match(lineas[i + 1]):
                i += 1
                filas.append(_celdas(lineas[i]))
            salida.append(_tabla(filas))
            continue
        # ¿Empieza un bloque de código? Se consume entero hasta la valla de cierre — o hasta el
        # final del documento si el autor se dejó la valla sin cerrar, en vez de tragarse el resto.
        if t.lstrip().startswith("```grafico") and graficos is not None:
            dentro = []
            i += 1
            while i < len(lineas) and not lineas[i].strip().startswith("```"):
                dentro.append(lineas[i])
                i += 1
            try:
                import json as _json
                spec = _json.loads("\n".join(dentro))
                if spec.get("categorias") and spec.get("series"):
                    graficos.append(spec)
                    n = len(graficos)
                    salida.append(_parrafo_grafico(n, f"rIdG{n}", spec.get("tipo") == "radar"))
            except Exception:                        # noqa: BLE001 — un gráfico roto no tira el documento
                pass
            continue
        if t.lstrip().startswith("```"):
            dentro = []
            i += 1
            while i < len(lineas) and not lineas[i].strip().startswith("```"):
                dentro.append(lineas[i])
                i += 1
            salida.append(_bloque_codigo(dentro))
            continue
        if t.startswith("> ") or t.strip() == ">":
            salida.append(_cita(t[2:] if t.startswith("> ") else ""))
            continue
        enc = re.match(r"^(#{1,4})\s+(.*)$", t)
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
    graficos = []
    cuerpo = "".join(markdown_a_parrafos(md, graficos))
    documento = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document {W} xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
        ' xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"><w:body>'
        f'{cuerpo}'
        '<w:sectPr><w:footerReference w:type="default" r:id="rId2"/><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1418" w:right="1418" w:bottom="1418" w:left="1418" w:header="709" w:footer="709"/></w:sectPr>'
        "</w:body></w:document>"
    )
    tipos = TIPOS
    rels = RELS_DOC
    if graficos:
        tipos = TIPOS.replace("</Types>", "".join(
            f'<Override PartName="/word/charts/chart{n}.xml" ContentType="application/vnd.openxmlformats-officedocument.drawingml.chart+xml"/>'
            for n in range(1, len(graficos) + 1)) + "</Types>")
        rels = RELS_DOC.replace("</Relationships>", "".join(
            f'<Relationship Id="rIdG{n}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart" Target="charts/chart{n}.xml"/>'
            for n in range(1, len(graficos) + 1)) + "</Relationships>")
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", tipos)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/_rels/document.xml.rels", rels)
        z.writestr("word/styles.xml", ESTILOS)
        z.writestr("word/footer1.xml", PIE)
        z.writestr("word/document.xml", documento)
        for n, spec in enumerate(graficos, start=1):
            z.writestr(f"word/charts/chart{n}.xml", grafico_xml(spec))
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
