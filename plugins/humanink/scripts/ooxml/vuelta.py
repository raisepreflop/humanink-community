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

SIN MARCAS (26-sep-2026). Lo anterior supone que la versión entregada conserva sus marcas, y en la
vida real no las conserva: el autor abre la v05, acepta en Word y GUARDA ENCIMA de la v05. Las marcas
desaparecen del único documento que las tenía, y la lectura de vuelta se quedaba sin nada que
comparar (el proyecto de Rais: diez versiones sin una marca y 375 cambios «sin leer»). Con el
manifiesto no hacen falta: dice, por párrafo, qué se quitaba y qué se ponía. `por_resultado` compara
la versión de ORIGEN de la pasada con la que el autor guardó y clasifica cada cambio por lo que quedó.

Uso:
    vuelta.py <entregada.docx> <guardada.docx> [--notas notas.json] [--json]
    vuelta.py <origen.docx> <guardada.docx> --manifiesto m.json [--notas notas.json] [--json]
"""
import argparse
import difflib
import hashlib
import json
import os
import re
import sys
from collections import Counter

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


# ── Sin marcas: por el resultado, con el manifiesto ──────────────────────────────────────────────

# Por debajo de este parecido, un párrafo no es «el mismo, retocado»: es otro.
PARECIDO_MISMO = 0.5
PARECIDO_RETOCADO = 0.6
PARECIDO_CONSERVADO = 0.75


def _parrafos(ruta):
    """Un texto por cada <w:p> del cuerpo, con las marcas aceptadas: los mismos índices con los que
    la pasada ancló sus cambios (`intervene.parrafos_de`)."""
    raiz = D.leer_xml(ruta)
    cuerpo = raiz.find(D.w("body"))
    if cuerpo is None:
        cuerpo = raiz
    return [_normal(D.texto_de_parrafo(p, D.ACEPTAR)) for p in cuerpo.iter(D.w("p"))]


def _parecido(a, b):
    if not a or not b:
        return 0.0
    m = difflib.SequenceMatcher(None, a, b, autojunk=False)
    if m.real_quick_ratio() < PARECIDO_MISMO or m.quick_ratio() < PARECIDO_MISMO:
        return m.quick_ratio()
    return m.ratio()


def _alinear(antes, despues):
    """Qué párrafo guardado es cada párrafo de origen: `igual[i] = j` si sigue intacto, y el tramo
    del guardado donde buscarlo si cambió."""
    sm = difflib.SequenceMatcher(None, antes, despues, autojunk=False)
    igual, tramo = {}, {}
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        for k in range(i1, i2):
            if tag == "equal":
                igual[k] = j1 + (k - i1)
            else:
                tramo[k] = (j1, j2)
    return igual, tramo


def _cerca(i, igual, tramo, n):
    """Dónde mirar en el guardado por el párrafo de origen `i`."""
    if i in igual:
        return igual[i], igual[i] + 1
    return tramo.get(i, (max(0, min(i, n) - 3), min(n, i + 3)))


def _cuenta(texto, trozo, otro):
    """Veces que aparece `trozo`, sin contar las que son parte de `otro` («casa» dentro de «casa grande»)."""
    if not trozo:
        return 0
    if otro and otro != trozo and trozo in otro:
        texto = texto.replace(otro, "\x00")
    return texto.count(trozo)


def _palabras(t):
    return len(t.split())


def _comun(a, b):
    """Largo del principio común de dos textos."""
    n = 0
    while n < min(len(a), len(b)) and a[n] == b[n]:
        n += 1
    return n


def _fragmento(S, P, q):
    """Lo que hay en el guardado donde estaba lo que se quitaba: `S` sin lo que comparte con el
    principio y el final del párrafo de origen alrededor de `q`."""
    k = P.find(q)
    antes_q, despues_q = P[:k], P[k + len(q):]
    a = 0
    while a < min(len(antes_q), len(S)) and S[a] == antes_q[a]:
        a += 1
    b = 0
    while b < min(len(despues_q), len(S) - a) and S[-1 - b] == despues_q[-1 - b]:
        b += 1
    return S[a:len(S) - b].strip()


def _reemplazo(c, antes, despues, igual, tramo):
    """(resultado, motivo, similitud con lo propuesto o None)."""
    i = c.get("parrafo")
    q, p = _normal(c.get("quita")), _normal(c.get("pone"))
    if not isinstance(i, int) or not 0 <= i < len(antes) or not q or q not in antes[i]:
        return "no_evaluable", "no encuentro su párrafo en la versión de origen", None
    P = antes[i]
    esperado = P.replace(q, p, 1)
    if i in igual:
        return "rechazado", "su párrafo sigue como estaba", None
    a, b = _cerca(i, igual, tramo, len(despues))
    S, mejor = None, 0.0
    for s in despues[max(0, a - 1):b + 1]:
        x = max(_parecido(s, P), _parecido(s, esperado))
        if x > mejor:
            S, mejor = s, x
    if S is None or mejor < PARECIDO_MISMO:
        # Ni cerca: ¿lo movió, o quitó el párrafo entero?
        if esperado and esperado in despues:
            return "aceptado", "está lo propuesto, en otro sitio del libro", 1.0
        if P in despues:
            return "rechazado", "sigue lo que había, en otro sitio del libro", None
        if not p:
            return "aceptado", "quitaste el párrafo entero, y con él lo que se quitaba", 1.0
        return "rechazado", "quitaste el párrafo entero", None
    sale = _cuenta(S, q, p) < _cuenta(P, q, p)
    entra = (_cuenta(S, p, q) > _cuenta(P, p, q)) if p else True
    if not p:
        return ("aceptado", "lo que se quitaba ya no está", 1.0) if sale else ("rechazado", "lo que se quitaba sigue ahí", None)
    if sale and entra:
        return "aceptado", "está lo que se ponía y no lo que se quitaba", 1.0
    # Se compara solo lo que de verdad cambiaba entre lo que había y lo propuesto: lo que comparten
    # (el arranque de la frase, el punto final) haría parecer «retocado» cualquier texto del autor.
    cp = _comun(q, p)
    cs = _comun(q[cp:][::-1], p[cp:][::-1])
    qc, pc = q[cp:len(q) - cs], p[cp:len(p) - cs]
    trozo = _fragmento(S, P, q)
    fc = trozo[_comun(trozo, q[:cp]):]
    fc = fc[:len(fc) - _comun(fc[::-1], q[len(q) - cs:][::-1])].strip()
    con_lo_propuesto = _parecido(fc, pc.strip()) if pc.strip() else 0.0
    con_lo_que_habia = _parecido(fc, qc.strip()) if qc.strip() else 0.0
    if not sale and not entra:
        # Lo que había sigue entero. Solo si lo propuesto era AÑADIR a eso («vacío» → «vacío y frío»)
        # y el autor añadió otra cosa en el mismo sitio, escribió encima de lo nuestro.
        if S != P and not qc.strip() and fc:
            return "retocado", "escribiste encima de lo propuesto", round(max(con_lo_propuesto, 0.1), 3)
        return "rechazado", "sigue lo que había", None
    if sale and not entra:
        if con_lo_propuesto >= PARECIDO_MISMO and con_lo_propuesto > con_lo_que_habia:
            return "retocado", "escribiste encima de lo propuesto", round(con_lo_propuesto, 3)
        # Quitó lo que había, pero no por lo nuestro: el texto es suyo (M-21, AWAP ×5 texto propio).
        return "suyo", ("lo cambiaste por texto tuyo" if trozo else "lo quitaste tú, sin lo propuesto"), None
    return "retocado", "están lo propuesto y lo que había", round(con_lo_propuesto, 3)


# El manifiesto guarda como mucho 2.000 caracteres por campo (`manifiesto.mjs`, LIMITE): de una
# inserción larga solo se conoce el principio, y su último párrafo visible puede estar cortado.
LIMITE_MANIFIESTO = 2000


def huella(t):
    """La misma que `manifiesto.mjs` (huellaDeParrafo): 16 hex de SHA-1 del texto normalizado."""
    return hashlib.sha1(_normal(t).encode("utf-8")).hexdigest()[:16]


def _nuevos(c, por_huella=None):
    """Los párrafos que una inserción ponía, y si el manifiesto los guarda enteros.

    Con `pone_huellas` (manifiestos desde el 26-sep) se reconocen todos, aunque `pone` vaya cortado:
    cada huella se traduce al párrafo del documento que la tiene. Una huella que no está en ningún
    lado es un párrafo que no quedó, y se representa con algo que no puede coincidir con nada.
    """
    huellas = c.get("pone_huellas")
    if huellas and por_huella is not None:
        return [por_huella.get(h, "\x00" + h) for h in huellas], False
    crudo = str(c.get("pone") or "")
    nuevos = [x for x in (_normal(t) for t in re.split(r"\n\s*\n", crudo)) if x]
    return nuevos, len(crudo) >= LIMITE_MANIFIESTO


class _Contexto:
    """Lo que comparten todas las lecturas de una versión."""

    def __init__(self, cambios, antes, despues, minimo, por_huella):
        self.antes, self.despues, self.minimo, self.por_huella = antes, despues, minimo, por_huella
        self.igual, self.tramo = _alinear(antes, despues)
        self.de_origen = {j: i for i, j in self.igual.items()}
        self.cuenta_antes, self.cuenta_despues = Counter(antes), Counter(despues)
        self.borrados = {c.get("parrafo") for c in cambios if c.get("op") == "borrar_parrafo"}
        self.borrados_txt = {antes[i] for i in self.borrados if isinstance(i, int) and 0 <= i < len(antes) and antes[i]}
        # Los párrafos que ponían las inserciones de esta pasada (los que el manifiesto conoce).
        self.nuestros = set()
        for c in cambios:
            if c.get("op") == "insertar_despues":
                self.nuestros.update(_nuevos(c, por_huella)[0])
        self.repuesto_por = {}     # párrafo re-puesto igual → resultado de la inserción que lo ponía
        self.regiones = []         # (inicio, fin) de inserciones CORTADAS aceptadas: lo que no se ve

    def esta(self, x, cortado):
        """¿Está este párrafo nuestro en el guardado? Si el manifiesto lo cortó, basta con su principio."""
        if self.cuenta_despues[x] > self.cuenta_antes[x]:
            return True
        return cortado and any(s.startswith(x) and not self.cuenta_antes[s] for s in self.despues)

    def donde(self, x, cortado):
        for j, s in enumerate(self.despues):
            if (s == x or (cortado and s.startswith(x))) and self.cuenta_despues[s] > self.cuenta_antes[s]:
                return j
        return None

    def fin_de_region(self, ancla, desde):
        """El primer párrafo del guardado, tras `desde`, que es un párrafo de origen posterior al
        ancla que la pasada no borraba: ahí acaba lo que trajo la inserción."""
        for j in sorted(self.de_origen):
            i = self.de_origen[j]
            if j > desde and i > ancla and i not in self.borrados:
                return j
        return len(self.despues)


def _insercion(c, cx):
    """(resultado, motivo, similitud)."""
    todos, cortado = _nuevos(c, cx.por_huella)
    if not todos:
        return "no_evaluable", "no se ponía texto", None
    ultimo = todos[-1]
    # Lo que la inserción volvía a poner y la pasada borraba en su sitio no dice nada por sí solo:
    # está igual si se aceptó todo que si se rechazó todo. Se lee por lo que traía de nuevo.
    nuevos = [x for x in todos if x not in cx.borrados_txt]
    if cortado and nuevos and nuevos[-1] is ultimo and any(s.startswith(ultimo) for s in cx.borrados_txt):
        nuevos.pop()
    ancla = c.get("parrafo") if isinstance(c.get("parrafo"), int) else -1
    if not nuevos:
        if cortado:
            return "no_evaluable", "el manifiesto no guarda lo nuevo que añadía (solo su principio)", None
        return "sin_efecto", "la pasada volvía a poner párrafos que ya estaban", None
    corta = [cortado and x is ultimo for x in nuevos]
    marca = [cx.esta(x, corta[k]) for k, x in enumerate(nuevos)]
    estan = sum(marca)
    if estan == len(nuevos):
        if cortado:
            # Lo visible está; lo que el manifiesto no guarda se estima por palabras: desde lo último
            # que se ve hasta el siguiente párrafo que la pasada no tocaba.
            ultimo_j = cx.donde(nuevos[-1], corta[-1])
            primero_j = cx.donde(nuevos[0], corta[0])
            if ultimo_j is not None and primero_j is not None:
                fin = cx.fin_de_region(ancla, ultimo_j)
                cx.regiones.append((ultimo_j, fin))
                hay = sum(_palabras(s) for s in cx.despues[primero_j:fin])
                total = int(c.get("palabras") or 0)
                if total and hay < 0.85 * total:
                    return "retocado", "falta parte de lo que se añadía", round(hay / total, 3)
            return "aceptado", "está lo que se añadía (el manifiesto guarda solo su principio)", 1.0
        return "aceptado", "están los párrafos que se añadían", 1.0
    if estan:
        dentro = sum(_palabras(x) for k, x in enumerate(nuevos) if marca[k])
        return "retocado", f"te quedaste con {estan} de {len(nuevos)} párrafos", round(dentro / max(1, sum(map(_palabras, nuevos))), 3)
    # Ninguno está tal cual: ¿escribió encima de lo propuesto, o solo retocó lo suyo?
    a, _b = _cerca(ancla if ancla >= 0 else 0, cx.igual, cx.tramo, len(cx.despues))
    cerca_origen = [P for P in cx.antes[max(0, ancla - 5):ancla + len(todos) + 40] if P]
    largos = [x for x in nuevos if len(x) >= cx.minimo]
    mejor = 0.0
    for s in cx.despues[max(0, a - 2):a + len(todos) + 40]:
        if not s or cx.cuenta_antes[s]:
            continue
        nuestro = max((_parecido(x, s) for x in largos), default=0.0)
        suyo = max((_parecido(P, s) for P in cerca_origen), default=0.0)
        if nuestro >= PARECIDO_RETOCADO and nuestro > suyo:
            mejor = max(mejor, nuestro)
    if mejor:
        return "retocado", "escribiste encima de los párrafos añadidos", round(mejor, 3)
    return "rechazado", "no están los párrafos que se añadían", None


def _borrado(c, cx):
    i = c.get("parrafo")
    if not isinstance(i, int) or not 0 <= i < len(cx.antes):
        return "no_evaluable", "no encuentro su párrafo en la versión de origen", None
    P = cx.antes[i]
    if not P:
        return "no_evaluable", "era un párrafo vacío", None
    hay, habia = cx.cuenta_despues[P], cx.cuenta_antes[P]
    # 1. Una inserción de esta pasada lo volvía a poner igual.
    r = cx.repuesto_por.get(P)
    if r in ("aceptado", "retocado", "sin_efecto"):
        if hay > habia:
            return "rechazado", "el párrafo está dos veces: el tuyo y el que volvía a poner la pasada", None
        if hay == habia:
            return "sin_efecto", "la pasada lo quitaba y lo volvía a poner igual", None
        return "aceptado", "el párrafo ya no está", 1.0
    a, b = _cerca(i, cx.igual, cx.tramo, len(cx.despues))
    donde = [cx.igual[i]] if i in cx.igual else [j for j in range(max(0, a - 2), min(len(cx.despues), b + 2)) if cx.despues[j] == P]
    # 2. Lo que una inserción cortada traía y el manifiesto no guarda: si está donde ella quedó.
    if P not in cx.nuestros and any(ini < j < fin for j in donde for ini, fin in cx.regiones):
        if hay > habia:
            return "rechazado", "el párrafo está dos veces: el tuyo y el que volvía a poner la pasada", None
        if hay == habia:
            return "sin_efecto", "la pasada lo quitaba y lo volvía a poner igual", None
    # Lo que trajo la pasada es nuestro, no el párrafo viejo conservado: el título «ESCENA 15.3 —
    # LA CONFESIÓN» se parece al que se borraba, pero es el de la escena nueva.
    ventana = [cx.despues[j] for j in range(max(0, a - 2), min(len(cx.despues), b + 2))
               if cx.despues[j] and cx.despues[j] not in cx.nuestros and not any(ini < j < fin for ini, fin in cx.regiones)]
    retocado_por_ti = len(P) >= cx.minimo and any(s != P and _parecido(P, s) >= PARECIDO_CONSERVADO for s in ventana)
    if hay < habia:
        # Una copia se fue. Si queda otra igual es otra copia (un «—No.» repetido); solo cuenta como
        # conservado si lo que queda es ESTE párrafo retocado.
        if retocado_por_ti:
            return "rechazado", "conservaste el párrafo, retocado por ti", None
        return "aceptado", "el párrafo ya no está", 1.0
    if i in cx.igual or P in ventana or retocado_por_ti:
        return "rechazado", "conservaste el párrafo", None
    return "aceptado", "el párrafo ya no está", 1.0


def por_resultado(manifiesto, origen, guardada, lista=None, minimo=MIN_RASTREABLE):
    """Cada cambio del manifiesto, clasificado por lo que quedó en el documento que el autor guardó.

    `origen` es la versión de la que partió la pasada y `guardada` la versión que ella escribió, tal
    como el autor la dejó al guardar desde Word. Sin marcas: la prueba es el texto.

    Resultados: aceptado · retocado (escribió encima de lo propuesto) · rechazado · suyo (cambió el
    original por texto propio, sin lo propuesto) · sin_efecto (lo que la pasada quitaba y volvía a
    poner igual: no es una decisión de nadie y no cuenta) · no_evaluable. `similitud` dice cuánto de
    lo propuesto quedó (1 = tal cual), para que un retoque no pese como una reescritura entera.
    """
    antes, despues = _parrafos(origen), _parrafos(guardada)
    cambios = manifiesto.get("cambios") or []
    por_huella = {huella(x): x for x in antes + despues if x}
    cx = _Contexto(cambios, antes, despues, minimo, por_huella)
    # Las inserciones primero: de lo que pasó con ellas depende cómo se leen los borrados.
    resultados = {}
    for c in cambios:
        if c.get("op") == "insertar_despues":
            r = _insercion(c, cx)
            resultados[c.get("n")] = r
            for x in _nuevos(c, por_huella)[0]:
                if x in cx.borrados_txt:
                    cx.repuesto_por[x] = r[0]
    uno_a_uno = []
    total = Counter()
    for c in cambios:
        op = c.get("op")
        if op == "reemplazar":
            r, motivo, sim = _reemplazo(c, antes, despues, cx.igual, cx.tramo)
        elif op == "borrar_parrafo":
            r, motivo, sim = _borrado(c, cx)
        elif op == "insertar_despues":
            r, motivo, sim = resultados[c.get("n")]
        else:
            r, motivo, sim = "no_evaluable", f"operación desconocida: {op}", None
        total[r] += 1
        uno_a_uno.append({"n": c.get("n"), "op": op, "resultado": r, "motivo": motivo, "similitud": sim})
    t = {"propuestas": len(cambios), "aceptadas": total["aceptado"], "rechazadas": total["rechazado"],
         "retocadas": total["retocado"], "suyas": total["suyo"], "no_evaluables": total["no_evaluable"],
         "sin_efecto": total["sin_efecto"]}
    t["evaluadas"] = t["aceptadas"] + t["rechazadas"] + t["retocadas"] + t["suyas"]
    t["ratio"] = round(t["aceptadas"] / t["evaluadas"], 3) if t["evaluadas"] else None
    return {
        "metodo": "resultado",
        "total": t,
        "cambios": uno_a_uno,
        "origen": os.path.basename(origen),
        "entregada": os.path.basename(guardada),
        "guardada": os.path.basename(guardada),
        "pendientes": sum(1 for _ in D.revisiones(guardada)),
        "minimo_rastreable": minimo,
        "notas": notas(origen, guardada, lista or [], minimo),
    }


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
    ap.add_argument("--manifiesto", help="sin marcas: el manifiesto de la pasada; el primer documento es su ORIGEN")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    lista = []
    if a.notas:
        with open(a.notas, encoding="utf-8") as f:
            d = json.load(f)
        lista = d.get("notas", d) if isinstance(d, dict) else d
    if a.manifiesto:
        with open(a.manifiesto, encoding="utf-8") as f:
            m = json.load(f)
        r = por_resultado(m, a.entregada, a.guardada, lista, a.min)
    else:
        r = leer(a.entregada, a.guardada, lista, a.min, a.detalle)
    print(json.dumps(r, ensure_ascii=False, indent=2)) if a.json else imprimir(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
