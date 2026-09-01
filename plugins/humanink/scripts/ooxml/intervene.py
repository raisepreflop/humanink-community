#!/usr/bin/env python3
"""intervene.py — aplica un lote de intervenciones sobre un .docx SIN reconstruirlo.

La diferencia con `md2docx.py --base` es toda: aquél abre el documento, se queda con
`paragraph.text` y escribe uno nuevo desde cero, así que pierde el formato, las tablas, las
imágenes y el control de cambios previo. Aquí se abre el .docx como zip, se opera sobre
`word/document.xml` con lxml **dentro de los `<w:p>` que ya existen**, y todo lo demás del
paquete se copia byte a byte. Lo que no se toca, no cambia.

Dos modos:
    firme      el texto se edita directamente (el build nuevo es el estado nuevo)
    marcado    se generan <w:ins>/<w:del> con autor de revisión, para aceptar/rechazar en Word

El modo marcado se reserva para pasadas mecánicas y masivas (ortotipografía, canon), donde
revisar cambio a cambio es absurdo pero rechazar en bloque por autor es un clic. Las escenas
nuevas entran en firme sobre un build nuevo: el rollback lo da la numeración, no las marcas.

El diff es a nivel de PALABRA dentro del párrafo, no de párrafo entero: reemplazar un adjetivo
marca ese adjetivo, no las trescientas palabras que lo rodean.

Formato del lote (JSON, lista de intervenciones):

    [
      {"op": "reemplazar", "parrafo": 412, "huella": "El coche negro se detuvo",
       "buscar": "muy despacio", "reemplazar": "sin prisa",
       "autor": "Fase 6 · adverbios", "motivo": "adverbio por verbo exacto"},

      {"op": "insertar_despues", "parrafo": 800, "huella": "cerró la puerta",
       "texto": ["Párrafo nuevo uno.", "Párrafo nuevo dos."],
       "autor": "Fase 5 · el embarcadero"},

      {"op": "borrar_parrafo", "parrafo": 1201, "huella": "Como decíamos antes,",
       "autor": "Fase 1 · poda"}
    ]

El **anclaje** es doble: índice de párrafo + huella de texto. Si la huella no está donde dice el
índice, se busca en una ventana alrededor; si tampoco, la intervención FALLA y se informa. Nunca
se aplica a ciegas: un ancla que se ha movido y se aplica igual corrompe el manuscrito en
silencio, que es el peor fallo posible en un libro.

Uso:
    intervene.py <entrada.docx> <salida.docx> --lote lote.json [--marcado] [--autor "X"]
    intervene.py <entrada.docx> --listar [--desde N] [--hasta N]   # índices y huellas
    intervene.py ... --dry-run                                     # sin escribir nada
"""
import argparse
import copy
import json
import re
import shutil
import sys
import zipfile
from datetime import datetime, timezone

from lxml import etree

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import docxtc as D  # noqa: E402
from docxtc import w  # noqa: E402

FECHA = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class ErrorDeAnclaje(Exception):
    """El ancla no se encontró. Nunca se aplica una intervención a ciegas."""


# ─────────────────────── utilidades de runs ───────────────────────

def _es_vivo(run):
    """¿Este <w:r> forma parte del texto actual? (no está dentro de un <w:del>)"""
    n = run.getparent()
    while n is not None:
        if n.tag == w("del"):
            return False
        if n.tag == w("p"):
            return True
        n = n.getparent()
    return True


def _runs_vivos(p):
    """[(run, texto, ini, fin)] sobre el texto visible del párrafo, en orden."""
    fuera, pos = [], 0
    for r in p.iter(w("r")):
        if not _es_vivo(r):
            continue
        t = "".join(n.text or "" for n in r if n.tag == w("t"))
        if not t:
            continue
        fuera.append([r, t, pos, pos + len(t)])
        pos += len(t)
    return fuera


