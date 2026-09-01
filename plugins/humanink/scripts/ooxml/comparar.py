#!/usr/bin/env python3
"""comparar.py — qué cambió de verdad entre dos builds de un manuscrito.

Mide sobre el XML resolviendo el control de cambios (vía docxtc), así que las cifras valen
también cuando hay cambios sin aceptar — cosa que `python-docx` no puede hacer. Y localiza los
pasajes: qué se añadió, qué se cortó y qué se reescribió, con su posición.

Existe porque "he ampliado el libro" no es un dato y "+13.311 palabras, +104 cortes de escena,
percentil 90 de párrafo de 133 a 90" sí lo es.

Uso:
    comparar.py <nuevo.docx> <anterior.docx>      # un par
    comparar.py --serie <carpeta>                 # toda la cadena de builds
    comparar.py ... --json
"""
import argparse
import difflib
import json
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import docxtc as D  # noqa: E402

CORTE = re.compile(r"^\s*(\*\s*\*\s*\*|---|—{3,}|#{3,})\s*$")
MENTE = re.compile(r"\b\w+(?:mente|ly)\b", re.I)
FRASE = re.compile(r"[^.!?…]+[.!?…]+")
DIALOGO = re.compile(r"^\s*[—–\-«\"“]")


def metricas(ruta, modo=D.ACEPTAR):
    ps = [p for p in D.parrafos(ruta, modo)]
    vivos = [p for p in ps if p.strip()]
    texto = "\n".join(vivos)
    frases = [f.strip() for f in FRASE.findall(texto) if f.strip()]
    largos = [len(f.split()) for f in frases] or [0]
    narrativos = [len(p.split()) for p in vivos if not DIALOGO.match(p) and len(p.split()) > 3]
    narrativos = narrativos or [0]
    pal = len(texto.split()) or 1
    return {
        "palabras": len(texto.split()),
        "parrafos": len(vivos),
        "parrafos_narrativos": len([1 for p in vivos if not DIALOGO.match(p) and len(p.split()) > 3]),
        "cortes_de_escena": sum(1 for p in ps if CORTE.match(p)),
        "frases": len(frases),
        "frase_media": round(statistics.fmean(largos), 1),
        "frase_mediana": round(statistics.median(largos), 1),
        "parrafo_mediana": round(statistics.median(narrativos), 1),
        "parrafo_p90": round(sorted(narrativos)[int(len(narrativos) * 0.9) - 1], 1) if narrativos else 0,
        "frases_cortas_pct": round(100 * sum(1 for x in largos if x <= 8) / len(largos), 1),
        # Dispersión (σ) y ALTERNANCIA. No son lo mismo y confundirlas es el error clásico:
        # un capítulo con todas las frases cortas al principio y todas largas al final tiene σ
        # alta y alternancia CERO. σ dice de qué está hecho el texto; la alternancia, en qué
        # orden — y el ritmo es orden. Alternancia = media de |largo(n) − largo(n−1)|.
        "frase_sigma": round(statistics.pstdev(largos), 1) if len(largos) > 1 else 0.0,
        "alternancia": round(
            statistics.fmean([abs(largos[i] - largos[i - 1]) for i in range(1, len(largos))]), 1
        ) if len(largos) > 1 else 0.0,
        "dialogo_pct_lineas": round(100 * sum(1 for p in vivos if DIALOGO.match(p)) / max(len(vivos), 1), 1),
        "adverbios_mente_por_mil": round(1000 * len(MENTE.findall(texto)) / pal, 2),
    }


def pasajes(antes, despues, contexto=1):
    """Tramos añadidos, cortados y reescritos, con posición y primeras palabras."""
    a = [p for p in D.parrafos(antes, D.ACEPTAR)]
    b = [p for p in D.parrafos(despues, D.ACEPTAR)]
    na = [D.normalizar(x) for x in a]
    nb = [D.normalizar(x) for x in b]
    fuera = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, na, nb, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        viejo = [x for x in a[i1:i2] if x.strip()]
        nuevo = [x for x in b[j1:j2] if x.strip()]
        delta = sum(len(x.split()) for x in nuevo) - sum(len(x.split()) for x in viejo)
        tipo = {"insert": "añadido", "delete": "cortado", "replace": "reescrito"}[tag]
        muestra = (nuevo or viejo)
        fuera.append({
            "tipo": tipo,
            "parrafo": j1,
            "parrafos_afectados": max(len(nuevo), len(viejo)),
            "delta_palabras": delta,
            "inicio": (muestra[0][:110] if muestra else ""),
        })
    return fuera


