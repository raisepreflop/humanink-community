#!/usr/bin/env python3
"""fase0_scan.py — inventario de los defectos mecánicos de un manuscrito.

Cuenta, no arregla. Su salida es lo que el colaborador Fase 0 cita al autor antes de proponer
nada, para que las cifras del acta sean medidas y no estimadas.

Mira siete cosas, todas objetivas:

  1. Dobles guiones por FUNCIÓN (apertura de parlamento / apertura de inciso / cierre), porque
     cada una lleva un espaciado distinto en norma RAE y un reemplazo global ciego crea cientos
     de errores nuevos donde había uno solo.
  2. Comillas rectas y puntos suspensivos de tres puntos.
  3. Tildes sistemáticas candidatas — CANDIDATAS: la decisión es caso por caso.
  4. Capítulos que no usan estilo de encabezado (se ven bien pero no salen en el índice).
  5. Capítulos sin ningún corte de escena, con sus saltos detectados.
  6. Nombres propios con variantes cercanas (el canon que baila).
  7. Párrafos por encima del techo de longitud.

Uso:  fase0_scan.py <manuscrito.docx> [--json] [--techo 120]
"""
import argparse
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import docxtc as D  # noqa: E402
from docxtc import w  # noqa: E402

# Palabras que se escriben sin tilde por error de mecanografía y cuya forma con tilde es la
# frecuente en narrativa. Son CANDIDATAS: cada una se decide mirando su contexto.
TILDES = {
    "tenia": "tenía", "sabia": "sabía", "seria": "sería", "habia": "había",
    "ejercito": "ejército", "miro": "miró", "afirmo": "afirmó", "pregunto": "preguntó",
    "contesto": "contestó", "entro": "entró", "continuo": "continuó", "numero": "número",
    "ultima": "última", "ultimo": "último", "ingles": "inglés", "asi": "así",
    "aqui": "aquí", "alli": "allí", "despues": "después", "tambien": "también",
    "quiza": "quizá", "aun": "aún", "mas": "más", "solo": "sólo",
}
AMBIGUAS = {"seria", "continuo", "numero", "mas", "solo", "aun", "pregunto", "miro"}

CAP = re.compile(r"^\s*(cap[íi]tulo\s+[\wáéíóú]+|[IVXLC]+\.?|\d+\.?)\s*$", re.I)
CORTE = re.compile(r"^\s*(\*\s*\*\s*\*|---|—{3,}|#{3,}|~{3,})\s*$")
PROPIO = re.compile(r"\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,}\b")
COMUNES = {"El", "La", "Los", "Las", "Un", "Una", "Su", "Sus", "Este", "Esta", "Eso", "Aquel",
           "Cuando", "Porque", "Pero", "Aunque", "Entonces", "Ahora", "Todo", "Nada", "Nunca",
           "Siempre", "Como", "Desde", "Hasta", "Para", "Por", "Sin", "Con", "Que", "Qué",
           "Quién", "Dónde", "Después", "Antes", "Mientras", "Durante", "Sobre", "Bajo"}


def distancia(a, b):
    """Levenshtein sencillo. Suficiente para 'Maerst' vs 'Maerts'."""
    if abs(len(a) - len(b)) > 2:
        return 9
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def guiones_por_funcion(parrafos):
    """Clasifica los `--` según lo que hacen. La diferencia decide el espaciado correcto."""
    apertura = inciso_abre = inciso_cierra = 0
    for p in parrafos:
        s = p.strip()
        if not s or "--" not in s:
            continue
        pos = [m.start() for m in re.finditer(r"--", s)]
        for k, i in enumerate(pos):
            if i == 0 and k == 0:
                apertura += 1                        # abre parlamento
            elif i + 2 < len(s) and s[i + 2] in " ":
                inciso_cierra += 1                   # `--dijo Juan-- y luego`
            else:
                inciso_abre += 1
    return {"apertura_parlamento": apertura, "apertura_inciso": inciso_abre,
            "cierre_inciso": inciso_cierra,
            "total": apertura + inciso_abre + inciso_cierra}


def encabezados(ruta):
    """Capítulos que son párrafo suelto en vez de estilo de encabezado."""
    raiz = D.leer_xml(ruta)
    cuerpo = raiz.find(w("body")) if raiz.find(w("body")) is not None else raiz
    con_estilo, sin_estilo = [], []
    for i, p in enumerate(cuerpo.iter(w("p"))):
        t = D.texto_de_parrafo(p, D.ACEPTAR).strip()
        if not t or len(t) > 60:
            continue
        est = p.find(f"{w('pPr')}/{w('pStyle')}")
        val = est.get(w("val")) if est is not None else None
        if val and ("eading" in val or "tulo" in val or "itle" in val):
            con_estilo.append(t)
        elif CAP.match(t):
            sin_estilo.append({"parrafo": i, "texto": t})
    return {"con_estilo": len(con_estilo), "sin_estilo": sin_estilo}


