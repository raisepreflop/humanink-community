"""vuelta.py — leer del documento lo que el autor decidió en Word (M-21, M-22, M-23).

«Resuelto» no se declara: se comprueba. El Studio entrega una versión con los cambios marcados y
firmados por su pasada; el autor los acepta, los rechaza o escribe encima con las herramientas de
Word. Aquí se lee el documento que él guardó y se clasifica cada cosa por el RESULTADO, no por el
botón que pulsó:

    aceptado   el texto propuesto está en lo que él se quedó
    rechazado  el texto propuesto no está, y el original sigue en su sitio
    retocado   ni lo uno ni lo otro: escribió encima. Es la decisión más valiosa, y hasta hoy se
               contaba como «rechazado», que es exactamente lo contrario de lo que pasó

Y por NOTA: una nota se cierra cuando su pasaje ya no dice lo que decía. Si sigue igual, sigue
esperando; si el pasaje cambió pero no por nuestra marca, queda «por comprobar» — el autor o su
corrector tocaron ahí, y eso se registra, no se vigila.

Límite honesto, el mismo que `decisiones.py`: una marca de menos de 25 caracteres no se puede
rastrear (una coma aparece en mil sitios). Se cuenta aparte y no entra en ninguna ratio.

Uso:
    vuelta.py <entregada.docx> <guardada.docx> [--notas notas.json] [--json]
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import docxtc as D  # noqa: E402
from decisiones import MIN_RASTREABLE  # noqa: E402


def _normal(t):
    return D.normalizar(t or "")


def marcas(entregada, guardada, minimo=MIN_RASTREABLE, detalle=False):
    """Qué pasó con cada marca de la versión entregada, por autor de revisión.

    Con `detalle`, además de las cifras devuelve una línea por marca —su texto y su resultado—,
    que es lo que el Studio necesita para decir, cambio a cambio, qué hizo el autor con él
    (M-28). Sin eso, la pantalla solo puede dar un total, y un total no explica nada.
    """
    # Lo que el autor ARRASTRÓ consigo: su documento rechazando las marcas que aún están pendientes.
    base = _normal(D.texto(guardada, D.RECHAZAR))
    aceptando = _normal(D.texto(guardada, D.ACEPTAR))

    por_autor = {}
    uno_a_uno = []
    for tipo, autor, _fecha, _id, txt in D.revisiones(entregada):
        autor = autor or "(sin autor)"
        a = por_autor.setdefault(autor, {"propuestas": 0, "aceptadas": 0, "rechazadas": 0,
                                         "retocadas": 0, "no_evaluables": 0})
        a["propuestas"] += 1
        t = _normal(txt)
        if len(t) < minimo:
            a["no_evaluables"] += 1
            if detalle:
                uno_a_uno.append({"tipo": tipo, "autor": autor, "texto": txt,
                                  "resultado": "no_evaluable"})
            continue
        if tipo == "ins":
            # Propuesto: ¿se quedó con él?
            if t in base or t in aceptando:
                resultado = "aceptado"
            else:
                resultado = "retocado" if _cambio_en_su_sitio(t, base) else "rechazado"
        else:
            # Lo que se proponía quitar: si sigue ahí, no lo quitó.
            resultado = "rechazado" if t in base else "aceptado"
        a[{"aceptado": "aceptadas", "rechazado": "rechazadas", "retocado": "retocadas"}[resultado]] += 1
        if detalle:
            uno_a_uno.append({"tipo": tipo, "autor": autor, "texto": txt, "resultado": resultado})

    for a in por_autor.values():
        a["evaluadas"] = a["aceptadas"] + a["rechazadas"] + a["retocadas"]
        a["ratio"] = round(a["aceptadas"] / a["evaluadas"], 3) if a["evaluadas"] else None

    total = {k: sum(v[k] for v in por_autor.values())
             for k in ("propuestas", "aceptadas", "rechazadas", "retocadas", "no_evaluables", "evaluadas")}
    total["ratio"] = round(total["aceptadas"] / total["evaluadas"], 3) if total["evaluadas"] else None
    salida = {"total": total, "por_autor": dict(sorted(por_autor.items(), key=lambda kv: -kv[1]["propuestas"]))}
    if detalle:
        salida["marcas"] = uno_a_uno
    return salida


def _cambio_en_su_sitio(propuesto, base, ventana=40):
    """¿Hay rastro de la propuesta —su principio o su final— aunque el texto no sea el mismo?

    Es lo que distingue «escribió encima» de «lo rechazó»: si el autor conservó el arranque de la
    frase propuesta y cambió el resto, la decisión es suya y es la más valiosa de todas.
    """
    if len(propuesto) < ventana * 2:
        return False
    return propuesto[:ventana] in base or propuesto[-ventana:] in base


def notas(entregada, guardada, lista, minimo=MIN_RASTREABLE):
    """Qué pasó con cada nota: se cierra cuando su pasaje ya no dice lo que decía."""
    antes = _normal(D.texto(entregada, D.RECHAZAR))     # el texto tal como estaba antes de la pasada
    ahora_base = _normal(D.texto(guardada, D.RECHAZAR))
    ahora = _normal(D.texto(guardada, D.ACEPTAR))
    fuera = []
    for n in lista or []:
        cita = _normal((n.get("ancla") or {}).get("cita") or n.get("cita") or "")
        if len(cita) < minimo:
            fuera.append({"id": n.get("id"), "estado": "por_comprobar", "motivo": "la cita es demasiado corta para rastrearla"})
            continue
        seguia = cita in antes
        sigue = cita in ahora_base or cita in ahora
        if sigue:
            fuera.append({"id": n.get("id"), "estado": "en_word", "motivo": "su pasaje sigue igual"})
        elif seguia:
            fuera.append({"id": n.get("id"), "estado": "resuelta", "motivo": "su pasaje cambió en el documento"})
        else:
            fuera.append({"id": n.get("id"), "estado": "por_comprobar", "motivo": "su pasaje ya no está en el documento"})
    return fuera


def leer(entregada, guardada, lista=None, minimo=MIN_RASTREABLE, detalle=False):
    r = marcas(entregada, guardada, minimo, detalle)
    r["entregada"] = os.path.basename(entregada)
    r["guardada"] = os.path.basename(guardada)
    r["minimo_rastreable"] = minimo
    r["notas"] = notas(entregada, guardada, lista or [], minimo)
    return r


def imprimir(r):
    t = r["total"]
    print(f"\n  De vuelta — {r['entregada']} → {r['guardada']}\n")
    print(f"  Aceptados tal cual   {t['aceptadas']:>4}")
    print(f"  Retocados por ti     {t['retocadas']:>4}")
    print(f"  Rechazados           {t['rechazadas']:>4}")
    if t["no_evaluables"]:
        print(f"  Sin rastrear         {t['no_evaluables']:>4}  (marcas de menos de {r['minimo_rastreable']} caracteres)")
    if r["notas"]:
        cerradas = sum(1 for n in r["notas"] if n["estado"] == "resuelta")
        print(f"\n  Notas: {cerradas} de {len(r['notas'])} cerradas con prueba\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("entregada")
    ap.add_argument("guardada")
    ap.add_argument("--notas", help="JSON con las notas que esperaban en Word")
    ap.add_argument("--min", type=int, default=MIN_RASTREABLE)
    ap.add_argument("--detalle", action="store_true", help="una línea por marca, con su resultado")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    lista = []
    if a.notas:
        with open(a.notas, encoding="utf-8") as f:
            d = json.load(f)
        lista = d.get("notas", d) if isinstance(d, dict) else d
    r = leer(a.entregada, a.guardada, lista, a.min, a.detalle)
    print(json.dumps(r, ensure_ascii=False, indent=2)) if a.json else imprimir(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