def escenas_de(parrafos):
    """Trocea la lista de párrafos en escenas por el separador (*** / --- / ###).

    Devuelve una lista de escenas; cada escena es la lista de sus párrafos vivos. El separador
    NO entra en la escena: es la frontera, no contenido. Un libro sin separadores da una sola
    escena, y entonces las cifras de escena no dicen nada — es correcto que no lo digan.
    """
    escenas, actual = [], []
    for x in parrafos:
        if CORTE.match(x):
            escenas.append(actual)
            actual = []
        elif x.strip():
            actual.append(x)
    escenas.append(actual)
    return [e for e in escenas if e]


def cambios_de_escena(parrafos_antes, parrafos_despues):
    """Escenas añadidas, borradas y modificadas — el mismo criterio que en párrafos.

    La regla es del autor y no necesita ningún umbral afinado a ojo, que es lo que la hace
    defendible: difflib compara escenas ENTERAS, así que
        insert  -> la escena es 100 % nueva            -> añadida
        delete  -> la escena se fue al 100 %           -> borrada
        replace -> cualquier cosa por debajo del 100 % -> modificada
    El corte es «exactamente el 100 %», no un parecido del 80 % que habría que justificar.

    Toma listas de párrafos y no rutas a propósito: así las pruebas comprueban ESTA función y
    no una copia suya. La primera versión del test reimplementaba la tabla de arriba y por eso
    seguía en verde con el motor roto a mano.
    """
    ea = escenas_de(parrafos_antes)
    eb = escenas_de(parrafos_despues)
    ka = ["\n".join(D.normalizar(x) for x in e) for e in ea]
    kb = ["\n".join(D.normalizar(x) for x in e) for e in eb]
    fuera = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ka, kb, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        viejo, nuevo = ea[i1:i2], eb[j1:j2]
        pal_v = sum(len(x.split()) for e in viejo for x in e)
        pal_n = sum(len(x.split()) for e in nuevo for x in e)
        muestra = (nuevo or viejo)[0]
        fuera.append({
            "tipo": {"insert": "añadida", "delete": "borrada", "replace": "modificada"}[tag],
            "escena": j1,
            "escenas_afectadas": max(len(nuevo), len(viejo)),
            "delta_palabras": pal_n - pal_v,
            "inicio": muestra[0][:110] if muestra else "",
        })
    return fuera


def pasajes_escena(antes, despues):
    """cambios_de_escena sobre dos .docx, resolviendo antes el control de cambios."""
    return cambios_de_escena(D.parrafos(antes, D.ACEPTAR), D.parrafos(despues, D.ACEPTAR))


def comparar(nuevo, anterior):
    ma, mb = metricas(anterior), metricas(nuevo)
    filas = []
    for k in ma:
        d = mb[k] - ma[k]
        pct = (100 * d / ma[k]) if ma[k] else 0
        filas.append({"magnitud": k, "antes": ma[k], "despues": mb[k],
                      "delta": round(d, 2), "pct": round(pct, 1)})
    ps = pasajes(anterior, nuevo)
    es = pasajes_escena(anterior, nuevo)
    return {
        "anterior": os.path.basename(anterior),
        "nuevo": os.path.basename(nuevo),
        "metricas": filas,
        "pasajes": ps,
        "escenas": es,
        "resumen": {
            "escenas_añadidas": sum(1 for e in es if e["tipo"] == "añadida"),
            "escenas_borradas": sum(1 for e in es if e["tipo"] == "borrada"),
            "escenas_modificadas": sum(1 for e in es if e["tipo"] == "modificada"),
            "añadidos": sum(1 for p in ps if p["tipo"] == "añadido"),
            "cortados": sum(1 for p in ps if p["tipo"] == "cortado"),
            "reescritos": sum(1 for p in ps if p["tipo"] == "reescrito"),
            "delta_palabras": mb["palabras"] - ma["palabras"],
        },
    }


# Una versión se reconoce por -v02 (nomenclatura nueva: DUOC-m10-v02) o -b32 (la vieja),
# SIN distinguir mayúsculas: los ficheros reales del autor venían en mayúscula (LDDLL-1-B32-…)
# y el patrón antiguo, solo minúsculas, no casaba con ninguno. La serie salía vacía con 39
# versiones delante.
RE_VERSION = re.compile(r"-[vb]0*(\d+)", re.I)


def _num_build(f):
    m = RE_VERSION.search(os.path.basename(f))
    return int(m.group(1)) if m else -1


