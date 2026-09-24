"""anotar.py — llevar las notas del Studio al documento de Word, sin tocar el texto.

Dos formas, y las dos usan lo que Word ya trae, sin complemento ni botones nuestros:

  marcadores   un marcador de Word por nota, en su párrafo, con nombre N_014. El autor va a
               «Ir a → Marcador», elige la nota y Word salta a su sitio. Un marcador no cambia el
               texto ni el recuento de palabras y sobrevive a aceptar o rechazar cambios (M-27).

  comentarios  la nota como comentario de Word anclado a su párrafo, con el autor «HumanInk · N-014».
               Se ven en el margen, se responden y se resuelven con las herramientas de siempre.
               Es opcional: el autor decide si quiere su documento con comentarios o limpio.

Nada de esto altera el cuerpo del texto: los marcadores son etiquetas vacías y el comentario vive en
word/comments.xml. El documento de partida no se toca nunca — se escribe una copia.
"""
import argparse
import json
import re
import sys
import zipfile
from datetime import datetime, timezone

try:
    from lxml import etree
except ImportError:  # equipo rojo, 24-sep-2026: un traceback de Python no le dice nada a un autor
    import sys as _sys
    _sys.exit("✗ Falta el módulo «lxml», que necesito para leer y escribir el control de cambios de Word.\n"
              "  En tu ordenador: python3 -m pip install lxml. En Cowork, dímelo en el chat y lo resolvemos.")

sys.path.insert(0, __file__.rsplit("/", 1)[0])

import docxtc as D  # noqa: E402
from intervene import _escribir, _texto_vivo, localizar, parrafos_de  # noqa: E402

W = D.W
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"


def w(tag):
    return f"{{{W}}}{tag}"


NOMBRE_VALIDO = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,39}$")


def _donde(ps, nota):
    """El párrafo de la nota: por su cita y, si ya no está viva, por su número.

    La pasada acaba de reescribir justo esos pasajes, así que la cita vieja vive dentro de un
    <w:del> y `localizar` no la ve: los marcadores fallaban precisamente en las notas trabajadas,
    y en silencio (equipo rojo 19-sep). El número de párrafo sigue valiendo para llevar al autor
    a su sitio, que es para lo que existe el marcador.
    """
    try:
        p, idx, desvio = localizar(ps, nota.get("parrafo") or 0, nota.get("cita") or "")
        return p, idx, "cita"
    except Exception:                                # noqa: BLE001
        p, idx, _ = localizar(ps, nota.get("parrafo") or 0, "")
        return p, idx, "numero"


def nombre_de_marcador(id_nota):
    """«N-014» → «N_014». Los marcadores de Word no admiten guiones ni empiezan por número."""
    n = re.sub(r"[^A-Za-z0-9_]", "_", str(id_nota or "").strip())
    if not n:
        return None
    if not n[0].isalpha() and n[0] != "_":
        n = "N_" + n
    return n[:40] if NOMBRE_VALIDO.match(n[:40]) else None


def _siguiente_id_marcador(raiz):
    usados = [int(b.get(w("id")) or -1) for b in raiz.iter(w("bookmarkStart"))]
    return max(usados, default=0) + 1


def marcadores(entrada, salida, notas):
    """Pone un marcador por nota en su párrafo. Devuelve qué notas se pudieron marcar y cuáles no."""
    raiz = D.leer_xml(entrada)
    cuerpo = raiz.find(w("body")) if raiz.find(w("body")) is not None else raiz
    ps = list(cuerpo.iter(w("p")))
    siguiente = _siguiente_id_marcador(raiz)
    informe = {"puestos": [], "fallidos": []}

    # Los ya existentes con nuestro nombre se quitan antes: volver a marcar no duplica.
    for b in list(raiz.iter(w("bookmarkStart"))):
        if (b.get(w("name")) or "").startswith("N_"):
            padre = b.getparent()
            fin_id = b.get(w("id"))
            padre.remove(b)
            for e in list(raiz.iter(w("bookmarkEnd"))):
                if e.get(w("id")) == fin_id:
                    e.getparent().remove(e)

    for nota in notas or []:
        nombre = nombre_de_marcador(nota.get("id"))
        if not nombre:
            informe["fallidos"].append({"id": nota.get("id"), "error": "nombre de marcador no válido"})
            continue
        try:
            p, idx, por = _donde(ps, nota)
        except Exception as e:                       # noqa: BLE001 — cualquier fallo de anclaje
            informe["fallidos"].append({"id": nota.get("id"), "error": str(e)})
            continue
        ini = etree.Element(w("bookmarkStart"))
        ini.set(w("id"), str(siguiente))
        ini.set(w("name"), nombre)
        fin = etree.Element(w("bookmarkEnd"))
        fin.set(w("id"), str(siguiente))
        siguiente += 1
        p.insert(0, ini)
        p.append(fin)
        informe["puestos"].append({"id": nota.get("id"), "marcador": nombre, "parrafo": idx, "por": por})

    _escribir(entrada, raiz, salida)
    return informe


# ── Comentarios ────────────────────────────────────────────────────────────────────────────────
COMENTARIOS_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"
COMENTARIOS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"


def _comentarios_existentes(entrada):
    try:
        with zipfile.ZipFile(entrada) as z:
            if "word/comments.xml" in z.namelist():
                return etree.fromstring(z.read("word/comments.xml"))
    except Exception:                                # noqa: BLE001
        pass
    return etree.Element(w("comments"), nsmap={"w": W})