def cortes_por_capitulo(parrafos):
    """Capítulos sin ninguna marca de corte. Los que más los necesitan son los que tienen 0."""
    caps, actual = [], {"titulo": "(preliminares)", "parrafos": 0, "cortes": 0}
    for p in parrafos:
        s = p.strip()
        if CAP.match(s) and len(s) < 60:
            caps.append(actual)
            actual = {"titulo": s, "parrafos": 0, "cortes": 0}
        elif CORTE.match(s):
            actual["cortes"] += 1
        elif s:
            actual["parrafos"] += 1
    caps.append(actual)
    return [c for c in caps if c["parrafos"] > 20]


def canon(texto, minimo=5):
    """Nombres propios con variantes que parecen ERRATAS, no nombres distintos.

    El filtro es lo difícil. Buscar simplemente "palabras parecidas en mayúscula" devuelve
    montañas de ruido: *Era*, *Eva*, *Ana* se parecen entre sí y no son nada, y *Jerry* / *Jersey*
    se parecen y son dos personajes distintos. Un aviso con cien falsos positivos no lo lee nadie,
    así que se exige que la variante se comporte como errata:

      · Sólo cuenta como nombre lo que aparece ALGUNA vez en mitad de frase. Una palabra que
        siempre va tras punto es una palabra común en mayúscula, no un nombre.
      · La variante tiene que ser RARA en absoluto (≤ 4 casos) y marginal frente a la forma
        principal (< 5 %). *Andreu* 4 frente a *Andrew* 374 es una errata; *Jersey* 20 frente a
        *Jerry* 331 es otro personaje.
    """
    # Un token es "nombre" si suele aparecer en MITAD de frase. Una palabra común en mayúscula
    # sólo aparece tras un final de frase, tras raya de diálogo o tras comilla de apertura —
    # olvidarse de la raya es lo que inundaba esto de "Hola", "Vaya" y "Todos".
    ARRANQUE = re.compile(r"(?:^|[.!?…:;]\s*|\n|[—–]\s*|--\s*|[«\"“¿¡(]\s*)$")
    medio_frase = collections.Counter()
    cuenta = collections.Counter()
    for m in re.finditer(r"\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,}\b", texto):
        tok = m.group(0)
        if tok in COMUNES:
            continue
        cuenta[tok] += 1
        if not ARRANQUE.search(texto[max(0, m.start() - 3):m.start()]):
            medio_frase[tok] += 1

    # Nombre de verdad: al menos 3 apariciones en mitad de frase y en la mayoría de los casos.
    nombres = {k: v for k, v in cuenta.items()
               if medio_frase.get(k, 0) >= 3 and medio_frase[k] / v >= 0.4}
    principales = {k: v for k, v in nombres.items() if v >= minimo}

    grupos, vistos = [], set()
    for a in sorted(principales, key=lambda x: -principales[x]):
        if a in vistos:
            continue
        # Umbral de distancia proporcional: en palabras largas caben más erratas
        # (Betelgeuse/Belegueuse está a 3) sin que se confundan nombres cortos distintos.
        # Umbral de distancia escalado con la longitud. En un nombre de cuatro letras, distancia 2
        # es media palabra: así entraban *Jobs* y *Down* como variantes de *John*. En uno de diez
        # caben tres erratas sin que deje de ser el mismo nombre (Betelgeuse/Belegueuse).
        tope = 1 if len(a) <= 5 else (2 if len(a) <= 8 else 3)
        familia, tipo = [(a, principales[a])], "errata"
        # Las variantes se buscan sobre TODOS los tokens, no sólo sobre los que pasan el filtro
        # de "es un nombre": una errata aparece una o dos veces, así que por definición nunca
        # cumpliría ese umbral. Lo que la avala es estar pegada a un nombre ya verificado.
        for b, nb in cuenta.items():
            if b == a or b in vistos or medio_frase.get(b, 0) < 1:
                continue
            if not 0 < distancia(a.lower(), b.lower()) <= tope:
                continue
            if nb <= 4 or nb < principales[a] * 0.05:
                familia.append((b, nb))          # rara y marginal: es una errata
                vistos.add(b)
            elif b in principales and nb >= principales[a] * 0.30:
                # Las dos formas pesan: no es una errata, es un "¿cuál es la buena?".
                # Ese caso lo decide el autor y hay que enseñárselo igualmente.
                familia.append((b, nb))
                vistos.add(b)
                tipo = "ambigua"
        vistos.add(a)
        if len(familia) > 1:
            grupos.append({"tipo": tipo, "formas": sorted(familia, key=lambda x: -x[1])})
    # Primero las ambiguas: son las que bloquean, porque hay que elegir.
    return sorted(grupos, key=lambda g: (g["tipo"] != "ambigua", -g["formas"][0][1]))