def _en_tabla(p):
    """¿Este párrafo está dentro de una tabla?

    Importa para el BORRADO, que es la operación destructiva: una celda vacía deja la tabla con
    una fila fantasma y el autor no entiende qué ha pasado. Y es un caso real, no teórico: el
    texto que extrae `docxtc` incluye las celdas, así que un diff del documento entero contra una
    propuesta que solo trae la prosa las lee como líneas borradas.
    """
    n = p.getparent()
    while n is not None:
        if n.tag == w("tbl"):
            return True
        n = n.getparent()
    return False


def _texto_vivo(p):
    return "".join(x[1] for x in _runs_vivos(p))


def _clonar_run(run, texto, borrado=False):
    """Copia un <w:r> con su formato (rPr) y otro texto. delText si va dentro de <w:del>."""
    nuevo = copy.deepcopy(run)
    for hijo in list(nuevo):
        if hijo.tag in (w("t"), w("delText"), w("tab"), w("br"), w("cr")):
            nuevo.remove(hijo)
    et = etree.SubElement(nuevo, w("delText") if borrado else w("t"))
    et.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    et.text = texto
    return nuevo


def _marca(tag, autor, contador):
    e = etree.Element(w(tag))
    e.set(w("id"), str(next(contador)))
    e.set(w("author"), autor)
    e.set(w("date"), FECHA)
    return e


def _partir_run(entrada, desplazamiento):
    """Parte un run en dos por un desplazamiento local. Devuelve (izquierda, derecha)."""
    run, texto = entrada[0], entrada[1]
    izq = _clonar_run(run, texto[:desplazamiento]) if desplazamiento > 0 else None
    der = _clonar_run(run, texto[desplazamiento:]) if desplazamiento < len(texto) else None
    return izq, der


# ─────────────────────── operaciones ───────────────────────

def op_reemplazar(p, buscar, reemplazar, autor, marcado, contador):
    """Sustituye `buscar` por `reemplazar` dentro del párrafo, preservando el formato.

    Localiza el tramo sobre el texto vivo (que puede cruzar varios runs), parte los runs por
    los bordes exactos y reconstruye: [antes] [del: viejo] [ins: nuevo] [después].
    """
    vivos = _runs_vivos(p)
    if not vivos:
        raise ErrorDeAnclaje("párrafo sin texto vivo")
    completo = "".join(x[1] for x in vivos)
    i = completo.find(buscar)
    if i < 0:
        raise ErrorDeAnclaje(f"no encuentro {buscar!r} en el párrafo")
    if completo.find(buscar, i + 1) >= 0:
        raise ErrorDeAnclaje(f"{buscar!r} aparece más de una vez: amplía el fragmento")
    j = i + len(buscar)

    afectados = [x for x in vivos if x[3] > i and x[2] < j]
    primero, ultimo = afectados[0], afectados[-1]
    ancla = primero[0]
    padre = ancla.getparent()
    posicion = list(padre).index(ancla)

    izq, _ = _partir_run(primero, i - primero[2])
    _, der = _partir_run(ultimo, j - ultimo[2])

    nuevos = []
    if izq is not None:
        nuevos.append(izq)
    if marcado:
        if buscar:
            d = _marca("del", autor, contador)
            d.append(_clonar_run(primero[0], buscar, borrado=True))
            nuevos.append(d)
        if reemplazar:
            ins = _marca("ins", autor, contador)
            ins.append(_clonar_run(primero[0], reemplazar))
            nuevos.append(ins)
    elif reemplazar:
        nuevos.append(_clonar_run(primero[0], reemplazar))
    if der is not None:
        nuevos.append(der)

    for x in afectados:                       # fuera los originales
        x[0].getparent().remove(x[0])
    for k, e in enumerate(nuevos):            # dentro los nuevos, en su sitio
        padre.insert(posicion + k, e)
    return 1


