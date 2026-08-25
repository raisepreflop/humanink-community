#!/usr/bin/env python3
"""verify_docx.py — el contrato de reversibilidad del sistema de builds.

La promesa al autor es "puedes volver atrás siempre". Esa promesa sólo vale si se comprueba, y
hasta ahora no se comprobaba en ninguna parte: ni el plugin, ni Word, ni el ojo humano detectan
que una pasada haya perdido cuatro espacios entre 1.504 sustituciones.

Comprueba tres cosas, en orden de gravedad:

  1. INTEGRIDAD   el .docx abre, el XML está bien formado, las marcas son legales
                  (<w:del> con <w:delText> y no con <w:t>, IDs de revisión sin repetir).
  2. PRESERVACIÓN el build nuevo conserva las tablas, imágenes y estilos del anterior.
                  Un motor que reconstruye el documento las pierde en silencio.
  3. REVERSIBILIDAD  rechazar todos los cambios del build N+1 devuelve EXACTAMENTE el estado
                  del build N. Es el criterio duro: si falla, el rollback es una ilusión.

Cuando (3) falla no basta con decirlo: imprime dónde, palabra a palabra, porque una desviación
de cuatro palabras en un manuscrito de sesenta mil no se encuentra a mano.

Uso:
    verify_docx.py <build.docx>                    # integridad del build suelto
    verify_docx.py <nuevo.docx> --base <ant.docx>  # + preservación + reversibilidad
    verify_docx.py ... --json                      # salida parseable
    verify_docx.py ... --max-diff 40               # cuántas divergencias imprimir

Salida: código 0 si todo pasa, 1 si algo falla. Pensado para encadenar en un workflow.
"""
import argparse
import collections
import difflib
import json
import sys
import zipfile

from lxml import etree

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import docxtc as D  # noqa: E402
from docxtc import w  # noqa: E402


class Resultado:
    """Acumula comprobaciones para poder informar de TODAS, no sólo de la primera que falla."""

    def __init__(self):
        self.checks = []

    def add(self, nombre, ok, detalle="", grave=True):
        self.checks.append({"check": nombre, "ok": bool(ok), "detalle": detalle, "grave": grave})
        return ok

    @property
    def fallos(self):
        return [c for c in self.checks if not c["ok"] and c["grave"]]

    @property
    def avisos(self):
        return [c for c in self.checks if not c["ok"] and not c["grave"]]

    @property
    def ok(self):
        return not self.fallos


# ─────────────────────────── 1. integridad ───────────────────────────

def integridad(ruta, r):
    try:
        with zipfile.ZipFile(ruta) as z:
            malo = z.testzip()
            r.add("zip íntegro", malo is None, f"parte corrupta: {malo}" if malo else "")
            necesarias = {"word/document.xml", "[Content_Types].xml"}
            faltan = necesarias - set(z.namelist())
            r.add("partes obligatorias", not faltan, f"faltan: {', '.join(faltan)}" if faltan else "")
    except zipfile.BadZipFile as e:
        r.add("zip íntegro", False, str(e))
        return None

    try:
        raiz = D.leer_xml(ruta)
    except etree.XMLSyntaxError as e:
        r.add("XML bien formado", False, str(e))
        return None
    r.add("XML bien formado", True)

    # <w:del> debe llevar <w:delText>, nunca <w:t>: Word lo abre igual pero al aceptar los
    # cambios reaparece el texto que creías borrado.
    malos = 0
    for de in raiz.iter(w("del")):
        if de.getparent() is not None and de.getparent().tag == w("rPr"):
            continue  # marca de párrafo, no lleva texto
        if de.findall(f".//{w('t')}"):
            malos += 1
    r.add("w:del usa w:delText", malos == 0,
          f"{malos} marcas de borrado con <w:t> — al aceptar reaparecería el texto")

    # IDs de revisión repetidos: Word se confunde al aceptar/rechazar por bloques.
    ids = [e.get(w("id")) for e in raiz.iter() if e.tag in (w("ins"), w("del")) and e.get(w("id"))]
    dup = [i for i, n in collections.Counter(ids).items() if n > 1]
    r.add("IDs de revisión únicos", not dup,
          f"{len(dup)} repetidos (p. ej. {dup[:5]})" if dup else "")

    # Toda marca debe llevar autor: es el eje por el que el autor acepta en bloque.
    sin_autor = sum(1 for e in raiz.iter()
                    if e.tag in (w("ins"), w("del")) and not e.get(w("author")))
    r.add("marcas con autor", sin_autor == 0,
          f"{sin_autor} marcas sin w:author — no se pueden aceptar por bloques", grave=False)
    return raiz


# ─────────────────────────── 2. preservación ───────────────────────────