def escanear(ruta, techo=120):
    ps = D.parrafos(ruta, D.ACEPTAR)
    texto = "\n".join(ps)
    palabras = texto.split()

    tildes = {}
    for mal, bien in TILDES.items():
        n = len(re.findall(rf"\b{mal}\b", texto))
        if n:
            tildes[mal] = {"→": bien, "casos": n, "ambigua": mal in AMBIGUAS}

    largos = [{"parrafo": i, "palabras": len(p.split()), "inicio": p[:60]}
              for i, p in enumerate(ps) if len(p.split()) > techo]

    return {
        "fichero": os.path.basename(ruta),
        "palabras": len(palabras),
        "parrafos": len([p for p in ps if p.strip()]),
        "guiones_dobles": guiones_por_funcion(ps),
        "comillas_rectas": texto.count('"') + texto.count("'"),
        "puntos_suspensivos_tres": len(re.findall(r"\.\.\.", texto)),
        "tildes_candidatas": tildes,
        "encabezados": encabezados(ruta),
        "capitulos_sin_cortes": [c for c in cortes_por_capitulo(ps) if c["cortes"] == 0],
        "capitulos_con_cortes": [c for c in cortes_por_capitulo(ps) if c["cortes"] > 0],
        "canon_dudoso": canon(texto),
        "parrafos_sobre_techo": {"techo": techo, "casos": len(largos), "mayores": largos[:10]},
    }


def imprimir(r):
    print(f"\n  Fase 0 · {r['fichero']} — {r['palabras']:,} palabras · {r['parrafos']:,} párrafos\n")

    g = r["guiones_dobles"]
    if g["total"]:
        print(f"  ⚠ Dobles guiones: {g['total']} — cada función lleva OTRO espaciado")
        print(f"      apertura de parlamento {g['apertura_parlamento']} · "
              f"apertura de inciso {g['apertura_inciso']} · cierre {g['cierre_inciso']}")
    else:
        print("  ✓ Sin dobles guiones")

    for etq, n in (("Comillas rectas", r["comillas_rectas"]),
                   ("Puntos suspensivos de tres puntos", r["puntos_suspensivos_tres"])):
        print(f"  {'⚠' if n else '✓'} {etq}: {n}")

    t = r["tildes_candidatas"]
    if t:
        amb = [k for k, v in t.items() if v["ambigua"]]
        print(f"  ⚠ Tildes candidatas: {sum(v['casos'] for v in t.values())} casos en {len(t)} palabras")
        for k, v in sorted(t.items(), key=lambda kv: -kv[1]["casos"])[:8]:
            marca = "  ← AMBIGUA, mirar una a una" if v["ambigua"] else ""
            print(f"      {k} → {v['→']}: {v['casos']}{marca}")
        if amb:
            print(f"      ({len(amb)} ambiguas: NO sustituir en bloque)")

    e = r["encabezados"]
    if e["sin_estilo"]:
        print(f"  ⚠ Capítulos sin estilo de encabezado: {len(e['sin_estilo'])} "
              f"(no salen en el índice automático)")
        for c in e["sin_estilo"][:6]:
            print(f"      párrafo {c['parrafo']}: {c['texto']!r}")
    else:
        print(f"  ✓ Encabezados: {e['con_estilo']} capítulos con estilo")

    sc = r["capitulos_sin_cortes"]
    if sc:
        print(f"  ⚠ Capítulos SIN ningún corte de escena: {len(sc)} "
              f"(de {len(sc) + len(r['capitulos_con_cortes'])})")
        for c in sc[:8]:
            print(f"      {c['titulo'][:40]:40} {c['parrafos']} párrafos")

    if r["canon_dudoso"]:
        amb = [g for g in r["canon_dudoso"] if g["tipo"] == "ambigua"]
        print(f"  ⚠ Nombres con variantes: {len(r['canon_dudoso'])} — decide el autor"
              + (f" ({len(amb)} sin forma mayoritaria clara)" if amb else ""))
        for g in r["canon_dudoso"][:10]:
            marca = "  ← ¿CUÁL ES LA BUENA?" if g["tipo"] == "ambigua" else ""
            print("      " + " · ".join(f"{n} ({c})" for n, c in g["formas"]) + marca)

    p = r["parrafos_sobre_techo"]
    if p["casos"]:
        print(f"  ⚠ Párrafos de más de {p['techo']} palabras: {p['casos']}")
    print()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("manuscrito")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--techo", type=int, default=120)
    a = ap.parse_args()
    r = escanear(a.manuscrito, a.techo)
    print(json.dumps(r, ensure_ascii=False, indent=2)) if a.json else imprimir(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