def op_insertar_despues(p, textos, autor, marcado, contador):
    """Añade párrafos nuevos detrás de `p`, heredando su estilo."""
    padre = p.getparent()
    pos = list(padre).index(p)
    for k, t in enumerate(textos):
        nuevo = etree.Element(w("p"))
        ppr_orig = p.find(w("pPr"))
        if ppr_orig is not None:
            ppr = copy.deepcopy(ppr_orig)
            for basura in ppr.findall(w("rPr")):
                ppr.remove(basura)
            nuevo.append(ppr)
        if marcado:
            # la MARCA de párrafo va insertada: al rechazar, el salto desaparece
            ppr = nuevo.find(w("pPr"))
            if ppr is None:
                ppr = etree.SubElement(nuevo, w("pPr"))
            rpr = etree.SubElement(ppr, w("rPr"))
            rpr.append(_marca("ins", autor, contador))
            ins = _marca("ins", autor, contador)
            r = etree.SubElement(ins, w("r"))
            et = etree.SubElement(r, w("t"))
            et.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            et.text = t
            nuevo.append(ins)
        else:
            r = etree.SubElement(nuevo, w("r"))
            et = etree.SubElement(r, w("t"))
            et.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            et.text = t
        padre.insert(pos + 1 + k, nuevo)
    return len(textos)


def op_borrar_parrafo(p, autor, marcado, contador):
    """Elimina el párrafo. En modo marcado se marca el texto y la marca de fin como borrados."""
    if not marcado:
        p.getparent().remove(p)
        return 1
    vivos = _runs_vivos(p)
    for run, texto, _, _ in vivos:
        padre = run.getparent()
        pos = list(padre).index(run)
        d = _marca("del", autor, contador)
        d.append(_clonar_run(run, texto, borrado=True))
        padre.remove(run)
        padre.insert(pos, d)
    ppr = p.find(w("pPr"))
    if ppr is None:
        ppr = etree.Element(w("pPr"))
        p.insert(0, ppr)
    rpr = ppr.find(w("rPr"))
    if rpr is None:
        rpr = etree.SubElement(ppr, w("rPr"))
    rpr.append(_marca("del", autor, contador))
    return 1


# ─────────────────────── anclaje ───────────────────────

def _normaliza(s):
    return re.sub(r"\s+", " ", s).strip()


def localizar(parrafos_xml, indice, huella, ventana=60):
    """El <w:p> que toca. Índice como pista, huella como prueba.

    Un manuscrito se mueve: si la pasada anterior insertó tres párrafos, todos los índices
    posteriores se han desplazado. Por eso la huella manda sobre el índice.
    """
    n = len(parrafos_xml)
    if not huella:
        if not 0 <= indice < n:
            raise ErrorDeAnclaje(f"índice {indice} fuera de rango (0-{n-1})")
        return parrafos_xml[indice], indice, 0
    h = _normaliza(huella)

    if 0 <= indice < n and h in _normaliza(_texto_vivo(parrafos_xml[indice])):
        return parrafos_xml[indice], indice, 0

    candidatos = []
    for d in range(1, ventana + 1):
        for i in (indice - d, indice + d):
            if 0 <= i < n and h in _normaliza(_texto_vivo(parrafos_xml[i])):
                candidatos.append((i, d))
        if candidatos:
            break
    if len(candidatos) == 1:
        i, d = candidatos[0]
        return parrafos_xml[i], i, i - indice
    if len(candidatos) > 1:
        raise ErrorDeAnclaje(
            f"huella ambigua cerca de {indice}: aparece en {[i for i, _ in candidatos]}")

    globales = [i for i in range(n) if h in _normaliza(_texto_vivo(parrafos_xml[i]))]
    if len(globales) == 1:
        return parrafos_xml[globales[0]], globales[0], globales[0] - indice
    if not globales:
        raise ErrorDeAnclaje(f"huella {huella!r} no aparece en el documento")
    raise ErrorDeAnclaje(f"huella {huella!r} aparece {len(globales)} veces: hazla más específica")