def ficha(fichero, anterior=None):
    """La medición de UN build, en la misma forma que usa `serie()`.

    Existe porque medir la cadena entera tras cada pasada son minutos sobre una novela con treinta
    y nueve builds, y lo que acaba de cambiar es UN par. Quien lee `telemetria/v29.json` no debe
    poder notar por cuál de los dos caminos se escribió: misma forma o la curva sale a trozos.
    """
    inv = D.inventario(fichero)
    previo = D.inventario(anterior)["palabras_aceptando"] if anterior else None
    return {
        "build": os.path.basename(fichero),
        "n": _num_build(fichero),
        "palabras": inv["palabras_aceptando"],
        "parrafos": inv["parrafos_aceptando"],
        "marcas": inv["marcas"],
        "autores": list(inv["autores"]),
        "delta": (inv["palabras_aceptando"] - previo) if previo is not None else 0,
        "metricas": metricas(fichero),
    }


def serie(carpeta):
    """La cadena entera de builds de un proyecto, ordenada por número."""
    fs = [os.path.join(carpeta, f) for f in os.listdir(carpeta)
          if f.lower().endswith(".docx") and RE_VERSION.search(f)
          and not f.startswith("~$") and "copia" not in f.lower() and "copy" not in f.lower()]
    fs.sort(key=_num_build)
    if len(fs) < 2:
        return {"error": f"hacen falta al menos 2 builds; encontrados {len(fs)}", "builds": fs}
    filas, previo = [], None
    for f in fs:
        inv = D.inventario(f)
        fila = {
            "build": os.path.basename(f),
            "n": _num_build(f),
            "palabras": inv["palabras_aceptando"],
            "parrafos": inv["parrafos_aceptando"],
            "marcas": inv["marcas"],
            "autores": list(inv["autores"]),
            "delta": (inv["palabras_aceptando"] - previo) if previo is not None else 0,
            # Métricas completas por versión: es lo que el panel necesita para dibujar el
            # ritmo (densidad, alternancia) y no solo el recuento de palabras.
            "metricas": metricas(f),
        }
        previo = inv["palabras_aceptando"]
        filas.append(fila)
    total = comparar(fs[-1], fs[0])
    return {"carpeta": carpeta, "builds": filas, "primero": os.path.basename(fs[0]),
            "ultimo": os.path.basename(fs[-1]), "global": total}


ETIQUETAS = {
    "palabras": "Palabras", "parrafos": "Párrafos",
    "parrafos_narrativos": "Párrafos narrativos", "cortes_de_escena": "Cortes de escena",
    "frases": "Frases", "frase_media": "Media de frase", "frase_mediana": "Mediana de frase",
    "parrafo_mediana": "Mediana de párrafo", "parrafo_p90": "Percentil 90 de párrafo",
    "frases_cortas_pct": "Frases cortas (≤8) %", "dialogo_pct_lineas": "Diálogo (% líneas)",
    "adverbios_mente_por_mil": "Adverbios -mente/1000",
}


def guardar_telemetria(carpeta, filas):
    """Escribe telemetria/v<N>.json — una ficha por versión, en la carpeta del proyecto.

    Antes esto se calculaba y se perdía en la salida del turno. Sobre una novela con treinta
    versiones eso son treinta mediciones tiradas, y sin la serie no hay forma de dibujar cómo
    evolucionó el manuscrito. Un número impreso se lee una vez; un fichero se compara.
    """
    destino = os.path.join(carpeta, "telemetria")
    try:
        os.makedirs(destino, exist_ok=True)
    except OSError as e:
        print(f"  ⚠ no se pudo crear {destino}: {e}")
        return []
    escritos = []
    for f in filas:
        n = f.get("n")
        if n is None:
            continue
        ruta = os.path.join(destino, f"v{n:02d}.json")
        try:
            with open(ruta, "w", encoding="utf-8") as fh:
                json.dump(f, fh, ensure_ascii=False, indent=1)
            escritos.append(ruta)
        except OSError as e:
            print(f"  ⚠ no se pudo escribir {ruta}: {e}")
    return escritos


def guardar_global(carpeta, r):
    """telemetria/global.json — el neto de la cadena: primera versión contra última."""
    destino = os.path.join(carpeta, "telemetria")
    try:
        os.makedirs(destino, exist_ok=True)
        g = dict(r.get("global") or {})
        g["primero"] = r.get("primero")
        g["ultimo"] = r.get("ultimo")
        g["versiones"] = len(r.get("builds") or [])
        with open(os.path.join(destino, "global.json"), "w", encoding="utf-8") as fh:
            json.dump(g, fh, ensure_ascii=False, indent=1)
        return True
    except OSError as e:
        print(f"  aviso: no se pudo guardar el global: {e}")
        return False