def preservacion(nuevo, base, r):
    def rasgos(raiz, ruta):
        with zipfile.ZipFile(ruta) as z:
            medios = [n for n in z.namelist() if n.startswith("word/media/")]
        estilos = {p.get(w("val")) for p in raiz.findall(f".//{w('pStyle')}")}
        return {
            "tablas": len(raiz.findall(f".//{w('tbl')}")),
            "imágenes": len(raiz.findall(f".//{w('drawing')}")),
            "ficheros de medios": len(medios),
            "estilos de párrafo": estilos,
        }

    a, b = rasgos(base, r.base_path), rasgos(nuevo, r.nuevo_path)
    for k in ("tablas", "imágenes", "ficheros de medios"):
        r.add(f"conserva {k}", b[k] >= a[k], f"base {a[k]} → nuevo {b[k]}")
    perdidos = a["estilos de párrafo"] - b["estilos de párrafo"]
    r.add("conserva estilos de párrafo", not perdidos,
          f"perdidos: {', '.join(sorted(x for x in perdidos if x))}" if perdidos else "")


# ─────────────────────────── 3. reversibilidad ───────────────────────────

def reversibilidad(nuevo, base, r, max_diff=25):
    """Rechazar todo en el build nuevo == estado del build anterior."""
    esperado = D.normalizar(D.texto(base, D.ACEPTAR)).split()
    obtenido = D.normalizar(D.texto(nuevo, D.RECHAZAR)).split()

    igual = esperado == obtenido
    detalle = ""
    divergencias = []
    if not igual:
        sm = difflib.SequenceMatcher(None, esperado, obtenido, autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                continue
            divergencias.append({
                "tipo": tag,
                "palabra_n": i1,
                "esperado": " ".join(esperado[i1:i2])[:120],
                "obtenido": " ".join(obtenido[j1:j2])[:120],
            })
        detalle = (f"{len(divergencias)} divergencias · "
                   f"{len(esperado):,} palabras esperadas vs {len(obtenido):,} obtenidas")

    r.add("REVERSIBILIDAD: rechazar todo == build anterior", igual, detalle)
    r.divergencias = divergencias[:max_diff]
    r.total_divergencias = len(divergencias)


# ─────────────────────────── informe ───────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("nuevo", help="el build a verificar")
    ap.add_argument("--base", help="el build anterior (activa preservación y reversibilidad)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--max-diff", type=int, default=25)
    a = ap.parse_args()

    r = Resultado()
    r.nuevo_path, r.base_path = a.nuevo, a.base
    r.divergencias, r.total_divergencias = [], 0

    raiz_nuevo = integridad(a.nuevo, r)
    raiz_base = None
    if a.base and raiz_nuevo is not None:
        raiz_base = D.leer_xml(a.base)
        preservacion(raiz_nuevo, raiz_base, r)
        reversibilidad(raiz_nuevo, raiz_base, r, a.max_diff)

    inv = D.inventario(a.nuevo) if raiz_nuevo is not None else {}

    if a.json:
        print(json.dumps({"ok": r.ok, "checks": r.checks, "inventario": inv,
                          "divergencias": r.divergencias,
                          "total_divergencias": r.total_divergencias},
                         ensure_ascii=False, indent=2))
        return 0 if r.ok else 1

    print(f"\n  Verificación de {a.nuevo}" + (f"  (base: {a.base})" if a.base else ""))
    print("  " + "─" * 66)
    for c in r.checks:
        icono = "✓" if c["ok"] else ("✗" if c["grave"] else "⚠")
        print(f"  {icono} {c['check']:44} {c['detalle']}")

    if inv:
        print(f"\n  {inv['palabras_aceptando']:,} palabras aceptando · "
              f"{inv['palabras_rechazando']:,} rechazando · "
              f"{inv['marcas']} marcas · {inv['tablas']} tablas · {inv['imagenes']} imágenes")
        if inv["autores"]:
            print("\n  Autores de revisión (se aceptan/rechazan por bloque en Word):")
            for autor, n in inv["autores"].items():
                print(f"    {n:>6}  {autor}")

    if r.divergencias:
        print(f"\n  Dónde falla la reversibilidad "
              f"(primeras {len(r.divergencias)} de {r.total_divergencias}):")
        for d in r.divergencias:
            print(f"    palabra ~{d['palabra_n']}")
            print(f"       esperado: {d['esperado']!r}")
            print(f"       obtenido: {d['obtenido']!r}")

    print()
    if r.ok:
        print("  ✅ VERIFICADO" + (" — el rollback está garantizado" if a.base else ""))
    else:
        print(f"  ❌ FALLA ({len(r.fallos)}) — no publicar este build")
    print()
    return 0 if r.ok else 1


if __name__ == "__main__":
    sys.exit(main())