def huella_de(parrafos_xml, indice, minimo=30, maximo=200):
    """El prefijo más corto de este párrafo que solo aparece en ÉL.

    Quien acuña el ancla tiene que ser el mismo código que la resuelve, y por eso esto vive aquí
    y no en el cliente: la huella se compara normalizada (`_normaliza`), y una reimplementación
    en otro lenguaje que no colapse los espacios igual produce anclas que `localizar` rechaza —o,
    peor, que casan donde no deben.

    Devuelve None cuando el párrafo se repite entero en el documento (encabezados, separadores).
    Decir «aquí no hay ancla honesta» es mejor que dar una que después falle por ambigua.
    """
    texto = _normaliza(_texto_vivo(parrafos_xml[indice]))
    if not texto:
        return None
    otros = [_normaliza(_texto_vivo(p)) for j, p in enumerate(parrafos_xml) if j != indice]
    largo = min(minimo, len(texto))
    while largo <= min(maximo, len(texto)):
        cand = texto[:largo]
        if not any(cand in o for o in otros):
            return cand
        largo += 10
    # Ni el párrafo entero (hasta el tope) distingue: es un duplicado.
    return None


# ─────────────────────── aplicación del lote ───────────────────────

def _siguiente_id(raiz):
    usados = [int(e.get(w("id")) or 0) for e in raiz.iter()
              if e.tag in (w("ins"), w("del")) and (e.get(w("id")) or "").isdigit()]
    n = max(usados) + 1 if usados else 1

    def contador():
        k = n
        while True:
            yield k
            k += 1
    return contador()


def aplicar(entrada, salida, lote, marcado=False, autor_defecto="HumanInk", dry_run=False,
            activar_track=False):
    raiz = D.leer_xml(entrada)
    cuerpo = raiz.find(w("body")) if raiz.find(w("body")) is not None else raiz
    parrafos_xml = list(cuerpo.iter(w("p")))
    contador = _siguiente_id(raiz)

    informe = {"aplicadas": 0, "fallidas": 0, "detalle": []}

    # De atrás hacia delante: así una inserción no desplaza los índices de las siguientes.
    for k, iv in sorted(enumerate(lote), key=lambda x: -(x[1].get("parrafo") or 0)):
        op = iv.get("op", "reemplazar")
        autor = iv.get("autor") or autor_defecto
        linea = {"n": k, "op": op, "autor": autor, "motivo": iv.get("motivo", "")}
        try:
            p, idx, desvio = localizar(parrafos_xml, iv.get("parrafo", 0), iv.get("huella", ""))
            linea["parrafo"] = idx
            if desvio:
                linea["aviso"] = f"ancla desplazada {desvio:+d} párrafos"

            if op == "reemplazar":
                op_reemplazar(p, iv["buscar"], iv.get("reemplazar", ""), autor, marcado, contador)
            elif op == "insertar_despues":
                textos = iv["texto"] if isinstance(iv["texto"], list) else [iv["texto"]]
                op_insertar_despues(p, textos, autor, marcado, contador)
            elif op == "borrar_parrafo":
                op_borrar_parrafo(p, autor, marcado, contador)
            else:
                raise ErrorDeAnclaje(f"operación desconocida: {op}")
            linea["ok"] = True
            informe["aplicadas"] += 1
        except (ErrorDeAnclaje, KeyError) as e:
            linea["ok"] = False
            linea["error"] = str(e)
            informe["fallidas"] += 1
        informe["detalle"].append(linea)

    informe["detalle"].sort(key=lambda x: x["n"])

    if dry_run:
        return informe

    if activar_track:
        _activar_track_changes(entrada, raiz, salida)
    else:
        _escribir(entrada, raiz, salida)
    return informe


def _escribir(entrada, raiz, salida, extra=None):
    """Copia el paquete entero y sustituye sólo document.xml. Lo demás, byte a byte."""
    extra = extra or {}
    nuevo = etree.tostring(raiz, xml_declaration=True, encoding="UTF-8", standalone=True)
    if entrada != salida:
        shutil.copyfile(entrada, salida)
    with zipfile.ZipFile(entrada) as z_in:
        items = [(i, z_in.read(i.filename)) for i in z_in.infolist()]
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as z_out:
        for info, datos in items:
            if info.filename == "word/document.xml":
                datos = nuevo
            elif info.filename in extra:
                datos = extra[info.filename]
            z_out.writestr(info, datos)


