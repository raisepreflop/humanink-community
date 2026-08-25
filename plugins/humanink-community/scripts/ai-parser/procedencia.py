#!/usr/bin/env python3
"""procedencia.py — qué marcas lleva de verdad un fichero.

Desde el 2 de agosto de 2026, Anthropic marca todo el texto que genera Claude (art. 50(2) del
Reglamento europeo de IA) y firma metadatos C2PA en las imágenes. Alcanza a Cowork, así que
alcanza a todo lo que producen los plugins de HumanInk. Un autor no tiene forma de saber qué
lleva dentro su propio manuscrito. Esto se lo dice.

QUÉ DETECTA — y qué NO, que es igual de importante:

  ✅ Caracteres invisibles     unicode de ancho cero, uniones, guiones blandos, homoglifos
  ✅ C2PA en imágenes          manifiestos dentro de word/media/ del .docx y en imágenes sueltas
  ✅ Metadatos del documento   docProps/core.xml y app.xml: quién, con qué, cuándo
  ❌ La marca de texto de Claude

Ese último NO es un olvido. Anthropic dice que "está trabajando para permitir que usuarios y
terceros detecten" sus marcas: **el detector todavía no existe**. Y no es cuestión de esfuerzo —
un watermark estadístico es indetectable sin la clave o sin un verificador del proveedor. Cuando
Anthropic lo publique, se integra aquí. Hasta entonces, este script NO puede decir si un texto
salió de Claude, y no lo va a fingir.

Corolario que va impreso en cada informe: **no encontrar marcas no significa que el texto sea
humano.** Significa que no se han encontrado marcas de las que se saben buscar.

Uso:
    procedencia.py <fichero.docx|.md|.txt|.png|.jpg>  [--json]
"""
import argparse
import json
import os
import re
import sys
import unicodedata
import zipfile

# ── Caracteres invisibles ──────────────────────────────────────────────────────
# Se clasifican por riesgo porque no todos son sospechosos: un espacio duro puede venir de Word y
# ser perfectamente legítimo, mientras que un ancho cero entre palabras no llega ahí solo.
INVISIBLES = {
    "​": ("ESPACIO DE ANCHO CERO", "alto"),
    "‌": ("NO-JUNTADOR DE ANCHO CERO", "alto"),
    "‍": ("JUNTADOR DE ANCHO CERO", "alto"),
    "⁠": ("JUNTADOR DE PALABRAS", "alto"),
    "﻿": ("MARCA DE ORDEN DE BYTES", "alto"),
    "᠎": ("SEPARADOR VOCAL MONGOL", "alto"),
    "­": ("GUIÓN BLANDO", "medio"),
    " ": ("SEPARADOR DE LÍNEA", "medio"),
    " ": ("SEPARADOR DE PÁRRAFO", "medio"),
    " ": ("ESPACIO FINO INSEPARABLE", "bajo"),
    " ": ("ESPACIO FINO", "bajo"),
    " ": ("ESPACIO INSEPARABLE", "bajo"),
}
# Marcas de dirección: legítimas en textos con árabe o hebreo, sospechosas en un texto español.
BIDI = {"‪", "‫", "‬", "‭", "‮", "⁦", "⁧", "⁨", "⁩"}

# Cirílicos y griegos que se ven idénticos a una letra latina. En un texto en español, uno solo
# ya es raro; varios son señal de que el texto pasó por una herramienta que los sustituyó.
HOMOGLIFOS = {
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x",
    "у": "y", "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M",
    "Н": "H", "О": "O", "Р": "P", "С": "C", "Т": "T", "Х": "X",
    "ο": "o", "α": "a", "Α": "A", "Β": "B", "Ε": "E", "Ο": "O",
}

# Firmas de C2PA dentro de los bytes de una imagen. C2PA guarda el manifiesto en una caja JUMBF
# (ISO/IEC 19566-5): en JPEG viaja en un marcador APP11, en PNG en un chunk `caBX`.
FIRMAS_C2PA = [b"jumb", b"c2pa", b"caBX", b"urn:uuid:", b"c2pa.assertions"]


