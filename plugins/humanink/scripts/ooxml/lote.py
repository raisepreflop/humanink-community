#!/usr/bin/env python3
"""lote.py — de «original + propuesta» a intervenciones ancladas.

POR QUÉ VIVE AQUÍ Y NO EN EL CLIENTE. `intervene.py` no acepta «cambia este texto por este otro»:
acepta anclas. Y sus dos anclas tienen contratos DISTINTOS, que es lo que hace esto delicado:

    huella   se compara NORMALIZADA  (localizar → _normaliza: espacios colapsados, strip)
    buscar   se compara EN CRUDO contra el texto vivo del párrafo, y debe ser ÚNICO en él
             (op_reemplazar lanza ErrorDeAnclaje si aparece dos veces)

Quien acuña un ancla tiene que ser el mismo código que la resuelve. Una reimplementación en otro
lenguaje que colapse los espacios de otra manera produce anclas que fallan —o, peor, que casan
donde no deben— y eso en un manuscrito es corromperlo en silencio.

El diff es a nivel de PÁRRAFO para emparejar, y de PALABRA dentro de cada párrafo emparejado: se
recortan el prefijo y el sufijo comunes para que `buscar` sea el tramo más corto que de verdad
cambia. Reemplazar un adjetivo marca ese adjetivo, no el párrafo entero.

Uso:
    lote.py <documento.docx> --original o.txt --propuesta p.txt --autor "Corrector" [--json]
"""
import argparse
import difflib
import json
import re
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import intervene as I  # noqa: E402


def _parrafos(texto):
    """Un texto plano en párrafos. Las líneas en blanco separan, no cuentan."""
    return [l.strip() for l in str(texto or "").splitlines() if l.strip()]


