#!/usr/bin/env python3
"""AWAP local — el registro de autoría, en la carpeta del libro y sin conector.

    python3 awap_local.py iniciar  <carpeta> --titulo "…" --autor "…"
    python3 awap_local.py base     <carpeta> <manuscrito>          manuscrito escrito antes de HumanInk
    python3 awap_local.py declarar <carpeta> <fichero> --origen humano|ia [--tipo T]
    python3 awap_local.py estado   <carpeta> [--json]
    python3 awap_local.py informe  <carpeta>
    python3 awap_local.py nota     <carpeta>
    python3 awap_local.py registro <carpeta> [--n 30]
    python3 awap_local.py verificar <carpeta>
    python3 awap_local.py certificado <carpeta> [--salida fichero.pdf]
    python3 awap_local.py inicio   <ruta>                          lo llama hi-args.py
    python3 awap_local.py fin      <ruta> --colab slug [--nombre N] [--modo M]   lo llama hi-log.sh
    python3 awap_local.py escrito  <fichero>                       lo llama el gancho de Write/Edit

POR QUÉ EXISTE (1-oct-2026). AWAP salió de la edición del Club el 10 de septiembre porque vivía en un
conector remoto: con un conector declarado, Cowork deshabilita el plugin hasta que el servidor
contesta. Pero el registro de autoría no necesita servidor: necesita ver los ficheros. Esto lo lleva
entero en `<carpeta del libro>/.awap/local/`, con la biblioteca estándar y nada más.

QUÉ MIDE, Y CÓMO. No pregunta a nadie cuántas palabras ha escrito: compara ficheros.
  - Lo que cambia MIENTRAS trabaja un colaborador de HumanInk es de la IA.
  - Lo que cambia ENTRE dos colaboradores es tuyo.
  - Cada palabra de cada documento lleva su procedencia (tuya o de la IA). Cuando un documento
    cambia, las palabras que siguen en su sitio conservan la suya y las nuevas son de quien hizo el
    cambio. Un fichero nuevo que sale de otro (una versión corregida, una copia) hereda la del
    original.
  - La procedencia va con el TEXTO, no con el fichero: un párrafo de la IA pegado en tu novela,
    cambiado de orden, partido en dos ficheros o guardado con otro nombre sigue siendo de la IA
    (`Indice`: todos los párrafos vistos y todos los tramos de cinco palabras de la IA).
  - Ante la duda, de la IA. Si una sesión de colaborador no se cerró, TODO lo que haya cambiado
    hasta la siguiente vez que se mira cuenta como generado y se marca «incierto»; tú puedes
    declararlo tuyo, y la declaración queda a la vista.

EL HAS es el de AWAP 1, con la misma fórmula que el servidor (`aip-server/src/engine/has-core.js`,
portada en `calcular_has` y comprobada contra el original en `test_awap_local.py`): la concepción
pesa 360 de 390 puntos. Lo local es la REDUCCIÓN: de los documentos vivos sale una entrada por
nivel, ponderada por palabras.

LO QUE NO ES. No está anclado en ningún servidor: el registro va encadenado (cada línea lleva la
huella de la anterior), así que una edición parcial se nota, pero quien tenga la carpeta puede
rehacerlo entero. El certificado que sale de aquí lo dice con esas palabras.
"""
import argparse
import datetime
import gzip
import hashlib
import json
import math
import os
import re
import sys
import time
import unicodedata
import uuid
import zipfile
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher

ESQUEMA = 1
VERSION_HAS = "awap1-local-1"
# En `.awap/local/`, no en `.awap/` a secas: el AWAP de Claude Code (aip-server) guarda ahí su
# `awap.db` y migra cualquier `.awap/project.json` que encuentre creyéndolo suyo.
DIR = os.path.join(".awap", "local")
EXTENSIONES = (".docx", ".md", ".txt")
PROFUNDIDAD = 6
MAX_FICHEROS = 3000
MAX_BYTES = 300 * 1024 * 1024
MIN_PARRAFO = 3             # palabras de un párrafo para reconocerlo en otro sitio
MIN_BASE = 500              # palabras tuyas en el manuscrito para que acredite la concepción sin documento
MIN_BASE_DOC = 3000         # y para que acredite entero un documento de concepción que redacta la IA
SESION_VIVA = 3 * 3600      # una sesión de colaborador sin cerrar se da por viva este tiempo
GRACIA_CIERRE = 120         # lo que se escribe hasta dos minutos después del cierre aún es del colaborador
HUECO = 45 * 60             # tres cuartos de hora sin señales: la sesión abierta era de otro colaborador
TRAS_ESCRITO = 600          # tras una escritura de la IA avisada por el gancho, lo que cambie en diez minutos
CERROJO_VIEJO = 120         # un cerrojo de más de dos minutos es de un proceso que murió
UMBRAL_FUENTE = 0.30        # parte de un fichero nuevo que tiene que venir de otro para ser «derivado»
COBERTURA_RELEVO = 0.60     # tamaño mínimo, respecto al original, para que el nuevo lo sustituya
TROZO = 3000                # palabras por trozo al comparar un bloque enorme

PUNTOS = {1: 100, 2: 85, 3: 75, 4: 60, 5: 40, 6: 25, 7: 5}
ETIQUETAS = {1: "Premisa", 2: "Sinopsis", 3: "Biblia", 4: "Escaleta", 5: "Estilo y voz",
             6: "Revisión humana", 7: "Texto"}
NIVEL_DE = {"premise": 1, "synopsis": 2, "bible": 3, "outline": 4, "style_instructions": 5,
            "revision": 6, "draft": 7}
NOMBRE_TIPO = {"premise": "premisa", "synopsis": "sinopsis", "bible": "biblia", "outline": "escaleta",
               "style_instructions": "estilo", "draft": "manuscrito"}
NIVELES = (1, 2, 3, 4, 5, 6, 7)
CONCEPCION = (1, 2, 3, 4, 5)


# ───────────────────────────── utilidades ─────────────────────────────

def ahora():
    """Segundos desde la época. `AWAP_AHORA` lo fija en las pruebas."""
    v = os.environ.get("AWAP_AHORA")
    return float(v) if v else time.time()


def iso(t=None):
    return datetime.datetime.fromtimestamp(ahora() if t is None else t, datetime.timezone.utc) \
        .strftime("%Y-%m-%dT%H:%M:%SZ")


def r2(n):
    """El redondeo de `Math.round(n*100)/100` de has-core.js (medio hacia arriba, no al par)."""
    return math.floor(n * 100 + 0.5) / 100


def _plano(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).lower()



def _leer_json(ruta, defecto=None):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return defecto


def _guardar_json(ruta, dato):
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dato, f, ensure_ascii=False, indent=1)
    os.replace(tmp, ruta)


def raiz_de(ruta, niveles=7):
    """La carpeta del libro: la primera, subiendo desde `ruta`, que tiene `.awap/local/project.json`."""
    p = os.path.abspath(os.path.expanduser(ruta or "."))
    if os.path.isfile(p):
        p = os.path.dirname(p)
    for _ in range(niveles + 1):
        if os.path.isfile(os.path.join(p, DIR, "project.json")):
            return p
        arriba = os.path.dirname(p)
        if arriba == p:
            break
        p = arriba
    return None


# ───────────────────────────── leer documentos ─────────────────────────────

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_FUERA = {_W + "del", _W + "delText", _W + "instrText", _W + "moveFrom"}


def _texto_nodo(nodo):
    partes = []
    for hijo in nodo:
        e = hijo.tag
        if e in _FUERA:
            continue
        if e == _W + "t":
            partes.append(hijo.text or "")
        elif e == _W + "tab":
            partes.append("\t")
        elif e in (_W + "br", _W + "cr"):
            partes.append("\n")
        else:
            partes.append(_texto_nodo(hijo))
    return "".join(partes)


def parrafos_de(ruta):
    """Los párrafos de un documento. En un .docx, el texto tal como queda ACEPTANDO los cambios
    pendientes: lo insertado cuenta y lo borrado no. Devuelve None si no se puede leer."""
    try:
        if ruta.lower().endswith(".docx"):
            with zipfile.ZipFile(ruta) as z:
                raiz = ET.fromstring(z.read("word/document.xml"))
            cuerpo = raiz.find(_W + "body")
            ps = [_texto_nodo(p).strip() for p in (cuerpo.iter(_W + "p") if cuerpo is not None else [])]
        else:
            with open(ruta, encoding="utf-8", errors="replace") as f:
                ps = [p.strip() for p in re.split(r"\n\s*\n", f.read())]
        return [p for p in ps if p]
    except Exception:
        return None


_PALABRA = re.compile(r"[^\W_]+(?:['’][^\W_]+)*", re.UNICODE)
# Guiones blandos, espacios de ancho cero y demás caracteres que no se ven: metidos dentro de una
# palabra la partían en dos y dejaba de reconocerse (equipo rojo, 1-oct-2026).
_INVISIBLES = re.compile("[\u00ad\u200b-\u200f\u2060-\u2064\ufeff]")


def palabras(texto):
    """Las palabras, sin puntuación y sin distinguir mayúsculas: una coma o una mayúscula corregida
    no es una palabra nueva."""
    return [p.casefold() for p in _PALABRA.findall(_INVISIBLES.sub("", texto))]


# ───────────────────────────── la procedencia, palabra a palabra ─────────────────────────────

def _casar_palabras(vp, vf, np_, quien, estricto):
    """Marcas de procedencia para las palabras nuevas `np_`, sabiendo las viejas `vp` con sus marcas
    `vf`. Lo que se conserva en su sitio hereda; lo demás es de `quien`."""
    if not np_:
        return ""
    if not vp:
        return quien * len(np_)
    if len(vp) + len(np_) > 4 * TROZO:
        # Un bloque enorme sin un solo párrafo intacto: se compara por trozos proporcionales, para
        # no pedirle a difflib cien mil palabras contra cien mil.
        n = max(1, math.ceil(max(len(vp), len(np_)) / TROZO))
        out = []
        for i in range(n):
            a0, a1 = len(vp) * i // n, len(vp) * (i + 1) // n
            b0, b1 = len(np_) * i // n, len(np_) * (i + 1) // n
            out.append(_casar_palabras(vp[a0:a1], vf[a0:a1], np_[b0:b1], quien, estricto))
        return "".join(out)
    # difflib da por «ruido» las palabras muy repetidas cuando el texto pasa de 200; en un bloque
    # pequeño eso deja sin casar justo lo que no ha cambiado, así que ahí se apaga.
    sm = SequenceMatcher(None, vp, np_, autojunk=len(vp) * len(np_) > 400_000)
    # En un texto reescrito de arriba abajo siguen coincidiendo «de», «la», «que» sueltos, en orden.
    # Eso no es conservar nada: si los dos textos se parecen poco, solo valen los tramos de varias
    # palabras seguidas. El listón es más alto cuando quien cambia es la IA (`estricto`): ante la
    # duda, lo que reescribe la IA es de la IA, y lo que reescribes tú sobre un texto de la IA
    # sigue siendo de la IA.
    parecido = sm.ratio()
    if estricto:
        minimo = 1 if parecido >= 0.5 else 4
    else:
        minimo = 1 if parecido >= 0.3 else 3
    marcas = [quien] * len(np_)
    for a, b, n in sm.get_matching_blocks():
        if n >= minimo:
            marcas[b:b + n] = vf[a:a + n]
    return "".join(marcas)


def trasladar(viejo, nuevo_p, quien, estricto=True):
    """Procedencia de un texto nuevo a partir del anterior.

    `viejo` es {"p": [párrafos], "f": [marcas por párrafo]} o None; `nuevo_p`, la lista de párrafos
    nuevos; `quien`, la letra que llevarán las palabras nuevas; `estricto`, si quien cambia es la IA. Devuelve las marcas, una cadena por párrafo
    con una letra por palabra.
    """
    nw = [palabras(p) for p in nuevo_p]
    if not viejo or not viejo.get("p"):
        return [quien * len(w) for w in nw]
    vw = [palabras(p) for p in viejo["p"]]
    vf = list(viejo["f"])
    # Un párrafo es «el mismo» si tiene las mismas palabras: un cambio de puntuación no lo mueve.
    va = [" ".join(w) for w in vw]
    na = [" ".join(w) for w in nw]
    out = [None] * len(nw)
    for op, i1, i2, j1, j2 in SequenceMatcher(None, va, na, autojunk=False).get_opcodes():
        if op == "equal":
            for k in range(j2 - j1):
                out[j1 + k] = vf[i1 + k]
        elif op == "insert":
            for j in range(j1, j2):
                out[j] = quien * len(nw[j])
        elif op == "replace":
            hecho = False
            if i2 - i1 == j2 - j1:
                # Tantos párrafos como había: lo normal es que cada uno sea el suyo, retocado. Se
                # comprueba: si la mayoría no se parece a su pareja, es que no iban emparejados.
                pares = [SequenceMatcher(None, vw[i1 + k], nw[j1 + k], autojunk=False).ratio() >= 0.3
                         for k in range(j2 - j1)]
                if sum(pares) * 2 >= len(pares):
                    for k in range(j2 - j1):
                        out[j1 + k] = _casar_palabras(vw[i1 + k], vf[i1 + k], nw[j1 + k], quien, estricto)
                    hecho = True
            if not hecho:
                # Junto: un párrafo partido en dos, o dos unidos, siguen casando.
                vp = [w for i in range(i1, i2) for w in vw[i]]
                np_ = [w for j in range(j1, j2) for w in nw[j]]
                todo = _casar_palabras(vp, "".join(vf[i1:i2]), np_, quien, estricto)
                c = 0
                for j in range(j1, j2):
                    out[j] = todo[c:c + len(nw[j])]
                    c += len(nw[j])
    return [m if m is not None else "" for m in out]


def _tejas(lista_palabras, n=5):
    return {hash(tuple(lista_palabras[i:i + n])) for i in range(len(lista_palabras) - n + 1)}


def _h_parrafo(ws):
    """Huella estable de un párrafo (la de `hash()` cambia en cada arranque de Python)."""
    return hashlib.blake2b(" ".join(ws).encode("utf-8"), digest_size=8).hexdigest()