def _contexto(texto, i, ancho=28):
    ini, fin = max(0, i - ancho), min(len(texto), i + ancho)
    frag = texto[ini:fin].replace("\n", "⏎")
    return ("…" if ini else "") + frag + ("…" if fin < len(texto) else "")


def invisibles(texto):
    """Caracteres que el ojo no ve pero que viajan en el fichero."""
    hallazgos = {}
    for i, ch in enumerate(texto):
        if ch in INVISIBLES:
            nombre, riesgo = INVISIBLES[ch]
        elif ch in BIDI:
            nombre, riesgo = ("CONTROL DE DIRECCIÓN", "alto")
        else:
            continue
        cp = f"U+{ord(ch):04X}"
        d = hallazgos.setdefault(cp, {"nombre": nombre, "riesgo": riesgo, "casos": 0, "ejemplos": []})
        d["casos"] += 1
        if len(d["ejemplos"]) < 3:
            d["ejemplos"].append(_contexto(texto, i))
    return hallazgos


def homoglifos(texto):
    """Letras cirílicas o griegas coladas en palabras latinas."""
    fuera = []
    for m in re.finditer(r"\w+", texto):
        pal = m.group(0)
        sosp = [(c, HOMOGLIFOS[c]) for c in pal if c in HOMOGLIFOS]
        if not sosp:
            continue
        # Sólo cuenta si la palabra es MAYORITARIAMENTE latina: una palabra entera en cirílico
        # es ruso, no una trampa.
        latinas = sum(1 for c in pal if "LATIN" in unicodedata.name(c, ""))
        if latinas == 0:
            continue
        fuera.append({
            "palabra": pal,
            "sustituciones": [{"cp": f"U+{ord(c):04X}", "parece": p} for c, p in sosp],
            "contexto": _contexto(texto, m.start()),
        })
    return fuera


def c2pa_en_bytes(datos):
    """¿Estos bytes de imagen contienen un manifiesto C2PA?

    Detecta la PRESENCIA, no valida la firma: validar exige la cadena de confianza y `c2patool`.
    Decirlo importa — "tiene manifiesto" no es lo mismo que "manifiesto válido".
    """
    cabeza = datos[:200_000]
    encontradas = [f.decode("latin-1") for f in FIRMAS_C2PA if f in cabeza]
    if not encontradas:
        return None
    generador = None
    for m in re.finditer(rb'"(?:claim_generator|softwareAgent)"\s*:\s*"([^"]{2,120})"', cabeza):
        generador = m.group(1).decode("utf-8", "replace")
        break
    return {"firmas": encontradas, "generador": generador}


def metadatos_docx(ruta):
    """Quién dice el documento que lo hizo, con qué y cuándo."""
    fuera = {}
    try:
        with zipfile.ZipFile(ruta) as z:
            nombres = z.namelist()
            for parte, campos in (
                ("docProps/core.xml", ["creator", "lastModifiedBy", "created", "modified", "title", "revision"]),
                ("docProps/app.xml", ["Application", "AppVersion", "Company", "TotalTime"]),
            ):
                if parte not in nombres:
                    continue
                xml = z.read(parte).decode("utf-8", "replace")
                for c in campos:
                    m = re.search(rf"<(?:\w+:)?{c}[^>]*>([^<]*)</(?:\w+:)?{c}>", xml)
                    if m and m.group(1).strip():
                        fuera[c] = m.group(1).strip()
    except Exception:
        pass
    return fuera


def imagenes_docx(ruta):
    """Las imágenes incrustadas y su procedencia. Aquí es donde C2PA sí viaja dentro de un .docx:
    Word no lleva C2PA, pero una imagen generada por IA y pegada dentro sí lo conserva."""
    fuera = []
    try:
        with zipfile.ZipFile(ruta) as z:
            for n in z.namelist():
                if not n.startswith("word/media/"):
                    continue
                datos = z.read(n)
                fuera.append({
                    "fichero": n.split("/")[-1],
                    "bytes": len(datos),
                    "c2pa": c2pa_en_bytes(datos),
                })
    except Exception:
        pass
    return fuera