def _activar_track_changes(entrada, raiz, salida):
    """Deja el documento en modo revisión, para que el autor siga marcando al editar."""
    extra = {}
    try:
        with zipfile.ZipFile(entrada) as z:
            if "word/settings.xml" in z.namelist():
                s = etree.fromstring(z.read("word/settings.xml"))
                if s.find(w("trackChanges")) is None:
                    s.insert(0, etree.Element(w("trackChanges")))
                extra["word/settings.xml"] = etree.tostring(
                    s, xml_declaration=True, encoding="UTF-8", standalone=True)
    except Exception:
        pass  # sin settings.xml el documento funciona igual; no vale la pena fallar por esto
    _escribir(entrada, raiz, salida, extra)


# ─────────────────────── CLI ───────────────────────

def parrafos_de(entrada):
    """Los <w:p> del cuerpo, que es sobre lo que se ancla todo."""
    raiz = D.leer_xml(entrada)
    cuerpo = raiz.find(w("body")) if raiz.find(w("body")) is not None else raiz
    return list(cuerpo.iter(w("p")))


def listar(entrada, desde, hasta, ancho=90, como_json=False):
    ps = parrafos_de(entrada)
    hasta = min(hasta if hasta is not None else len(ps), len(ps))
    desde = max(desde, 0)

    if not como_json:
        for i in range(desde, hasta):
            t = _normaliza(_texto_vivo(ps[i]))
            if t:
                print(f"{i:>5}  {t[:ancho]}")
        return

    # El JSON NO trunca. El texto de la vista de arriba se corta a 90 caracteres porque lo lee
    # una persona; este lo lee el motor para calcular `buscar`, que se compara EN CRUDO contra
    # el texto vivo. Un texto recortado produciría un `buscar` que no existe en el párrafo.
    salida = []
    for i in range(desde, hasta):
        vivo = _texto_vivo(ps[i])
        if not vivo.strip():
            continue
        salida.append({
            "i": i,
            "texto": vivo,
            "palabras": len(vivo.split()),
            "huella": huella_de(ps, i),
        })
    print(json.dumps({
        "fichero": entrada,
        "sha256": D.sha256_de(entrada),
        "total": len(ps),
        "parrafos": salida,
    }, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("entrada")
    ap.add_argument("salida", nargs="?")
    ap.add_argument("--lote", help="JSON con la lista de intervenciones")
    ap.add_argument("--marcado", action="store_true", help="genera w:ins/w:del en vez de editar en firme")
    ap.add_argument("--autor", default="HumanInk", help="autor de revisión por defecto")
    ap.add_argument("--activar-track", action="store_true", help="deja Word en modo revisión")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--listar", action="store_true", help="imprime índice y texto de cada párrafo")
    ap.add_argument("--desde", type=int, default=0)
    ap.add_argument("--hasta", type=int)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.listar:
        listar(a.entrada, a.desde, a.hasta, como_json=a.json)
        return 0

    if not a.lote:
        ap.error("hace falta --lote (o --listar)")
    with open(a.lote, encoding="utf-8") as f:
        lote = json.load(f)
    if not a.salida and not a.dry_run:
        ap.error("hace falta la salida (o --dry-run)")

    inf = aplicar(a.entrada, a.salida, lote, a.marcado, a.autor, a.dry_run, a.activar_track)

    if a.json:
        print(json.dumps(inf, ensure_ascii=False, indent=2))
    else:
        print(f"\n  {inf['aplicadas']} aplicadas · {inf['fallidas']} fallidas"
              f"{'  (dry-run: no se ha escrito nada)' if a.dry_run else ''}")
        for d in inf["detalle"]:
            if d["ok"]:
                aviso = f"  ⚠ {d['aviso']}" if d.get("aviso") else ""
                print(f"   ✓ [{d['n']}] {d['op']:18} párrafo {d.get('parrafo')}"
                      f"  {d['autor']}{aviso}")
            else:
                print(f"   ✗ [{d['n']}] {d['op']:18} {d['error']}")
        if not a.dry_run and inf["aplicadas"]:
            print(f"\n  → {a.salida}")
            print("  Verifica antes de seguir:")
            print(f"     python3 verify_docx.py {a.salida} --base {a.entrada}")
        print()
    return 1 if inf["fallidas"] else 0


if __name__ == "__main__":
    sys.exit(main())