def _norm(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _tramo_que_cambia(viejo, nuevo):
    """El fragmento más corto que de verdad cambia, en palabras.

    Recorta el prefijo y el sufijo comunes. Devuelve (buscar, reemplazar) sobre el texto vivo, o
    None si son iguales. Trabaja con palabras y no con caracteres para no partir una palabra por
    la mitad: `buscar` se busca literalmente dentro del párrafo, y medio «despacio» casaría en
    sitios absurdos.
    """
    a, b = viejo.split(" "), nuevo.split(" ")
    ini = 0
    while ini < len(a) and ini < len(b) and a[ini] == b[ini]:
        ini += 1
    fin = 0
    while fin < len(a) - ini and fin < len(b) - ini and a[len(a) - 1 - fin] == b[len(b) - 1 - fin]:
        fin += 1
    if ini == 0 and fin == 0 and viejo == nuevo:
        return None
    buscar = " ".join(a[ini:len(a) - fin])
    reemplazar = " ".join(b[ini:len(b) - fin])
    if buscar == reemplazar:
        return None
    return buscar, reemplazar, ini, fin


def _unico_en(parrafo, buscar, viejo, ini, fin):
    """Extiende `buscar` por los bordes hasta que aparezca UNA sola vez en el párrafo.

    `op_reemplazar` lo exige y hace bien: si «muy despacio» está dos veces, cambiar la primera y
    dejar la segunda es peor que no cambiar nada. Devuelve None si ni el párrafo entero distingue.
    """
    palabras = viejo.split(" ")
    i, f = ini, fin
    while True:
        cand = " ".join(palabras[i:len(palabras) - f])
        if cand and parrafo.count(cand) == 1:
            return cand, i, f
        if i == 0 and f == 0:
            return None            # ni el párrafo entero: no hay ancla
        if i > 0:
            i -= 1
        elif f > 0:
            f -= 1


def construir(parrafos, original, propuesta, autor, motivo=""):
    """Las intervenciones que llevan del original a la propuesta.

    `parrafos`: [{"i","texto","huella"}] tal y como los devuelve `intervene.py --listar --json`,
    es decir, los del documento REAL. `original` y `propuesta`, texto plano.

    Devuelve {lote, sin_ancla, resumen}. Lo que no se puede anclar se DEVUELVE APARTE, nunca se
    aproxima: una intervención que se aplica en el sitio equivocado no se nota hasta que el libro
    está impreso.
    """
    orig = _parrafos(original)
    prop = _parrafos(propuesta)

    # Cada párrafo del original, en su sitio del documento. Se busca por texto normalizado y se
    # avanza: el original viene de este mismo documento, así que el orden se conserva.
    indice = {}
    cursor = 0
    for n, t in enumerate(orig):
        clave = _norm(t)
        for k in range(cursor, len(parrafos)):
            if _norm(parrafos[k]["texto"]) == clave:
                indice[n] = k
                cursor = k + 1
                break

    lote, sin_ancla = [], []
    ops = difflib.SequenceMatcher(None, [_norm(t) for t in orig], [_norm(t) for t in prop]).get_opcodes()

    for etiqueta, i1, i2, j1, j2 in ops:
        if etiqueta == "equal":
            continue

        if etiqueta == "replace":
            # Los que se emparejan, uno a uno; el resto, altas o bajas.
            for k in range(min(i2 - i1, j2 - j1)):
                n = i1 + k
                if n not in indice:
                    sin_ancla.append({"motivo": "el párrafo original no está en el documento",
                                      "texto": orig[n][:120]})
                    continue
                p = parrafos[indice[n]]
                tramo = _tramo_que_cambia(p["texto"], prop[j1 + k])
                if not tramo:
                    continue
                buscar, reemplazar, ini, fin = tramo
                unico = _unico_en(p["texto"], buscar, p["texto"], ini, fin)
                if not unico:
                    # Sin ancla única dentro del párrafo se degrada a borrar + insertar, que
                    # siempre es aplicable. Marca más texto del necesario, pero es correcto.
                    lote.append({"op": "borrar_parrafo", "parrafo": p["i"], "huella": p["huella"],
                                 "autor": autor, "motivo": motivo or "reescritura"})
                    lote.append({"op": "insertar_despues", "parrafo": p["i"], "huella": p["huella"],
                                 "texto": [prop[j1 + k]], "autor": autor,
                                 "motivo": motivo or "reescritura"})
                    continue
                cand, ci, cf = unico
                pal_v, pal_n = p["texto"].split(" "), prop[j1 + k].split(" ")
                lote.append({
                    "op": "reemplazar", "parrafo": p["i"], "huella": p["huella"],
                    "buscar": cand,
                    "reemplazar": " ".join(pal_n[ci:len(pal_n) - cf]),
                    "autor": autor, "motivo": motivo or "reescritura",
                })
            # Sobrantes del original → borrados; sobrantes de la propuesta → inserciones.
            for n in range(i1 + min(i2 - i1, j2 - j1), i2):
                if n not in indice:
                    continue
                p = parrafos[indice[n]]
                if p.get("tabla"):
                    sin_ancla.append({"motivo": "está dentro de una tabla y no se borra",
                                      "texto": orig[n][:120]})
                    continue
                lote.append({"op": "borrar_parrafo", "parrafo": p["i"], "huella": p["huella"],
                             "autor": autor, "motivo": motivo or "poda"})
            resto = [prop[j] for j in range(j1 + min(i2 - i1, j2 - j1), j2)]
            if resto:
                ancla = _ancla_anterior(indice, parrafos, i1)
                if ancla:
                    lote.append({"op": "insertar_despues", "parrafo": ancla["i"],
                                 "huella": ancla["huella"], "texto": resto, "autor": autor,
                                 "motivo": motivo or "añadido"})
                else:
                    sin_ancla.append({"motivo": "no hay párrafo anterior donde colgar el texto nuevo",
                                      "texto": resto[0][:120]})

        elif etiqueta == "delete":
            for n in range(i1, i2):
                if n not in indice:
                    sin_ancla.append({"motivo": "el párrafo a borrar no está en el documento",
                                      "texto": orig[n][:120]})
                    continue
                p = parrafos[indice[n]]
                if p.get("tabla"):
                    sin_ancla.append({"motivo": "está dentro de una tabla y no se borra",
                                      "texto": orig[n][:120]})
                    continue
                lote.append({"op": "borrar_parrafo", "parrafo": p["i"], "huella": p["huella"],
                             "autor": autor, "motivo": motivo or "poda"})

        elif etiqueta == "insert":
            ancla = _ancla_anterior(indice, parrafos, i1)
            nuevos = [prop[j] for j in range(j1, j2)]
            if ancla:
                lote.append({"op": "insertar_despues", "parrafo": ancla["i"],
                             "huella": ancla["huella"], "texto": nuevos, "autor": autor,
                             "motivo": motivo or "añadido"})
            else:
                sin_ancla.append({"motivo": "no hay párrafo anterior donde colgar el texto nuevo",
                                  "texto": nuevos[0][:120]})

    palabras = lambda t: len(str(t or "").split())  # noqa: E731
    return {
        "lote": lote,
        "sin_ancla": sin_ancla,
        "resumen": {
            "reemplazos": sum(1 for x in lote if x["op"] == "reemplazar"),
            "inserciones": sum(1 for x in lote if x["op"] == "insertar_despues"),
            "borrados": sum(1 for x in lote if x["op"] == "borrar_parrafo"),
            "palabras_delta": sum(palabras(t) for t in prop) - sum(palabras(t) for t in orig),
        },
    }


def _ancla_anterior(indice, parrafos, n):
    """El párrafo del documento tras el que colgar texto nuevo: el anterior que sí esté anclado."""
    for k in range(n - 1, -1, -1):
        if k in indice:
            return parrafos[indice[k]]
    return None


def main():
    ap = argparse.ArgumentParser(description="Construye un lote de intervenciones a partir de dos textos.")
    ap.add_argument("documento")
    ap.add_argument("--original", required=True, help="fichero con el texto de partida")
    ap.add_argument("--propuesta", required=True, help="fichero con el texto propuesto")
    ap.add_argument("--autor", default="HumanInk")
    ap.add_argument("--motivo", default="")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    ps = I.parrafos_de(a.documento)
    parrafos = [{"i": i, "texto": I._texto_vivo(p), "huella": I.huella_de(ps, i),
                 "tabla": I._en_tabla(p)}
                for i, p in enumerate(ps) if I._texto_vivo(p).strip()]

    with open(a.original, encoding="utf-8") as f:
        original = f.read()
    with open(a.propuesta, encoding="utf-8") as f:
        propuesta = f.read()

    r = construir(parrafos, original, propuesta, a.autor, a.motivo)
    if a.json:
        print(json.dumps(r, ensure_ascii=False))
    else:
        s = r["resumen"]
        print(f"  {s['reemplazos']} reemplazos · {s['inserciones']} inserciones · "
              f"{s['borrados']} borrados · {s['palabras_delta']:+} palabras")
        for x in r["sin_ancla"]:
            print(f"   ⚠ sin ancla: {x['motivo']} — {x['texto'][:60]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