class Indice:
    """Todo el texto que el registro ha visto, para reconocerlo cuando reaparece en otro sitio.

    (Equipo rojo, 1-oct-2026.) La procedencia se heredaba del propio fichero o de UN fichero del que
    saliera el nuevo. Bastaba pegar un capítulo generado al final de la novela, montar cuatro en un
    manuscrito, partir uno en dos o darle la vuelta a los párrafos para que contase como del autor.
    Aquí está, de todas las instantáneas guardadas (también las de ficheros que ya no existen):
      - `parrafos`: cada párrafo, por sus palabras → sus marcas;
      - `tejas_ia`: cada tramo de cinco palabras seguidas en el que alguna es de la IA → sus marcas.
    Cuando el mismo texto está en dos sitios con marcas distintas, gana la que tiene más de la IA.
    """

    def __init__(self, p, esperadas=None, archivadas=0):
        """`esperadas`: {nombre del fichero de instantánea: huella anotada en el registro};
        `archivadas`: cuántas palabras de la IA dice el registro que hay en el archivo. Si algo no
        cuadra, `integro` queda en falso: lo guardado no es de fiar y quien mira no puede acreditar
        nada nuevo al autor."""
        self.p = p
        self.integro = True
        self._tejas_h = None
        self._viejas_h = []        # instantáneas sobrescritas en esta pasada: su texto propio sigue contando
        self.h_pars, self.por_palabra_h = [], {}
        self.parrafos = {}
        self.tejas_ia = {}
        self.ia_pars = []          # párrafos con algo de la IA: (palabras, marcas)
        self.ia_vistos = set()
        self.por_palabra = {}      # palabra larga → en qué párrafos de la IA sale
        try:
            nombres = sorted(os.listdir(p.d_textos))
        except OSError:
            nombres = []
        for n in nombres:
            if not n.endswith(".json.gz"):
                continue
            try:
                with gzip.open(os.path.join(p.d_textos, n), "rt", encoding="utf-8") as f:
                    snap = json.load(f)
                if esperadas and n in esperadas and Proyecto.huella_texto(snap["p"], snap["f"]) != esperadas[n]:
                    self.integro = False
                self.sumar(snap["p"], snap["f"], snap.get("h"))
            except Exception:
                if esperadas and n in esperadas:
                    self.integro = False
                continue
        # Y lo que la IA escribió y ya no está en ninguna instantánea (ver `guardar_instantanea`).
        en_archivo = 0
        try:
            with gzip.open(p.f_archivo_ia, "rt", encoding="utf-8") as f:
                for linea in f:
                    try:
                        x = json.loads(linea)
                        self.sumar([x["p"]], [x["f"]], [x.get("h")] if x.get("h") else None)
                        en_archivo += x["f"].count("A")
                    except Exception:
                        continue
        except Exception:
            pass
        if en_archivo < archivadas:
            self.integro = False

    @staticmethod
    def _mas_ia(a, b):
        return a if a.count("A") >= b.count("A") else b

    def conocidas_del_autor(self, pars, marcas):
        """De las palabras «N» (nuevas) de un documento, cuáles caen en un tramo de cinco palabras
        que YA era del autor en algún texto guardado: una lista con un sí o un no por palabra. No son
        nuevas: son suyas, pero copiadas.

        (Equipo rojo, 1-oct-2026.) Tapar un capítulo de la IA con párrafos de la propia novela no
        contaba si eran idénticos, pero bastaba añadirles una palabra, unirlos de dos en dos o
        pegarlos con otro formato para que contasen como escritura nueva: 22 de los 25 puntos de
        revisión sin escribir. Solo se calcula cuando hace falta (el autor ha quitado texto de la IA
        y ha puesto otro): recorre todas las instantáneas."""
        if self._tejas_h is None:
            self._tejas_h = set()
            try:
                nombres = sorted(os.listdir(self.p.d_textos))
            except OSError:
                nombres = []
            for n in nombres:
                if not n.endswith(".json.gz"):
                    continue
                try:
                    with gzip.open(os.path.join(self.p.d_textos, n), "rt", encoding="utf-8") as f:
                        snap = json.load(f)
                except Exception:
                    continue
                self.recordar_h(snap["p"], snap["f"])
            for p_, f_ in self._viejas_h:
                self.recordar_h(p_, f_)
        ws_por = [palabras(par) for par in pars]
        ws = [w for l in ws_por for w in l]
        m = "".join(marcas)
        cubierta = [False] * len(ws)
        for i in range(len(ws) - 4):
            if "N" in m[i:i + 5] and hash(tuple(ws[i:i + 5])) in self._tejas_h:
                for k in range(5):
                    cubierta[i + k] = True
        # Y el párrafo propio retocado más de una palabra de cada cinco (relleno cada cuatro, pares
        # cambiados de orden, una de cada tres traducida): el mismo casado difuso que protege a los
        # párrafos de la IA en `heredar`, aplicado a los tuyos. Cuenta como copiado lo que casa.
        c = 0
        for j, (par_ws, mp) in enumerate(zip(ws_por, marcas)):
            if "N" in mp and len(par_ws) >= 8 and self.h_pars:
                largas = {w for w in par_ws if len(w) >= 5}
                votos = {}
                for w in largas:
                    sitios = self.por_palabra_h.get(w)
                    if sitios and len(sitios) <= 60:
                        for k in sitios:
                            votos[k] = votos.get(k, 0) + 1
                minimo = max(4, 0.3 * len(largas))
                for k, n in sorted(votos.items(), key=lambda kv: -kv[1])[:3]:
                    if n < minimo:
                        break
                    suyas = _casar_palabras(self.h_pars[k][0], self.h_pars[k][1], par_ws, "N", False)
                    for i, (x, y) in enumerate(zip(mp, suyas)):
                        if x == "N" and y == "H":
                            cubierta[c + i] = True
            c += len(par_ws)
        return [c and m[i] == "N" for i, c in enumerate(cubierta)]

    def recordar_h(self, pars, marcas):
        """Los tramos de cinco palabras tuyas y los párrafos tuyos de un texto guardado, para
        `conocidas_del_autor`. Se llama al construir los tramos y, si ya están construidos, con cada
        texto que se guarda o se sobrescribe durante la pasada (si no, lo que se guardó antes en la
        misma pasada no se reconocía, y dependía del orden de los ficheros)."""
        if self._tejas_h is None:
            self._viejas_h.append((pars, marcas))
            return
        ws_todo, m_todo = [], []
        for par, m in zip(pars, marcas):
            ws = palabras(par)
            if len(ws) != len(m):
                return
            ws_todo.extend(ws)
            m_todo.append(m)
            if "H" in m and len(ws) >= 8:
                k = len(self.h_pars)
                self.h_pars.append((ws, m))
                for w in set(ws):
                    if len(w) >= 5:
                        self.por_palabra_h.setdefault(w, []).append(k)
        m_todo = "".join(m_todo)
        for i in range(len(ws_todo) - 4):
            if m_todo[i:i + 5] == "HHHHH":
                self._tejas_h.add(hash(tuple(ws_todo[i:i + 5])))

    def sumar(self, pars, marcas, hashes=None):
        if self._tejas_h is not None:
            self.recordar_h(pars, marcas)
        ws_todo, m_todo = [], []
        hay_ia = any("A" in m for m in marcas)
        for i, (par, m) in enumerate(zip(pars, marcas)):
            ws = None
            if hay_ia:
                ws = palabras(par)
                ws_todo.extend(ws)
                m_todo.append(m)
            if len(m) >= MIN_PARRAFO:
                h = hashes[i] if hashes and i < len(hashes) and hashes[i] else \
                    _h_parrafo(ws if ws is not None else palabras(par))
                ant = self.parrafos.get(h)
                self.parrafos[h] = m if ant is None or len(ant) != len(m) else self._mas_ia(ant, m)
                if "A" in m and len(m) >= 8 and (h, m) not in self.ia_vistos and len(ws) == len(m):
                    self.ia_vistos.add((h, m))
                    k = len(self.ia_pars)
                    self.ia_pars.append((ws, m))
                    for w in set(ws):
                        if len(w) >= 5:
                            self.por_palabra.setdefault(w, []).append(k)
        if hay_ia:
            # Los tramos se cuentan sobre el texto seguido, sin mirar dónde acaba cada párrafo: así
            # una ristra de frases cortas de diálogo también se reconoce.
            m_todo = "".join(m_todo)
            for i in range(len(ws_todo) - 4):
                seg = m_todo[i:i + 5]
                if "A" in seg:
                    k = hash(tuple(ws_todo[i:i + 5]))
                    ant = self.tejas_ia.get(k)
                    self.tejas_ia[k] = seg if ant is None else self._mas_ia(ant, seg)

    def heredar(self, pars, marcas, cambia_el_autor):
        """Resuelve las palabras «N» (nuevas) de un documento contra lo ya visto. Un párrafo que ya
        existía, idéntico, trae sus marcas. Y si quien cambia es el autor, una palabra nueva que
        cae dentro de un tramo conocido de la IA es de la IA. Devuelve (marcas, cuántas de la IA
        han entrado así)."""
        if not any("N" in m for m in marcas):
            return marcas, 0
        out, ws_por = [], []
        for par, m in zip(pars, marcas):
            ws = palabras(par)
            ws_por.append(ws)
            if "N" in m and len(ws) >= MIN_PARRAFO:
                conocido = self.parrafos.get(_h_parrafo(ws))
                if conocido is not None and len(conocido) == len(ws):
                    # De lo que ya traía por su sitio no se pierde nada de la IA.
                    # Con el índice no íntegro (una instantánea o el archivo no cuadran) lo que diga el
                    # índice de «tuyo» no vale: ante la duda, de la IA.
                    m = "".join((c if self.integro else "A") if a == "N" else ("A" if "A" in (a, c) else a)
                                for a, c in zip(m, conocido))
            out.append(m)
        antes = "".join(marcas).count("A")
        if cambia_el_autor and self.tejas_ia and any("N" in m for m in out):
            ws = [w for l in ws_por for w in l]
            plano = list("".join(out))
            for i in range(len(ws) - 4):
                if "N" in plano[i:i + 5]:
                    seg = self.tejas_ia.get(hash(tuple(ws[i:i + 5])))
                    if seg:
                        for k in range(5):
                            if plano[i + k] == "N" and seg[k] == "A":
                                plano[i + k] = "A"
            c, nuevo = 0, []
            for m in out:
                nuevo.append("".join(plano[c:c + len(m)]))
                c += len(m)
            out = nuevo
        if cambia_el_autor and self.ia_pars:
            # Un párrafo de la IA pegado en otro sitio y retocado (una palabra de cada cinco rompe
            # todos los tramos): se busca el párrafo de la IA al que más se parece y se compara
            # palabra a palabra, con el mismo listón que si lo hubiera retocado en su sitio.
            for j, m in enumerate(out):
                ws = ws_por[j]
                if "N" not in m or len(ws) < 8:
                    continue
                largas = {w for w in ws if len(w) >= 5}
                votos = {}
                for w in largas:
                    sitios = self.por_palabra.get(w)
                    if sitios and len(sitios) <= 60:
                        for k in sitios:
                            votos[k] = votos.get(k, 0) + 1
                minimo = max(4, 0.3 * len(largas))
                for k, n in sorted(votos.items(), key=lambda kv: -kv[1])[:3]:
                    if n < minimo or "N" not in m:
                        break
                    suyas = _casar_palabras(self.ia_pars[k][0], self.ia_pars[k][1], ws, "N", False)
                    m = "".join("A" if a == "N" and b == "A" else a for a, b in zip(m, suyas))
                out[j] = m
        return out, "".join(out).count("A") - antes


# ───────────────────────────── el almacén (.awap/local/) ─────────────────────────────