def imprimir_par(r):
    print(f"\n  {r['anterior']}  →  {r['nuevo']}\n")
    print(f"  {'Magnitud':26} {'Antes':>10} {'Después':>10} {'Dif.':>10} {'%':>8}")
    print("  " + "─" * 68)
    for f in r["metricas"]:
        signo = f"{f['delta']:+g}" if f["delta"] else "="
        pct = f"{f['pct']:+.1f}%" if f["delta"] else ""
        print(f"  {ETIQUETAS.get(f['magnitud'], f['magnitud']):26} "
              f"{f['antes']:>10} {f['despues']:>10} {signo:>10} {pct:>8}")
    s = r["resumen"]
    print(f"\n  {s['añadidos']} pasajes añadidos · {s['cortados']} cortados · "
          f"{s['reescritos']} reescritos · {s['delta_palabras']:+,} palabras\n")
    if r["pasajes"]:
        print("  Los pasajes (por tamaño):")
        for p in sorted(r["pasajes"], key=lambda x: -abs(x["delta_palabras"]))[:20]:
            print(f"    {p['tipo']:10} párrafo {p['parrafo']:>5}  {p['delta_palabras']:+6} pal.  "
                  f"{p['inicio'][:70]!r}")
    print()


def imprimir_serie(r):
    if "error" in r:
        print(f"\n  {r['error']}\n")
        return
    print(f"\n  Serie de builds — {r['primero']} → {r['ultimo']}\n")
    print(f"  {'Build':28} {'Palabras':>10} {'Dif.':>9} {'Marcas':>7}  Autores de revisión")
    print("  " + "─" * 84)
    for b in r["builds"]:
        d = f"{b['delta']:+,}" if b["delta"] else "="
        aut = ", ".join(b["autores"][:2])[:34]
        print(f"  {b['build'][:28]:28} {b['palabras']:>10,} {d:>9} {b['marcas']:>7}  {aut}")
    g = r["global"]["resumen"]
    print(f"\n  Global: {g['delta_palabras']:+,} palabras · {g['añadidos']} pasajes añadidos · "
          f"{g['cortados']} cortados · {g['reescritos']} reescritos")
    print()
    imprimir_par(r["global"])


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("nuevo", nargs="?")
    ap.add_argument("anterior", nargs="?")
    ap.add_argument("--serie", metavar="CARPETA")
    ap.add_argument("--json", action="store_true")
    # La telemetría se guarda POR DEFECTO: el objetivo de todo esto es que la medición deje de
    # perderse. --sin-guardar existe para inspeccionar una carpeta ajena sin dejar rastro.
    ap.add_argument("--sin-guardar", action="store_true",
                    help="no escribir telemetria/v<N>.json (por defecto sí se escribe)")
    a = ap.parse_args()

    if a.serie:
        r = serie(a.serie)
        if not a.sin_guardar and "builds" in r and not r.get("error"):
            escritos = guardar_telemetria(a.serie, r["builds"])
            # El NETO primera→última: es el diff que el autor hace a mano en Word (b02 vs b39) y
            # la vista en la que más confía. serie() ya lo calcula; hasta ahora se imprimía y se
            # perdía. Se guarda aparte porque no pertenece a ninguna versión: es la cadena entera.
            guardar_global(a.serie, r)
            if escritos and not a.json:
                print(f"\n  ✓ telemetría guardada: {len(escritos)} versiones en "
                      f"{os.path.join(a.serie, 'telemetria')}/")
        print(json.dumps(r, ensure_ascii=False, indent=2)) if a.json else imprimir_serie(r)
        return 0

    if not (a.nuevo and a.anterior):
        ap.error("hacen falta dos builds, o --serie <carpeta>")
    r = comparar(a.nuevo, a.anterior)
    # También en modo par. Antes solo guardaba `--serie`, así que aplicar una pasada medía el
    # cambio y lo tiraba: la carpeta `telemetria/` no aparecía nunca y la curva no tenía de dónde
    # salir. Aquí se escribe la ficha del build nuevo, que es lo que acaba de cambiar.
    if not a.sin_guardar:
        try:
            f = ficha(a.nuevo, a.anterior)
            if f.get("n") is not None:
                guardar_telemetria(os.path.dirname(os.path.abspath(a.nuevo)) or ".", [f])
                r["ficha"] = f
        except Exception as e:            # medir nunca puede tumbar una comparación
            print(f"  ⚠ no se pudo guardar la ficha: {e}")
    print(json.dumps(r, ensure_ascii=False, indent=2)) if a.json else imprimir_par(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
