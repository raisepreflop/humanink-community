#!/usr/bin/env python3
"""docxtc.py — lectura de .docx CON control de cambios. Base común del motor quirúrgico.

Existe porque `python-docx` miente sobre un manuscrito revisado: `paragraph.text` sólo devuelve
los `<w:r>` que cuelgan directamente del `<w:p>`, así que **el texto dentro de `<w:ins>` y
`<w:del>` desaparece**. Sobre un build con cambios sin aceptar, cualquier recuento hecho con
python-docx es sistemáticamente falso — y de ahí salen informes que dicen cifras que no son.

Aquí se lee el XML con lxml y se resuelven las marcas en uno de tres modos:

    ACEPTAR   lo insertado se queda, lo borrado desaparece   (= "aceptar todos los cambios")
    RECHAZAR  lo insertado desaparece, lo borrado vuelve     (= "rechazar todos los cambios")
    CRUDO     todo el texto tal cual, sin resolver           (para diagnóstico)

La distinción no es académica: RECHAZAR sobre el build N+1 tiene que devolver exactamente el
estado del build N. Ese es el contrato de reversibilidad del sistema de builds, y es lo que
comprueba `verify_docx.py`.

Contrastado contra Word (9 ago 2026, una versión real con 9 marcas de revisión):
este módulo predijo 44.169 palabras aceptando y 44.004 rechazando; Microsoft Word, tras
"Aceptar todos los cambios", mostró **44.169**. La interpretación de las marcas coincide.
"""
import re
import zipfile

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}


def w(tag):
    return f"{{{W}}}{tag}"


ACEPTAR, RECHAZAR, CRUDO = "aceptar", "rechazar", "crudo"


def leer_xml(ruta, parte="word/document.xml"):
    """El árbol lxml de una parte del .docx. No modifica nada."""
    with zipfile.ZipFile(ruta) as z:
        return etree.fromstring(z.read(parte))


def _texto_de_run(run, modo):
    """El texto visible de un <w:r> según el modo. El padre decide si cuenta."""
    partes = []
    for hijo in run:
        if hijo.tag == w("t"):
            partes.append(hijo.text or "")
        elif hijo.tag == w("delText"):
            # Sólo aparece dentro de <w:del>. En modo CRUDO lo damos igualmente.
            partes.append(hijo.text or "")
        elif hijo.tag in (w("tab"),):
            partes.append("\t")
        elif hijo.tag in (w("br"), w("cr")):
            partes.append("\n")
    return "".join(partes)


def texto_de_parrafo(p, modo=ACEPTAR):
    """Texto de un <w:p> resolviendo las marcas de revisión.

    Recorre los hijos del párrafo en orden. Un <w:r> suelto siempre cuenta; uno dentro de
    <w:ins> o <w:del> cuenta o no según el modo. Los <w:ins>/<w:del> pueden anidarse dentro de
    <w:hyperlink> y de <w:smartTag>, así que se baja recursivamente.
    """
    partes = []

    def recorrer(nodo, dentro_ins=False, dentro_del=False):
        for hijo in nodo:
            if hijo.tag == w("ins"):
                recorrer(hijo, True, dentro_del)
            elif hijo.tag == w("del"):
                recorrer(hijo, dentro_ins, True)
            elif hijo.tag in (w("hyperlink"), w("smartTag"), w("sdtContent"), w("bookmarkStart")):
                recorrer(hijo, dentro_ins, dentro_del)
            elif hijo.tag == w("r"):
                if modo == CRUDO:
                    partes.append(_texto_de_run(hijo, modo))
                elif dentro_del:
                    # texto borrado: vuelve sólo si rechazamos
                    if modo == RECHAZAR:
                        partes.append(_texto_de_run(hijo, modo))
                elif dentro_ins:
                    # texto insertado: se queda sólo si aceptamos
                    if modo == ACEPTAR:
                        partes.append(_texto_de_run(hijo, modo))
                else:
                    partes.append(_texto_de_run(hijo, modo))

    recorrer(p)
    return "".join(partes)


def _marca_de_parrafo(p):
    """(insertada, borrada) — si la MARCA de fin de párrafo lleva revisión.

    Es la parte que casi todo el mundo se salta y la que hace que los recuentos cuadren: si la
    marca de párrafo está insertada y rechazas, ese párrafo se funde con el siguiente; si está
    borrada y rechazas, sigue separado.
    """
    rpr = p.find(f"{w('pPr')}/{w('rPr')}")
    if rpr is None:
        return False, False
    return rpr.find(w("ins")) is not None, rpr.find(w("del")) is not None