class Proyecto:
    def __init__(self, raiz):
        self.raiz = raiz
        self.dir = os.path.join(raiz, DIR)
        self.f_proyecto = os.path.join(self.dir, "project.json")
        self.f_eventos = os.path.join(self.dir, "events.jsonl")
        self.f_cache = os.path.join(self.dir, "estado.json")
        self.f_sesion = os.path.join(self.dir, "sesion.json")
        self.d_textos = os.path.join(self.dir, "textos")
        self.f_archivo_ia = os.path.join(self.d_textos, "_ia.jsonl.gz")
        self.f_cerrojo = os.path.join(self.dir, ".cerrojo")
        self.f_pendientes = os.path.join(self.dir, "pendientes.jsonl")
        self.datos = _leer_json(self.f_proyecto, {}) or {}
        self._eventos = None

    # ── eventos: una línea por hecho, cada una con la huella de la anterior ──
    def eventos(self):
        if self._eventos is None:
            self._eventos = []
            try:
                with open(self.f_eventos, encoding="utf-8") as f:
                    for linea in f:
                        linea = linea.strip()
                        if linea:
                            try:
                                self._eventos.append(json.loads(linea))
                            except Exception:
                                self._eventos.append({"_roto": linea})
            except FileNotFoundError:
                pass
        return self._eventos

    @staticmethod
    def _huella(ev):
        cuerpo = {k: v for k, v in ev.items() if k != "hash"}
        return hashlib.sha256(json.dumps(cuerpo, sort_keys=True, ensure_ascii=False,
                                         separators=(",", ":")).encode("utf-8")).hexdigest()

    def anotar(self, **campos):
        evs = self.eventos()
        prev = evs[-1].get("hash") if evs else "genesis:" + str(self.datos.get("id", ""))
        ev = {"seq": len(evs) + 1, "timestamp": iso()}
        ev.update({k: v for k, v in campos.items() if v is not None})
        ev["prev"] = prev
        ev["hash"] = self._huella(ev)
        os.makedirs(self.dir, exist_ok=True)
        with open(self.f_eventos, "a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False, separators=(",", ":")) + "\n")
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        evs.append(ev)
        return ev

    def cadena(self):
        """(íntegra, primera línea rota o None)."""
        prev = "genesis:" + str(self.datos.get("id", ""))
        for i, ev in enumerate(self.eventos(), 1):
            if "_roto" in ev or ev.get("prev") != prev or ev.get("hash") != self._huella(ev) \
                    or ev.get("seq") != i:
                return False, i
            prev = ev["hash"]
        return True, None

    # ── instantáneas: el último texto visto de cada documento, con su procedencia ──
    def _f_texto(self, rel):
        return os.path.join(self.d_textos, hashlib.sha1(rel.encode("utf-8")).hexdigest() + ".json.gz")

    def instantanea(self, rel):
        try:
            with gzip.open(self._f_texto(rel), "rt", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def guardar_instantanea(self, rel, parrafos, marcas, archivar=True):
        """Guarda el último texto visto de un documento. Lo que la IA había escrito en la versión
        anterior y ya no está en la nueva NO se tira: pasa a `textos/_ia.jsonl.gz`. Sin eso bastaba
        quitar hoy un capítulo generado y pegarlo mañana en la novela para que contase como del
        autor (equipo rojo, 1-oct-2026). Solo crece con lo que la IA ha escrito. Devuelve cuántas
        palabras de la IA ha archivado: va al evento, y `verificar` comprueba que siguen ahí."""
        os.makedirs(self.d_textos, exist_ok=True)
        ruta = self._f_texto(rel)
        vieja = self.instantanea(rel) if archivar else None
        archivadas = 0
        if vieja:
            quedan = {_h_parrafo(palabras(x)) for x in parrafos}
            fuera = []
            for par, m in zip(vieja["p"], vieja["f"]):
                if "A" in m:
                    h = _h_parrafo(palabras(par))
                    if h not in quedan:
                        fuera.append(json.dumps({"p": par, "f": m, "h": h}, ensure_ascii=False))
                        archivadas += m.count("A")
            if fuera:
                with gzip.open(self.f_archivo_ia, "at", encoding="utf-8") as f:
                    f.write("\n".join(fuera) + "\n")
        with gzip.open(ruta + ".tmp", "wt", encoding="utf-8") as f:
            json.dump({"p": parrafos, "f": marcas, "h": [_h_parrafo(palabras(x)) for x in parrafos]},
                      f, ensure_ascii=False)
        os.replace(ruta + ".tmp", ruta)
        return archivadas, self.huella_texto(parrafos, marcas)

    @staticmethod
    def huella_texto(parrafos, marcas):
        """La huella de una instantánea (texto y marcas). Va al evento: si alguien cambia las marcas
        a mano en el fichero guardado, `verificar` lo nota (equipo rojo, 1-oct-2026)."""
        return hashlib.sha256(json.dumps({"p": parrafos, "f": marcas}, ensure_ascii=False,
                                         separators=(",", ":")).encode("utf-8")).hexdigest()

    def en_archivo(self):
        """Palabras de la IA que hay en el archivo (0 si no está o no se puede leer)."""
        n = 0
        try:
            with gzip.open(self.f_archivo_ia, "rt", encoding="utf-8") as f:
                for linea in f:
                    try:
                        n += json.loads(linea)["f"].count("A")
                    except Exception:
                        continue
        except Exception:
            pass
        return n

    # ── el cerrojo: el gancho de escritura y un colaborador pueden llegar a la vez, y dos procesos
    #    añadiendo líneas a la cadena la romperían ──
    def cerrar_paso(self, espera):
        limite = time.time() + espera
        while True:
            try:
                fd = os.open(self.f_cerrojo, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                return True
            except FileExistsError:
                try:
                    # `abs`: un cerrojo con fecha del futuro (otro reloj) tampoco es de nadie vivo.
                    if abs(time.time() - os.stat(self.f_cerrojo).st_mtime) > CERROJO_VIEJO:
                        os.remove(self.f_cerrojo)
                        continue
                except OSError:
                    continue
                if time.time() >= limite:
                    return False
                time.sleep(0.1)
            except OSError:
                return True      # carpeta de solo lectura: que falle después, con su mensaje

    def abrir_paso(self):
        try:
            os.remove(self.f_cerrojo)
        except OSError:
            pass

    # ── la sesión de colaborador abierta ──
    def sesion(self):
        return _leer_json(self.f_sesion)

    def abrir_sesion(self):
        _guardar_json(self.f_sesion, {"abierta": ahora(), "ultima": ahora()})

    def latido(self, s):
        s["ultima"] = ahora()
        _guardar_json(self.f_sesion, s)

    def cerrar_sesion(self):
        try:
            os.remove(self.f_sesion)
        except OSError:
            pass


# ───────────────────────────── clasificar documentos ─────────────────────────────

_NO_CUENTA = re.compile(
    r"informe|report|plan-?reescritura|plan de reescritura|perfil|promesas|canon|estado-personajes|"
    r"checkpoint|veredicto|ficha|bitacora|comparativa|certificado|readme|handoff|diagnostico|"
    r"telemetria|query|carta|blurb|contraportada|anuncio|campan|calendario|prohibidas")


def clasificar(rel):
    """El tipo de documento por su nombre, o None si no es de los que cuentan (informes, planes…)."""
    partes = rel.replace("\\", "/").split("/")
    nombre = _plano(os.path.splitext(partes[-1])[0])
    carpetas = [_plano(p) for p in partes[:-1]]
    if _NO_CUENTA.search(nombre):
        return None
    if nombre.startswith(("premisa", "premise")):
        return "premise"
    if nombre.startswith(("sinopsis", "synopsis")):
        return "synopsis"
    if nombre.startswith(("biblia", "bible")):
        return "bible"
    if nombre.startswith(("escaleta", "outline", "estructura", "structure")):
        return "outline"
    if nombre.startswith(("estilo", "style", "voz", "voice", "instrucciones", "instructions")):
        return "style_instructions"
    if (re.search(r"(^|[-_ ])(cap|capitulo|chapter|ch)[-_ ]?\d", nombre)
            or re.search(r"-m\d+-v\d+|-b\d+($|[-_ ])|-corregido|-humanizado", nombre)
            or re.search(r"(^|[-_ ])(prologo|epilogo|prefacio|introduccion|interludio|escena|parte)([-_ ]|\d|$)", nombre)
            or re.match(r"\d{1,3}[-_ .]", nombre)
            or nombre.startswith(("manuscrito", "manuscript", "borrador", "draft", "novela", "novel"))
            or any(c in ("capitulos", "chapters", "manuscrito") for c in carpetas)):
        return "draft"
    return None


def ficheros(raiz):
    """Los documentos de la carpeta del libro: {ruta relativa: (tamaño, mtime)}."""
    out = {}
    base = raiz.rstrip(os.sep)
    for carpeta, subs, nombres in os.walk(base):
        prof = carpeta[len(base):].count(os.sep)
        # Una subcarpeta con su propio registro es otro libro: lo suyo no se cuenta aquí.
        subs[:] = sorted(d for d in subs if not d.startswith(".") and d != "node_modules"
                         and not os.path.isfile(os.path.join(carpeta, d, DIR, "project.json"))) \
            if prof < PROFUNDIDAD else []
        for n in sorted(nombres):
            if n.startswith(("~$", ".")) or not n.lower().endswith(EXTENSIONES):
                continue
            ruta = os.path.join(carpeta, n)
            try:
                st = os.stat(ruta)
            except OSError:
                continue
            if st.st_size > MAX_BYTES:
                continue
            out[os.path.relpath(ruta, base).replace(os.sep, "/")] = (st.st_size, st.st_mtime)
            if len(out) >= MAX_FICHEROS:
                return out
    return out


# ───────────────────────────── el estado, reconstruido del registro ─────────────────────────────

def documentos(eventos):
    """El estado de cada documento, repasando el registro. Es la ÚNICA fuente: el HAS se puede
    recalcular con el `events.jsonl` y nada más."""
    docs = {}
    for ev in eventos:
        rel = ev.get("document")
        t = ev.get("event_type")
        if not rel or t == "collaborator_run":
            continue
        if t == "document_removed":
            if rel in docs:
                docs[rel]["existe"] = False
            continue
        d = docs.setdefault(rel, {"existe": True, "relevado_por": None})
        d.update({
            "existe": True,
            "tipo": ev.get("document_type"),
            "nivel": ev.get("hierarchical_level"),
            "sha": (ev.get("document_hash") or "").replace("sha256:", ""),
            "palabras": ev.get("words", 0),
            "humanas": ev.get("human_words", 0),
            "ia_intro": ev.get("ai_words_introduced", 0),
            "atribucion": ev.get("attribution"),
            "de_base": bool(ev["derived_from_baseline"]) if "derived_from_baseline" in ev else bool(d.get("de_base")),
            "es_base": d.get("es_base") or t == "baseline_declared",
            "fuente": ev.get("source") or d.get("fuente"),
            "cuando": ev.get("timestamp"),
            "huella_texto": ev.get("snapshot_hash") or d.get("huella_texto"),
            "pegadas": ev.get("ai_words_pasted_by_author", 0),
        })
        if ev.get("supersedes") and ev["supersedes"] in docs:
            docs[ev["supersedes"]]["relevado_por"] = rel
    return docs


def cabezas(docs):
    """Los documentos que cuentan: los que existen y no han sido relevados por una versión posterior."""
    return {r: d for r, d in docs.items() if d["existe"] and not d["relevado_por"] and d.get("nivel")}


def hay_base(eventos):
    for ev in eventos:
        if ev.get("event_type") == "baseline_declared":
            return ev
    return None


# ───────────────────────────── el HAS ─────────────────────────────

def factor_base(docs, minimo=MIN_BASE, declaradas=0):
    """Cuánto acredita el manuscrito previo la concepción del libro: entera si las palabras tuyas
    que hay en el manuscrito llegan a `minimo` y son al menos la mitad; si no, en proporción.

    (Equipo rojo, 1-oct-2026.) El servidor la acredita entera con cualquier manuscrito declarado.
    Aquí bastaba declarar uno pequeño y dejar que la IA escribiera 40.000 palabras para sacar un 92.
    Es MÁS ESTRICTO que el servidor a propósito, y solo cuando la IA ha escrito más que el autor o
    el manuscrito no llega a ser un manuscrito: un relato de 2.500 palabras escrito entero por su
    autor da el mismo número que en el servidor.
    """
    texto = [d for d in docs.values() if d["nivel"] == 7]
    hum = sum(d["humanas"] for d in texto)
    total = sum(d["palabras"] for d in texto)
    if not total:
        # El manuscrito ya no está en la carpeta (lo ha sacado, o trabaja en otra): vale el tamaño
        # con que se declaró. En cuanto haya texto en la carpeta, manda el texto.
        return min(1.0, (declaradas or 0) / minimo)
    return min(1.0, hum / minimo) * min(1.0, 2 * hum / total)


def entradas(eventos):
    """De los documentos vivos, una entrada por nivel, ponderada por palabras. Es lo que entra en
    la fórmula (la del servidor promedia entradas; aquí cada nivel llega ya resumido en una)."""
    docs = cabezas(documentos(eventos))
    base = hay_base(eventos)
    declaradas = (base or {}).get("baseline_words") or 0
    factor = factor_base(docs, MIN_BASE, declaradas) if base else 0.0
    # Un documento de concepción que redacta la IA pide más manuscrito detrás que un nivel sin
    # documento: se le acredita entero con 3.000 palabras tuyas, y por debajo, en proporción.
    factor_doc = factor_base(docs, MIN_BASE_DOC, declaradas) if base else 0.0
    ents = []
    for nivel in (1, 2, 3, 4, 5, 7):
        suyos = [d for d in docs.values() if d["nivel"] == nivel and d["palabras"] > 0]
        pal = sum(d["palabras"] for d in suyos)
        if not pal:
            if base and nivel in CONCEPCION and factor < 1:
                # Sin documento, lo acredita el manuscrito previo; pero solo en la parte que le toca.
                ents.append({"event_type": "baseline_share", "hierarchical_level": nivel,
                             "revision_ratio": r2(factor), "has_contribution": r2(PUNTOS[nivel] * r2(factor)),
                             "tokens_generated": 0, "tokens_revised_by_human": 0,
                             "timestamp": base.get("timestamp") or ""})
            continue
        # Un documento de concepción que la IA saca de un manuscrito que ya era tuyo no es
        # concepción de la IA: transcribe la tuya. Misma regla que `derived_from_baseline`.
        hum = sum(max(d["humanas"], d["palabras"] * factor_doc) if (d["de_base"] and nivel in CONCEPCION)
                  else d["humanas"] for d in suyos)
        ratio = r2(min(hum / pal, 1))
        ents.append({"event_type": "document_state", "hierarchical_level": nivel,
                     "revision_ratio": ratio, "has_contribution": r2(PUNTOS[nivel] * ratio),
                     "tokens_generated": pal - hum, "tokens_revised_by_human": hum,
                     "timestamp": max(d["cuando"] or "" for d in suyos)})
    # Nivel 6, la revisión: de las palabras que la IA ha metido en el manuscrito, cuántas has
    # SUSTITUIDO tú por otras tuyas. Se cuenta sobre el libro entero, no fichero a fichero: mover un
    # texto de la IA de un fichero a otro no es revisarlo. Y borrarlo tampoco: lo borrado sigue
    # contando como metido y no como revisado (equipo rojo, 1-oct: generar cinco capítulos y
    # borrarlos daba los 25 puntos; y si lo borrado dejara de contar, bastaría dejar una palabra
    # tuya en su lugar). Solo salen de la cuenta lo que la IA quita de su propio texto y lo que el
    # autor declara suyo.
    texto = [d for d in docs.values() if d["nivel"] == 7]
    vivas = sum(d["palabras"] - d["humanas"] for d in texto)
    del7 = [e for e in eventos if e.get("hierarchical_level") == 7]
    metidas = sum(e.get("tokens_generated", 0) - e.get("ai_words_removed_by_ai", 0) - e.get("ai_words_written_off", 0)
                  for e in del7)
    sustituidas = sum(e.get("ai_words_replaced_by_human", 0) for e in del7)
    intro = max(metidas, vivas)
    if intro > 0:
        revisadas = min(sustituidas, max(intro - vivas, 0))
        ratio = r2(min(revisadas / intro, 1))
        ents.append({"event_type": "document_state", "hierarchical_level": 6,
                     "revision_ratio": ratio, "has_contribution": r2(PUNTOS[6] * ratio),
                     "tokens_generated": intro, "tokens_revised_by_human": revisadas,
                     "timestamp": max((d["cuando"] or "" for d in texto), default="")})
    if base:
        ents.append({"event_type": "baseline_declared", "hierarchical_level": None, "revision_ratio": 1,
                     "has_contribution": 0, "tokens_generated": 0, "tokens_revised_by_human": 0,
                     "baseline_words": base.get("baseline_words"),
                     "document_hash": base.get("document_hash"), "timestamp": base.get("timestamp")})
    return ents


def calcular_has(logs):
    """`computeHASFrom` de has-core.js, tal cual: mismos pesos, mismo denominador de 390, misma
    regla del manuscrito preexistente. El modificador conversacional no se aplica aquí: en el
    registro local nadie anota turnos de conversación."""
    por_nivel = {n: [] for n in NIVELES}
    for e in logs:
        if e.get("hierarchical_level") in por_nivel:
            por_nivel[e["hierarchical_level"]].append(e)
    base = next((e for e in logs if e.get("event_type") == "baseline_declared" or e.get("is_baseline")), None)
    desglose = []
    for n in NIVELES:
        es = por_nivel[n]
        presente = bool(es)
        media = sum(e["revision_ratio"] for e in es) / len(es) if es else 0
        por_base = bool(base) and n in CONCEPCION and not presente
        if por_base:
            presente, media = True, 1
        desglose.append({"level": n, "label": ETIQUETAS[n], "max_points": PUNTOS[n],
                         "earned_points": r2(PUNTOS[n] * media if presente else 0),
                         "presence_verified": presente, "average_revision_ratio": r2(media),
                         "events_count": len(es), "credited_by_baseline": por_base})
    maximo = sum(PUNTOS.values())
    ganado = sum(b["earned_points"] for b in desglose)
    return {"has_global": math.floor((ganado / maximo) * 10000 + 0.5) / 100, "breakdown": desglose,
            "baseline": {"declared": True, "words": base.get("baseline_words"),
                         "manuscript_hash": base.get("document_hash"),
                         "declared_at": base.get("timestamp")} if base else {"declared": False}}


def interpretar(has):
    if has >= 80:
        return "autoría humana dominante"
    if has >= 50:
        return "autoría humana sustancial"
    if has >= 20:
        return "autoría humana limitada"
    return "autoría humana mínima"


# ───────────────────────────── mirar la carpeta y anotar lo que ha cambiado ─────────────────────────────

def _sha_fichero(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for trozo in iter(lambda: f.read(1 << 20), b""):
            h.update(trozo)
    return h.hexdigest()


def _ventanas(p, eventos, sesion):
    """Los ratos en que lo que cambia no es del autor: [(desde, hasta, por qué)]. Mientras trabaja un
    colaborador (y dos minutos después), y los diez minutos que siguen a cada escritura de la IA
    fuera de sesión (la avisa el gancho): lo que escriba a continuación desde un guion no pasa por
    el gancho."""
    v = [(ev["file_mtime"] - 60, ev["file_mtime"] + TRAS_ESCRITO,
          "cambió justo después de que la IA escribiera en la carpeta")
         for ev in eventos if ev.get("outside_session") and ev.get("file_mtime")]
    v += [(x.get("mtime", 0) - 60, x.get("mtime", 0) + TRAS_ESCRITO,
           "cambió justo después de que la IA escribiera en la carpeta") for x in pendientes(p)]
    for ev in eventos:
        if ev.get("event_type") == "collaborator_run":
            v.append((ev.get("opened") or 0, (ev.get("closed") or 0) + GRACIA_CIERRE,
                      "cambió mientras trabajaba un colaborador, o justo después"))
    if sesion and sesion.get("abierta"):
        v.append((sesion["abierta"], float("inf"), "un colaborador no cerró su sesión"))
    return v


def pendientes(p):
    """Las escrituras de la IA que el gancho no pudo anotar porque el registro estaba ocupado."""
    out = []
    try:
        with open(p.f_pendientes, encoding="utf-8") as f:
            for linea in f:
                try:
                    out.append(json.loads(linea))
                except Exception:
                    continue
    except OSError:
        pass
    return out


def _buscar_fuente(p, rel, nuevas, docs, tejas_de):
    """El documento del que sale uno nuevo, si lo hay: (ruta, instantánea, palabras que tenía).
    Es el que más se le parece de los conocidos, exista todavía o no: copiar un texto a un fichero
    nuevo y borrar el viejo no le cambia la procedencia."""
    if len(nuevas) < 40:
        return None
    tejas = _tejas(nuevas)
    if not tejas:
        return None
    mejor = None
    for r in sorted(docs):
        if r == rel or not docs[r].get("nivel"):
            continue
        if r not in tejas_de:
            snap = p.instantanea(r)
            viejas = [w for par in snap["p"] for w in palabras(par)] if snap else []
            tejas_de[r] = (_tejas(viejas), len(viejas))
        suyas, n = tejas_de[r]
        if not suyas:
            continue
        parte = len(tejas & suyas) / len(tejas)
        if parte >= UMBRAL_FUENTE and (mejor is None or parte > mejor[1]):
            mejor = (r, parte, n)
    if not mejor:
        return None
    snap = p.instantanea(mejor[0])
    return (mejor[0], snap, mejor[2]) if snap else None


def _cabeza_de(rel, docs):
    """La última versión del linaje de un documento."""
    vistos = set()
    while docs.get(rel, {}).get("relevado_por") and rel not in vistos:
        vistos.add(rel)
        rel = docs[rel]["relevado_por"]
    return rel


_NOMBRE = re.compile(r"[^\W\d_]{4,}", re.UNICODE)


def _nombres_propios(pars):
    """Las palabras con mayúscula que no abren frase: en castellano, casi siempre nombres propios."""
    out = set()
    for par in pars:
        for m in _NOMBRE.finditer(par):
            w = m.group(0)
            if not w[0].isupper() or w.isupper():
                continue
            antes = par[:m.start()].rstrip(" \t\"'«“‘(¿¡*_#>-—–")
            if not antes or antes[-1] in ".!?:;\n…":
                continue
            out.add(w.casefold())
    return out


def _sale_del_manuscrito(p, base, docs, pars):
    """¿Hay rastro del manuscrito previo en este documento de concepción que ha escrito la IA?

    (Equipo rojo, 1-oct-2026.) Se acreditaba al autor CUALQUIER premisa, biblia o escaleta escrita
    por la IA con solo haber declarado un manuscrito, aunque fuera de cincuenta palabras; el
    servidor solo lo hace cuando el documento se EXTRAE del manuscrito. Aquí se exige prueba: un
    manuscrito de verdad, y que el documento comparta con él sus nombres propios o cite frases suyas.
    """
    rel = _cabeza_de(base.get("document"), docs) if base.get("document") in docs else base.get("document")
    snap = p.instantanea(rel) or p.instantanea(base.get("document"))
    if not snap:
        return False
    ms = [w for par in snap["p"] for w in palabras(par)]
    if len(ms) < 200:           # no hay con qué comparar
        return False
    vocab = set(ms)
    # Los nombres propios del manuscrito (los que salen con mayúscula en mitad de frase) que el
    # documento también lleva con mayúscula, esté donde esté: una biblia los pone en títulos y en
    # listas, no en mitad de frase. Hacen falta cuatro. Y si el documento trae sus propios nombres
    # en mitad de frase, que la mayoría sean del manuscrito: una biblia inventada trae otros.
    del_ms = _nombres_propios(snap["p"])
    en_doc = {m.group(0).casefold() for par in pars for m in _NOMBRE.finditer(par)
              if m.group(0)[0].isupper() and not m.group(0).isupper()}
    suyos = _nombres_propios(pars)
    if len(en_doc & del_ms) >= 4 and (len(suyos) < 4 or sum(1 for n in suyos if n in vocab) >= 0.6 * len(suyos)):
        return True
    # Tramos de cinco palabras iguales (citas del manuscrito): tres como poco, y que no sean una
    # casualidad en un documento largo.
    suyas = _tejas([w for par in pars for w in palabras(par)])
    comunes = len(suyas & _tejas(ms))
    return comunes >= 3 and comunes >= 0.005 * len(suyas)


def mirar(p, quien, colab=None, atribucion="medido", modelo=None, motivo=None, hasta=None, solo=None):
    """Compara la carpeta con lo último que se vio y anota los cambios como de `quien` ("H" o "A").

    Cuando `quien` es "H", lo que se escribió mientras trabajaba un colaborador no es tuyo aunque
    aparezca ahora: va como de la IA, «incierto». Devuelve (lo anotado, los ficheros sin tipo).
    """
    evs = p.eventos()
    docs = documentos(evs)
    cache = _leer_json(p.f_cache, {}) or {}
    vistos = cache.get("ficheros", {})
    en_disco = ficheros(p.raiz)
    base = hay_base(evs)
    ventanas = _ventanas(p, evs, p.sesion()) if quien == "H" else []
    leidos = pendientes(p) if quien == "H" else []
    sin_anotar = {x.get("document") for x in leidos}
    anotado = []
    otros = []

    # Primero, qué ha cambiado. Por orden de antigüedad: en una serie de versiones, la última es la
    # que queda viva.
    cambiados = []
    for rel, (tam, mt) in sorted(en_disco.items(), key=lambda kv: (kv[1][1], kv[0])):
        ant = vistos.get(rel)
        if ant and ant[0] == tam and abs(ant[1] - mt) < 1e-6:
            continue
        if hasta is not None and mt > hasta:
            continue
        if solo is not None and rel != solo:
            continue
        try:
            sha = _sha_fichero(os.path.join(p.raiz, rel))
        except OSError:
            continue
        conocido = docs.get(rel)
        # Sin la caché (se ha borrado, o es otra máquina) la huella del registro dice si ha cambiado.
        if (ant and len(ant) > 2 and ant[2] == sha) or (conocido and conocido["existe"] and conocido["sha"] == sha):
            vistos[rel] = [tam, mt, sha]
            continue
        cambiados.append((rel, tam, mt, sha))

    # El índice se carga ANTES de tocar ninguna instantánea: si el autor recorta un capítulo y guarda
    # el trozo en otro fichero, el texto recortado tiene que seguir a la vista cuando llegue el otro.
    indice = None
    if cambiados:
        indice = Indice(p, {os.path.basename(p._f_texto(r)): h for r, h in huellas_anotadas(p).items()},
                        sum(e.get("ai_words_archived", 0) for e in evs))
    tejas_de = {}
    for rel, tam, mt, sha in cambiados:
        ruta = os.path.join(p.raiz, rel)
        conocido = docs.get(rel)
        if quien == "H" and rel not in sin_anotar and os.path.exists(p.f_pendientes):
            # Un aviso del gancho que ha llegado durante esta misma pasada (el gancho no espera al
            # cerrojo más de unos segundos): se lee otra vez antes de dar este fichero por tuyo.
            for x in pendientes(p):
                if x not in leidos and x.get("document") == rel:    # solo el de este fichero: los demás, a la siguiente
                    leidos.append(x)
                    sin_anotar.add(rel)
        pars = parrafos_de(ruta)
        if pars is None:
            continue
        nuevas = [w for par in pars for w in palabras(par)]

        de_quien, como, por_que = quien, atribucion, motivo
        if quien == "H" and not indice.integro:
            # Falta parte de lo que el registro guarda para reconocer el texto de la IA, o está
            # manipulado: no se le puede acreditar nada nuevo al autor.
            de_quien, como, por_que = "A", "incierto", "al registro le falta parte de lo que guarda, o está manipulado"
        elif quien == "H" and rel in sin_anotar:
            de_quien, como, por_que = "A", "incierto", "la IA escribió en este fichero y no se pudo anotar en el momento"
        elif quien == "H":
            en = next((m_ for a_, b_, m_ in ventanas if a_ <= mt <= b_), None)
            if en:
                de_quien, como, por_que = "A", "incierto", en

        snap = p.instantanea(rel)
        # Un texto guardado que no es el que se anotó (alguien ha tocado sus marcas, o el proceso
        # murió a medias) no sirve para medir: se trata como si faltase (equipo rojo, 1-oct: bastaba
        # reescribir el .json.gz con todo «H» y tocar una palabra para que la biblia fuera tuya).
        if snap is not None and conocido and conocido.get("huella_texto") \
                and p.huella_texto(snap.get("p", []), snap.get("f", [])) != conocido["huella_texto"]:
            snap = None
        propia = snap is not None
        fuente = releva = None
        tipo = conocido["tipo"] if conocido else clasificar(rel)
        ia_intro_ant = conocido["ia_intro"] if conocido else 0
        pegadas_ant = conocido["pegadas"] if conocido else 0
        if not propia and not (conocido and conocido["palabras"]):
            hallada = _buscar_fuente(p, rel, nuevas, docs, tejas_de)
            # El texto guardado del que «sale» este fichero tiene que ser el que se anotó: si no, un
            # texto de la IA con las marcas cambiadas a mano serviría de origen «tuyo» (equipo rojo, 5ª).
            if hallada and docs[hallada[0]].get("huella_texto") \
                    and p.huella_texto(hallada[1].get("p", []), hallada[1].get("f", [])) != docs[hallada[0]]["huella_texto"]:
                hallada = None
            if hallada:
                fuente, snap, n_viejas = hallada
                tipo = tipo or docs[fuente]["tipo"]
                cabeza = _cabeza_de(fuente, docs)
                if cabeza != rel and docs[cabeza]["tipo"] == tipo and n_viejas \
                        and len(nuevas) >= COBERTURA_RELEVO * n_viejas:
                    releva = cabeza
                    ia_intro_ant = docs[fuente]["ia_intro"]
                    pegadas_ant = docs[fuente]["pegadas"]

        if conocido and not propia and not fuente and conocido["palabras"]:
            # Un documento conocido cuyo texto anterior ya no está en .awap/local/textos: no se puede medir
            # qué ha cambiado. Se conserva la proporción que tenía; nunca sube sola.
            k = min(len(nuevas), round(conocido["humanas"] / conocido["palabras"] * len(nuevas)))
            marcas_n = trasladar({"p": [" ".join(nuevas)], "f": ["H" * k + "A" * (len(nuevas) - k)]}, pars, "N")
            como, por_que = "incierto", "falta el texto guardado de la versión anterior, o no es el que se anotó"
        else:
            # «N»: palabra nueva; H y A, heredadas del texto anterior.
            marcas_n = trasladar(snap, pars, "N", estricto=de_quien == "A")
        her_a = "".join(marcas_n).count("A")            # las de la IA que siguen en su sitio
        en_sitio = marcas_n
        # Lo nuevo puede no serlo: se busca en todo lo que el registro ha visto.
        marcas_n, a_indice = indice.heredar(pars, marcas_n, cambia_el_autor=de_quien == "H")
        junto = "".join(marcas_n)
        nuevas_n, her_h = junto.count("N"), junto.count("H")
        marcas = [m.replace("N", de_quien) for m in marcas_n]
        total = len(junto)

        if not tipo:
            # Sin tipo no cuenta para el HAS, pero lo que escribe la IA se guarda igual: si mañana
            # reaparece con nombre de capítulo, se le reconoce (equipo rojo, 1-oct).
            suya = None
            if de_quien == "A":
                _, suya = p.guardar_instantanea(rel, pars, marcas)
                indice.sumar(pars, marcas)
            otros.append({"document": rel, "words": len(nuevas), "sha": sha, "snapshot_hash": suya})
            vistos[rel] = [tam, mt, sha]
            continue

        if de_quien == "A":
            hum, ia_vivas = her_h, her_a + a_indice + nuevas_n
            # Lo que mete la IA ahora, menos lo suyo que ella misma quita: lo que quita la IA no
            # cuenta como revisado por ti.
            a_antes = "".join(snap["f"]).count("A") if (snap and (propia or releva)) else her_a
            quitadas = max(a_antes - her_a, 0)
            ia_intro = max(ia_intro_ant - quitadas + nuevas_n + a_indice, ia_vivas)
            tg, tr = nuevas_n, 0
            sustituidas = borradas = 0
            pegadas = pegadas_ant
        else:
            hum, ia_vivas = her_h + nuevas_n, her_a + a_indice
            ia_intro = max(ia_intro_ant + a_indice, ia_vivas)
            tg, tr, quitadas = 0, nuevas_n, 0
            # De lo que había de la IA, lo que ya no está: si en su lugar hay texto tuyo, lo has
            # sustituido (eso es revisar); si no hay nada, lo has borrado (eso no).
            a_antes = "".join(snap["f"]).count("A") if (snap and (propia or releva)) else her_a
            fuera = max(a_antes - ia_vivas, 0)
            # El texto de la IA que el propio autor trajo aquí pegándolo no cuenta al quitarlo: lo que
            # se revisa es lo que la IA escribió, no lo que uno pega y despega.
            descuento = min(fuera, pegadas_ant)
            fuera -= descuento
            pegadas = pegadas_ant - descuento + a_indice
            # Lo tuyo que cuenta como sustitución: las palabras NUEVAS de verdad, y las que devuelves
            # a como estaban dentro de un párrafo que sigue siendo el mismo (rechazar un cambio del
            # corrector). Un párrafo entero copiado de otro documento tuyo NO: el registro sabe que
            # no es nuevo (equipo rojo, 1-oct: sustituir un capítulo de la IA por párrafos copiados
            # de la novela daba 22 puntos de revisión).
            # Y de las nuevas, las que no lo son: tramos que ya eran tuyos en otro texto guardado.
            # Dentro de un párrafo que sigue en su sitio es devolver tu texto (cuenta); en un párrafo
            # traído entero de otra parte es copiar (no cuenta).
            ya_tuyas = indice.conocidas_del_autor(pars, marcas_n) if fuera and nuevas_n else None
            devueltas = copiadas = c_ = 0
            for antes_, ahora_ in zip(en_sitio, marcas_n):
                en_su_sitio = bool(antes_) and (len(antes_) - antes_.count("N")) * 2 >= len(antes_)
                for k, (x, y) in enumerate(zip(antes_, ahora_)):
                    if en_su_sitio and x == "N" and y == "H":
                        devueltas += 1
                    elif not en_su_sitio and y == "N" and ya_tuyas and ya_tuyas[c_ + k]:
                        copiadas += 1
                c_ += len(ahora_)
            sustituidas = min(fuera, max(nuevas_n - copiadas, 0) + devueltas)
            borradas = fuera - sustituidas
        if fuente and not releva:
            ia_intro = ia_vivas          # un fragmento sacado de otro: su cuenta empieza aquí

        if propia and conocido and conocido["existe"] and nuevas_n == 0 and marcas == list(snap["f"]) \
                and conocido["palabras"] == total and conocido["humanas"] == hum \
                and conocido["huella_texto"] == p.huella_texto(pars, marcas):
            # Ni una palabra nueva y las mismas de antes (Word lo ha vuelto a guardar): nada que anotar.
            # Mirar solo las marcas no basta: un texto reescrito entero por la IA sobre otro de la IA
            # tiene las mismas marcas y es otro texto.
            vistos[rel] = [tam, mt, sha]
            continue

        nivel = NIVEL_DE[tipo]
        ratio = r2(hum / total) if total else 1
        if de_quien == "A":
            tipo_ev = "text_generated"
        elif conocido or fuente:
            tipo_ev = "text_revised"
        else:
            tipo_ev = "document_created"
        # Lo decide cada vez que la IA escribe el documento; cuando lo cambias tú, se conserva.
        de_base = None
        if de_quien == "A" and nivel in CONCEPCION and base:
            de_base = _sale_del_manuscrito(p, base, docs, pars)
        # La instantánea, antes que el evento: si el proceso muere entre los dos, el texto guardado
        # y sus marcas siguen ahí y la vez siguiente se anota lo que falte.
        if snap is not None and propia:
            indice.recordar_h(snap["p"], snap["f"])    # lo tuyo de la versión que se sobrescribe sigue contando
        archivadas, huella = p.guardar_instantanea(rel, pars, marcas)
        indice.sumar(pars, marcas)
        ev = p.anotar(
            event_type=tipo_ev, document=rel, document_type=tipo, hierarchical_level=nivel,
            document_hash="sha256:" + sha, words=total, human_words=hum,
            ai_words_introduced=ia_intro, tokens_generated=tg, tokens_revised_by_human=tr,
            revision_ratio=ratio, has_contribution=r2(PUNTOS[nivel] * ratio),
            ai_model=(modelo or "claude") if de_quien == "A" else None,
            collaborator=colab if de_quien == "A" else None, attribution=como,
            ai_words_removed_by_ai=quitadas or None,
            ai_words_replaced_by_human=sustituidas or None, ai_words_deleted_by_human=borradas or None,
            ai_words_archived=archivadas or None, snapshot_hash=huella,
            ai_words_pasted_by_author=pegadas or None,
            # Fuera de sesión (lo avisó el gancho, ahora o en un aviso que quedó apuntado): los diez
            # minutos de después cuentan desde aquí.
            outside_session=True if (solo is not None or rel in sin_anotar) else None,
            file_mtime=(mt if solo is not None else
                        max((x.get("mtime", 0) for x in leidos if x.get("document") == rel), default=mt)
                        if rel in sin_anotar else None),
            uncertain_reason=por_que if como == "incierto" else None,
            source=fuente, supersedes=releva, derived_from_baseline=de_base)
        tejas_de.pop(rel, None)
        vistos[rel] = [tam, mt, sha]
        docs = documentos(p.eventos())
        anotado.append(ev)

    # Lo que ya no está. Su texto se queda en .awap/local/textos: si reaparece copiado en otro fichero,
    # se le reconoce.
    for rel, d in list(docs.items()):
        if d["existe"] and rel not in en_disco and hasta is None and solo is None:
            # Si lo retira un colaborador, su texto de la IA sale de la cuenta. Si lo borra el autor,
            # no: borrar no es revisar.
            de_ia = (d["palabras"] - d["humanas"]) if not d["relevado_por"] else 0
            anotado.append(p.anotar(event_type="document_removed", document=rel,
                                    document_type=d["tipo"], hierarchical_level=d["nivel"],
                                    ai_words_removed_by_ai=de_ia if quien == "A" and de_ia else None,
                                    ai_words_deleted_by_human=de_ia if quien != "A" and de_ia else None))
            vistos.pop(rel, None)
    if hasta is None and solo is None:
        for rel in [r for r in vistos if r not in en_disco]:
            vistos.pop(rel, None)
        # Los avisos atendidos se quitan; los que hayan llegado mientras tanto (el gancho escribe sin
        # cerrojo) se quedan para la siguiente mirada. Borrar el fichero entero perdía el aviso y la
        # escritura de la IA pasaba por tuya (equipo rojo, quinta pasada).
        try:
            quedan = [x for x in pendientes(p) if x not in leidos] if quien == "H" else []
            if quedan:
                with open(p.f_pendientes + ".tmp", "w", encoding="utf-8") as f:
                    f.write("".join(json.dumps(x) + "\n" for x in quedan))
                os.replace(p.f_pendientes + ".tmp", p.f_pendientes)
            else:
                os.remove(p.f_pendientes)
        except OSError:
            pass
    # La huella del texto guardado de un fichero sin tipo que ha escrito la IA tiene que estar en la
    # cadena: si no, la siguiente pasada la daría por manipulada. Cuando el que mira es un
    # colaborador, va en su `collaborator_run`; en los demás casos (gancho fuera de sesión, aviso
    # pendiente), aquí (equipo rojo, quinta pasada: un informe reescrito fuera de sesión dejaba
    # todo «incierto» para siempre y sin certificado).
    sueltas = [o for o in otros if o.get("snapshot_hash")]
    if sueltas and (quien == "H" or solo is not None):
        p.anotar(event_type="ai_wrote_untyped", collaborator=colab, produced=sueltas)

    cache["ficheros"] = vistos
    os.makedirs(p.dir, exist_ok=True)
    _guardar_json(p.f_cache, cache)
    return anotado, otros


def _producido(anotado, otros):
    return [{"document": e["document"], "words": e["words"]} for e in anotado
            if e.get("event_type") != "document_removed"] + otros


def ponerse_al_dia(p):
    """Lo que ha cambiado desde la última vez y no es de ningún colaborador: es tuyo.

    Salvo que haya una sesión de colaborador que nadie cerró (el modelo se saltó el último bloque,
    o se interrumpió). Entonces no hay forma de saber qué escribió él y qué tú: TODO lo que haya
    cambiado hasta ahora cuenta como de la IA, «incierto», por tarde que lleve la fecha del fichero
    —la fecha solo dice cuándo se guardó por última vez, y basta abrir un capítulo generado y
    añadirle una palabra para que sea de hoy (equipo rojo, 1-oct-2026)—. La sesión queda anotada.
    """
    s = p.sesion()
    if s and s.get("abierta"):
        anotado, otros = mirar(p, "A", atribucion="incierto",
                               motivo="un colaborador no cerró su sesión")
        p.anotar(event_type="collaborator_run", collaborator="(sesión sin cerrar)", unclosed=True,
                 opened=s["abierta"], closed=ahora(), produced=_producido(anotado, otros))
        p.cerrar_sesion()
        return
    mirar(p, "H")


# ───────────────────────────── órdenes ─────────────────────────────

def _proyecto(ruta, exigir=True):
    raiz = raiz_de(ruta)
    if not raiz:
        if exigir:
            sys.exit("No hay registro de autoría en esta carpeta todavía. Empieza con:\n"
                     "  /humanink:auditor \"<carpeta del libro>\" --init")
        return None
    return Proyecto(raiz)


def cmd_iniciar(a):
    carpeta = os.path.abspath(os.path.expanduser(a.carpeta))
    if os.path.isfile(carpeta):          # le han pasado el manuscrito: la carpeta del libro es la suya
        carpeta = os.path.dirname(carpeta)
    if not os.path.isdir(carpeta):
        sys.exit(f"No veo la carpeta «{carpeta}» desde aquí. En Cowork, conecta la carpeta del libro "
                 "a la conversación y vuelve a intentarlo.")
    p = Proyecto(carpeta)
    arriba = raiz_de(os.path.dirname(carpeta), niveles=6)
    if arriba and not os.path.isfile(p.f_proyecto):
        sys.exit(f"Esta carpeta está dentro de un libro que ya tiene registro: «{arriba}». Un registro "
                 "dentro de otro contaría dos veces los mismos textos. Usa el de ese libro, o saca esta "
                 "carpeta fuera.")
    if os.path.isfile(p.f_proyecto):
        print(f"El registro de «{p.datos.get('title', '')}» ya existía (desde {p.datos.get('created_at', '?')}). "
              "No se ha tocado.")
        return cmd_estado(a)
    try:
        os.makedirs(p.dir, exist_ok=True)
    except OSError as e:
        sys.exit(f"No puedo escribir en «{carpeta}»: {e}")
    # Con el cerrojo puesto ANTES de que exista el proyecto: en cuanto existe, un gancho de otra
    # conversación podría ponerse a escribir en la cadena a la vez que esta primera mirada.
    p.cerrar_paso(20)
    try:
        p.datos = {"schema": ESQUEMA, "id": str(uuid.uuid4()), "title": a.titulo or os.path.basename(carpeta),
                   "author": a.autor or "", "created_at": iso(), "has_version": VERSION_HAS}
        _guardar_json(p.f_proyecto, p.datos)
        p.anotar(event_type="project_created", description=f"Registro abierto: {p.datos['title']}")
        # Lo que ya había en la carpeta es anterior al registro: nadie lo ha visto escribirse. Entra
        # como tuyo POR DECLARACIÓN, y así consta. Lo que generase la IA antes, lo dices tú.
        anotado, _ = mirar(p, "H", atribucion="preexistente")
    finally:
        p.abrir_paso()
    print(f"Registro de autoría abierto para «{p.datos['title']}»"
          + (f", de {p.datos['author']}" if p.datos["author"] else "") + ".")
    if anotado:
        print(f"\nDocumentos que ya estaban en la carpeta ({len(anotado)}). Entran como tuyos, por declaración:")
        for ev in anotado:
            print(f"  · {ev['document']}  ({NOMBRE_TIPO.get(ev['document_type'], ev['document_type'])}, "
                  f"{ev['words']} palabras)")
        print("\nSi alguno lo generó la IA, se marca con:  declarar <carpeta> <fichero> --origen ia")
    else:
        print("\nNo he encontrado premisa, sinopsis, biblia, escaleta, estilo ni manuscrito con esos nombres.")
    print("\nA partir de ahora, lo que escriba cada colaborador de HumanInk en esta carpeta se anota solo, "
          "y lo que cambies tú entre uno y otro, también.")


def _rel(p, fichero):
    ruta = os.path.abspath(os.path.expanduser(fichero))
    if not os.path.isfile(ruta):
        cand = os.path.join(p.raiz, fichero)
        if os.path.isfile(cand):
            ruta = cand
        else:
            sys.exit(f"No encuentro «{fichero}».")
    rel = os.path.relpath(ruta, p.raiz).replace(os.sep, "/")
    if rel.startswith(".."):
        sys.exit("Ese fichero no está dentro de la carpeta del libro.")
    return ruta, rel


def _declarar(p, ruta, rel, origen, tipo, evento, descripcion, extra=None):
    pars = parrafos_de(ruta)
    if pars is None:
        sys.exit(f"No puedo leer «{rel}».")
    letra = "H" if origen == "humano" else "A"
    marcas = [letra * len(palabras(par)) for par in pars]
    n = sum(len(m) for m in marcas)
    docs = documentos(p.eventos())
    ant = docs.get(rel)
    tipo = tipo or (ant and ant["tipo"]) or clasificar(rel) or "draft"
    nivel = NIVEL_DE[tipo]
    sha = _sha_fichero(ruta)
    hum = n if letra == "H" else 0
    contradice = bool(ant and letra == "H" and ant["palabras"] - ant["humanas"] > 0
                      and ant.get("atribucion") == "medido")
    ev = p.anotar(event_type=evento, document=rel, document_type=tipo, hierarchical_level=nivel,
                  document_hash="sha256:" + sha, words=n, human_words=hum,
                  ai_words_introduced=n if letra == "A" else 0,
                  # Declararlo tuyo no cuenta como haberlo revisado: sus palabras de la IA dejan de
                  # contar como metidas. Y declararlo de la IA las mete.
                  ai_words_written_off=(ant["palabras"] - ant["humanas"]) if ant and letra == "H" and ant["existe"]
                  and not ant["relevado_por"] else None,
                  tokens_generated=max(n - (ant["palabras"] - ant["humanas"] if ant else 0), 0) if letra == "A" else 0,
                  tokens_revised_by_human=0,
                  revision_ratio=1 if letra == "H" else 0,
                  has_contribution=r2(PUNTOS[nivel] * (1 if letra == "H" else 0)),
                  attribution="declarado", overrides_measured=True if contradice else None,
                  derived_from_baseline=False, description=descripcion,
                  snapshot_hash=p.huella_texto(pars, marcas), **(extra or {}))
    p.guardar_instantanea(rel, pars, marcas, archivar=False)   # lo declarado tuyo no va al archivo de la IA
    cache = _leer_json(p.f_cache, {}) or {}
    st = os.stat(ruta)
    cache.setdefault("ficheros", {})[rel] = [st.st_size, st.st_mtime, sha]
    _guardar_json(p.f_cache, cache)
    return ev, contradice


def cmd_base(a):
    p = _proyecto(a.carpeta, exigir=False) or _proyecto(a.fichero)
    ponerse_al_dia(p)
    ruta, rel = _rel(p, a.fichero)
    if hay_base(p.eventos()):
        b = hay_base(p.eventos())
        sys.exit(f"Ya hay un manuscrito previo declarado: «{b.get('document')}» ({b.get('baseline_words')} "
                 f"palabras, el {b.get('timestamp', '')[:10]}). Solo puede haber uno.")
    pars = parrafos_de(ruta) or []
    n = sum(len(palabras(x)) for x in pars)
    ev, contradice = _declarar(p, ruta, rel, "humano", "draft", "baseline_declared",
                               "Manuscrito preexistente declarado por el autor", {"baseline_words": n})
    r = calcular_has(entradas(p.eventos()))
    print(f"Manuscrito previo declarado: «{rel}», {n} palabras.\nHuella: {ev['document_hash']}")
    if contradice:
        print("⚠️ El registro había medido parte de este fichero como generado por la IA. Queda anotado "
              "que lo declaras tuyo.")
    print(f"\nHAS ahora: {_n(r['has_global'])}/100.")
    f = factor_base(cabezas(documentos(p.eventos())), MIN_BASE, n)
    if f >= 1:
        print("La premisa, la sinopsis, la biblia, la escaleta y el estilo quedan acreditados: el manuscrito "
              "los demuestra.")
    else:
        print(f"El manuscrito acredita la concepción del libro al {round(f * 100)} %: para acreditarla entera "
              f"hacen falta al menos {MIN_BASE} palabras tuyas en el manuscrito, y que sean al menos la mitad de él.")
    print("A partir de aquí se anota lo que se haga con la IA. El certificado dirá que la puntuación parte de "
          "un manuscrito previo declarado por ti.")


def cmd_declarar(a):
    p = _proyecto(a.carpeta, exigir=False) or _proyecto(a.fichero)
    ponerse_al_dia(p)
    ruta, rel = _rel(p, a.fichero)
    if a.origen == "manuscrito":
        # «Esto lo ha redactado la IA, pero sale de mi manuscrito»: la concepción es tuya. No cambia
        # de quién son las palabras; cambia cómo cuenta el documento, y consta como declaración.
        d = documentos(p.eventos()).get(rel)
        if not hay_base(p.eventos()):
            sys.exit("Para eso tiene que haber un manuscrito previo declarado (--base).")
        if not d or d.get("nivel") not in CONCEPCION:
            sys.exit("Solo vale para la premisa, la sinopsis, la biblia, la escaleta o el estilo que ya "
                     "estén en el registro.")
        p.anotar(event_type="declaration", document=rel, document_type=d["tipo"], hierarchical_level=d["nivel"],
                 document_hash="sha256:" + d["sha"], words=d["palabras"], human_words=d["humanas"],
                 ai_words_introduced=d["ia_intro"], tokens_generated=0, tokens_revised_by_human=0,
                 revision_ratio=1, has_contribution=r2(PUNTOS[d["nivel"]]), attribution="declarado",
                 snapshot_hash=d.get("huella_texto"), ai_words_pasted_by_author=d.get("pegadas") or None,
                 derived_from_baseline=True, description="El autor declara que el documento sale de su manuscrito")
        r = calcular_has(entradas(p.eventos()))
        print(f"Anotado: «{rel}» sale de tu manuscrito, por declaración tuya. La concepción se te acredita.\n"
              f"HAS ahora: {_n(r['has_global'])}/100.")
        return
    ev, contradice = _declarar(p, ruta, rel, a.origen, a.tipo, "declaration",
                               "El autor declara que el documento es suyo" if a.origen == "humano"
                               else "El autor declara que el documento lo generó la IA")
    de = "tuyo" if a.origen == "humano" else "generado por la IA"
    print(f"Anotado: «{rel}» ({NOMBRE_TIPO.get(ev['document_type'], ev['document_type'])}, "
          f"{ev['words']} palabras) consta como {de}, por declaración.")
    if contradice:
        print("⚠️ El registro lo había medido como generado por la IA. La declaración queda a la vista "
              "en el informe y en el certificado.")
    r = calcular_has(entradas(p.eventos()))
    print(f"HAS ahora: {_n(r['has_global'])}/100.")


def cmd_inicio(a):
    """Empieza a trabajar un colaborador. Lo llama hi-args.py, y lo llama en CADA bloque: si la
    sesión ya está abierta no se hace nada (lo escrito a medias no es del autor)."""
    p = _proyecto(a.ruta, exigir=False)
    if not p:
        return
    s = p.sesion()
    if s and s.get("abierta") and ahora() - s.get("ultima", s["abierta"]) < HUECO:
        p.latido(s)
        return
    # No hay sesión, o la que hay lleva tres cuartos de hora sin dar señales: era de otro colaborador
    # que no cerró. Lo suyo no es de este (equipo rojo, 1-oct: salía «medido» a nombre del siguiente).
    ponerse_al_dia(p)
    p.abrir_sesion()


def cmd_fin(a):
    """Termina un colaborador. Lo llama hi-log.sh. Lo que ha cambiado desde que empezó es suyo."""
    p = _proyecto(a.ruta, exigir=False)
    if not p:
        return
    s = p.sesion() or {}
    abierta = s.get("abierta")
    if not abierta:
        # Termina un colaborador que no avisó de que empezaba (hi-args no llegó a correr, o miraba
        # otra carpeta). Lo que lleva horas guardado no puede ser suyo: es del autor, como lo habría
        # sido al empezar. Lo reciente no se sabe, y va como incierto.
        mirar(p, "H", hasta=ahora() - SESION_VIVA)
    anotado, otros = mirar(p, "A", colab=a.colab, modelo=a.modelo,
                           atribucion="medido" if abierta else "incierto",
                           motivo=None if abierta else "el colaborador terminó sin haber avisado de que empezaba")
    p.anotar(event_type="collaborator_run", collaborator=a.colab, collaborator_name=a.nombre,
             mode=a.modo, opened=abierta or ahora(), closed=ahora(),
             produced=_producido(anotado, otros))
    p.cerrar_sesion()


def cmd_escrito(a):
    """La IA acaba de escribir este fichero (lo avisa el gancho de Write/Edit).

    Dentro de una sesión de colaborador es una señal de vida: el colaborador sigue trabajando y lo
    suyo se anotará al cerrar. FUERA de sesión —un «alárgalo un poco» en el turno siguiente, que no
    pasa por hi-args.py— se anota AHORA, como de la IA: si solo se guardara un aviso, bastaría que
    el autor abriera el fichero un cuarto de hora después y lo guardase para que todo contase como
    suyo (equipo rojo, 1-oct-2026)."""
    if not a.ruta or not os.path.isfile(a.ruta):
        return
    p = _proyecto(a.ruta, exigir=False)
    if not p:
        return
    ruta = os.path.abspath(a.ruta)
    rel = os.path.relpath(ruta, p.raiz).replace(os.sep, "/")
    if rel.startswith("..") or not rel.lower().endswith(EXTENSIONES):
        return
    s = p.sesion()
    if s and s.get("abierta") and ahora() - s.get("ultima", s["abierta"]) < HUECO:
        p.latido(s)
        return
    mirar(p, "A", colab="(fuera de sesión)", solo=rel)


def _n(x):
    return f"{x:.2f}".replace(".", ",")


def _resumen(p):
    evs = p.eventos()
    docs = documentos(evs)
    vivos = cabezas(docs)
    r = calcular_has(entradas(evs))
    todas = [e for e in evs if e.get("event_type") == "collaborator_run"]
    corridas = [e for e in todas if not e.get("unclosed")]
    por_colab = {}
    for e in corridas:
        k = e.get("collaborator_name") or e.get("collaborator") or "?"
        por_colab[k] = por_colab.get(k, 0) + 1
    integra, rota = p.cadena()
    for b in r["breakdown"]:
        suyos = [d for d in vivos.values() if d["nivel"] == b["level"]]
        b["from_manuscript"] = bool(suyos) and b["level"] in CONCEPCION and all(d["de_base"] for d in suyos)
        # Sin documento y acreditado solo en parte: el manuscrito previo es pequeño para este libro.
        b["partial_baseline"] = not suyos and b["level"] in CONCEPCION and b["presence_verified"] \
            and not b["credited_by_baseline"]
    return {
        "project": p.datos, "has": r["has_global"], "interpretacion": interpretar(r["has_global"]),
        "breakdown": r["breakdown"], "baseline": r["baseline"],
        "documentos": [{"document": rel, "tipo": d["tipo"], "palabras": d["palabras"],
                        "humanas": d["humanas"], "parte_humana": r2(d["humanas"] / d["palabras"]) if d["palabras"] else 1,
                        "atribucion": d["atribucion"], "de_base": d["de_base"], "sha": d["sha"]}
                       for rel, d in sorted(vivos.items())],
        "colaboradores": por_colab, "sesiones": len(corridas), "sin_cerrar": len(todas) - len(corridas),
        "eventos": len(evs),
        "declaraciones": [{"document": e.get("document"), "fecha": e.get("timestamp"),
                           "que": e.get("description"), "contradice": bool(e.get("overrides_measured"))}
                          for e in evs if e.get("event_type") in ("declaration", "baseline_declared")],
        "inciertos": sorted(rel for rel, d in vivos.items() if d["atribucion"] == "incierto"),
        "motivos": {e["document"]: e.get("uncertain_reason") for e in evs
                    if e.get("attribution") == "incierto" and e.get("document")},
        "factor_base": r2(factor_base(vivos, MIN_BASE, r["baseline"].get("words") or 0))
        if r["baseline"]["declared"] else None,
        "palabras": sum(d["palabras"] for d in vivos.values()),
        "palabras_ia": sum(d["palabras"] - d["humanas"] for d in vivos.values()),
        "palabras_tuyas_despues": sum(e.get("tokens_revised_by_human", 0) for e in evs
                                      if e.get("event_type") == "text_revised"),
        "primer_evento": evs[0]["timestamp"] if evs else None,
        "ultimo_evento": evs[-1]["timestamp"] if evs else None,
        "huella_registro": evs[-1].get("hash") if evs else None,
        "cadena_integra": integra, "linea_rota": rota, "has_version": VERSION_HAS,
    }


_COMO = {"medido": "medido", "declarado": "declarado por ti", "preexistente": "anterior al registro",
         "incierto": "incierto (cuenta como IA)"}


def _pinta_niveles(r):
    lineas = []
    for b in r["breakdown"]:
        if b["credited_by_baseline"]:
            como = "por el manuscrito previo"
        elif not b["presence_verified"]:
            como = "sin documento" if b["level"] != 6 else "la IA no ha escrito en el manuscrito"
        elif b["level"] == 6:
            como = f"has sustituido el {round(b['average_revision_ratio'] * 100)} % de lo que metió la IA"
        elif b.get("partial_baseline"):
            como = f"por el manuscrito previo, al {round(b['average_revision_ratio'] * 100)} %: es poco para este libro"
        elif b.get("from_manuscript"):
            como = "la redactó la IA a partir de tu manuscrito"
        else:
            como = f"{round(b['average_revision_ratio'] * 100)} % tuyo"
        lineas.append(f"  {b['label']:<16} {_n(b['earned_points']):>7} / {b['max_points']:<3}  {como}")
    return "\n".join(lineas)


def cmd_estado(a):
    p = _proyecto(a.carpeta)
    ponerse_al_dia(p)
    r = _resumen(p)
    if getattr(a, "json", False):
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return
    print(f"AWAP local — {r['project'].get('title', '')}")
    print(f"HAS: {_n(r['has'])}/100 — {r['interpretacion']}")
    print(f"Eventos: {r['eventos']} · Sesiones con colaboradores: {r['sesiones']} · "
          f"Documentos que cuentan: {len(r['documentos'])}")
    if r["baseline"]["declared"]:
        print(f"Parte de un manuscrito previo declarado ({r['baseline']['words']} palabras).")
    if r["inciertos"]:
        print(f"⚠️ En {len(r['inciertos'])} documento(s) hay cambios que no se han podido atribuir con seguridad, "
              "y cuentan como generados:")
        for rel in r["inciertos"]:
            print(f"   · {rel} — {r['motivos'].get(rel) or 'sin atribución segura'}")
        print("   Si lo escribiste tú, decláralo con --mine <fichero>.")
    if not r["cadena_integra"]:
        print(f"⚠️ El registro no cuadra a partir de la línea {r['linea_rota']}: alguien lo ha editado a mano.")


def cmd_nota(a):
    p = _proyecto(a.carpeta)
    ponerse_al_dia(p)
    r = _resumen(p)
    print(f"HAS: {_n(r['has'])}/100 — {r['interpretacion']}")


def cmd_informe(a):
    p = _proyecto(a.carpeta)
    ponerse_al_dia(p)
    r = _resumen(p)
    print(f"AWAP local — informe de «{r['project'].get('title', '')}»\n")
    print(f"HAS: {_n(r['has'])}/100 — {r['interpretacion']}\n")
    print("Por niveles (obtenido / máximo):")
    print(_pinta_niveles(r))
    if r["baseline"]["declared"]:
        print(f"\nManuscrito previo declarado: {r['baseline']['words']} palabras "
              f"({(r['baseline']['declared_at'] or '')[:10]}).")
    print("\nDocumentos que cuentan:")
    if not r["documentos"]:
        print("  (ninguno todavía)")
    for d in r["documentos"]:
        if d["de_base"] and d["tipo"] != "draft":
            de = "lo redactó la IA a partir de tu manuscrito: la concepción se te acredita" \
                 + (" (por declaración tuya)" if d["atribucion"] == "declarado" else "")
        else:
            de = f"{round(d['parte_humana'] * 100)} % tuyo ({_COMO.get(d['atribucion'], d['atribucion'])})"
        print(f"  · {d['document']} — {NOMBRE_TIPO.get(d['tipo'], d['tipo'])}, {d['palabras']} palabras, {de}")
    sin_rastro = [d["document"] for d in r["documentos"] if d["tipo"] != "draft" and not d["de_base"]
                  and d["parte_humana"] < 1 and r["baseline"]["declared"]]
    if sin_rastro:
        print("\nSi alguno de estos lo redactó la IA A PARTIR de tu manuscrito (" + ", ".join(sin_rastro) + "), el "
              "registro no ha encontrado el rastro (nombres propios o frases del manuscrito). Puedes declararlo:\n"
              "  declarar <carpeta> <fichero> --origen manuscrito")
    if r["colaboradores"]:
        print("\nColaboradores que han trabajado: "
              + ", ".join(f"{k} ×{v}" for k, v in sorted(r["colaboradores"].items())))
    if r["sin_cerrar"]:
        print(f"Sesiones de colaborador que no se cerraron bien: {r['sin_cerrar']} (lo que cambió en ellas cuenta "
              "como generado).")
    print(f"\nPalabras de la IA en los documentos que cuentan: {r['palabras_ia']} de {r['palabras']}")
    print(f"Palabras tuyas nuevas desde que hay registro: {r['palabras_tuyas_despues']}")
    if r["declaraciones"]:
        print("\nPor declaración tuya (no medido):")
        for d in r["declaraciones"]:
            print(f"  · {d['document']} — {d['que']} ({(d['fecha'] or '')[:10]})"
                  + (" — contradice lo medido" if d["contradice"] else ""))
    print(f"\nRegistro: {r['eventos']} eventos, del {(r['primer_evento'] or '')[:10]} al "
          f"{(r['ultimo_evento'] or '')[:10]}. Cadena {'íntegra' if r['cadena_integra'] else 'ROTA en la línea ' + str(r['linea_rota'])}.")
    print("El modificador conversacional de AWAP no se aplica en el registro local.")


def cmd_registro(a):
    p = _proyecto(a.carpeta)
    evs = p.eventos()[-a.n:]
    if not evs:
        print("Todavía no hay nada registrado.")
        return
    que = {"project_created": "registro abierto", "document_created": "documento tuyo",
           "text_generated": "texto de la IA", "text_revised": "cambio tuyo",
           "baseline_declared": "manuscrito previo declarado", "declaration": "declaración",
           "document_removed": "documento retirado", "collaborator_run": "colaborador",
           "ai_wrote_untyped": "texto de la IA en ficheros que no cuentan"}
    for e in evs:
        t = e.get("event_type")
        linea = f"{e.get('seq'):>4}  {e.get('timestamp', '')[:16].replace('T', ' ')}  {que.get(t, t)}"
        if t in ("collaborator_run", "ai_wrote_untyped"):
            linea += f": {e.get('collaborator_name') or e.get('collaborator')} ({e.get('mode') or ''})" \
                     f" — {len(e.get('produced') or [])} fichero(s)"
        elif e.get("document"):
            linea += f": {e['document']}"
            if t == "text_generated":
                linea += f" (+{e.get('tokens_generated', 0)} palabras de la IA" \
                         + (f", {e['collaborator']}" if e.get("collaborator") else "") \
                         + (", incierto" if e.get("attribution") == "incierto" else "") + ")"
            elif t == "text_revised":
                linea += f" (+{e.get('tokens_revised_by_human', 0)} palabras tuyas)"
            elif e.get("words") is not None:
                linea += f" ({e['words']} palabras)"
        print(linea)


def huellas_anotadas(p):
    """La huella que el registro anotó para el texto guardado de cada documento: {ruta: huella}."""
    anotada = {}
    for e in p.eventos():
        if e.get("document") and e.get("snapshot_hash"):
            anotada[e["document"]] = e["snapshot_hash"]
        for x in e.get("produced") or []:
            if x.get("snapshot_hash"):
                anotada[x["document"]] = x["snapshot_hash"]
    return anotada


def faltas(p):
    """Lo que falta de lo que el registro necesita para medir, además de la cadena: el texto guardado
    de cada documento vivo y el archivo de lo que la IA escribió y ya no está en ningún fichero. Sin
    ellos, texto generado puede volver a entrar como del autor; por eso `verificar` lo mira y el
    certificado no se emite si falta algo (equipo rojo, 1-oct-2026: un `rm` y el registro «cuadraba»)."""
    out = []
    sin_texto = [rel for rel in cabezas(documentos(p.eventos())) if p.instantanea(rel) is None]
    if sin_texto:
        out.append(f"Falta el texto guardado de {len(sin_texto)} documento(s) ({', '.join(sin_texto[:5])}"
                   + ("…" if len(sin_texto) > 5 else "") + "): alguien ha borrado parte de .awap/local/textos. "
                   "Sin él no se puede medir qué cambia, y lo que cambie contará como incierto.")
    # Y que cada texto guardado sea el que se anotó: mismas palabras, mismas marcas.
    tocadas = []
    for rel, h in huellas_anotadas(p).items():
        snap = p.instantanea(rel)
        if snap is not None and p.huella_texto(snap.get("p", []), snap.get("f", [])) != h:
            tocadas.append(rel)
    if tocadas:
        out.append(f"El texto guardado de {len(tocadas)} documento(s) no es el que se anotó ({', '.join(tocadas[:5])}"
                   + ("…" if len(tocadas) > 5 else "") + "): está manipulado, o a medio escribir. Mira el estado "
                   "una vez más; si sigue saliendo, alguien ha editado .awap/local/textos a mano.")
    debe = sum(e.get("ai_words_archived", 0) for e in p.eventos())
    hay = p.en_archivo()
    if hay < debe:
        out.append(f"Falta parte del archivo de lo que escribió la IA (.awap/local/textos/_ia.jsonl.gz): el registro "
                   f"anotó {debe} palabras archivadas y hay {hay}. Sin él, ese texto puede volver a entrar como tuyo.")
    return out


def cmd_verificar(a):
    p = _proyecto(a.carpeta)
    integra, rota = p.cadena()
    n = len(p.eventos())
    if integra:
        print(f"✓ El registro cuadra: {n} eventos encadenados, sin huecos ni ediciones.")
        print(f"  Huella del registro: {p.eventos()[-1]['hash'] if n else '(vacío)'}")
    else:
        print(f"✗ El registro NO cuadra a partir de la línea {rota} de {n}: se ha editado, borrado o "
              "reordenado algo a mano.")
    cert = _leer_json(os.path.join(p.dir, "certificado.json"))
    if cert:
        igual = any(e.get("hash") == cert.get("huella_registro") for e in p.eventos())
        print(("✓" if igual and integra else "✗") + f" El último certificado ({cert.get('emitido', '')[:10]}) "
              + ("sale de este registro." if igual else "NO corresponde a este registro."))
    for falta in faltas(p):
        print("✗ " + falta)
        integra = False
    cambiados = []
    en_disco = ficheros(p.raiz)
    for rel, d in cabezas(documentos(p.eventos())).items():
        if rel in en_disco and _sha_fichero(os.path.join(p.raiz, rel)) != d["sha"]:
            cambiados.append(rel)
    if cambiados:
        print(f"  {len(cambiados)} documento(s) han cambiado desde la última anotación: se anotarán "
              "la próxima vez que mires el estado.")
    if not integra:
        sys.exit(1)


# ───────────────────────────── el certificado (PDF sin dependencias) ─────────────────────────────

_ANCHOS = dict(zip(range(32, 127), [
    278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278, 556, 556, 556, 556,
    556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556, 1015, 667, 667, 722, 722, 667, 611, 778,
    722, 278, 500, 667, 556, 833, 722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278,
    278, 278, 469, 556, 333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
    556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584]))


class _PDF:
    """Un PDF de texto, con las fuentes que trae cualquier lector (Helvetica y Courier). Sin
    dependencias: en la máquina de Cowork no hay con qué hacer otro."""
    ANCHO, ALTO, MARGEN = 595.28, 841.89, 56

    def __init__(self):
        self.paginas = []
        self._nueva()

    def _nueva(self):
        self.ops = []
        self.paginas.append(self.ops)
        self.y = self.ALTO - 56

    def _ancho(self, s, tam, fuente):
        if fuente == "F3":
            return len(s) * 0.6 * tam
        total = 0
        for c in s:
            base = unicodedata.normalize("NFKD", c)[0]
            total += _ANCHOS.get(ord(base), 556)
        return total * tam / 1000 * (1.06 if fuente == "F2" else 1)

    @staticmethod
    def _esc(s):
        b = s.encode("cp1252", errors="replace")
        return b.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")

    def _partir(self, s, tam, fuente, ancho):
        lineas, actual = [], ""
        for palabra in s.split():
            while self._ancho(palabra, tam, fuente) > ancho:      # una huella larga, sin espacios
                corte = max(1, int(len(palabra) * ancho / self._ancho(palabra, tam, fuente)) - 1)
                if actual:
                    lineas.append(actual)
                    actual = ""
                lineas.append(palabra[:corte])
                palabra = palabra[corte:]
            prueba = (actual + " " + palabra).strip()
            if self._ancho(prueba, tam, fuente) <= ancho:
                actual = prueba
            else:
                lineas.append(actual)
                actual = palabra
        if actual:
            lineas.append(actual)
        return lineas or [""]

    def texto(self, s, tam=10, fuente="F1", gris=0.1, x=None, ancho=None, tras=0):
        x = self.MARGEN if x is None else x
        ancho = ancho or (self.ANCHO - self.MARGEN - x)
        for linea in self._partir(s, tam, fuente, ancho):
            if self.y - tam < 72:
                self._nueva()
            self.y -= tam               # `y` es el borde de arriba de la línea: se baja a su base
            self.ops.append(b"BT /%s %d Tf %.2f g %.1f %.1f Td (" % (fuente.encode(), tam, gris, x, self.y)
                            + self._esc(linea) + b") Tj ET")
            self.y -= tam * 0.45
        self.y -= tras

    def fila(self, celdas, xs, tam=9, fuente="F1", gris=0.1):
        if self.y - tam < 72:
            self._nueva()
        self.y -= tam
        for i, (s, x) in enumerate(zip(celdas, xs)):
            limite = (xs[i + 1] if i + 1 < len(xs) else self.ANCHO - self.MARGEN) - x - 6
            s = str(s)
            while len(s) > 1 and self._ancho(s, tam, fuente) > limite:
                s = s[:-2] + "…"
            self.ops.append(b"BT /%s %d Tf %.2f g %.1f %.1f Td (" % (fuente.encode(), tam, gris, x, self.y)
                            + self._esc(s) + b") Tj ET")
        self.y -= tam * 0.6

    def regla(self, tras=10):
        self.y -= 4
        self.ops.append(b"0.75 G 0.5 w %.1f %.1f m %.1f %.1f l S"
                        % (self.MARGEN, self.y, self.ANCHO - self.MARGEN, self.y))
        self.y -= tras

    def espacio(self, n=8):
        self.y -= n

    def reserva(self, alto):
        """Si no caben `alto` puntos, pasa de página: un título no se queda solo al pie."""
        if self.y - alto < 72:
            self._nueva()

    def bytes(self, pie):
        objetos = [None,
                   None,  # 1 catálogo
                   None,  # 2 páginas
                   b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
                   b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
                   b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>"]
        hijos = []
        for i, ops in enumerate(self.paginas, 1):
            texto_pie = f"{pie} · página {i} de {len(self.paginas)}"
            cuerpo = b"\n".join(ops + [b"BT /F1 8 Tf 0.45 g %.1f 40 Td (" % self.MARGEN
                                       + self._esc(texto_pie) + b") Tj ET"])
            objetos.append(b"<< /Length %d >>\nstream\n" % len(cuerpo) + cuerpo + b"\nendstream")
            n_contenido = len(objetos) - 1
            objetos.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %.2f %.2f] /Contents %d 0 R "
                           b"/Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >> >> >>"
                           % (self.ANCHO, self.ALTO, n_contenido))
            hijos.append(len(objetos) - 1)
        objetos[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
        objetos[2] = b"<< /Type /Pages /Kids [" + b" ".join(b"%d 0 R" % h for h in hijos) \
                     + b"] /Count %d >>" % len(hijos)
        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        pos = [0]
        for n in range(1, len(objetos)):
            pos.append(len(out))
            out += b"%d 0 obj\n" % n + objetos[n] + b"\nendobj\n"
        xref = len(out)
        out += b"xref\n0 %d\n" % len(objetos) + b"0000000000 65535 f \n"
        for n in range(1, len(objetos)):
            out += b"%010d 00000 n \n" % pos[n]
        out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objetos), xref)
        return bytes(out)


def cmd_certificado(a):
    p = _proyecto(a.carpeta)
    ponerse_al_dia(p)
    r = _resumen(p)
    if not r["cadena_integra"]:
        sys.exit(f"No se emite el certificado: el registro no cuadra a partir de la línea {r['linea_rota']}. "
                 "Un certificado sobre un registro editado a mano no vale nada.")
    if not r["documentos"]:
        sys.exit("No se emite el certificado: todavía no hay ningún documento que cuente en el registro.")
    falta = faltas(p)
    if falta:
        sys.exit("No se emite el certificado: al registro le falta algo.\n  " + "\n  ".join(falta))
    cert = {"tipo": "awap-local-borrador", "emitido": iso(), "has_version": VERSION_HAS,
            "proyecto": r["project"], "has": r["has"], "interpretacion": r["interpretacion"],
            "niveles": r["breakdown"], "manuscrito_previo": r["baseline"], "documentos": r["documentos"],
            "colaboradores": r["colaboradores"], "sesiones_sin_cerrar": r["sin_cerrar"],
            "declaraciones": r["declaraciones"],
            "inciertos": r["inciertos"], "eventos": r["eventos"], "primer_evento": r["primer_evento"],
            "ultimo_evento": r["ultimo_evento"], "huella_registro": r["huella_registro"],
            "anclado_en_servidor": False}
    cert["huella_certificado"] = hashlib.sha256(json.dumps(cert, sort_keys=True, ensure_ascii=False,
                                                           separators=(",", ":")).encode("utf-8")).hexdigest()
    titulo = r["project"].get("title", "")
    autor = r["project"].get("author", "")

    d = _PDF()
    d.texto("HUMANINK · AWAP", 8, "F2", 0.45, tras=6)
    d.texto("Certificado de autoría", 22, "F2", 0.05, tras=2)
    d.texto("Borrador de autoauditoría · registro local, no anclado en ningún servidor", 10, "F1", 0.4, tras=8)
    d.regla(14)
    d.texto(titulo, 15, "F2", 0.05, tras=2)
    if autor:
        d.texto(autor, 11, "F1", 0.2)
    d.espacio(14)
    d.texto(f"HAS {_n(r['has'])} / 100", 26, "F2", 0.05, tras=2)
    d.texto(r["interpretacion"].capitalize(), 11, "F1", 0.2, tras=8)
    d.regla(14)

    d.reserva(150)
    d.texto("Por niveles", 11, "F2", 0.05, tras=4)
    xs = [56, 190, 250, 320]
    d.fila(["Nivel", "Máximo", "Obtenido", "Cómo se acredita"], xs, 8, "F2", 0.4)
    for b in r["breakdown"]:
        if b["credited_by_baseline"]:
            como = "Por el manuscrito previo declarado"
        elif not b["presence_verified"]:
            como = "Sin documento" if b["level"] != 6 else "La IA no ha escrito en el manuscrito"
        elif b["level"] == 6:
            como = f"Has sustituido el {round(b['average_revision_ratio'] * 100)} % de lo que metió la IA"
        elif b.get("partial_baseline"):
            como = f"Por el manuscrito previo, al {round(b['average_revision_ratio'] * 100)} %"
        elif b.get("from_manuscript"):
            como = "Redactado por la IA a partir de tu manuscrito"
        else:
            como = f"{round(b['average_revision_ratio'] * 100)} % de las palabras son tuyas"
        d.fila([b["label"], b["max_points"], _n(b["earned_points"]), como], xs)
    d.espacio(8)

    if r["baseline"]["declared"]:
        d.reserva(70)
        d.texto("Manuscrito previo", 11, "F2", 0.05, tras=2)
        d.texto(f"El autor declaró el {(r['baseline']['declared_at'] or '')[:10]} un manuscrito de "
                f"{r['baseline']['words']} palabras, escrito antes de usar HumanInk. La puntuación parte "
                "de esa declaración: la concepción del libro se le acredita porque el manuscrito la demuestra"
                + (f", en un {round((r['factor_base'] or 0) * 100)} %: sus palabras son pocas para el libro actual."
                   if (r["factor_base"] or 0) < 1 else "."), 9)
        d.texto(str(r["baseline"]["manuscript_hash"] or ""), 7, "F3", 0.35, tras=8)

    d.reserva(70)
    d.texto("Documentos que cuentan", 11, "F2", 0.05, tras=4)
    xs = [56, 262, 322, 377, 422]
    d.fila(["Documento", "Tipo", "Palabras", "Tuyo", "Cómo se sabe"], xs, 8, "F2", 0.4)
    for doc in r["documentos"]:
        if doc["de_base"] and doc["tipo"] != "draft":
            tuyo = "—"
            como = "declarado: de tu manuscrito" if doc["atribucion"] == "declarado" else "la IA, de tu manuscrito"
        else:
            tuyo = f"{round(doc['parte_humana'] * 100)} %"
            como = "incierto: como IA" if doc["atribucion"] == "incierto" else _COMO.get(doc["atribucion"], doc["atribucion"])
        d.fila([doc["document"], NOMBRE_TIPO.get(doc["tipo"], doc["tipo"]), doc["palabras"], tuyo, como], xs)
    d.espacio(8)

    if r["colaboradores"]:
        d.reserva(50)
        d.texto("Colaboradores de HumanInk que han trabajado", 11, "F2", 0.05, tras=2)
        d.texto(", ".join(f"{k} ×{v}" for k, v in sorted(r["colaboradores"].items()))
                + ". Funcionan sobre Claude, de Anthropic.", 9, tras=8)

    if r["declaraciones"]:
        d.reserva(50)
        d.texto("Por declaración del autor (no medido)", 11, "F2", 0.05, tras=2)
        for x in r["declaraciones"]:
            d.texto(f"· {x['document']} — {x['que']} ({(x['fecha'] or '')[:10]})"
                    + (" — contradice lo que había medido el registro" if x["contradice"] else ""), 9)
        d.espacio(8)
    if r["inciertos"]:
        d.reserva(50)
        d.texto("Sin atribución segura", 11, "F2", 0.05, tras=2)
        d.texto("Cambios que no se han podido atribuir con seguridad y cuentan como generados por la IA: "
                + "; ".join(f"{x} ({r['motivos'].get(x) or 'sin atribución segura'})" for x in r["inciertos"]) + ".",
                9, tras=8)

    d.reserva(150)
    d.texto("Qué acredita este documento, y qué no", 11, "F2", 0.05, tras=2)
    d.texto(f"Acredita el proceso registrado en la carpeta del libro desde el {(r['primer_evento'] or '')[:10]}: "
            "qué documentos había, qué escribió cada colaborador de HumanInk y qué cambió el autor después. "
            "No se pregunta a nadie: se comparan los ficheros, palabra a palabra, y la procedencia sigue al "
            "texto aunque cambie de fichero.", 9, tras=3)
    d.texto("No acredita lo anterior al registro (eso lo declara el autor y así consta), ni el trabajo hecho "
            "con una IA fuera de HumanInk. Mide el proceso, no detecta si un texto «suena» a IA.", 9, tras=3)
    d.texto("No está anclado en ningún servidor ni registrado ante terceros. El registro va encadenado, de "
            "modo que una edición parcial se nota, pero quien tenga la carpeta puede rehacerlo entero. Es un "
            "borrador para el propio autor. El certificado verificable por terceros se emite con HumanInk Studio.",
            9, tras=10)
    d.regla()
    d.texto(f"Registro: {r['eventos']} eventos, del {(r['primer_evento'] or '')[:10]} al "
            f"{(r['ultimo_evento'] or '')[:10]} · Emitido el {cert['emitido'][:10]} · Fórmula {VERSION_HAS}", 8, "F1", 0.3)
    d.texto("Huella del registro", 8, "F2", 0.3)
    d.texto(str(r["huella_registro"]), 7, "F3", 0.3)
    d.texto("Huella del certificado", 8, "F2", 0.3)
    d.texto(cert["huella_certificado"], 7, "F3", 0.3)

    salida = a.salida or os.path.join(p.raiz, f"Certificado AWAP (borrador) {cert['emitido'][:10]}.pdf")
    salida = os.path.abspath(os.path.expanduser(salida))
    with open(salida, "wb") as f:
        f.write(d.bytes(f"{titulo} · certificado AWAP, borrador local"))
    _guardar_json(os.path.join(p.dir, "certificado.json"), cert)
    print(f"Certificado (borrador local) generado:\n  {salida}")
    print(f"HAS: {_n(r['has'])}/100 — {r['interpretacion']}")
    print(f"Huella del registro: {r['huella_registro']}")
    print("Es un borrador para ti: no está registrado en ningún servidor y un tercero no puede comprobarlo.")


def main(argv=None):
    ap = argparse.ArgumentParser(description="AWAP local — registro de autoría en la carpeta del libro")
    sub = ap.add_subparsers(dest="orden", required=True)

    s = sub.add_parser("iniciar"); s.add_argument("carpeta"); s.add_argument("--titulo", default="")
    s.add_argument("--autor", default=""); s.set_defaults(f=cmd_iniciar)
    s = sub.add_parser("base"); s.add_argument("carpeta"); s.add_argument("fichero"); s.set_defaults(f=cmd_base)
    s = sub.add_parser("declarar"); s.add_argument("carpeta"); s.add_argument("fichero")
    s.add_argument("--origen", choices=("humano", "ia", "manuscrito"), required=True)
    s.add_argument("--tipo", choices=tuple(k for k in NIVEL_DE if k != "revision")); s.set_defaults(f=cmd_declarar)
    s = sub.add_parser("estado"); s.add_argument("carpeta"); s.add_argument("--json", action="store_true")
    s.set_defaults(f=cmd_estado)
    s = sub.add_parser("informe"); s.add_argument("carpeta"); s.set_defaults(f=cmd_informe)
    s = sub.add_parser("nota"); s.add_argument("carpeta"); s.set_defaults(f=cmd_nota)
    s = sub.add_parser("registro"); s.add_argument("carpeta"); s.add_argument("--n", type=int, default=30)
    s.set_defaults(f=cmd_registro)
    s = sub.add_parser("verificar"); s.add_argument("carpeta"); s.set_defaults(f=cmd_verificar)
    s = sub.add_parser("certificado"); s.add_argument("carpeta"); s.add_argument("--salida")
    s.set_defaults(f=cmd_certificado)
    s = sub.add_parser("inicio"); s.add_argument("ruta"); s.set_defaults(f=cmd_inicio)
    s = sub.add_parser("escrito"); s.add_argument("ruta"); s.set_defaults(f=cmd_escrito)
    s = sub.add_parser("fin"); s.add_argument("ruta"); s.add_argument("--colab", default="awos-unknown")
    s.add_argument("--nombre", default=""); s.add_argument("--modo", default="")
    s.add_argument("--modelo", default=""); s.set_defaults(f=cmd_fin)

    a = ap.parse_args(argv)
    silenciosa = a.orden in ("inicio", "fin", "escrito")
    if a.orden == "escrito" and a.ruta == "-":      # el JSON del gancho, por la entrada estándar
        try:
            a.ruta = str((json.load(sys.stdin).get("tool_input") or {}).get("file_path") or "")
        except Exception:
            return 0
        if not a.ruta:
            return 0
    # Una sola orden escribe en el registro a la vez: el gancho de escritura y un colaborador pueden
    # coincidir. El gancho espera poco y se retira (no puede retrasar una escritura); el cierre de
    # un colaborador espera más, porque si no cierra, su sesión se queda abierta.
    cerrojo = None
    if a.orden not in ("registro", "verificar", "iniciar"):
        raiz = raiz_de(getattr(a, "carpeta", None) or getattr(a, "ruta", None) or ".") \
            or (raiz_de(a.fichero) if getattr(a, "fichero", None) else None)
        if raiz:
            cerrojo = Proyecto(raiz)
            # El cierre de un colaborador espera más que lo que tarda en caducar un cerrojo muerto:
            # si se pierde, la sesión se queda abierta.
            # El gancho corre DESPUÉS de la escritura: esperar no la retrasa, solo el paso siguiente.
            espera = float(os.environ.get("AWAP_ESPERA") or (8 if a.orden == "escrito" else
                                                             CERROJO_VIEJO + 15 if a.orden == "fin" else 20))
            if not cerrojo.cerrar_paso(espera):
                p_, cerrojo = cerrojo, None       # no es nuestro: no se toca al salir
                if a.orden == "escrito":
                    # El gancho no puede esperar más, pero la escritura no se pierde: queda apuntada
                    # (una línea, sin tocar la cadena) y la siguiente mirada la cuenta como de la IA.
                    try:
                        ruta = os.path.abspath(a.ruta)
                        rel = os.path.relpath(ruta, raiz).replace(os.sep, "/")
                        if os.path.isfile(ruta) and not rel.startswith("..") and rel.lower().endswith(EXTENSIONES):
                            with open(p_.f_pendientes, "a", encoding="utf-8") as f:
                                f.write(json.dumps({"document": rel, "mtime": os.stat(ruta).st_mtime}) + "\n")
                    except Exception:
                        pass
                if silenciosa:
                    return 0
                sys.exit("El registro está ocupado ahora mismo (otro proceso lo está escribiendo). Repite en un momento.")
    try:
        if silenciosa:
            # Nunca rompe a un colaborador: si algo falla aquí, el colaborador sigue y no dice nada.
            try:
                a.f(a)
            except BaseException:
                pass
            return 0
        try:
            a.f(a)
        except OSError as e:
            sys.exit(f"No puedo escribir en la carpeta del libro ({e.strerror or e}). Mira que esté conectada a la "
                     "conversación con permiso de escritura y que no sea de solo lectura.")
        return 0
    finally:
        if cerrojo:
            cerrojo.abrir_paso()


if __name__ == "__main__":
    sys.exit(main())
