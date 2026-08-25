#!/usr/bin/env python3
"""Qué decidió el autor entre dos versiones: propuesto vs. aceptado, por autor de revisión.

Todo lo demás que medimos cuenta VOLUMEN — cuántas palabras, cuántos párrafos, cuántas marcas.
Esto cuenta JUICIO: de lo que se propuso, cuánto se quedó. Es la única cifra que no se puede
inflar sin hacer el trabajo, y la que de verdad distingue a un autor que decide de uno que
acepta todo sin mirar.

Cómo se sabe. En la versión N una intervención vive como marca pendiente: <w:ins> con el texto
propuesto, <w:del> con el texto que se propone quitar. En la versión N+1 el autor ya decidió, así
que basta mirar SU BASE — el texto de N+1 rechazando todas sus marcas nuevas, que es exactamente
lo que arrastró consigo:

    <w:ins> aceptada   →  su texto ESTÁ en la base de N+1
    <w:del> aceptada   →  su texto NO está en la base de N+1

Límite honesto: una marca corta —una raya de diálogo, una tilde, una coma— no se puede rastrear
así, porque su texto aparece en mil sitios. Se cuentan aparte como «no evaluables» y no entran en
la ratio. En una Fase 0 con 1.500 rayas eso es casi todo, y está bien que así sea: la ratio mide
decisiones editoriales, no ortotipografía.

Uso:
    decisiones.py <version-anterior.docx> <version-siguiente.docx> [--json] [--min N]
"""
import argparse
import json
import re
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import docxtc as D  # noqa: E402

# El umbral no es a ojo. Medido sobre un manuscrito real con 9 marcas, contrastando contra el
# estado "aceptando todo" (donde lo correcto es 0 rechazadas), los falsos negativos desaparecen a
# partir de 15 y la cobertura ya no mejora por encima:
#
#     umbral   evaluadas   aceptadas   rechazadas
#          5           8           5            3   <- falsos negativos
#         10           5           4            1   <- falsos negativos
#         15           4           4            0
#         25           4           4            0
#
# Se deja en 25: en un manuscrito largo una frase corta se repite y 15 dejaria de proteger.
MIN_RASTREABLE = 25
RE_VERSION = re.compile(r"-[vb]0*(\d+)", re.I)


def decisiones(anterior, siguiente, minimo=MIN_RASTREABLE):
    marcas = D.revisiones(anterior)
    base = D.normalizar(D.texto(siguiente, D.RECHAZAR))

    por_autor = {}
    for tipo, autor, _fecha, _id, txt in marcas:
        autor = autor or "(sin autor)"
        a = por_autor.setdefault(autor, {"propuestas": 0, "aceptadas": 0,
                                         "rechazadas": 0, "no_evaluables": 0})
        a["propuestas"] += 1
        t = D.normalizar(txt)
        if len(t) < minimo:
            a["no_evaluables"] += 1
            continue
        presente = t in base
        aceptada = presente if tipo == "ins" else not presente
        a["aceptadas" if aceptada else "rechazadas"] += 1

    for a in por_autor.values():
        evaluadas = a["aceptadas"] + a["rechazadas"]
        a["evaluadas"] = evaluadas
        a["ratio"] = round(a["aceptadas"] / evaluadas, 3) if evaluadas else None

    tot = {k: sum(v[k] for v in por_autor.values())
           for k in ("propuestas", "aceptadas", "rechazadas", "no_evaluables", "evaluadas")}
    tot["ratio"] = round(tot["aceptadas"] / tot["evaluadas"], 3) if tot["evaluadas"] else None

    return {
        "anterior": os.path.basename(anterior),
        "siguiente": os.path.basename(siguiente),
        "minimo_rastreable": minimo,
        "total": tot,
        "por_autor": dict(sorted(por_autor.items(), key=lambda kv: -kv[1]["propuestas"])),
    }


def imprimir(r):
    t = r["total"]
    print(f"\n  Decisiones — {r['anterior']} → {r['siguiente']}\n")
    if not t["propuestas"]:
        print("  La versión anterior no tiene marcas de revisión: no hay nada que decidir.\n")
        return
    print(f"  {'Autor de revisión':34} {'Prop.':>6} {'Acep.':>6} {'Rech.':>6} {'Ratio':>7}")
    print("  " + "─" * 64)
    for autor, a in r["por_autor"].items():
        ratio = f"{a['ratio']:.0%}" if a["ratio"] is not None else "—"
        print(f"  {autor[:34]:34} {a['propuestas']:>6} {a['aceptadas']:>6} "
              f"{a['rechazadas']:>6} {ratio:>7}")
    print("  " + "─" * 64)
    ratio = f"{t['ratio']:.0%}" if t["ratio"] is not None else "—"
    print(f"  {'TOTAL':34} {t['propuestas']:>6} {t['aceptadas']:>6} {t['rechazadas']:>6} {ratio:>7}")
    if t["no_evaluables"]:
        pct = 100 * t["no_evaluables"] / t["propuestas"]
        print(f"\n  {t['no_evaluables']} marcas ({pct:.0f} %) demasiado cortas para rastrearlas "
              f"una a una — típico de\n  la limpieza ortotipográfica. No entran en la ratio.")
    print()


def _guardar(siguiente, r):
    """Junto al manuscrito, en telemetria/, con la misma clave de version que el resto."""
    m = RE_VERSION.search(os.path.basename(siguiente))
    if not m:
        return None
    destino = os.path.join(os.path.dirname(os.path.abspath(siguiente)), "telemetria")
    try:
        os.makedirs(destino, exist_ok=True)
        ruta = os.path.join(destino, f"decisiones-v{int(m.group(1)):02d}.json")
        with open(ruta, "w", encoding="utf-8") as fh:
            json.dump(r, fh, ensure_ascii=False, indent=1)
        return ruta
    except OSError as e:
        print(f"  aviso: no se pudo guardar la telemetria: {e}")
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("anterior")
    ap.add_argument("siguiente")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--min", type=int, default=MIN_RASTREABLE,
                    help=f"caracteres mínimos para rastrear una marca (por defecto {MIN_RASTREABLE})")
    ap.add_argument("--sin-guardar", action="store_true",
                    help="no escribir telemetria/decisiones-v<N>.json (por defecto si se escribe)")
    a = ap.parse_args()
    r = decisiones(a.anterior, a.siguiente, a.min)
    if not a.sin_guardar:
        ruta = _guardar(a.siguiente, r)
        if ruta and not a.json:
            print(f"  OK guardado en {ruta}\n")
    print(json.dumps(r, ensure_ascii=False, indent=2)) if a.json else imprimir(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