def parrafos(ruta_o_arbol, modo=ACEPTAR, incluir_tablas=True):
    """Lista de párrafos del documento, ya resueltos según el modo.

    Aplica el fundido por marca de párrafo: dos párrafos separados por una marca insertada son
    UN párrafo cuando se rechaza. Sin esto, el recuento de párrafos de un build revisado no
    coincide nunca con el del build anterior.
    """
    raiz = ruta_o_arbol if hasattr(ruta_o_arbol, "iter") else leer_xml(ruta_o_arbol)
    cuerpo = raiz.find(w("body"))
    if cuerpo is None:
        cuerpo = raiz

    fuera = []
    pendiente = None  # párrafo arrastrado por una marca de fin insertada
    for p in cuerpo.iter(w("p")):
        if not incluir_tablas and p.getparent() is not None and p.getparent().tag == w("tc"):
            continue
        t = texto_de_parrafo(p, modo)
        ins_marca, del_marca = _marca_de_parrafo(p)

        if pendiente is not None:
            t = pendiente + t
            pendiente = None

        # marca insertada + rechazamos → el salto no existía: arrastra al siguiente
        if modo == RECHAZAR and ins_marca:
            pendiente = t
            continue
        # marca borrada + aceptamos → el salto desaparece: arrastra al siguiente
        if modo == ACEPTAR and del_marca:
            pendiente = t
            continue
        fuera.append(t)

    if pendiente is not None:
        fuera.append(pendiente)
    return fuera


def texto(ruta_o_arbol, modo=ACEPTAR):
    return "\n".join(parrafos(ruta_o_arbol, modo))


def palabras(ruta_o_arbol, modo=ACEPTAR):
    return len(texto(ruta_o_arbol, modo).split())


def revisiones(ruta_o_arbol):
    """Inventario de marcas: [(tipo, autor, fecha, id, texto)] en orden de documento."""
    raiz = ruta_o_arbol if hasattr(ruta_o_arbol, "iter") else leer_xml(ruta_o_arbol)
    fuera = []
    for e in raiz.iter():
        if e.tag not in (w("ins"), w("del")):
            continue
        # las marcas de <w:rPr> son de la marca de párrafo, no llevan texto propio
        en_rpr = e.getparent() is not None and e.getparent().tag == w("rPr")
        t = "" if en_rpr else "".join(
            (n.text or "") for n in e.iter() if n.tag in (w("t"), w("delText")))
        fuera.append((
            "ins" if e.tag == w("ins") else "del",
            e.get(w("author")) or "",
            e.get(w("date")) or "",
            e.get(w("id")) or "",
            t,
        ))
    return fuera


def autores(ruta_o_arbol):
    """Autores de revisión con su número de marcas — el eje por el que el autor acepta en bloque."""
    conteo = {}
    for tipo, autor, _, _, _ in revisiones(ruta_o_arbol):
        conteo[autor] = conteo.get(autor, 0) + 1
    return dict(sorted(conteo.items(), key=lambda kv: -kv[1]))


_ESPACIOS = re.compile(r"\s+")


def normalizar(s):
    """Para comparar dos estados del manuscrito sin que el espaciado meta ruido."""
    return _ESPACIOS.sub(" ", s).strip()


def inventario(ruta):
    """Resumen de un build. Lo que se imprime al verificar una pasada."""
    raiz = leer_xml(ruta)
    with zipfile.ZipFile(ruta) as z:
        partes = len(z.namelist())
    return {
        "fichero": ruta,
        "partes_zip": partes,
        "parrafos_aceptando": len(parrafos(raiz, ACEPTAR)),
        "parrafos_rechazando": len(parrafos(raiz, RECHAZAR)),
        "palabras_aceptando": palabras(raiz, ACEPTAR),
        "palabras_rechazando": palabras(raiz, RECHAZAR),
        "marcas": len(revisiones(raiz)),
        "autores": autores(raiz),
        "tablas": len(raiz.findall(f".//{w('tbl')}")),
        "imagenes": len(raiz.findall(f".//{w('drawing')}")),
    }


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        sys.exit("uso: docxtc.py <fichero.docx> [aceptar|rechazar|crudo|inventario]")
    ruta = sys.argv[1]
    modo = sys.argv[2] if len(sys.argv) > 2 else "inventario"
    if modo == "inventario":
        print(json.dumps(inventario(ruta), ensure_ascii=False, indent=2))
    else:
        print(texto(ruta, modo))