def texto_de(ruta):
    if ruta.lower().endswith(".docx"):
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ooxml"))
            import docxtc as D
            return D.texto(ruta, D.ACEPTAR)
        except Exception:
            try:
                from docx import Document
                return "\n".join(p.text for p in Document(ruta).paragraphs)
            except Exception:
                return ""
    if ruta.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".svg")):
        return ""
    try:
        with open(ruta, encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return ""


def escanear(ruta):
    es_imagen = ruta.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".svg"))
    texto = texto_de(ruta)
    r = {
        "fichero": os.path.basename(ruta),
        "tipo": "imagen" if es_imagen else ("docx" if ruta.lower().endswith(".docx") else "texto"),
        "palabras": len(texto.split()),
        "invisibles": invisibles(texto) if texto else {},
        "homoglifos": homoglifos(texto) if texto else [],
        "metadatos": metadatos_docx(ruta) if ruta.lower().endswith(".docx") else {},
        "imagenes": imagenes_docx(ruta) if ruta.lower().endswith(".docx") else [],
        "marca_de_texto": {
            "detectada": None,
            "motivo": "No hay detector público. Anthropic ha anunciado que trabaja en permitir "
                      "la detección por terceros; hasta que lo publique, la marca del texto no se "
                      "puede comprobar desde fuera.",
        },
    }
    if es_imagen:
        try:
            with open(ruta, "rb") as f:
                r["imagenes"] = [{"fichero": r["fichero"], "bytes": os.path.getsize(ruta),
                                  "c2pa": c2pa_en_bytes(f.read())}]
        except Exception:
            pass
    return r


AVISO = ("No encontrar marcas NO significa que el texto sea humano: significa que no se han "
         "encontrado las marcas que este escáner sabe buscar.")


def imprimir(r):
    print(f"\n  Procedencia · {r['fichero']}"
          + (f"  ({r['palabras']:,} palabras)" if r["palabras"] else ""))
    print("  " + "─" * 68)

    inv = r["invisibles"]
    if inv:
        altos = sum(d["casos"] for d in inv.values() if d["riesgo"] == "alto")
        print(f"  ⚠ Caracteres invisibles: {sum(d['casos'] for d in inv.values())} "
              f"({altos} de riesgo alto)")
        for cp, d in sorted(inv.items(), key=lambda kv: -kv[1]["casos"]):
            marca = {"alto": "❗", "medio": "·", "bajo": " "}[d["riesgo"]]
            print(f"    {marca} {cp}  {d['nombre']:32} {d['casos']:>5}")
            if d["riesgo"] == "alto":
                for e in d["ejemplos"][:2]:
                    print(f"         {e!r}")
    else:
        print("  ✓ Sin caracteres invisibles")

    if r["homoglifos"]:
        print(f"  ⚠ Homoglifos (letras cirílicas/griegas en palabras latinas): {len(r['homoglifos'])}")
        for h in r["homoglifos"][:6]:
            subs = ", ".join(f"{s['cp']}→{s['parece']}" for s in h["sustituciones"])
            print(f"    {h['palabra']!r}  ({subs})")
    elif r["palabras"]:
        print("  ✓ Sin homoglifos")

    if r["imagenes"]:
        con = [i for i in r["imagenes"] if i["c2pa"]]
        print(f"  {'⚠' if con else '✓'} Imágenes: {len(r['imagenes'])} · con manifiesto C2PA: {len(con)}")
        for i in con:
            gen = i["c2pa"].get("generador") or "(generador no legible)"
            print(f"    {i['fichero']}  →  {gen}")
        if con:
            print("      (se detecta el manifiesto; validar la firma exige c2patool)")

    if r["metadatos"]:
        print("  · Metadatos del documento:")
        for k, v in r["metadatos"].items():
            print(f"      {k:16} {v[:60]}")

    print(f"\n  Marca de texto de Claude: NO COMPROBABLE")
    print(f"    {r['marca_de_texto']['motivo']}")
    print(f"\n  ⚠️  {AVISO}\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fichero")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if not os.path.exists(a.fichero):
        sys.exit(f"No existe: {a.fichero}")
    r = escanear(a.fichero)
    if a.json:
        r["aviso"] = AVISO
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        imprimir(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