def _con_parte(entrada, extra):
    """Declara word/comments.xml en [Content_Types].xml y en las relaciones del documento."""
    with zipfile.ZipFile(entrada) as z:
        nombres = z.namelist()
        ct = etree.fromstring(z.read("[Content_Types].xml"))
        rels = etree.fromstring(z.read("word/_rels/document.xml.rels"))

    if not any((o.get("PartName") or "") == "/word/comments.xml" for o in ct.iter(f"{{{CT}}}Override")):
        o = etree.SubElement(ct, f"{{{CT}}}Override")
        o.set("PartName", "/word/comments.xml")
        o.set("ContentType", COMENTARIOS_CT)
        extra["[Content_Types].xml"] = etree.tostring(ct, xml_declaration=True, encoding="UTF-8", standalone=True)

    if not any((r.get("Type") or "") == COMENTARIOS_REL for r in rels):
        usados = [int((r.get("Id") or "rId0")[3:] or 0) for r in rels if (r.get("Id") or "").startswith("rId")]
        rel = etree.SubElement(rels, f"{{{R}}}Relationship")
        rel.set("Id", f"rId{max(usados, default=0) + 1}")
        rel.set("Type", COMENTARIOS_REL)
        rel.set("Target", "comments.xml")
        extra["word/_rels/document.xml.rels"] = etree.tostring(rels, xml_declaration=True, encoding="UTF-8", standalone=True)
    return "word/comments.xml" in nombres


def comentarios(entrada, salida, notas, autor="HumanInk"):
    """Deja cada nota como comentario de Word en su párrafo. No toca el texto del documento."""
    raiz = D.leer_xml(entrada)
    cuerpo = raiz.find(w("body")) if raiz.find(w("body")) is not None else raiz
    ps = list(cuerpo.iter(w("p")))
    coms = _comentarios_existentes(entrada)
    usados = [int(c.get(w("id")) or -1) for c in coms.iter(w("comment"))]
    siguiente = max(usados, default=-1) + 1
    ahora = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    informe = {"puestos": [], "fallidos": []}

    for nota in notas or []:
        try:
            p, idx, por = _donde(ps, nota)
        except Exception as e:                       # noqa: BLE001
            informe["fallidos"].append({"id": nota.get("id"), "error": str(e)})
            continue
        cid = str(siguiente)
        siguiente += 1

        c = etree.SubElement(coms, w("comment"))
        c.set(w("id"), cid)
        c.set(w("author"), f"{autor} · {nota.get('id', '')}".strip(" ·"))
        c.set(w("initials"), "HI")
        c.set(w("date"), ahora)
        for linea in [t for t in [nota.get("titulo"), nota.get("problema"), nota.get("arreglo")] if t]:
            cp = etree.SubElement(c, w("p"))
            cpr = etree.SubElement(cp, w("pPr"))
            etree.SubElement(cpr, w("pStyle")).set(w("val"), "CommentText")
            run = etree.SubElement(cp, w("r"))
            ref = etree.SubElement(run, w("rPr"))
            etree.SubElement(ref, w("rStyle")).set(w("val"), "CommentReference")
            t = etree.SubElement(run, w("t"))
            t.text = str(linea)[:2000]
            t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")

        ini = etree.Element(w("commentRangeStart"))
        ini.set(w("id"), cid)
        fin = etree.Element(w("commentRangeEnd"))
        fin.set(w("id"), cid)
        ref_run = etree.Element(w("r"))
        rpr = etree.SubElement(ref_run, w("rPr"))
        etree.SubElement(rpr, w("rStyle")).set(w("val"), "CommentReference")
        etree.SubElement(ref_run, w("commentReference")).set(w("id"), cid)
        p.insert(0, ini)
        p.append(fin)
        p.append(ref_run)
        informe["puestos"].append({"id": nota.get("id"), "comentario": cid, "parrafo": idx, "por": por})

    extra = {"word/comments.xml": etree.tostring(coms, xml_declaration=True, encoding="UTF-8", standalone=True)}
    _con_parte(entrada, extra)
    _escribir(entrada, raiz, salida, extra)
    return informe


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("entrada")
    ap.add_argument("salida")
    ap.add_argument("--notas", required=True, help="JSON con [{id, parrafo, cita, titulo, problema, arreglo}]")
    ap.add_argument("--comentarios", action="store_true", help="además de marcadores, dejar comentarios de Word")
    ap.add_argument("--solo-comentarios", action="store_true")
    ap.add_argument("--autor", default="HumanInk")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    with open(a.notas, encoding="utf-8") as f:
        notas = json.load(f)
    if isinstance(notas, dict):
        notas = notas.get("notas", [])

    if a.solo_comentarios:
        r = comentarios(a.entrada, a.salida, notas, a.autor)
    elif a.comentarios:
        marcadores(a.entrada, a.salida, notas)
        r = comentarios(a.salida, a.salida, notas, a.autor)
        r["marcadores"] = True
    else:
        r = marcadores(a.entrada, a.salida, notas)

    print(json.dumps(r, ensure_ascii=False, indent=2) if a.json else
          f"  ✓ {len(r['puestos'])} notas en el documento" + (f" · {len(r['fallidos'])} sin sitio" if r["fallidos"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
