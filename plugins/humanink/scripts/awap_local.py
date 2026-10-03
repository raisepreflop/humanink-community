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
    python3 awap_local.py antes -  /  despues -                    los ganchos de antes y después de cada
                                                                   orden de la IA (el JSON, por la entrada)

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
import fnmatch
import glob
import gzip
import hashlib
import itertools
import json
import math
import os
import re
import shlex
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
COBERTURA_COPIA = 0.90      # y cuando el fichero nuevo lo hace el autor: casi entero, o es un trozo que saca
REPITE_CIERRE = 120         # un segundo cierre del mismo colaborador en dos minutos es el mismo trabajo
MIN_PREVIO = 100            # palabras que tenía que tener ya: un título suelto no es un manuscrito
MARGEN_PREVIO = 1.25        # lo que puede haber crecido un manuscrito desde que trabaja la IA y seguir siendo «previo»
TROZO = 3000                # palabras por trozo al comparar un bloque enorme

PUNTOS = {1: 100, 2: 85, 3: 75, 4: 60, 5: 40, 6: 25, 7: 5}
ETIQUETAS = {1: "Premisa", 2: "Sinopsis", 3: "Biblia", 4: "Escaleta", 5: "Estilo y voz",
             6: "Revisión humana", 7: "Texto"}
NIVEL_DE = {"premise": 1, "synopsis": 2, "bible": 3, "outline": 4, "style_instructions": 5,
            "revision": 6, "draft": 7}
NOMBRE_TIPO = {"premise": "premisa", "synopsis": "sinopsis", "bible": "biblia", "outline": "escaleta",
               "style_instructions": "estilo", "draft": "manuscrito"}
COLABORADORES = {
    "awos-escritor": "Escritor fantasma", "awos-corrector": "Corrector", "awos-coach": "Coach literario",
    "awos-lector": "Lector profesional", "awos-humanizador": "Humanizador", "awos-estilo": "Editor de estilo",
    "awos-editor": "Editor de mesa", "awos-beta": "Lectores beta", "awos-autor": "Perfil de autor",
    "awos-analista": "Analista de mercado", "awos-maquetador": "Maquetador", "awos-portadista": "Portadista",
    "awos-asesor": "Agente literario", "awos-copywriter": "Copywriter", "awos-community": "Community manager",
    "awos-comparador": "Comparador de versiones", "awos-marketero": "Gestor de anuncios",
    "(fuera de sesión)": "la IA, fuera de un colaborador", "(sesión sin cerrar)": "un colaborador que no cerró",
    "(sin identificar)": "un colaborador sin identificar (cerró desde otra carpeta, o sin decir el libro)",
}
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


def colaborador(slug, nombre=None):
    """El nombre de un colaborador tal como lo conoce el autor, no su identificador."""
    return COLABORADORES.get(slug) or nombre or (slug or "").replace("awos-", "") or "un colaborador"


def fecha(marca, hora=False):
    """Una marca del registro (UTC) en la fecha del autor: a las 00:30 de aquí no es «ayer»."""
    try:
        d = datetime.datetime.strptime(marca, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc).astimezone()
        return d.strftime("%Y-%m-%d %H:%M" if hora else "%Y-%m-%d")
    except Exception:
        return (marca or "")[:16 if hora else 10].replace("T", " ")


def epoca(marca):
    """Una marca del registro (UTC), en segundos. 0 si no se entiende."""
    try:
        return datetime.datetime.strptime(marca, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc).timestamp()
    except Exception:
        return 0


def pct(parte, total):
    """Un porcentaje que no redondea a lo que no es: 158 palabras de la IA en 72.550 no es «100 % del
    autor», es «99,7 %» (UAT, 2-oct-2026). 100 y 0 solo cuando lo son."""
    if not total:
        return "100 %"
    x = parte / total * 100
    if parte >= total:
        return "100 %"
    if parte <= 0:
        return "0 %"
    if x >= 99 or x < 1:
        x = min(max(math.floor(x * 10) / 10, 0.1), 99.9)
        return f"{x:.1f}".replace(".", ",") + " %"
    return f"{round(x)} %"


def pl(n, uno, varios):
    return f"{n} {uno if n == 1 else varios}"


_SUFIJO_VERSION = re.compile(
    r"(?:^|[-_ .]+)(?:v\d+|b\d+|m\d+|ver(?:sion)?[-_ ]?\d*|rev\d*|copia|copy|final|definitiv[oa]|corregid[oa]|"
    r"humanizad[oa]|reescrit[oa]|revisad[oa]|nuev[oa]|bis|ok|\(\d+\)|\d{4}-\d{2}-\d{2})$")


def _raiz_nombre(rel):
    """El nombre de un fichero sin sus coletillas de versión: «DMVM-m01-v02-corregido» → «dmvm»."""
    s = _plano(os.path.splitext(os.path.basename(rel))[0]).strip(" -_.")
    while s:
        s2 = _SUFIJO_VERSION.sub("", s).strip(" -_.")
        if s2 == s or not s2:
            break
        s = s2
    return s


def misma_familia(a, b):
    """¿Se llaman como dos versiones de lo mismo? «novela v2» y «novela»; «NEMI-b20» y «NEMI-b41». No
    «capitulo-03» y «capitulo-02», ni «capitulo-2» y «capitulo-22»."""
    ra, rb = _raiz_nombre(a), _raiz_nombre(b)
    if not ra or not rb:
        return False
    if ra == rb:
        return True
    corto, largo = sorted((ra, rb), key=len)
    return largo.startswith(corto) and largo[len(corto)] in "-_ .("


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


def _f_libros():
    """Dónde se apunta qué libros con registro se están usando. En dos sitios, porque en Cowork los
    ganchos y los bloques de las skills no siempre ven el mismo disco."""
    if os.environ.get("AWAP_LIBROS"):
        return [os.environ["AWAP_LIBROS"]]
    return ["/tmp/humanink/awap-libros.json", os.path.join(os.path.expanduser("~"), ".humanink", "awap-libros.json")]


def apuntar_libro(raiz):
    """Este libro está en uso. Sirve para dos cosas que no saben de qué libro se trata: una orden de
    la IA que no nombra la carpeta (un guion con la ruta dentro) y el cierre de un colaborador que
    llega sin ella. En silencio: si no se puede apuntar, no pasa nada."""
    for f in _f_libros():
        try:
            d = _leer_json(f, {})
            d = {k: v for k, v in d.items() if isinstance(v, (int, float))} if isinstance(d, dict) else {}
            if abs(ahora() - d.get(raiz, 0)) < 300:
                continue
            d[raiz] = ahora()
            d = dict(sorted(d.items(), key=lambda kv: -kv[1])[:12])
            os.makedirs(os.path.dirname(f), exist_ok=True)
            _guardar_json(f, d)
        except Exception:
            continue


def libros_en_uso(horas=12):
    """Las carpetas de libro con registro usadas en las últimas horas, la más reciente primero."""
    juntos = {}
    for f in _f_libros():
        d = _leer_json(f, {})
        if not isinstance(d, dict):         # un fichero estropeado no puede apagar los ganchos
            continue
        for raiz, cuando in d.items():
            if isinstance(raiz, str) and isinstance(cuando, (int, float)):
                juntos[raiz] = max(juntos.get(raiz, 0), cuando)
    return [r for r, c in sorted(juntos.items(), key=lambda kv: -kv[1])
            if ahora() - c < horas * 3600 and os.path.isfile(os.path.join(r, DIR, "project.json"))][:6]


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


_MC_FALLBACK = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback"
_CUADRO = _W + "txbxContent"


def _texto_nodo(nodo):
    partes = []
    for hijo in nodo:
        e = hijo.tag
        # El texto de un cuadro de texto son párrafos aparte (los recoge `_parrafos_xml`); y Word
        # guarda cada cuadro dos veces, en formato nuevo y en el antiguo (Fallback).
        if e in _FUERA or e == _MC_FALLBACK or e == _CUADRO:
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


def _parrafos_xml(nodo, out):
    """Los párrafos de un documento de Word, en orden, cada uno una vez (UAT, 2-oct-2026: el texto de
    un cuadro de texto contaba cuatro veces: dentro del párrafo que lo ancla, como párrafo propio, y
    las dos otra vez en la copia de compatibilidad)."""
    for hijo in nodo:
        if hijo.tag == _MC_FALLBACK or hijo.tag in _FUERA:
            continue
        if hijo.tag == _W + "p":
            out.append(_texto_nodo(hijo).strip())
        _parrafos_xml(hijo, out)


def parrafos_de(ruta):
    """Los párrafos de un documento. En un .docx, el texto tal como queda ACEPTANDO los cambios
    pendientes: lo insertado cuenta y lo borrado no. Las notas al pie no se leen. Devuelve None si
    no se puede leer."""
    try:
        if ruta.lower().endswith(".docx"):
            with zipfile.ZipFile(ruta) as z:
                raiz = ET.fromstring(z.read("word/document.xml"))
            cuerpo = raiz.find(_W + "body")
            ps = []
            if cuerpo is not None:
                _parrafos_xml(cuerpo, ps)
        else:
            with open(ruta, "rb") as f:
                crudo = f.read()
            if crudo[:2] in (b"\xff\xfe", b"\xfe\xff"):       # el «Unicode» del Bloc de notas
                texto = crudo.decode("utf-16", errors="replace")
            else:
                try:
                    texto = crudo.decode("utf-8-sig")
                except UnicodeDecodeError:  # un .txt antiguo: con «replace» cada ñ partía una palabra
                    texto = crudo.decode("cp1252", errors="replace")
            ps = [p.strip() for p in re.split(r"\n\s*\n", texto)]
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

    def __init__(self, p, esperadas=None, archivadas=0, propias=0):
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
        if esperadas and any(n not in nombres for n in esperadas):
            self.integro = False            # falta el texto guardado de algo que el registro anotó
        # Y lo que la IA escribió y ya no está en ninguna instantánea (ver `guardar_instantanea`).
        en_archivo = en_archivo_h = 0
        self._archivo_h = []        # lo del autor que salió de algún documento: para `_cargar_h`
        try:
            with gzip.open(p.f_archivo_ia, "rt", encoding="utf-8") as f:
                for linea in f:
                    try:
                        x = json.loads(linea)
                        if "fs" in x:           # un tramo de párrafos del autor que salió de un documento
                            self.sumar(x["ps"], x["fs"])
                            en_archivo_h += sum(len(m) for m in x["fs"])
                            self._archivo_h.append((x["ps"], x["fs"]))
                            continue
                        self.sumar([x["p"]], [x["f"]], [x.get("h")] if x.get("h") else None)
                        en_archivo += x["f"].count("A")
                        if "A" not in x["f"]:
                            en_archivo_h += len(x["f"])
                            self._archivo_h.append(([x["p"]], [x["f"]]))
                    except Exception:
                        continue
        except Exception:
            pass
        if en_archivo < archivadas or en_archivo_h < propias:
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
        self._cargar_h()
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

    def _cargar_h(self):
        """Los tramos y párrafos del autor de todo lo guardado. Solo cuando hace falta: recorre todas
        las instantáneas."""
        if self._tejas_h is not None:
            return
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
        for ps_, fs_ in self._archivo_h:
            self.recordar_h(ps_, fs_)
        for p_, f_ in self._viejas_h:
            self.recordar_h(p_, f_)

    def del_autor(self, pars, marcas, racha=10):
        """Cuando escribe la IA: las palabras «N» que forman una racha de al menos `racha` palabras
        seguidas que YA eran del autor en algún texto guardado pasan a «H». Copiar no es generar.

        (UAT, 2-oct-2026.) El maquetador junta los capítulos en un solo fichero, con otros saltos de
        párrafo: ningún párrafo coincidía entero, las 49.638 palabras del libro salían «de la IA» y,
        peor, quedaban guardadas como texto de la IA: mover después un párrafo propio de un capítulo
        a otro lo contaba como generado. Un tramo que también conste como de la IA no vale."""
        m = "".join(marcas)
        if "N" * racha not in m:
            return marcas
        self._cargar_h()
        ws = [w for par in pars for w in palabras(par)]
        if len(ws) != len(m):
            return marcas
        cubierta = [False] * len(ws)
        for i in range(len(ws) - 4):
            k = hash(tuple(ws[i:i + 5]))
            if k in self._tejas_h and k not in self.tejas_ia:
                for j in range(5):
                    cubierta[i + j] = True
        plano, i = list(m), 0
        while i < len(plano):
            if plano[i] == "N" and cubierta[i]:
                j = i
                while j < len(plano) and plano[j] == "N" and cubierta[j]:
                    j += 1
                if j - i >= racha:
                    plano[i:j] = "H" * (j - i)
                i = j
            else:
                i += 1
        out, c = [], 0
        for x in marcas:
            out.append("".join(plano[c:c + len(x)]))
            c += len(x)
        return out

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
        self.f_marca = os.path.join(self.dir, "orden-en-curso.json")
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
        self.propias_archivadas = 0
        if vieja:
            # Lo que queda, con sus marcas nuevas: un párrafo que sigue pero pierde marcas de la IA
            # (una declaración «es mío») también se archiva como estaba: la declaración vale para
            # ese documento, no para ese texto en cualquier otro sitio.
            quedan = {}
            for x, m in zip(parrafos, marcas):
                h = _h_parrafo(palabras(x))
                quedan[h] = min(quedan.get(h, len(m)), m.count("A"))
            fuera, tramo = [], ([], [])

            def cierra_tramo():
                # Lo TUYO que sale, por tramos de párrafos seguidos: en un diálogo de líneas de cinco
                # palabras, lo que se reconoce después son los tramos que cruzan de una línea a otra.
                if sum(len(x) for x in tramo[1]) >= 5:
                    fuera.append(json.dumps({"ps": list(tramo[0]), "fs": list(tramo[1])}, ensure_ascii=False))
                    self.propias_archivadas += sum(len(x) for x in tramo[1])
                tramo[0].clear()
                tramo[1].clear()

            for par, m in zip(vieja["p"], vieja["f"]):
                h = _h_parrafo(palabras(par))
                if "A" in m:
                    cierra_tramo()
                    if h not in quedan or quedan[h] < m.count("A"):
                        fuera.append(json.dumps({"p": par, "f": m, "h": h}, ensure_ascii=False))
                        archivadas += m.count("A")
                elif h not in quedan and m:
                    # Sin eso, pedir una reescritura entera en el propio fichero y restaurar después
                    # tu original contaba como haberla revisado: 25 de 25 y HAS 100, más que un
                    # libro escrito a mano (equipo rojo, 2-oct-2026). El registro tiene que poder
                    # reconocer que ese texto ya era tuyo.
                    tramo[0].append(par)
                    tramo[1].append(m)
                else:
                    cierra_tramo()
            cierra_tramo()
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

    def en_archivo(self, letra="A"):
        """Palabras de la IA (o del autor, con «H») que hay en el archivo (0 si no está o no se lee)."""
        n = 0
        try:
            with gzip.open(self.f_archivo_ia, "rt", encoding="utf-8") as f:
                for linea in f:
                    try:
                        x = json.loads(linea)
                        if "fs" in x:           # un tramo de párrafos del autor
                            n += 0 if letra == "A" else sum(len(m) for m in x["fs"])
                        else:
                            m = x["f"]
                            n += m.count("A") if letra == "A" else (len(m) if "A" not in m else 0)
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


def de_salida(rel):
    """¿Está en una carpeta de entregables (lo que sale del maquetador o de la portada)? Eso no es el
    manuscrito ni una versión suya, se llame como se llame y salga de donde salga."""
    # Solo «output»: es donde escriben el maquetador y la portada. «Entregables», «export» o
    # «salida» puede ser donde un autor guarda su manuscrito (UAT, 2-oct: ahí la IA no contaba).
    return any(_plano(c) == "output" for c in rel.replace("\\", "/").split("/")[:-1])


def clasificar(rel):
    """El tipo de documento por su nombre, o None si no es de los que cuentan (informes, planes…)."""
    partes = rel.replace("\\", "/").split("/")
    nombre = _plano(os.path.splitext(partes[-1])[0])
    carpetas = [_plano(p) for p in partes[:-1]]
    if _NO_CUENTA.search(nombre) or de_salida(rel):
        return None
    if re.search(r"(^|[-_ ])guia[-_ ]de[-_ ]estilo|style[-_ ]guide", nombre):
        return "style_instructions"
    if re.match(r"\d+[-_ ]", nombre) and re.search(r"biblia|escaleta|premisa|sinopsis", nombre):
        return None             # «2 Biblias», «3 escaletas»: apuntes, no el documento
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
    if re.search(r"propuesta|cortes|descarte|apuntes|ideas|brainstorm|lluvia|versiones|comparacion", nombre):
        return None
    if (re.search(r"(^|[-_ ])(cap|capitulo|chapter|ch)[-_ ]?\d", nombre)
            or re.search(r"-m\d+-v\d+|-b\d+($|[-_ ])|-corregido|-humanizado", nombre)
            or re.search(r"(^|[-_ ])(prologo|epilogo|prefacio|introduccion|interludio)([-_ ]|\d|$)", nombre)
            or re.search(r"(^|[-_ ])escena[-_ ]?\d", nombre)
            or re.search(r"(^|[-_ ])parte([-_ ]|\d|$)", nombre)
            or re.match(r"\d{2,3}[-_. ]\D", nombre)
            or re.search(r"(^|[-_ ])(novela|novel|manuscrito|manuscript|borrador|draft)([-_ ]|\d|$)", nombre)
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
    ia_ya = False           # ¿ha trabajado ya la IA en este libro?
    al_abrir = {}           # lo que había al abrir el registro sin nombre de documento: {ruta: palabras}
    for ev in eventos:
        rel = ev.get("document")
        t = ev.get("event_type")
        if t in ("collaborator_run", "ai_wrote_untyped"):
            ia_ya = True
        for x in ev.get("seen") or []:
            al_abrir[x.get("document")] = x.get("words", 0)
            if x.get("sha"):
                al_abrir["sha256:" + x["sha"]] = x.get("words", 0)      # el mismo fichero, con otro nombre
        if not rel or t == "collaborator_run":
            continue
        if t == "document_removed":
            if rel in docs:
                docs[rel]["existe"] = False
            continue
        if t == "baseline_declared" and ev.get("hierarchical_level") is None:
            continue            # el manuscrito previo declarado como CARPETA de capítulos: no es un documento
        nuevo = rel not in docs
        d = docs.setdefault(rel, {"existe": True, "relevado_por": None, "antes_ia": 0, "tras_ia": 0})
        if nuevo and ev.get("supersedes") in docs:
            d["antes_ia"] = docs[ev["supersedes"]]["antes_ia"]      # una copia entera hereda la edad del original
            d["tras_ia"] = docs[ev["supersedes"]]["tras_ia"]
        if nuevo and (rel in al_abrir or ev.get("document_hash") in al_abrir):
            # Entra ahora en el registro como documento, pero ya estaba al abrirlo, con ese tamaño
            # (también si se le ha cambiado el nombre para que se reconozca).
            d["antes_ia"] = al_abrir.get(rel) or al_abrir[ev.get("document_hash")]
        elif ia_ya and t in ESCRITURAS:
            # Lo que el autor escribe en él después de que la IA trabajase en el libro: no es previo,
            # esté en el fichero que esté (equipo rojo, 2-oct: copiar un capítulo, reescribirlo entero
            # y declararlo; así, sin tope).
            d["tras_ia"] += ev.get("tokens_revised_by_human", 0) or 0
        if d["relevado_por"] and t in ESCRITURAS and (
                ev.get("tokens_revised_by_human") or ev.get("tokens_generated")
                or ev.get("words", 0) != d.get("palabras") or not d["existe"]):
            # (Con palabras que cambian: tocar una coma o volver a guardar no deja atrás la otra versión.)
            # Se ha vuelto a escribir en una versión que ya tenía relevo: el autor sigue en ella (ignoró
            # la corregida, o la borró y volvió a su Word de siempre). Vuelve a ser la que cuenta, y la
            # que la relevó pasa a ser la de atrás (UAT, 2-oct-2026: el manuscrito dejaba de contar
            # para siempre y lo que la IA escribiera después en él no movía el HAS).
            fin = _cabeza_de(rel, docs)
            d["relevado_por"] = None
            if fin != rel:
                docs[fin]["relevado_por"] = rel
                d["retoma"] = {"de": fin, "seq": ev.get("seq")}
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
            # ¿Ha escrito aquí la IA de forma MEDIDA (un colaborador con su sesión)? Lo hereda de su origen.
            "ia_medida": bool(d.get("ia_medida") or (t == "text_generated" and ev.get("attribution") == "medido")
                              or ev.get("ai_words_pasted_by_author")
                              or (ev.get("source") and docs.get(ev["source"], {}).get("ia_medida"))),
            "pegadas": ev.get("ai_words_pasted_by_author", 0),
            "motivo": ev.get("uncertain_reason"),
        })
        if ev.get("supersedes") and ev["supersedes"] in docs and ev["supersedes"] != rel:
            docs[ev["supersedes"]]["relevado_por"] = rel
        for x in ev.get("releases") or []:
            # Este documento ya no lleva el texto de aquel al que relevaba (era una copia para
            # empezar otro capítulo, y se ha reescrito): el otro vuelve a contar por sí mismo.
            if x in docs and docs[x]["relevado_por"] == rel:
                docs[x]["relevado_por"] = None
        if ev.get("behind") in docs and ev["behind"] != rel:
            d["relevado_por"] = ev["behind"]        # copia de una versión de atrás: se queda atrás con ella
        if t == "text_generated":
            ia_ya = True
        if not ia_ya:
            d["antes_ia"] = d["palabras"]       # lo que tenía antes de que la IA trabajase en el libro
    return docs


ESCRITURAS = ("document_created", "text_generated", "text_revised")


def _relevo_vivo(rel, docs):
    """La versión posterior de un documento que sigue en la carpeta, o None. Una versión que se borra
    deja de relevar a la anterior: si borras la corregida, vuelve a contar tu original."""
    vistos = set()
    r = docs.get(rel, {}).get("relevado_por")
    while r and r not in vistos:
        if docs.get(r, {}).get("existe"):
            return r
        vistos.add(r)
        r = docs.get(r, {}).get("relevado_por")
    return None


def cabeza_viva(rel, docs):
    """La versión de este documento que cuenta hoy (él mismo, si no tiene otra posterior en la carpeta)."""
    sig = _relevo_vivo(rel, docs)
    while sig:
        rel, sig = sig, _relevo_vivo(sig, docs)
    return rel


def previos_a_declarar(docs):
    """Los manuscritos que se pueden declarar como previos, uno por cada documento que cuenta: él
    mismo si vale, o su versión anterior más reciente que valga (el original, cuando la que cuenta
    es la corregida por la IA) (UAT, 2-oct: HAS 1,28 tras el primer colaborador y ni una pista)."""
    out = []
    for cab, dc in sorted(cabezas(docs).items()):
        if dc["tipo"] != "draft":
            continue
        if previo_posible(dc) and dc["humanas"] == dc["palabras"]:
            out.append(cab)
            continue
        # Mejor el original entero tuyo que la versión en la que ya ha escrito la IA.
        atras = [r for r, d in docs.items() if d["existe"] and d.get("tipo") == "draft" and r != cab
                 and cabeza_viva(r, docs) == cab and previo_posible(d) and d["humanas"] == d["palabras"]]
        if atras:
            out.append(max(atras, key=lambda r: (docs[r]["cuando"] or "", r)))
        elif previo_posible(dc):
            out.append(cab)
    return out


def dejadas_atras(docs):
    """Versiones que siguen en la carpeta, no cuentan porque hay otra posterior, y tienen MÁS texto de
    la IA que la que cuenta. Es lo que pasa cuando el autor deja la versión de la IA y vuelve a la
    suya: es su derecho, y tiene que verse en el informe y en el certificado."""
    out = []
    for rel, d in sorted(docs.items()):
        if not d["existe"] or not d.get("nivel"):
            continue
        cab = None
        sig = _relevo_vivo(rel, docs)
        while sig:
            cab, sig = sig, _relevo_vivo(sig, docs)
        ia = d["palabras"] - d["humanas"]
        if cab and ia > docs[cab]["palabras"] - docs[cab]["humanas"]:
            out.append({"document": rel, "palabras": d["palabras"], "palabras_ia": ia, "cuenta": cab})
    return out


def cabezas(docs):
    """Los documentos que cuentan: los que existen y no tienen una versión posterior en la carpeta."""
    return {r: d for r, d in docs.items() if d["existe"] and d.get("nivel") and not _relevo_vivo(r, docs)}


def previo_posible(d):
    """¿Puede declararse como manuscrito previo? Lo que ya estaba antes de que la IA trabajase en el
    libro. Vale por las palabras del autor que tenía entonces (`previas_de`): lo que ha crecido
    después y lo que la IA haya escrito en él no son previos, y lo que nació después tampoco.

    (UAT, 2-oct-2026.) Antes se exigía que no tuviera ni una palabra de la IA: quien no declaraba al
    abrir y dejaba que la IA añadiese un párrafo se quedaba sin poder declarar su novela, salvo
    declarando suyas las palabras de la IA."""
    return d["palabras"] > 0 and previas_de(d) >= MIN_PREVIO


def palabras_previas(n, antes):
    """Cuántas palabras de un manuscrito cuentan como previas: todas, si no ha crecido más que el
    margen desde que trabaja la IA; si ha crecido más, las que tenía entonces."""
    return n if n <= MARGEN_PREVIO * antes + 100 else antes


def previas_de(d):
    """Las palabras previas de un documento del registro: las que ya tenía antes de la IA, y nunca
    más de las que no se le han visto escribir después."""
    return max(0, min(palabras_previas(d["palabras"], d.get("antes_ia", 0)), d["palabras"] - d.get("tras_ia", 0),
                      d["humanas"]))


def primera_ia(eventos):
    """Cuándo trabajó la IA por primera vez en este libro (segundos), o None si todavía no."""
    for ev in eventos:
        if ev.get("event_type") in ("collaborator_run", "ai_wrote_untyped", "text_generated"):
            return epoca(ev.get("timestamp") or "")
    return None


def previo_suelto(p, eventos, rel, n):
    """Lo mismo que `previo_posible`, para un fichero que no está en el registro como documento (su
    nombre no dice qué es): vale si ya estaba, con ese tamaño, al abrir el registro; o si se guardó
    por última vez antes de que la IA trabajase en el libro. Devuelve (por qué vale, cuántas de sus
    palabras son previas), o (None, 0)."""
    for ev in eventos:
        for x in ev.get("seen") or []:
            if x.get("document") == rel:
                w0 = x.get("words", 0)
                return ("visto al abrir el registro", palabras_previas(n, w0)) if w0 >= MIN_PREVIO else (None, 0)
    cuando = primera_ia(eventos)
    if cuando is None:
        return "la IA aún no había trabajado en el libro", n
    try:
        # Es lo único que hay, y vale lo que vale una fecha: por eso se anota y el certificado lo dice.
        return ("la fecha del fichero", n) if os.stat(os.path.join(p.raiz, rel)).st_mtime < cuando else (None, 0)
    except OSError:
        return None, 0


def candidatos(p, docs, minimo=3000, cuantos=4):
    """Ficheros de la carpeta que por tamaño podrían ser el manuscrito y que el registro no cuenta
    porque su nombre no dice qué son: [(ruta, palabras)]. No entran los informes ni lo que escribió la IA."""
    out, mirados = [], 0
    for rel, (tam, _) in sorted(ficheros(p.raiz).items(), key=lambda kv: (-kv[1][0], kv[0])):
        if tam < 8000 or mirados >= 12 or len(out) >= cuantos:
            break
        if rel in docs or _NO_CUENTA.search(_plano(os.path.splitext(os.path.basename(rel))[0])) or de_salida(rel):
            continue
        s_ = p.instantanea(rel)
        if s_ and "".join(s_["f"]).count("A") * 2 > sum(len(m) for m in s_["f"]):
            continue                    # lo ha escrito sobre todo la IA: no es tu manuscrito
        mirados += 1
        n = sum(len(palabras(x)) for x in parrafos_de(os.path.join(p.raiz, rel)) or [])
        if n >= minimo:
            out.append((rel, n))
    return out


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
    # Lo que acredita la concepción es el manuscrito PREVIO: si se declararon 150 palabras, escribir
    # 4.000 después (con la biblia de la IA delante) no las convierte en un manuscrito previo de
    # 4.000 (equipo rojo, 2-oct-2026). La segunda condición sí mira el texto de hoy.
    previo = min(hum, MARGEN_PREVIO * declaradas + 100) if declaradas else hum
    return min(1.0, previo / minimo) * min(1.0, 2 * hum / total)


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
    # Los diez minutos solo valen para un aviso que el gancho no pudo anotar (registro ocupado).
    # Antes valían tras CUALQUIER escritura de la IA fuera de sesión, para cubrir lo que escribiera
    # después con un guion; desde que cada orden lleva sus ganchos de antes y después sobraba, y al
    # autor le costaba diez minutos de autoría cada vez que la IA tocaba el libro (UAT, 2-oct-2026).
    v = [(x.get("mtime", 0) - 60, x.get("mtime", 0) + TRAS_ESCRITO,
          "cambió justo después de que la IA escribiera en la carpeta") for x in pendientes(p)]
    for ev in eventos:
        if ev.get("event_type") == "collaborator_run":
            v.append((ev.get("opened") or 0, (ev.get("closed") or 0) + GRACIA_CIERRE,
                      "cambió mientras trabajaba un colaborador, o justo después"))
    if sesion and sesion.get("abierta"):
        v.append((sesion["abierta"], float("inf"), "un colaborador no cerró su sesión"))
    marca = _leer_json(p.f_marca) or {}
    if marca.get("antes"):
        # Una orden de la IA empezó y nadie anotó su final (se interrumpió, falló o el gancho no
        # llegó): lo que cambió desde entonces no se sabe de quién es (equipo rojo, 2-oct-2026).
        # Media hora como mucho (lo mismo que se le da a una orden para terminar): sin tope, un Stop
        # a las diez convertía en «sin atribuir» todo lo que el autor escribiera esa tarde.
        v.append((marca["antes"] - 5, marca["antes"] + 1800, "cambió mientras la IA ejecutaba una orden que no terminó"))
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
        # Con una palabra de cada cinco cambiada no queda casi ningún tramo de cinco igual, y la
        # reescritura salía entera «de la IA» con su original contando al lado (UAT, 2-oct-2026:
        # «pásalo a presente»). Entre ficheros que se llaman como versiones de lo mismo se compara
        # por palabras largas: una reescritura conserva la mayoría; otro capítulo, no.
        largas = [w for w in nuevas if len(w) >= 5]
        if len(largas) >= 30:
            cuenta = {}
            for w in largas:
                cuenta[w] = cuenta.get(w, 0) + 1
            for r in sorted(docs):
                if r == rel or not docs[r].get("nivel") or not misma_familia(rel, r):
                    continue
                s_ = p.instantanea(r)
                suyas_ = [w for par in s_["p"] for w in palabras(par)] if s_ else []
                if not suyas_ or not 0.5 <= len(nuevas) / len(suyas_) <= 2:
                    continue
                quedan, comunes = dict(cuenta), 0
                for w in suyas_:
                    if len(w) >= 5 and quedan.get(w, 0) > 0:
                        quedan[w] -= 1
                        comunes += 1
                parte = comunes / len(largas)
                if parte >= 0.5 and (mejor is None or parte > mejor[1]):
                    mejor = (r, parte, len(suyas_))
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
    # El manuscrito es todo el texto vivo del libro que tiene algo del autor: una novela en un
    # fichero o una carpeta de capítulos.
    snap = {"p": []}
    for r_, d_ in sorted(cabezas(docs).items()):
        if d_["nivel"] == 7 and d_["humanas"] > 0:
            s_ = p.instantanea(r_)
            if s_:
                # Solo los párrafos que son sobre todo del autor: una palabra suya en un capítulo de
                # la IA no convierte ese capítulo en «su manuscrito».
                snap["p"].extend(par for par, m in zip(s_["p"], s_["f"]) if m.count("H") * 2 > len(m))
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


def _origen_sin_registrar(p, rel, nuevas, en_disco, docs, antes, anotadas=()):
    """El fichero del autor del que sale uno nuevo, cuando ese fichero no está en el registro porque
    su nombre no dice qué es: (ruta, párrafos) o None.

    (UAT con libros reales, 2-oct-2026.) Un manuscrito llamado «EL-ESCRUTINIO-final.docx» no se
    reconocía; pasaba el corrector, escribía «…-final-corregido.docx» y, como el original no
    constaba, la novela entera salía «0 % tuyo». Solo vale un fichero que ya estaba a la vista antes
    de esta pasada y en el que la IA no ha escrito nunca (no tiene texto guardado)."""
    if len(nuevas) < 200:
        return None
    tejas = _tejas(nuevas)
    raiz_nombre = _plano(os.path.splitext(os.path.basename(rel))[0])[:6]
    # «No tiene texto guardado» no basta: si el registro anotó una huella para ese fichero, es que la
    # IA escribió en él, aunque alguien haya borrado después el texto guardado.
    # Vale también el que se guardó al abrir el registro (por tamaño podía ser el manuscrito),
    # mientras su texto guardado siga siendo aquel: nadie ha escrito en él desde entonces.
    anotadas = dict(anotadas) if anotadas else {}
    vistas = {x["document"]: x.get("snapshot_hash") for e in p.eventos() for x in e.get("seen") or []}

    def libre(r):
        s = p.instantanea(r)
        if s is None:
            return r not in anotadas
        return bool(vistas.get(r)) and anotadas.get(r) == vistas[r] and p.huella_texto(s["p"], s["f"]) == vistas[r]

    cands = [r for r in en_disco if r != rel and r not in docs and r in antes and en_disco[r][0] > 1500 and libre(r)]
    cands.sort(key=lambda r: (not _plano(os.path.basename(r)).startswith(raiz_nombre), r))
    mejor = None
    for r in cands[:40]:
        pars = parrafos_de(os.path.join(p.raiz, r))
        if not pars:
            continue
        suyas = _tejas([w for par in pars for w in palabras(par)])
        parte = len(tejas & suyas) / len(tejas) if tejas else 0
        if parte >= UMBRAL_FUENTE and (mejor is None or parte > mejor[2]):
            mejor = (r, pars, parte)
            if parte >= 0.8:
                break
    return mejor[:2] if mejor else None


def mirar(p, quien, colab=None, atribucion="medido", modelo=None, motivo=None, hasta=None, solo=None,
          desde=None, fuera=False):
    """Compara la carpeta con lo último que se vio y anota los cambios como de `quien` ("H" o "A").

    Cuando `quien` es "H", lo que se escribió mientras trabajaba un colaborador no es tuyo aunque
    aparezca ahora: va como de la IA, «incierto». Devuelve (lo anotado, los ficheros sin tipo).
    """
    evs = p.eventos()
    docs = documentos(evs)
    cache = _leer_json(p.f_cache, {}) or {}
    vistos = cache.get("ficheros", {})
    antes = set(vistos)             # lo que ya estaba a la vista antes de esta pasada
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
        if desde is not None and mt < desde:
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
    anotadas = huellas_anotadas(p) if cambiados else {}
    if cambiados:
        indice = Indice(p, {os.path.basename(p._f_texto(r)): h for r, h in anotadas.items()},
                        sum(e.get("ai_words_archived", 0) for e in evs),
                        sum(e.get("own_words_archived", 0) for e in evs))
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
        por_rato = False            # ¿la duda viene solo de CUÁNDO se guardó?
        if quien == "H" and not indice.integro:
            # Falta parte de lo que el registro guarda para reconocer el texto de la IA, o está
            # manipulado: no se le puede acreditar nada nuevo al autor.
            de_quien, como, por_que = "A", "incierto", "al registro le falta parte de lo que guarda, o está manipulado"
        elif quien == "H" and rel in sin_anotar:
            de_quien, como, por_que = "A", "incierto", "la IA escribió en este fichero y no se pudo anotar en el momento"
        elif quien == "H":
            en = next((m_ for a_, b_, m_ in ventanas if a_ <= mt <= b_), None)
            if en:
                de_quien, como, por_que, por_rato = "A", "incierto", en, True

        snap = p.instantanea(rel)
        if snap is None and not conocido and indice.integro and not de_salida(rel):
            # ¿Es una copia idéntica de un documento del registro (un cambio de nombre, un duplicado
            # del Finder)? No ha cambiado ni una palabra: hereda lo que era, sin dudas nuevas, la haga
            # quien la haga y cuando la haga (UAT, 2-oct: renombrar la corregida al rato daba ⚠️).
            gemelo = next((r for r in sorted(docs) if r != rel and docs[r].get("nivel") and docs[r]["sha"] == sha), None)
            sg = p.instantanea(gemelo) if gemelo else None
            if sg and sg.get("p") == pars and p.huella_texto(sg["p"], sg.get("f", [])) == docs[gemelo].get("huella_texto"):
                g = docs[gemelo]
                tipo_g = clasificar(rel) or g["tipo"]
                marcas = list(sg["f"])
                junto = "".join(marcas)
                cabeza = _cabeza_de(gemelo, docs)
                # La copia de una versión que ya tiene otra posterior no la releva: se queda atrás
                # con su original (equipo rojo, 2-oct: un `cp` del original dejaba fuera de la cuenta
                # la versión corregida por la IA sin haber escrito ni una palabra).
                detras = _relevo_vivo(gemelo, docs)
                archivadas, huella = p.guardar_instantanea(rel, pars, marcas)
                indice.sumar(pars, marcas)
                nivel_g = NIVEL_DE[tipo_g]
                ratio_g = r2(junto.count("H") / len(junto)) if junto else 1
                anotado.append(p.anotar(
                    event_type="document_copied", document=rel, document_type=tipo_g, hierarchical_level=nivel_g,
                    document_hash="sha256:" + sha, words=len(junto), human_words=junto.count("H"),
                    ai_words_introduced=g["ia_intro"], tokens_generated=0, tokens_revised_by_human=0,
                    revision_ratio=ratio_g, has_contribution=r2(PUNTOS[nivel_g] * ratio_g),
                    attribution=g["atribucion"], uncertain_reason=g.get("motivo") if g["atribucion"] == "incierto" else None,
                    ai_words_archived=archivadas or None, snapshot_hash=huella,
                    ai_words_pasted_by_author=g["pegadas"] or None, source=gemelo,
                    supersedes=cabeza if not detras and cabeza != rel and docs[cabeza]["tipo"] == tipo_g else None,
                    behind=detras, derived_from_baseline=g["de_base"],
                    description=f"Copia idéntica de «{gemelo}» (un cambio de nombre o un duplicado)"))
                tejas_de.pop(rel, None)
                vistos[rel] = [tam, mt, sha]
                docs = documentos(p.eventos())
                continue
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
                tipo = tipo or (None if de_salida(rel) else docs[fuente]["tipo"])
                cabeza = _cabeza_de(fuente, docs)
                # Lo que escribe la IA releva al original con el 60 %: una reescritura acorta. Lo que
                # hace el autor, también si se llama como una versión suya («novela v2»: una versión
                # recortada es una versión); con otro nombre, solo si lo trae casi entero: sacar un
                # capítulo a un fichero aparte no deja atrás el manuscrito (UAT, 2-oct).
                # (Y vale igual para la IA: el fantasma que continúa una escena en «cap-03» con media
                # página de «cap-02» no deja tu capítulo 2 fuera de la cuenta — equipo rojo, 2-oct.)
                version = misma_familia(rel, fuente) or misma_familia(rel, cabeza)
                if not version and fuente in tejas_de and tejas_de[fuente][0]:
                    # Medido por lo que queda del original, no por el tamaño: un capítulo nuevo tan
                    # largo como el anterior y con un tercio de su texto no es su versión siguiente.
                    queda = len(_tejas(nuevas) & tejas_de[fuente][0]) / len(tejas_de[fuente][0])
                else:
                    queda = 1
                if tipo and cabeza != rel and docs[cabeza]["tipo"] == tipo and n_viejas and queda >= 0.75 \
                        and len(nuevas) >= (COBERTURA_RELEVO if version else COBERTURA_COPIA) * n_viejas:
                    releva = cabeza
                    ia_intro_ant = docs[fuente]["ia_intro"]
                    pegadas_ant = docs[fuente]["pegadas"]
            elif de_quien == "A" and tipo and indice.integro:
                suelta = _origen_sin_registrar(p, rel, nuevas, en_disco, docs, antes, anotadas)
                if suelta:
                    # Sale de un fichero del autor que el registro no tenía por documento: se anota
                    # ahora como suyo, y este nuevo es su versión siguiente.
                    fuente, pars_f = suelta
                    # No se da por del autor sin más: si ese texto ya consta como de la IA (un
                    # fichero suyo al que se le cambió el nombre, o texto que solo queda en el
                    # archivo), lo sigue siendo (equipo rojo, 2-oct-2026).
                    marcas_f, _ = indice.heredar(pars_f, ["N" * len(palabras(x)) for x in pars_f],
                                                 cambia_el_autor=True)
                    marcas_f = [m.replace("N", "H") for m in marcas_f]
                    n_f = sum(len(m) for m in marcas_f)
                    h_f = "".join(marcas_f).count("H")
                    sha_f = _sha_fichero(os.path.join(p.raiz, fuente))
                    _, huella_f = p.guardar_instantanea(fuente, pars_f, marcas_f)
                    indice.sumar(pars_f, marcas_f)
                    # Es un manuscrito, sea lo que sea lo que la IA saca de él: una biblia que cita
                    # cinco párrafos de la novela no convierte la novela en «biblia» (UAT, 2-oct).
                    tipo_o = clasificar(fuente) or "draft"
                    anotado.append(p.anotar(
                        event_type="document_created", document=fuente, document_type=tipo_o,
                        hierarchical_level=NIVEL_DE[tipo_o], document_hash="sha256:" + sha_f, words=n_f,
                        human_words=h_f, ai_words_introduced=n_f - h_f, tokens_generated=0,
                        tokens_revised_by_human=h_f, ai_words_pasted_by_author=(n_f - h_f) or None,
                        revision_ratio=r2(h_f / n_f) if n_f else 1,
                        has_contribution=r2(PUNTOS[NIVEL_DE[tipo_o]] * (h_f / n_f if n_f else 1)), attribution="medido",
                        snapshot_hash=huella_f, found_in_folder=True,
                        description=f"Estaba en la carpeta sin que su nombre dijera qué era; de él sale «{rel}»"))
                    vistos[fuente] = [en_disco[fuente][0], en_disco[fuente][1], sha_f]
                    docs = documentos(p.eventos())
                    snap = p.instantanea(fuente)
                    if tipo == tipo_o and len(nuevas) >= (COBERTURA_RELEVO if misma_familia(rel, fuente) else COBERTURA_COPIA) * n_f:
                        releva = fuente

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
        if de_quien == "A" and indice.integro:
            marcas_n = indice.del_autor(pars, marcas_n)       # lo que la IA copia de ti sigue siendo tuyo
        junto = "".join(marcas_n)
        nuevas_n, her_h = junto.count("N"), junto.count("H")
        if por_rato and nuevas_n == 0:
            # No hay ni una palabra nueva: no hay nada que atribuir, cayera el guardado en el rato que
            # cayera (UAT, 2-oct: renombrar la corregida con el nombre del original daba ⚠️).
            de_quien, como, por_que = quien, atribucion, motivo
        marcas = [m.replace("N", de_quien) for m in marcas_n]
        total = len(junto)

        if not tipo:
            # Sin tipo no cuenta para el HAS, pero lo que escribe la IA se guarda igual: si mañana
            # reaparece con nombre de capítulo, se le reconoce (equipo rojo, 1-oct).
            suya = None
            if de_quien == "A" or (atribucion == "preexistente" and len(nuevas) >= 1000):
                # También lo que ya estaba al abrir el registro y por tamaño puede ser el manuscrito:
                # si la IA escribe después en él, hay con qué comparar y solo cuenta suyo lo que añade
                # (UAT, 2-oct: una novela con nombre no reconocido quedaba entera «de la IA» por 162
                # palabras, y sin salida).
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
            ia_quitada = max(a_antes - ia_vivas, 0)
            # El texto de la IA que el propio autor trajo aquí pegándolo no cuenta al quitarlo: lo que
            # se revisa es lo que la IA escribió, no lo que uno pega y despega.
            descuento = min(ia_quitada, pegadas_ant)
            ia_quitada -= descuento
            pegadas = pegadas_ant - descuento + a_indice
            # Lo tuyo que cuenta como sustitución: las palabras NUEVAS de verdad, y las que devuelves
            # a como estaban dentro de un párrafo que sigue siendo el mismo (rechazar un cambio del
            # corrector). Un párrafo entero copiado de otro documento tuyo NO: el registro sabe que
            # no es nuevo (equipo rojo, 1-oct: sustituir un capítulo de la IA por párrafos copiados
            # de la novela daba 22 puntos de revisión).
            # Y de las nuevas, las que no lo son: tramos que ya eran tuyos en otro texto guardado.
            # Dentro de un párrafo que sigue en su sitio es devolver tu texto (cuenta); en un párrafo
            # traído entero de otra parte es copiar (no cuenta).
            ya_tuyas = indice.conocidas_del_autor(pars, marcas_n) if ia_quitada and nuevas_n else None
            devueltas = copiadas = c_ = 0
            for antes_, ahora_ in zip(en_sitio, marcas_n):
                en_su_sitio = bool(antes_) and (len(antes_) - antes_.count("N")) * 2 >= len(antes_)
                for k, (x, y) in enumerate(zip(antes_, ahora_)):
                    if en_su_sitio and x == "N" and y == "H":
                        devueltas += 1
                    elif not en_su_sitio and y == "N" and ya_tuyas and ya_tuyas[c_ + k]:
                        copiadas += 1
                c_ += len(ahora_)
            sustituidas = min(ia_quitada, max(nuevas_n - copiadas, 0) + devueltas)
            borradas = ia_quitada - sustituidas
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
        # ¿Releva este documento a otro cuyo texto ya no lleva? (Se copió un capítulo para empezar
        # el siguiente y se ha reescrito.) Lo suelta. Entre versiones con el mismo nombre no: la
        # nueva versión de una novela releva a la anterior aunque no se le parezca.
        sueltos_, mias_ = [], None
        if conocido:
            for x, dx in docs.items():
                if dx["relevado_por"] == rel and dx["existe"] and x != rel and not misma_familia(x, rel):
                    if x not in tejas_de:
                        sx = p.instantanea(x)
                        vx = [w for par in sx["p"] for w in palabras(par)] if sx else []
                        tejas_de[x] = (_tejas(vx), len(vx))
                    mias_ = _tejas(nuevas) if mias_ is None else mias_
                    if tejas_de[x][0] and len(tejas_de[x][0] & mias_) / len(tejas_de[x][0]) < UMBRAL_FUENTE:
                        sueltos_.append(x)
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
            ai_words_archived=archivadas or None, own_words_archived=p.propias_archivadas or None,
            snapshot_hash=huella,
            ai_words_pasted_by_author=pegadas or None,
            # Fuera de sesión (lo avisó el gancho, ahora o en un aviso que quedó apuntado): los diez
            # minutos de después cuentan desde aquí.
            outside_session=True if (solo is not None or fuera or rel in sin_anotar) else None,
            file_mtime=(mt if (solo is not None or fuera) else
                        max((x.get("mtime", 0) for x in leidos if x.get("document") == rel), default=mt)
                        if rel in sin_anotar else None),
            uncertain_reason=por_que if como == "incierto" else None,
            source=fuente, supersedes=releva, derived_from_baseline=de_base, releases=sueltos_ or None)
        tejas_de.pop(rel, None)
        vistos[rel] = [tam, mt, sha]
        docs = documentos(p.eventos())
        anotado.append(ev)

    # Lo que ya no está. Su texto se queda en .awap/local/textos: si reaparece copiado en otro fichero,
    # se le reconoce.
    for rel, d in list(docs.items()):
        if d["existe"] and rel not in en_disco and hasta is None and solo is None and desde is None:
            # Si lo retira un colaborador, su texto de la IA sale de la cuenta. Si lo borra el autor,
            # no: borrar no es revisar.
            de_ia = (d["palabras"] - d["humanas"]) if not _relevo_vivo(rel, docs) else 0
            anotado.append(p.anotar(event_type="document_removed", document=rel,
                                    document_type=d["tipo"], hierarchical_level=d["nivel"],
                                    ai_words_removed_by_ai=de_ia if quien == "A" and de_ia else None,
                                    ai_words_deleted_by_human=de_ia if quien != "A" and de_ia else None))
            vistos.pop(rel, None)
    if hasta is None and solo is None and desde is None:
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
    # (Lo que se guarda al abrir el registro no lo ha escrito la IA: su huella va en `seen_at_start`.)
    sueltas = [o for o in otros if o.get("snapshot_hash")]
    if sueltas and atribucion != "preexistente" and (quien == "H" or solo is not None or fuera):
        p.anotar(event_type="ai_wrote_untyped", collaborator=colab, produced=sueltas)

    cache["ficheros"] = vistos
    os.makedirs(p.dir, exist_ok=True)
    _guardar_json(p.f_cache, cache)
    return anotado, otros


def _quitar(ruta):
    try:
        os.remove(ruta)
    except OSError:
        pass


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
    if s and s.get("abierta") and _sesion_viva(p):
        # Hay un colaborador trabajando ahora mismo: lo que está cambiando es suyo y lo anotará su
        # cierre. Mirar el registro no le cierra la sesión (UAT, 2-oct-2026: preguntar por el HAS a
        # mitad de un coach dejaba su biblia «sin atribuir» y el resto «fuera de un colaborador»).
        return "trabajando"
    if s and s.get("abierta"):
        anotado, otros = mirar(p, "A", atribucion="incierto",
                               motivo="un colaborador no cerró su sesión")
        p.anotar(event_type="collaborator_run", collaborator="(sesión sin cerrar)", unclosed=True,
                 opened=s["abierta"], closed=ahora(), produced=_producido(anotado, otros))
        p.cerrar_sesion()
        _quitar(p.f_marca)
        return
    mirar(p, "H")          # con una orden de la IA a medias, `_ventanas` aparta lo de su rato
    _quitar(p.f_marca)


# ───────────────────────────── órdenes ─────────────────────────────

_ESPERA = ("Hay un colaborador de HumanInk con el trabajo abierto en este libro: lo que está escribiendo todavía no está "
           "anotado. Espera a que termine y repite. Si no hay ninguno (la conversación se cortó, o se quedó esperando "
           "tu respuesta), se da por terminado cuando lleve 45 minutos sin trabajar; pasado ese plazo, pide el estado: "
           "todo lo que haya cambiado en el libro hasta ese momento contará como de la IA, sin atribuir, y lo que "
           "escribas a partir de ahí volverá a ser tuyo.")

def _proyecto(ruta, exigir=True):
    raiz = raiz_de(ruta)
    if raiz:
        apuntar_libro(raiz)
    if not raiz:
        if exigir and not os.path.exists(os.path.abspath(os.path.expanduser(ruta or "."))):
            sys.exit(f"No veo la carpeta «{ruta}» desde aquí. En Cowork, conecta la carpeta del libro a la "
                     "conversación y vuelve a intentarlo.")
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
        print(f"El registro de «{p.datos.get('title', '')}» ya existía (desde el {fecha(p.datos.get('created_at', ''))}). "
              "No se ha tocado.")
        return cmd_estado(a)
    try:
        os.makedirs(p.dir, exist_ok=True)
    except OSError as e:
        sys.exit(f"No puedo escribir en «{carpeta}» ({e.strerror or e}). Mira que la carpeta esté conectada a la "
                 "conversación con permiso de escritura.")
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
        anotado, sueltos = mirar(p, "H", atribucion="preexistente")
        # Lo que había en la carpeta sin nombre de documento, con su tamaño: si mañana resulta ser el
        # manuscrito, consta que ya estaba al abrir el registro.
        grandes = sorted((o for o in sueltos if o["words"] >= 1000), key=lambda o: -o["words"])[:40]
        if grandes:
            p.anotar(event_type="seen_at_start",
                     seen=[{"document": o["document"], "words": o["words"], "sha": o.get("sha"),
                            "snapshot_hash": o.get("snapshot_hash")} for o in grandes],
                     description="Ficheros que ya estaban en la carpeta y cuyo nombre no dice qué son")
    finally:
        p.abrir_paso()
    apuntar_libro(carpeta)
    orden = f'/humanink:auditor "{carpeta}"'
    print(f"Registro de autoría abierto para «{p.datos['title']}»"
          + (f", de {p.datos['author']}" if p.datos["author"] else "") + ".")
    if anotado:
        print(f"\nDocumentos que ya estaban en la carpeta ({len(anotado)}). Entran como tuyos, por declaración:")
        for ev in anotado:
            print(f"  · {ev['document']}  ({NOMBRE_TIPO.get(ev['document_type'], ev['document_type'])}, "
                  f"{ev['words']} palabras)")
        print(f"\nSi alguno lo generó una IA, hay que decirlo:  {orden} --ai \"<fichero>\"")
    hay_manuscrito = any(ev.get("document_type") == "draft" for ev in anotado)
    largos = sorted((o for o in sueltos if o["words"] >= 3000), key=lambda o: -o["words"])[:6]
    ilegibles = _ilegibles(carpeta)
    if ilegibles:
        print("\nVeo estos ficheros, pero no los sé leer: " + ", ".join(ilegibles[:6]) + ". Si alguno es tu "
              "manuscrito, ábrelo y guárdalo como .docx: el registro solo lee Word (.docx) y texto (.md, .txt).")
    if not hay_manuscrito and largos:
        # (UAT, 2-oct-2026.) Un manuscrito llamado como la novela no se reconoce por el nombre, y
        # antes solo se decía «no he encontrado nada con esos nombres», sin decir qué nombres.
        print("\nNo he reconocido cuál es tu manuscrito por el nombre del fichero (reconozco «novela», "
              "«manuscrito», «borrador», «capítulo 3», «cap-07», una carpeta «capitulos»…).")
        print("Por tamaño, podría ser uno de estos:")
        for o in largos:
            print(f"  · {o['document']}  ({o['words']} palabras)")
    elif not hay_manuscrito:
        print("\nNo hay todavía un manuscrito en la carpeta. Si lo vas a escribir desde aquí, no hay nada que declarar.")
    if hay_manuscrito or largos:
        print("\nSi el manuscrito lo escribiste tú antes de usar HumanInk, decláralo: es lo que acredita la "
              f"concepción del libro.\n  {orden} --base \"<fichero, o la carpeta de capítulos>\"")
    print("\nA partir de ahora, lo que escriba cada colaborador de HumanInk en esta carpeta se anota solo, "
          "y lo que cambies tú entre uno y otro, también.")
    print("Una cosa que sí conviene recordar: mientras un colaborador o la IA están trabajando en esta conversación "
          "(en el libro o en otra cosa), y un par de minutos después, no guardes cambios tuyos en los ficheros del "
          "libro. Contarían como de la IA. Con los colaboradores que conversan contigo (el coach, el perfil de autor, "
          "el estilo), eso incluye el rato en que te toca contestar: escribe en tu novela antes o después.")


def _ilegibles(carpeta):
    """Ficheros de la carpeta que podrían ser el manuscrito pero el registro no sabe leer."""
    out = []
    try:
        for n in sorted(os.listdir(carpeta)):
            if n.lower().endswith((".doc", ".odt", ".rtf", ".pdf", ".pages", ".epub")) and not n.startswith(("~$", ".")) \
                    and os.path.getsize(os.path.join(carpeta, n)) > 20000 and "certificado awap" not in n.lower():
                out.append(n)
    except OSError:
        pass
    return out


def _como_en_disco(raiz, rel):
    """El mismo fichero, con el nombre tal como está ESCRITO en el disco.

    El autor teclea «Guía de estilo.md» con la í en un carácter; Word y el Finder guardan la i y la
    tilde por separado. A la vista es el mismo nombre; como cadena, no. En un Mac el fichero se abre
    igual con las dos, así que la declaración se apuntaba con el nombre tecleado, el registro —que
    recorre el disco— no encontraba ese nombre, lo daba por «retirado» y el documento volvía a contar
    como del autor (UAT, 2-oct-2026: HAS 11,54 en vez de 1,28). En la máquina de Cowork, que distingue
    las dos formas, ni siquiera lo encontraba. Lo mismo con las mayúsculas («ángel.md» por «Ángel.md»).
    Tramo a tramo: el nombre exacto si está; si no, el único que es igual salvo la forma de las tildes;
    si no, el único que es igual salvo eso y las mayúsculas. Si no hay uno solo, None."""
    donde, hechos = raiz, []
    nfc = lambda x: unicodedata.normalize("NFC", x)
    rel = os.path.normpath(rel.replace("/", os.sep)) if rel not in ("", ".") else ""
    if rel == os.pardir or rel.startswith(os.pardir + os.sep) or os.path.isabs(rel):
        return None             # «Capítulos/../Guía.md» vale; lo que sale del libro, no
    for tramo in [t for t in rel.replace(os.sep, "/").split("/") if t not in ("", ".")]:
        try:
            nombres = os.listdir(donde)
        except OSError:
            return None
        if tramo in nombres:
            real = tramo
        else:
            iguales = [n for n in nombres if nfc(n) == nfc(tramo)]
            if len(iguales) != 1:
                iguales = [n for n in nombres if nfc(n).casefold() == nfc(tramo).casefold()]
            if len(iguales) != 1:
                return None
            real = iguales[0]
        hechos.append(real)
        donde = os.path.join(donde, real)
    return "/".join(hechos)


def _bajo(raiz, ruta):
    """El tramo de `ruta` por debajo de la carpeta del libro («» si es la carpeta misma), o None si
    está fuera. Subiendo de carpeta en carpeta y preguntando al disco si es LA MISMA: comparar las
    cadenas decía «no está dentro de la carpeta del libro» cuando la carpeta llevaba una tilde escrita
    de una forma en una ruta y de otra en la otra —la del proyecto, tecleada; la del fichero,
    arrastrada del Finder— (equipo rojo, 3-oct-2026). Donde el disco no sabe contestar, se comparan
    con las tildes escritas igual."""
    nfc = lambda x: unicodedata.normalize("NFC", os.path.normpath(x))
    r, cola = os.path.abspath(ruta), []
    while True:
        try:
            misma = os.path.samefile(r, raiz)
        except OSError:
            misma = nfc(r) == nfc(os.path.abspath(raiz))
        if misma:
            return "/".join(reversed(cola))
        padre = os.path.dirname(r)
        if padre == r:
            return None
        cola.append(os.path.basename(r))
        r = padre


def _rel_en_disco(raiz, ruta):
    """El nombre con el que el recorrido del disco ve ese fichero o carpeta del libro, o None."""
    bajo = _bajo(raiz, ruta)
    return None if bajo is None else _como_en_disco(raiz, bajo)


def _rel(p, fichero):
    ruta = os.path.abspath(os.path.expanduser(fichero))
    # Se busca por el nombre del disco ANTES de mirar si existe: donde el sistema distingue las dos
    # formas de escribir una tilde, el nombre tecleado «no existe» aunque el fichero esté ahí.
    cands = [_rel_en_disco(p.raiz, ruta)]
    if not os.path.isabs(os.path.expanduser(fichero)):
        cands.append(_como_en_disco(p.raiz, fichero))
    rel = next((r for r in cands if r and os.path.isfile(os.path.join(p.raiz, *r.split("/")))), None)
    if rel is None:
        if os.path.isfile(ruta) and _bajo(p.raiz, ruta) is None:
            sys.exit("Ese fichero no está dentro de la carpeta del libro.")
        sys.exit(f"No encuentro «{fichero}».")
    return os.path.join(p.raiz, *rel.split("/")), rel


def _indice(p):
    """El índice de todo lo visto, con la custodia de siempre (huellas anotadas y archivo)."""
    evs = p.eventos()
    return Indice(p, {os.path.basename(p._f_texto(r)): h for r, h in huellas_anotadas(p).items()},
                  sum(e.get("ai_words_archived", 0) for e in evs), sum(e.get("own_words_archived", 0) for e in evs))


def marcas_de_suelto(p, rel, pars, indice=None):
    """De quién es cada palabra de un fichero que el registro no tiene por documento, tal como está
    HOY en el disco: (marcas, cuántas palabras conserva de su texto guardado).

    Lo que conserva de su texto guardado hereda. Lo demás se busca en todo lo que el registro ha
    visto: si es texto de la IA, es de la IA; si no, del autor. (Equipo rojo, 2-oct-2026: se
    comparaba solo con el texto guardado al abrir el registro, y lo que el autor pegase después —19
    capítulos del fantasma— entraba como suyo al declararlo. Con el índice no íntegro, lo nuevo es
    de la IA.)"""
    snap = p.instantanea(rel)
    marcas = trasladar(snap, pars, "N", estricto=False) if snap else ["N" * len(palabras(x)) for x in pars]
    conserva = sum(len(m) - m.count("N") for m in marcas)
    indice = indice or _indice(p)
    marcas, _ = indice.heredar(pars, marcas, cambia_el_autor=True)
    return [m.replace("N", "H" if indice.integro else "A") for m in marcas], conserva


def _ia_guardadas(p, rel):
    """Palabras de la IA en un fichero que no está en el registro como documento, tal como está hoy."""
    ruta = os.path.join(p.raiz, rel)
    pars = parrafos_de(ruta) if os.path.isfile(ruta) else None
    if not pars:
        snap = p.instantanea(rel)
        return "".join(snap["f"]).count("A") if snap else 0
    return "".join(marcas_de_suelto(p, rel, pars)[0]).count("A")


def _de_ia(p, docs, rel):
    """Cuántas palabras tiene un fichero que el registro cuenta como de la IA, las midiera o no: las
    de un documento registrado, o las del texto guardado de un fichero sin tipo que escribió la IA.

    (Equipo rojo, 2-oct-2026.) Antes solo contaban las «medidas», y bastaba que el colaborador no
    cerrase su sesión (el capítulo sale «sin atribuir») para declararlo manuscrito previo: HAS 93."""
    d = docs.get(rel)
    if d:
        return max(d["palabras"] - d["humanas"], 0)
    return _ia_guardadas(p, rel)


def _declarar(p, ruta, rel, origen, tipo, evento, descripcion, extra=None):
    pars = parrafos_de(ruta)
    if pars is None:
        sys.exit(f"No puedo leer «{rel}».")
    letra = "H" if origen == "humano" else "A"
    marcas = [letra * len(palabras(par)) for par in pars]
    n = sum(len(m) for m in marcas)
    docs = documentos(p.eventos())
    ant = docs.get(rel)
    de_ia_guardadas = _ia_guardadas(p, rel)
    tipo = tipo or (ant and ant["tipo"]) or clasificar(rel) or "draft"
    nivel = NIVEL_DE[tipo]
    sha = _sha_fichero(ruta)
    hum = n if letra == "H" else 0
    # Contradice lo medido si en el documento hay palabras de la IA y alguna la escribió un
    # colaborador con su sesión, aunque lo último que pasara en él fuese «incierto» (UAT, 2-oct).
    contradice = letra == "H" and bool((ant and ant["palabras"] - ant["humanas"] > 0 and ant.get("ia_medida"))
                                       or (not ant and de_ia_guardadas))
    # Declarado sobre texto que el registro contaba como de la IA sin haberlo podido atribuir.
    sobre_ia = letra == "H" and not contradice and bool(ant and ant["palabras"] - ant["humanas"] > 0)
    ev = p.anotar(event_type=evento, document=rel, document_type=tipo, hierarchical_level=nivel,
                  document_hash="sha256:" + sha, words=n, human_words=hum,
                  ai_words_introduced=n if letra == "A" else 0,
                  # Declararlo tuyo no cuenta como haberlo revisado: sus palabras de la IA dejan de
                  # contar como metidas. Y declararlo de la IA las mete.
                  ai_words_written_off=(ant["palabras"] - ant["humanas"]) if ant and letra == "H" and ant["existe"]
                  and not _relevo_vivo(rel, docs) else None,
                  tokens_generated=max(n - (ant["palabras"] - ant["humanas"] if ant else 0), 0) if letra == "A" else 0,
                  tokens_revised_by_human=0,
                  revision_ratio=1 if letra == "H" else 0,
                  has_contribution=r2(PUNTOS[nivel] * (1 if letra == "H" else 0)),
                  attribution="declarado", overrides_measured=True if contradice else None,
                  overrides_uncertain=True if sobre_ia else None,
                  derived_from_baseline=False, description=descripcion,
                  snapshot_hash=p.huella_texto(pars, marcas), **(extra or {}))
    # Lo que la IA había escrito aquí pasa al archivo: la declaración vale para ESTE documento, y
    # si ese texto aparece mañana en otro, el registro lo sigue reconociendo.
    p.guardar_instantanea(rel, pars, marcas, archivar=True)
    cache = _leer_json(p.f_cache, {}) or {}
    st = os.stat(ruta)
    cache.setdefault("ficheros", {})[rel] = [st.st_size, st.st_mtime, sha]
    _guardar_json(p.f_cache, cache)
    return ev, contradice


def _anotar_previo(p, docs, rel, evento, descripcion, extra=None):
    """Anota un documento como manuscrito previo (o parte de él) SIN cambiar de quién es cada
    palabra. Devuelve (evento, palabras, palabras del autor).

    Antes, declarar el manuscrito previo lo declaraba además entero «del autor», y por eso no se
    podía declarar uno en el que la IA hubiera escrito un párrafo (UAT, 2-oct-2026)."""
    d = docs.get(rel)
    if d:
        ratio = r2(d["humanas"] / d["palabras"]) if d["palabras"] else 1
        ev = p.anotar(event_type=evento, document=rel, document_type=d["tipo"], hierarchical_level=d["nivel"],
                      document_hash="sha256:" + d["sha"], words=d["palabras"], human_words=d["humanas"],
                      ai_words_introduced=d["ia_intro"], tokens_generated=0, tokens_revised_by_human=0,
                      revision_ratio=ratio, has_contribution=r2(PUNTOS[d["nivel"]] * ratio), attribution=d["atribucion"],
                      uncertain_reason=d.get("motivo") if d["atribucion"] == "incierto" else None,
                      snapshot_hash=d.get("huella_texto"), ai_words_pasted_by_author=d.get("pegadas") or None,
                      description=descripcion, **(extra or {}))
        return ev, d["palabras"], d["humanas"]
    # Un fichero que el registro no tenía por documento (su nombre no dice qué es): entra ahora, con
    # las marcas de su texto guardado si lo hay (lo que la IA haya escrito en él sigue siendo suyo).
    ruta = os.path.join(p.raiz, rel)
    pars = parrafos_de(ruta) or []
    marcas, _ = marcas_de_suelto(p, rel, pars)
    junto = "".join(marcas)
    n, hum = len(junto), junto.count("H")
    sha = _sha_fichero(ruta)
    _, huella = p.guardar_instantanea(rel, pars, marcas)
    ratio = r2(hum / n) if n else 1
    ev = p.anotar(event_type=evento, document=rel, document_type="draft", hierarchical_level=7,
                  document_hash="sha256:" + sha, words=n, human_words=hum, ai_words_introduced=n - hum,
                  tokens_generated=0, tokens_revised_by_human=0, revision_ratio=ratio,
                  has_contribution=r2(PUNTOS[7] * ratio), attribution="declarado", snapshot_hash=huella,
                  own_words_archived=p.propias_archivadas or None, description=descripcion, **(extra or {}))
    cache = _leer_json(p.f_cache, {}) or {}
    st = os.stat(ruta)
    cache.setdefault("ficheros", {})[rel] = [st.st_size, st.st_mtime, sha]
    _guardar_json(p.f_cache, cache)
    return ev, n, hum


def _suelto_previo(p, evs, rel, indice=None):
    """Para un fichero que no es documento del registro: (por qué vale como previo, palabras previas,
    palabras, palabras de la IA que el registro le conoce)."""
    pars = parrafos_de(os.path.join(p.raiz, rel)) or []
    n = sum(len(palabras(x)) for x in pars)
    marcas, conserva = marcas_de_suelto(p, rel, pars, indice) if n else ([], 0)
    ia = "".join(marcas).count("A")
    por, previas = previo_suelto(p, evs, rel, n) if n else (None, 0)
    previas = min(previas, n - ia)
    if por == "visto al abrir el registro":
        # Previo es lo que conserva de lo que había al abrir (más el margen de siempre): lo que se
        # le haya añadido después no lo es, lo escribiera quien lo escribiera.
        previas = min(previas, palabras_previas(n - ia, conserva))
    return (por if previas >= MIN_PREVIO else None), previas, n, ia


def _previo_de_doc(p, evs, rel, d):
    """Para un documento del registro: (por qué vale como previo, cuántas palabras), o (None, 0).

    Si el registro sabe que ya estaba antes de la IA, vale por eso. Si no lo sabe (entró en el
    registro después: el autor lo trajo a la carpeta con la IA ya trabajando), es entero suyo y la
    fecha del fichero es anterior a la primera vez que trabajó la IA, vale por la fecha, y así consta
    (equipo rojo, 2-oct-2026: se negaba con «el registro lo ha visto escribirse», que no era verdad)."""
    if previo_posible(d):
        return "el registro", previas_de(d)
    cuando = primera_ia(evs)
    try:
        antigua = cuando is not None and os.stat(os.path.join(p.raiz, rel)).st_mtime < cuando
    except OSError:
        antigua = False
    if antigua and d["palabras"] >= MIN_PREVIO and d["humanas"] == d["palabras"] and not d.get("ia_medida"):
        return "la fecha del fichero", d["palabras"]
    return None, 0


_NO_PREVIO = ("pero la concepción del libro (premisa, sinopsis, biblia, escaleta y estilo) solo se acredita con un "
              "manuscrito anterior a la IA o con esos documentos escritos por ti.")


def cmd_base(a):
    p = _proyecto(a.carpeta, exigir=False) or _proyecto(a.fichero)
    if ponerse_al_dia(p) == "trabajando":
        sys.exit(_ESPERA)
    if hay_base(p.eventos()):
        b = hay_base(p.eventos())
        cual = "la carpeta del libro" if b.get("document") == "." else f"«{b.get('document')}»"
        sys.exit(f"Ya hay un manuscrito previo declarado: {cual} ({b.get('baseline_words')} "
                 f"palabras, el {fecha(b.get('timestamp', ''))}). Solo puede haber uno, y no hace falta más: lo que "
                 "ya estaba en la carpeta al abrir el registro cuenta como tuyo, esté declarado o no.")
    if a.fichero.strip() in ("", ".", "./"):
        a.fichero = p.raiz              # «--base .» desde la skill: la carpeta del libro, no la de trabajo
    donde = os.path.abspath(os.path.expanduser(a.fichero))
    if not os.path.exists(donde) and os.path.exists(os.path.join(p.raiz, a.fichero)):
        donde = os.path.join(p.raiz, a.fichero)
    # La carpeta, con el nombre del disco (ver _como_en_disco): «Capítulos» tecleado no es la misma
    # cadena que el «Capítulos» que guardó el Finder, y con el tecleado no casaba ningún capítulo.
    for real in [_rel_en_disco(p.raiz, donde)] + \
                ([_como_en_disco(p.raiz, a.fichero)] if not os.path.isabs(os.path.expanduser(a.fichero)) else []):
        if real is not None and os.path.isdir(os.path.join(p.raiz, *real.split("/")) if real else p.raiz):
            donde = os.path.join(p.raiz, *real.split("/")) if real else p.raiz
            break
    if os.path.isdir(donde):
        return _base_carpeta(p, donde)
    if not a.fichero.lower().endswith(EXTENSIONES):
        # (UAT, 2-oct.) Con un PDF se «declaraban» 217.246 palabras de un libro de 45.767: se leía el
        # fichero como si fuera texto.
        sys.exit("El manuscrito previo tiene que ser un Word (.docx) o un texto (.md, .txt): son los que el "
                 "registro sabe leer y comparar. Un PDF, un .doc antiguo, un .rtf, un .odt o un .epub no valen: "
                 "guárdalo como .docx desde Word y declara ese.")
    ruta, rel = _rel(p, a.fichero)
    evs = p.eventos()
    docs = documentos(evs)
    if not parrafos_de(ruta):
        sys.exit(f"No he podido leer texto en «{rel}». ¿Está vacío, o es un .docx protegido o dañado?")
    if rel in docs:
        d = docs[rel]
        por, previas = _previo_de_doc(p, evs, rel, d)
        n, ia = d["palabras"], d["palabras"] - d["humanas"]
    else:
        por, previas, n, ia = _suelto_previo(p, evs, rel)
    if not por:
        # (UAT, 2-oct.) Quien empezaba de cero con la biblia de la IA declaraba «previo» el capítulo que
        # escribía al día siguiente (o el que le acababa de escribir el fantasma), y el certificado
        # decía «escrito antes de usar HumanInk» de un fichero que el propio registro había visto nacer.
        sys.exit(f"«{rel}» no se puede declarar como manuscrito previo: su texto es posterior a que la IA empezase a "
                 "trabajar en el libro (el registro lo ha visto escribirse). "
                 + ("Lo que tiene de ti ya cuenta como tuyo, palabra por palabra; " if rel in docs else
                    f"Si lo has escrito tú, decláralo tuyo con --mine \"{rel}\" y contará como texto tuyo; ")
                 + _NO_PREVIO)
    ev, n, hum = _anotar_previo(p, docs, rel, "baseline_declared", "Manuscrito preexistente declarado por el autor",
                                {"baseline_words": previas, "previous_by": por})
    if previas < n:
        print(f"Manuscrito previo declarado: «{rel}». De sus {n} palabras, {previas} ya estaban antes de que la IA "
              "trabajase en el libro: esas son el manuscrito previo. Las demás son posteriores"
              + (f" ({ia} de la IA)" if ia else "") + " y cuentan como lo que son.\n"
              f"Huella: {ev['document_hash']}")
    else:
        print(f"Manuscrito previo declarado: «{rel}», {n} palabras.\nHuella: {ev['document_hash']}")
    _tras_base(p, previas)


def _base_carpeta(p, donde):
    """El manuscrito previo de quien escribe por capítulos: la carpeta entera."""
    pre = _rel_en_disco(p.raiz, donde)
    if pre is None:
        if _bajo(p.raiz, donde) is None:
            sys.exit("Esa carpeta no está dentro de la carpeta del libro.")
        pre = _bajo(p.raiz, donde)
    pre = "" if pre in ("", ".") else pre.rstrip("/") + "/"
    dentro = sorted(r for r in ficheros(p.raiz) if r.startswith(pre))
    if not pre:
        # La carpeta del libro entera: solo lo que es manuscrito por su nombre. Lo demás (notas,
        # informes, apuntes) no es el manuscrito aunque esté ahí.
        dentro = [r for r in dentro if clasificar(r) == "draft"]
    evs_ = p.eventos()
    docs = documentos(evs_)
    vivos = cabezas(docs)
    valen, fuera = [], []           # [(ruta, palabras previas, ¿suma?, por qué)], [rutas que se quedan fuera]
    indice_ = None
    for r in dentro:
        if clasificar(r) not in (None, "draft") or de_salida(r):
            continue
        if r in docs:
            d = docs[r]
            if not d["existe"] or not d["palabras"] or d["tipo"] != "draft":
                continue
            por, previas = _previo_de_doc(p, evs_, r, d)
            if por:
                # De una serie de versiones valen todas, pero el tamaño del manuscrito es el de la
                # que cuenta: 41 versiones de una novela no son un manuscrito de tres millones.
                valen.append((r, previas, r in vivos or cabeza_viva(r, docs) not in dentro, por))
            else:
                fuera.append(r)
        else:
            indice_ = indice_ or _indice(p)
            por, previas, n_, ia_ = _suelto_previo(p, evs_, r, indice_)
            if por:
                valen.append((r, previas, True, por))
            elif n_ and ia_ * 2 <= n_:
                fuera.append(r)         # (un fichero de trabajo de la IA —un informe, un checkpoint— ni se nombra)
    if not valen:
        sys.exit(f"No he encontrado en {('«' + pre.rstrip('/') + '»') if pre else 'la carpeta del libro'} ningún manuscrito "
                 "(.docx, .md o .txt) con texto tuyo anterior a que la IA trabajase en el libro."
                 + (f" Lo que hay ({', '.join(fuera[:5])}{'…' if len(fuera) > 5 else ''}) es posterior: ya cuenta "
                    "como es, y no hay nada que declarar." if fuera else ""))
    total, huellas = 0, []
    for rel, previas, suma, _ in valen:
        if rel in docs:
            huellas.append("sha256:" + docs[rel]["sha"])        # ya es un documento del registro: no cambia nada en él
        else:
            ev, _, _ = _anotar_previo(p, docs, rel, "declaration", "Parte del manuscrito preexistente declarado por el autor")
            huellas.append(ev["document_hash"])
        total += previas if suma else 0
    hechos = len(valen)
    conjunto = "sha256:" + hashlib.sha256("\n".join(huellas).encode()).hexdigest()
    p.anotar(event_type="baseline_declared", document=pre.rstrip("/") or ".", document_type="draft",
             document_hash=conjunto, baseline_words=total, attribution="declarado",
             # Si de alguno solo consta que era anterior por la fecha del fichero, el conjunto vale eso.
             previous_by="la fecha del fichero" if any(x[3] == "la fecha del fichero" for x in valen) else "el registro",
             files=[x[0] for x in valen][:200], left_out=fuera or None,
             description=f"Manuscrito preexistente declarado por el autor: {pl(hechos, 'fichero', 'ficheros')}")
    print("Manuscrito previo declarado: " + ("1 fichero" if hechos == 1 else f"los {hechos} ficheros") + " de "
          + (f"«{pre.rstrip('/')}»" if pre else "la carpeta del libro") + f", {total} palabras.\n"
          f"Huella del conjunto: {conjunto}")
    if fuera:
        uno = len(fuera) == 1
        print(f"Se {'queda' if uno else 'quedan'} fuera {pl(len(fuera), 'fichero', 'ficheros')} que el registro vio nacer "
              f"después de que trabajase la IA: {', '.join(fuera[:6])}{'…' if len(fuera) > 6 else ''}. "
              f"Ya {'cuenta como es; no hay que declararlo' if uno else 'cuentan como son; no hay que declararlos'}.")
    _tras_base(p, total)


def _enlazar_concepcion(p):
    """Recién declarado el manuscrito previo: la premisa, la biblia o la escaleta que la IA redactó
    ANTES de declararlo, ¿salen de él? Se mira ahora, con la misma regla que cuando la IA las
    escribe con el manuscrito ya declarado (UAT, 2-oct-2026: el orden importaba; con el coach antes
    de declarar, la biblia se quedaba a cero y el HAS en 74 en vez de 93)."""
    evs = p.eventos()
    base, docs = hay_base(evs), documentos(evs)
    enlazados = []
    for rel, d in sorted(cabezas(docs).items()):
        if d["nivel"] in CONCEPCION and not d["de_base"] and d["palabras"] > d["humanas"]:
            snap = p.instantanea(rel)
            if snap and p.huella_texto(snap["p"], snap["f"]) == d.get("huella_texto") \
                    and _sale_del_manuscrito(p, base, docs, snap["p"]):
                _anotar_previo(p, docs, rel, "baseline_link", "Sale del manuscrito previo (comprobado al declararlo)",
                               {"derived_from_baseline": True})
                enlazados.append(rel)
    return enlazados


def _tras_base(p, n):
    enlazados = _enlazar_concepcion(p)
    if enlazados:
        print("Salen de tu manuscrito, y la concepción se te acredita aunque los redactase la IA: " + ", ".join(enlazados) + ".")
    r = calcular_has(entradas(p.eventos()))
    print(f"\nHAS ahora: {_n(r['has_global'])}/100.")
    f = factor_base(cabezas(documentos(p.eventos())), MIN_BASE, n)
    por_base = [b["label"].lower() for b in r["breakdown"] if b["level"] in CONCEPCION and b["credited_by_baseline"]]
    con_doc = [b["label"].lower() for b in r["breakdown"] if b["level"] in CONCEPCION and not b["credited_by_baseline"]
               and b["presence_verified"] and b["events_count"]]
    if f >= 1:
        # Solo lo que de verdad queda acreditado: lo que tiene documento propio cuenta por su
        # documento (la biblia que escribió la IA sigue siendo de la IA).
        if por_base:
            print("Quedan acreditados por el manuscrito: " + ", ".join(por_base) + ".")
        if con_doc:
            print("Tienen documento propio y cuentan por él: " + ", ".join(con_doc) + ".")
    else:
        print(f"El manuscrito acredita la concepción del libro al {round(f * 100)} %: para acreditarla entera "
              f"hacen falta al menos {MIN_BASE} palabras tuyas en el manuscrito, y que sean al menos la mitad de él.")
    print("A partir de aquí se anota lo que se haga con la IA. El certificado dirá que la puntuación parte de "
          "un manuscrito previo declarado por ti.")


def cmd_declarar(a):
    p = _proyecto(a.carpeta, exigir=False) or _proyecto(a.fichero)
    if ponerse_al_dia(p) == "trabajando":
        sys.exit(_ESPERA)
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
    de_ia = _de_ia(p, documentos(p.eventos()), rel)
    if a.origen == "humano" and de_ia and not a.confirmo:
        sys.exit(f"«{rel}» tiene {de_ia} palabras que el registro cuenta como escritas por la IA.\n"
                 "Declararlo tuyo lo declara ENTERO: esas palabras dejarían de contar como de la IA, y en el informe y "
                 "en el certificado constará que la declaración se hizo sobre texto que el registro contaba como de la IA.\n"
                 "Si aun así el documento entero es tuyo, repite la orden con --confirmo. Si solo hay un cambio suelto "
                 "en duda, lo honrado es dejarlo como está.")
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
    s = _sesion_viva(p)
    if s:
        p.latido(s)
        return
    # No hay sesión, o la que hay lleva tres cuartos de hora sin dar señales: era de otro colaborador
    # que no cerró. Lo suyo no es de este (equipo rojo, 1-oct: salía «medido» a nombre del siguiente).
    ponerse_al_dia(p)
    p.abrir_sesion()


def raices_del_cierre(ruta):
    """El libro que cierra un colaborador. Si la carpeta que trae no tiene registro (el bloque de
    cierre de varios colaboradores usa una variable de un bloque anterior y llega vacía), los libros
    en uso que tengan una sesión abierta."""
    raiz = raiz_de(ruta)
    if raiz and (Proyecto(raiz).sesion() or {}).get("abierta"):
        return [raiz]
    # El libro que nombra no tiene sesión (o no nombra ninguno): la sesión de este colaborador está
    # abierta en otro libro en uso (UAT, 2-oct: preguntar por el HAS de otro libro a mitad de un
    # colaborador mandaba el cierre a ese otro libro y dejaba abierta la sesión buena).
    return ([raiz] if raiz else []) + [r for r in libros_en_uso() if r != raiz and _sesion_viva(Proyecto(r))]


def cmd_fin(a):
    """Termina un colaborador. Lo llama hi-log.sh. Lo que ha cambiado desde que empezó es suyo."""
    p = Proyecto(a.raiz) if getattr(a, "raiz", None) else _proyecto(a.ruta, exigir=False)
    if not p:
        return
    s = p.sesion() or {}
    if s.get("abierta") and ahora() - s["abierta"] >= SESION_VIVA:
        # Una sesión que lleva más de tres horas abierta no es de quien cierra ahora: su colaborador
        # murió sin cerrar. Lo que cambió desde entonces no se sabe de quién es, y no se le pone el
        # nombre de este (equipo rojo, 2-oct: 600 palabras del autor salían «medido» de un coach).
        ponerse_al_dia(p)
        s = {}
    abierta = s.get("abierta")
    seguro, motivo, sigue = bool(abierta), None, False
    if not abierta:
        # Termina un colaborador que no avisó de que empezaba (hi-args no llegó a correr, o miraba
        # otra carpeta). Lo que lleva horas guardado no puede ser suyo: es del autor, como lo habría
        # sido al empezar. Lo reciente no se sabe, y va como incierto.
        mirar(p, "H", hasta=ahora() - SESION_VIVA)
        motivo = "el colaborador terminó sin haber avisado de que empezaba"
        # Salvo en dos casos en que sí se sabe (UAT, 2-oct: cada capítulo del fantasma acababa con un
        # aviso por repetir el bloque de cierre): es el mismo colaborador, que acaba de cerrar y
        # cierra otra vez (en los dos minutos en que lo que cambia aún es suyo, no más: a los diez,
        # lo que el autor hubiera guardado entre medias salía «medido» a nombre del colaborador);
        # o el cierre corre dentro de una orden de la IA cuyo «antes» ya dejó anotado lo del autor.
        ult = next((e for e in reversed(p.eventos()) if e.get("event_type") == "collaborator_run"), None)
        marca = _leer_json(p.f_marca) or {}
        if ult and not ult.get("unclosed") and ult.get("collaborator") == a.colab \
                and 0 <= ahora() - (ult.get("closed") or 0) < REPITE_CIERRE:
            seguro, abierta, sigue = True, ult.get("closed"), True
        elif marca.get("antes") and 0 <= ahora() - marca["antes"] < 1800:
            seguro, abierta = True, marca["antes"]
    if getattr(a, "raiz", None) and getattr(a, "nombrada", None) is not None and a.raiz != a.nombrada \
            and getattr(a, "dudoso", False):
        # El cierre no decía de qué libro era y hay más de uno con un colaborador trabajando: no se
        # le puede poner el nombre de este a lo que ha cambiado aquí.
        seguro, motivo = False, "se cerró un colaborador sin decir en cuál de los libros en uso trabajaba"
    # El cierre que no nombra este libro (llegó con otra carpeta, o sin ninguna) cierra la sesión que
    # hay aquí, y lo que cambió en ella es de la IA; pero no se sabe que sea de ESTE colaborador: el
    # que cierra pudo trabajar en otra carpeta (equipo rojo, 2-oct: la biblia del coach y un
    # capítulo del autor salían «medido» a nombre de un copywriter que nunca tocó el libro).
    ajeno = bool(getattr(a, "raiz", None)) and getattr(a, "nombrada", None) is not None and a.raiz != a.nombrada
    quien_ = "(sin identificar)" if ajeno else a.colab
    anotado, otros = mirar(p, "A", colab=quien_, modelo=a.modelo,
                           atribucion="medido" if seguro else "incierto", motivo=None if seguro else motivo)
    if s.get("abierta") or anotado or otros:
        # Un cierre sin sesión y sin nada que anotar no es un trabajo de colaborador: no se apunta.
        p.anotar(event_type="collaborator_run", collaborator=quien_, collaborator_name=None if ajeno else a.nombre,
                 closed_by=a.colab if ajeno else None,
                 mode=a.modo, opened=abierta or ahora(), closed=ahora(),
                 continues=True if sigue else None, produced=_producido(anotado, otros))
    p.cerrar_sesion()


_RUTA_EN_ORDEN = re.compile(r'''"([^"\n]{1,400})"|'([^'\n]{1,400})'|(?:^|[\s=<>|(])((?:\\.|[^\s"';|&<>()])+)''')
_PARECE_RUTA = re.compile(r"/|\.(?:docx|md|txt)$", re.I)


def raices_de_orden(datos):
    """Las carpetas de libro con registro a las que toca una orden de la IA (el JSON de un gancho):
    la del fichero que escribe, o las de las rutas que aparecen en una orden de Bash y su carpeta de
    trabajo. Devuelve ([raíces], ruta del fichero escrito o None, {raíces que la orden nombra})."""
    ti = datos.get("tool_input") or {}
    escrito = ti.get("file_path") if isinstance(ti.get("file_path"), str) else None
    rutas = [escrito] if escrito else []
    orden = ti.get("command")
    cwd = datos.get("cwd") if isinstance(datos.get("cwd"), str) else None
    if isinstance(orden, str):
        vistas = set()
        # Primero, como las lee la shell, línea a línea: «"${HOME}"/Libros/"Mi novela"/cap.docx»
        # (comillas pegadas), «Mi\ novela\ \(2ª\ versión\)/…» (escapes) y «--output=/ruta» (UAT,
        # 2-oct: al día siguiente, lo que la IA alargaba con esas órdenes salía como del autor).
        for linea in orden[:400_000].split("\n")[:400]:
            if len(linea) > 20_000:
                continue
            try:
                piezas = shlex.split(linea, posix=True)
            except ValueError:
                continue            # comillas sin cerrar: el cuerpo de un heredoc, un apóstrofo
            for pieza in piezas:
                for r in (pieza, pieza.split("=", 1)[1] if "=" in pieza else ""):
                    if "$" in r:
                        r = os.path.expandvars(r)
                    if not r or len(r) > 400 or r in vistas or r.startswith("-") or not _PARECE_RUTA.search(r):
                        continue
                    vistas.add(r)
                    if r.startswith(("/", "~")):
                        rutas.append(r)
                    elif cwd:
                        rutas.append(os.path.join(cwd, r))
            if len(rutas) > 200:
                break
        vistas = set()
        for m in _RUTA_EN_ORDEN.finditer(orden[:2_000_000]):
            r = next(x for x in m.groups() if x).replace("\\ ", " ")
            if "$" in r:
                r = os.path.expandvars(r)           # «$HOME/Libros/…»
            if r in vistas or r.startswith("-") or not _PARECE_RUTA.search(r):
                continue
            vistas.add(r)
            if r.startswith(("/", "~")):
                rutas.append(r)
                # «"/Users/ana/Mi novela 3 --goal"»: la ruta es el principio de lo entrecomillado.
                trozos = r.split(" ")
                rutas.extend(" ".join(trozos[:n]) for n in range(len(trozos) - 1, 0, -1))
            elif cwd:
                rutas.append(os.path.join(cwd, r))      # relativa a la carpeta de trabajo
            if len(rutas) > 400:
                break
        # Y las rutas absolutas que queden dentro de comillas anidadas («"$(dirname "/libro/cap.md")"»),
        # donde la primera pasada casa mal las comillas.
        for m in re.finditer(r"(?:~|/)[^\"'\n`$;|&<>()]{2,400}", orden[:2_000_000]):
            r = m.group(0).rstrip(" ")
            if r not in vistas and "/" in r[1:]:
                vistas.add(r)
                trozos = r.split(" ")
                rutas.extend(" ".join(trozos[:n]) for n in range(len(trozos), 0, -1))
            if len(rutas) > 400:
                break
        # Y cualquier ruta absoluta que vaya entera entre comillas, lleve lo que lleve dentro
        # (paréntesis, «&»): «python3 -c "…f='/Libros/Mi novela (2ª versión)/cap.docx'…"» (UAT, 2-oct).
        for m in re.finditer(r"""["']((?:~|/)[^"'\n]{2,400})["']""", orden[:2_000_000]):
            r = m.group(1)
            if r not in vistas:
                vistas.add(r)
                rutas.insert(0, r)
            if len(rutas) > 400:
                break
        # Con comodines («/Libros/Mi*/cap.docx»). Sin recorrer el disco: «ls /Users/*/*/*/*/*.md»
        # dejaba el gancho colgado más de cien segundos (equipo rojo, 2-oct-2026). Se compara el
        # patrón con los libros en uso; y solo si lleva UN comodín, y no en los dos primeros niveles,
        # se mira esa carpeta.
        for r in [x for x in rutas[:60] if any(c in x for c in "*?[")][:10]:
            partes = [x for x in os.path.expanduser(r).split("/") if x]
            for raiz in libros_en_uso():
                suyas = [x for x in raiz.split("/") if x]
                if len(suyas) <= len(partes) and all(fnmatch.fnmatchcase(a_, b_) for a_, b_ in zip(suyas, partes)):
                    rutas.insert(0, raiz)
            con = [i for i, x in enumerate(partes) if any(c in x for c in "*?[")]
            if len(con) == 1 and con[0] >= 2 and "**" not in r:
                try:
                    rutas[0:0] = list(itertools.islice(glob.iglob(os.path.expanduser(r)), 20))
                except Exception:
                    pass
        if cwd:
            rutas.append(cwd)
    raices = []
    for r in rutas[:400]:
        raiz = raiz_de(r)
        if raiz and raiz not in raices:
            raices.append(raiz)
    nombradas = set(raices)
    if isinstance(orden, str):
        # Una orden puede escribir en el libro sin nombrarlo (un guion con la ruta dentro): se miran
        # también los libros usados en la última hora (UAT, 2-oct: 508 palabras de la IA como del
        # autor). Lo que cambie en ellos durante la orden va «sin atribuir», no «medido»: la orden
        # podía no tener nada que ver con el libro.
        for raiz in libros_en_uso(horas=1):
            if raiz not in raices:
                raices.append(raiz)
    for raiz in nombradas:
        apuntar_libro(raiz)
    return raices, escrito, nombradas


def _sesion_viva(p):
    """La sesión de colaborador abierta, si sigue viva: ha dado señales hace menos de tres cuartos de
    hora Y se abrió hace menos de tres horas. Lo segundo es el tope: los ganchos dan señal de vida en
    cada orden de la IA, y una sesión que nadie cerró se mantendría viva toda la conversación,
    con el trabajo del autor saliendo «sin atribuir» horas después (equipo rojo, 2-oct-2026)."""
    s = p.sesion()
    if s and s.get("abierta") and ahora() - s.get("ultima", s["abierta"]) < HUECO \
            and ahora() - s["abierta"] < SESION_VIVA:
        return s
    return None


def gancho_antes(p, orden_id=None, late=True):
    """La IA va a ejecutar una orden o a escribir un fichero. Si hay un colaborador trabajando, es
    una señal de vida. Si no, lo que haya cambiado hasta este momento es del autor: se anota ahora,
    para que no se lo lleve lo que la IA escriba a continuación.

    `late`: una orden que solo mira el registro (el auditor) no es señal de vida de nadie. Si lo
    fuera, pedir el estado o el certificado cada media hora mantendría viva tres horas la sesión de
    un colaborador que se quedó colgado (UAT, 2-oct-2026: «espera y repite» alargaba la espera)."""
    s = _sesion_viva(p)
    if s:
        if late:
            p.latido(s)
        return
    ponerse_al_dia(p)
    _guardar_json(p.f_marca, {"antes": ahora(), "orden": orden_id})


def gancho_despues(p, escrito=None, orden_id=None, nombrado=True, late=True):
    """La IA ha terminado esa orden. Fuera de un colaborador, lo que haya cambiado desde `gancho_antes`
    lo ha escrito ella: se anota ahora, como de la IA.

    (UAT, 2-oct-2026.) Antes solo se avisaba de Write y Edit, y un Word no se puede escribir con
    ellos: lo que la IA alargaba con un guion fuera de sesión contaba como del autor."""
    s = _sesion_viva(p)
    if s:
        if late:
            p.latido(s)
        return
    marca = _leer_json(p.f_marca) or {}
    suya = marca.get("antes") and ahora() - marca["antes"] < 1800 \
        and (not marca.get("orden") or not orden_id or marca["orden"] == orden_id)
    if marca.get("antes") and not suya:
        # La marca es de OTRA orden, que no llegó a terminar: lo cambiado desde entonces no es de esta
        # orden ni se sabe de quién. Se aparta como sin atribuir y se sigue con esta.
        mirar(p, "H")
    _quitar(p.f_marca)
    if suya and nombrado:
        mirar(p, "A", colab="(fuera de sesión)", fuera=True)
    elif suya:
        mirar(p, "A", colab="(fuera de sesión)", fuera=True, atribucion="incierto",
              motivo="cambió mientras la IA ejecutaba una orden que no nombraba este libro")
    elif escrito:
        # No hubo «antes» (el gancho no llegó a correr): solo el fichero que ha escrito.
        # Con el nombre DEL DISCO: la IA manda «Capítulo 1.md» con la tilde en un carácter y el disco lo
        # tiene con la tilde aparte; `mirar(solo=…)` no casaba ninguno, no anotaba nada, y la siguiente
        # mirada le daba lo escrito al autor, «medido» (equipo rojo, 3-oct-2026).
        rel = _rel_en_disco(p.raiz, escrito)
        if rel and os.path.isfile(os.path.join(p.raiz, *rel.split("/"))) and rel.lower().endswith(EXTENSIONES):
            mirar(p, "A", colab="(fuera de sesión)", solo=rel)
    else:
        # Una orden sin «antes»: solo lo recién guardado, para no llevarse trabajo del autor sin anotar.
        mirar(p, "A", colab="(fuera de sesión)", fuera=True, desde=ahora() - 120, atribucion="incierto",
              motivo="cambió mientras la IA ejecutaba una orden fuera de un colaborador")


def cmd_gancho(a):
    """`antes -` y `despues -`: el JSON del gancho llega por la entrada estándar. `escrito <fichero>`
    es el nombre antiguo de `despues` para una escritura. En silencio, y cada libro con su cerrojo."""
    datos = getattr(a, "datos", None)
    if datos is None:
        datos = {"tool_input": {"file_path": a.ruta}}
    raices, escrito, nombradas = raices_de_orden(datos)
    orden_ = (datos.get("tool_input") or {}).get("command")
    late = not (isinstance(orden_, str) and ("awap_local.py" in orden_ or "HI_SIN_AWAP" in orden_))   # el auditor solo mira
    for raiz in raices:
        p = Proyecto(raiz)
        if not p.cerrar_paso(float(os.environ.get("AWAP_ESPERA") or 8)):
            if a.orden != "antes":
                # El gancho no puede esperar más, pero la escritura no se pierde: queda apuntada (una
                # línea, sin tocar la cadena) y la siguiente mirada la cuenta como de la IA.
                try:
                    rel = None
                    if escrito and os.path.isfile(escrito):
                        rel = _rel_en_disco(raiz, escrito)      # el nombre del disco, como arriba
                    with open(p.f_pendientes, "a", encoding="utf-8") as f:
                        f.write(json.dumps({"document": rel, "mtime": os.stat(escrito).st_mtime if rel else ahora()}) + "\n")
                except Exception:
                    pass
            continue
        try:
            oid = datos.get("tool_use_id") if isinstance(datos.get("tool_use_id"), str) else None
            if a.orden == "antes":
                gancho_antes(p, oid, late)
            else:
                gancho_despues(p, escrito, oid, nombrado=raiz in nombradas, late=late)
        except BaseException:
            pass
        finally:
            p.abrir_paso()


def _n(x):
    return f"{x:.2f}".replace(".", ",")


def _resumen(p):
    evs = p.eventos()
    docs = documentos(evs)
    vivos = cabezas(docs)
    ents = entradas(evs)
    r = calcular_has(ents)
    # Las dos cifras de la revisión, para DECIR el porcentaje que es. Los puntos salen del ratio
    # redondeado a dos decimales, igual que en el servidor; pero 23 palabras de 9.484 no son «el 0 %»
    # (equipo rojo, 3-oct-2026: el arreglo de la 2.3.3 candidata pintaba el ratio YA redondeado).
    e6 = next((e for e in ents if e.get("hierarchical_level") == 6), None)
    revision = {"sustituidas": e6["tokens_revised_by_human"], "de": e6["tokens_generated"]} if e6 else None
    todas = [e for e in evs if e.get("event_type") == "collaborator_run"]
    # Un cierre repetido es el mismo trabajo: no cuenta dos veces («Escritor fantasma ×2» por uno).
    corridas = [e for e in todas if not e.get("unclosed") and not e.get("continues")]
    por_colab = {}
    for e in corridas:
        k = colaborador(e.get("collaborator"), e.get("collaborator_name"))
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
                        "atribucion": d["atribucion"], "de_base": d["de_base"], "sha": d["sha"],
                        "previo_posible": previo_posible(d)}
                       for rel, d in sorted(vivos.items())],
        "colaboradores": por_colab, "sesiones": len(corridas),
        "sin_cerrar": sum(1 for e in todas if e.get("unclosed")),
        "eventos": len(evs),
        "declaraciones": [{"document": "la carpeta del libro" if e.get("document") == "." else e.get("document"), "fecha": e.get("timestamp"),
                           "que": e.get("description"), "contradice": bool(e.get("overrides_measured")),
                           "sobre_ia": bool(e.get("overrides_measured") or e.get("overrides_uncertain"))}
                          for e in evs if e.get("event_type") in ("declaration", "baseline_declared")
                          and not (e.get("description") or "").startswith("Parte del manuscrito preexistente")],
        "declarado_de_ia": sum(e.get("ai_words_written_off", 0) for e in evs),
        "revision": revision,
        "inciertos": sorted(rel for rel, d in vivos.items() if d["atribucion"] == "incierto"),
        "motivos": {e["document"]: e.get("uncertain_reason") for e in evs
                    if e.get("attribution") == "incierto" and e.get("document")},
        "factor_base": r2(factor_base(vivos, MIN_BASE, r["baseline"].get("words") or 0))
        if r["baseline"]["declared"] else None,
        "fuera_de_sesion": {"palabras": sum(e.get("tokens_generated", 0) for e in evs if e.get("event_type") == "text_generated"
                                            and e.get("collaborator") == "(fuera de sesión)"),
                            "veces": sum(1 for e in evs if e.get("event_type") == "text_generated"
                                         and e.get("collaborator") == "(fuera de sesión)")},
        "atras": dejadas_atras(docs),
        "previos": previos_a_declarar(docs),
        "retomas": [{"document": rel, "de": d["retoma"]["de"], "seq": d["retoma"]["seq"]} for rel, d in sorted(vivos.items())
                    if d.get("retoma") and docs.get(d["retoma"]["de"], {}).get("existe")],
        "previo_por": (hay_base(evs) or {}).get("previous_by"),
        "palabras": sum(d["palabras"] for d in vivos.values()),
        "palabras_ia": sum(d["palabras"] - d["humanas"] for d in vivos.values()),
        # Lo que ya estaba al abrir el registro no es «nuevo desde que hay registro».
        "palabras_tuyas_despues": sum(e.get("tokens_revised_by_human", 0) for e in evs
                                      if (e.get("event_type") == "text_revised" and e.get("attribution") != "preexistente")
                                      # y un capítulo que escribes en un fichero nuevo (no lo que sale de otro
                                      # fichero tuyo que ya estaba en la carpeta sin nombre de documento)
                                      or (e.get("event_type") == "document_created" and e.get("attribution") == "medido"
                                          and not (e.get("description") or "").startswith("Estaba en la carpeta"))),
        "primer_evento": evs[0]["timestamp"] if evs else None,
        "ultimo_evento": evs[-1]["timestamp"] if evs else None,
        "huella_registro": evs[-1].get("hash") if evs else None,
        "cadena_integra": integra, "linea_rota": rota, "has_version": VERSION_HAS,
    }


_COMO = {"medido": "medido", "declarado": "declarado por ti", "preexistente": "anterior al registro",
         "incierto": "con cambios sin atribuir, contados como de la IA"}


def _parte(r, b):
    """«99,7 %» del nivel, con las palabras de sus documentos: el 1,00 del desglose ya viene redondeado."""
    suyos = [d for d in r["documentos"] if NIVEL_DE.get(d["tipo"]) == b["level"]]
    hum, pal = sum(d["humanas"] for d in suyos), sum(d["palabras"] for d in suyos)
    if round(b["average_revision_ratio"] * 100) == 100 and pal and hum < pal:
        return pct(hum, pal)
    return f"{round(b['average_revision_ratio'] * 100)} %"


def _pinta_niveles(r):
    lineas = []
    for b in r["breakdown"]:
        if b["credited_by_baseline"]:
            como = "por el manuscrito previo"
        elif not b["presence_verified"]:
            como = "sin documento" if b["level"] != 6 else (
                "lo que había de la IA lo has declarado tuyo" if r.get("declarado_de_ia") else "la IA no ha escrito en el manuscrito")
        elif b["level"] == 6:
            rv = r.get("revision")
            cuanto = pct(rv["sustituidas"], rv["de"]) if rv else pct(b["average_revision_ratio"], 1)
            como = f"has sustituido el {cuanto} de lo que metió la IA"
        elif b.get("partial_baseline"):
            como = f"por el manuscrito previo, al {round(b['average_revision_ratio'] * 100)} %: es poco para este libro"
        elif b.get("from_manuscript"):
            como = "la redactó la IA a partir de tu manuscrito"
        else:
            como = f"{_parte(r, b)} tuyo"
        lineas.append(f"  {b['label']:<16} {_n(b['earned_points']):>7} / {b['max_points']:<3}  {como}")
    return "\n".join(lineas)


def cmd_estado(a):
    p = _proyecto(a.carpeta)
    trabajando = ponerse_al_dia(p) == "trabajando"
    r = _resumen(p)
    if getattr(a, "json", False):
        r["colaborador_trabajando"] = trabajando
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return
    print(f"AWAP local — {r['project'].get('title', '')}")
    print(f"HAS: {_n(r['has'])}/100 — {r['interpretacion']}")
    if trabajando:
        print("(Hay un colaborador con el trabajo abierto: lo que está escribiendo se anotará cuando termine. Si se "
              "quedó a medias, se da por terminado cuando lleve 45 minutos sin trabajar: pide entonces el estado antes "
              "de ponerte a escribir, porque lo que cambie hasta ese momento contará como de la IA.)")
    print(f"Eventos: {r['eventos']} · Sesiones con colaboradores: {r['sesiones']} · "
          f"Documentos que cuentan: {len(r['documentos'])}")
    if r["baseline"]["declared"]:
        print(f"Parte de un manuscrito previo declarado ({r['baseline']['words']} palabras).")
    elif r["previos"]:
        # Solo se invita a lo que `--base` va a aceptar: un manuscrito entero tuyo que ya estaba antes
        # de que trabajase la IA (UAT, 2-oct: invitaba y luego se negaba). Y con el fichero exacto: el
        # original, si el que cuenta es la versión corregida; la carpeta, si escribes por capítulos.
        cual = r["previos"][0]
        if len(r["previos"]) > 1:
            carpetas = {os.path.dirname(x) for x in r["previos"]}
            cual = os.path.join(p.raiz, carpetas.pop()) if len(carpetas) == 1 else p.raiz
        print("No hay manuscrito previo declarado. Si el manuscrito lo escribiste tú antes de usar HumanInk, "
              f"decláralo: es lo que acredita la concepción del libro.\n  /humanink:auditor \"{p.raiz}\" --base \"{cual}\"")
    if not any(d["tipo"] == "draft" for d in r["documentos"]) and not r["baseline"]["declared"]:
        # (UAT, 2-oct.) Un HAS a cero sin una palabra de por qué: el manuscrito está en la carpeta,
        # pero su nombre no dice qué es y solo lo avisaba el --init.
        evs_ = p.eventos()
        cands = candidatos(p, documentos(evs_))
        if cands:
            print("\nNo hay ningún manuscrito en la cuenta, y por eso la nota es tan baja: por el nombre del fichero no "
                  "he reconocido cuál es. Por tamaño, podría ser:")
            for rel, n in cands:
                print(f"  · {rel}  ({n} palabras)")
            rel, n = cands[0]
            if previo_suelto(p, evs_, rel, n)[0]:
                print("Si es tu manuscrito y lo escribiste antes de usar HumanInk, decláralo:\n"
                      f"  /humanink:auditor \"{p.raiz}\" --base \"{rel}\"")
            else:
                print("Si es tu manuscrito y lo has escrito tú, dilo:\n"
                      f"  /humanink:auditor \"{p.raiz}\" --mine \"{rel}\"")
        elif not r["documentos"]:
            print("\nTodavía no hay ningún documento del libro en la cuenta (manuscrito, premisa, biblia, escaleta…).")
    # El aviso sale UNA vez por cada cambio sin atribuir; después queda en el informe, sin alarma.
    cache = _leer_json(p.f_cache, {}) or {}
    ya = set(cache.get("avisados", []))
    ultimos = {e["document"]: e["seq"] for e in p.eventos() if e.get("attribution") == "incierto" and e.get("document")}
    nuevos = [rel for rel in r["inciertos"] if ultimos.get(rel) not in ya]
    # Cuando cambia la versión que cuenta, se dice UNA vez (UAT, 2-oct: corregir una errata en una
    # versión vieja la ponía a contar y nadie avisaba).
    ya_r = set(cache.get("retomas", []))
    for x in r["retomas"]:
        if x["seq"] not in ya_r:
            print(f"Ahora cuenta «{x['document']}» y no «{x['de']}»: es la última versión en la que se ha escrito. "
                  f"Si la buena es «{x['de']}», escribe en ella (basta una palabra) y volverá a contar.")
    if any(x["seq"] not in ya_r for x in r["retomas"]):
        cache["retomas"] = sorted(ya_r | {x["seq"] for x in r["retomas"]})
        try:
            _guardar_json(p.f_cache, cache)
        except OSError:
            pass
    if r["atras"]:
        print(f"Hay {pl(len(r['atras']), 'versión dejada', 'versiones dejadas')} atrás con más texto de la IA que la "
              "que cuenta (en el informe).")
    if r["inciertos"] and not nuevos:
        print(pl(len(r["inciertos"]), "documento tiene", "documentos tienen") + " cambios sin atribuir de antes (están en el informe).")
    if nuevos:
        cache["avisados"] = sorted(ya | {ultimos[rel] for rel in nuevos})
        try:
            _guardar_json(p.f_cache, cache)
        except OSError:
            pass
        print(f"⚠️ En {pl(len(nuevos), 'documento', 'documentos')} hay cambios sin atribuir: el registro no ha podido saber "
              "si eran tuyos o de la IA, y los cuenta como de la IA. Solo esos cambios, no el documento entero.")
        for rel in nuevos:
            print(f"   · {rel} — {r['motivos'].get(rel) or 'sin atribución segura'}")
        print("   El resto del documento cuenta como estaba. Si un documento ENTERO lo has escrito tú, se puede "
              "declarar con --mine \"<fichero>\"; pero eso lo declara entero, también lo que hubiera de la IA.")
    if not r["cadena_integra"]:
        print(f"⚠️ El registro no cuadra a partir de la línea {r['linea_rota']}: alguien lo ha editado a mano.")


def cmd_nota(a):
    p = _proyecto(a.carpeta)
    trabajando = ponerse_al_dia(p) == "trabajando"
    r = _resumen(p)
    print(f"HAS: {_n(r['has'])}/100 — {r['interpretacion']}")
    if trabajando:
        print("(Hay un colaborador con el trabajo abierto: lo que está escribiendo se anotará cuando termine. Si se "
              "quedó a medias, se da por terminado cuando lleve 45 minutos sin trabajar: pide entonces el estado antes "
              "de ponerte a escribir, porque lo que cambie hasta ese momento contará como de la IA.)")


def cmd_informe(a):
    p = _proyecto(a.carpeta)
    trabajando = ponerse_al_dia(p) == "trabajando"
    r = _resumen(p)
    print(f"AWAP local — informe de «{r['project'].get('title', '')}»\n")
    if trabajando:
        print("(Hay un colaborador con el trabajo abierto: lo que está escribiendo se anotará cuando termine. Si se "
              "quedó a medias, se da por terminado cuando lleve 45 minutos sin trabajar: pide entonces el estado antes "
              "de ponerte a escribir, porque lo que cambie hasta ese momento contará como de la IA.)")
    print(f"HAS: {_n(r['has'])}/100 — {r['interpretacion']}\n")
    print("Por niveles (obtenido / máximo):")
    print(_pinta_niveles(r))
    if r["baseline"]["declared"]:
        print(f"\nManuscrito previo declarado: {r['baseline']['words']} palabras "
              f"({fecha(r['baseline']['declared_at'] or '')}).")
    print("\nDocumentos que cuentan:")
    if not r["documentos"]:
        print("  (ninguno todavía)")
    for d in r["documentos"]:
        if d["de_base"] and d["tipo"] != "draft":
            de = "lo redactó la IA a partir de tu manuscrito: la concepción se te acredita" \
                 + (" (por declaración tuya)" if d["atribucion"] == "declarado" else "")
        else:
            de = f"{pct(d['humanas'], d['palabras'])} tuyo ({_COMO.get(d['atribucion'], d['atribucion'])})"
        print(f"  · {d['document']} — {NOMBRE_TIPO.get(d['tipo'], d['tipo'])}, {d['palabras']} palabras, {de}")
    sin_rastro = [d["document"] for d in r["documentos"] if d["tipo"] != "draft" and not d["de_base"]
                  and d["parte_humana"] < 1 and r["baseline"]["declared"]]
    if sin_rastro:
        print("\nSi alguno de estos lo redactó la IA A PARTIR de tu manuscrito (" + ", ".join(sin_rastro) + "), el "
              "registro no ha encontrado el rastro (nombres propios o frases del manuscrito). Puedes declararlo:\n"
              f"  /humanink:auditor \"{p.raiz}\" --from-manuscript \"<fichero>\"")
    if r["colaboradores"]:
        print("\nColaboradores que han trabajado: "
              + ", ".join(f"{k} ×{v}" for k, v in sorted(r["colaboradores"].items())))
    if r["sin_cerrar"]:
        print(f"Sesiones de colaborador que no se cerraron bien: {r['sin_cerrar']} (lo que cambió en ellas cuenta "
              "como generado).")
    print(f"\nPalabras de la IA en los documentos que cuentan: {r['palabras_ia']} de {r['palabras']}")
    if r["fuera_de_sesion"]["veces"]:
        print(f"De lo que la IA ha escrito en el libro, {r['fuera_de_sesion']['palabras']} palabras fueron fuera de un "
              "colaborador de HumanInk (una orden directa en la conversación), en "
              f"{pl(r['fuera_de_sesion']['veces'], 'ocasión', 'ocasiones')}.")
    print(f"Palabras tuyas nuevas desde que hay registro (en todos los ficheros): {r['palabras_tuyas_despues']}")
    if r["atras"]:
        print("\nVersiones que has dejado atrás (siguen en la carpeta, pero cuenta otra versión del mismo texto):")
        for x in r["atras"]:
            print(f"  · {x['document']} — {x['palabras']} palabras, {x['palabras_ia']} de la IA; cuenta «{x['cuenta']}»")
    if r["declaraciones"]:
        print("\nPor declaración tuya (no medido):")
        for d in r["declaraciones"]:
            print(f"  · {d['document']} — {d['que']} ({fecha(d['fecha'] or '')})"
                  + (" — contradice lo medido" if d["contradice"] else
                     " — sobre texto que el registro contaba como de la IA" if d.get("sobre_ia") else ""))
    print(f"\nRegistro: {r['eventos']} eventos, del {fecha(r['primer_evento'] or '')} al "
          f"{fecha(r['ultimo_evento'] or '')}. "
          + ("Nadie lo ha tocado a mano." if r["cadena_integra"] else f"NO cuadra a partir de la línea {r['linea_rota']}."))


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
           "document_copied": "copia o cambio de nombre", "seen_at_start": "lo que ya había en la carpeta",
           "baseline_link": "sale de tu manuscrito",
           "ai_wrote_untyped": "texto de la IA en ficheros que aún no cuentan"}
    for e in evs:
        t = e.get("event_type")
        linea = f"{e.get('seq'):>4}  {fecha(e.get('timestamp', ''), hora=True)}  {que.get(t, t)}"
        quien = colaborador(e.get("collaborator"), e.get("collaborator_name")) if e.get("collaborator") else ""
        if t == "collaborator_run":
            # Los documentos del libro, aparte de los ficheros de trabajo (informes, notas), que no
            # cuentan (UAT, 2-oct: «2 fichero(s)» cuando el coach había escrito un documento).
            hechos = e.get("produced") or []
            docs_ = sum(1 for x in hechos if "sha" not in x)
            otros_ = len(hechos) - docs_
            partes = ([pl(docs_, "documento del libro", "documentos del libro")] if docs_ else []) \
                + ([pl(otros_, "fichero de trabajo, que no cuenta", "ficheros de trabajo, que no cuentan")] if otros_ else [])
            linea += f": {quien} — " + (" y ".join(partes) if partes else "sin cambios en el libro")
        elif t == "ai_wrote_untyped":
            linea += f": {pl(len(e.get('produced') or []), 'fichero de trabajo', 'ficheros de trabajo')}" \
                     + (f", {quien}" if quien else "")
        elif t == "seen_at_start":
            linea += f": {pl(len(e.get('seen') or []), 'fichero cuyo nombre no dice qué es', 'ficheros cuyo nombre no dice qué son')}"
        elif t == "baseline_declared":
            linea += ": " + ("la carpeta del libro" if e.get("document") == "." else str(e.get("document"))) \
                     + f" ({e.get('baseline_words', 0)} palabras previas)"
        elif e.get("document") and e.get("attribution") == "preexistente" and t in ESCRITURAS:
            # Lo que había al abrir el registro no es un «cambio tuyo» de hoy (UAT: 40 líneas de
            # «cambio tuyo: NEMI-b20.docx (+450 palabras tuyas)» con la fecha de abrir el registro).
            linea = linea[:linea.rindex("  ") + 2] + f"ya estaba al abrir el registro: {e['document']} ({e.get('words', 0)} palabras)"
        elif e.get("document"):
            linea += f": {e['document']}"
            if t == "text_generated" and not e.get("tokens_generated"):
                # «+0 palabras de la IA» de un Word que sale de un texto ya anotado no decía nada.
                linea = linea[:linea.rindex("  ") + 2] + f"guardado sin palabras nuevas: {e['document']} (lo que lleva ya estaba anotado)"
            elif t == "text_generated":
                linea += f" (+{e.get('tokens_generated', 0)} palabras de la IA" \
                         + (", fuera de un colaborador" if e.get("collaborator") == "(fuera de sesión)"
                            else f", {quien}" if quien else "") \
                         + (", sin atribución segura" if e.get("attribution") == "incierto" else "") + ")"
            elif t == "text_revised":
                # «+0 palabras tuyas» al deshacer 45 correcciones de la IA no decía nada.
                n_, s_, b_ = e.get("tokens_revised_by_human", 0), e.get("ai_words_replaced_by_human", 0), \
                    e.get("ai_words_deleted_by_human", 0)
                cosas = (["+" + pl(n_, "palabra tuya", "palabras tuyas")] if n_ else [] if (s_ or b_) else ["sin palabras nuevas: texto que ya estaba anotado"]) \
                    + ([f"{s_} de la IA sustituidas por texto tuyo"] if s_ else []) \
                    + ([f"{b_} de la IA borradas"] if b_ else [])
                linea += " (" + ", ".join(cosas) + ")"
            elif e.get("words") is not None:
                linea += f" ({e['words']} palabras)"
        print(linea)


def huellas_anotadas(p):
    """La huella que el registro anotó para el texto guardado de cada documento: {ruta: huella}."""
    anotada = {}
    for e in p.eventos():
        if e.get("document") and e.get("snapshot_hash"):
            anotada[e["document"]] = e["snapshot_hash"]
        for x in (e.get("produced") or []) + (e.get("seen") or []):
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
        out.append(f"Falta el texto guardado de {pl(len(sin_texto), 'documento', 'documentos')} ({', '.join(sin_texto[:5])}"
                   + ("…" if len(sin_texto) > 5 else "") + "): alguien ha borrado parte de .awap/local/textos. "
                   "Sin él no se puede medir qué cambia, y lo que cambie contará como incierto.")
    # Y que cada texto guardado sea el que se anotó: mismas palabras, mismas marcas.
    tocadas, borradas = [], []
    for rel, h in huellas_anotadas(p).items():
        snap = p.instantanea(rel)
        if snap is None:
            if rel not in sin_texto:
                borradas.append(rel)        # también los ficheros sin tipo que escribió la IA
        elif p.huella_texto(snap.get("p", []), snap.get("f", [])) != h:
            tocadas.append(rel)
    if borradas:
        out.append(f"Falta el texto guardado de {pl(len(borradas), 'fichero', 'ficheros')} que el registro anotó ({', '.join(borradas[:5])}"
                   + ("…" if len(borradas) > 5 else "") + "): alguien lo ha borrado de .awap/local/textos. Sin él, "
                   "ese texto puede volver a entrar como tuyo.")
    if tocadas:
        out.append(f"El texto guardado de {pl(len(tocadas), 'documento', 'documentos')} no es el que se anotó ({', '.join(tocadas[:5])}"
                   + ("…" if len(tocadas) > 5 else "") + "): está manipulado, o a medio escribir. Mira el estado "
                   "una vez más; si sigue saliendo, alguien ha editado .awap/local/textos a mano.")
    debe_h = sum(e.get("own_words_archived", 0) for e in p.eventos())
    hay_h = p.en_archivo("H")
    if hay_h < debe_h:
        out.append(f"Falta parte del archivo de lo que era tuyo y salió de algún documento (.awap/local/textos/"
                   f"_ia.jsonl.gz): el registro anotó {debe_h} palabras y hay {hay_h}. Sin él, volver a poner ese texto "
                   "contaría como haber revisado a la IA.")
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
        cuando = fecha(cert.get("emitido", ""))
        if igual and integra:
            print(f"✓ El último certificado ({cuando}) sale de este registro.")
        elif igual:
            print(f"✗ El último certificado ({cuando}) se emitió sobre este registro, pero el registro ya no cuadra.")
        else:
            print(f"✗ El último certificado ({cuando}) NO corresponde a este registro.")
    for falta in faltas(p):
        print("✗ " + falta)
        integra = False
    cambiados = []
    en_disco = ficheros(p.raiz)
    for rel, d in cabezas(documentos(p.eventos())).items():
        if rel in en_disco and _sha_fichero(os.path.join(p.raiz, rel)) != d["sha"]:
            cambiados.append(rel)
    if cambiados:
        print(f"  {pl(len(cambiados), 'documento ha', 'documentos han')} cambiado desde la última anotación: se anotará "
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
            if unicodedata.combining(c):       # una tilde suelta no ocupa: va sobre la letra anterior
                continue
            base = unicodedata.normalize("NFKD", c)[0]
            total += _ANCHOS.get(ord(base), 556)
        return total * tam / 1000 * (1.06 if fuente == "F2" else 1)

    @staticmethod
    def _esc(s):
        # Lo que no existe en la codificación del PDF (una «Ł») va con su letra base, no con «?».
        # Las tildes, juntas con su letra: un nombre de fichero las trae por separado («A» + «´») y la
        # tilde suelta no existe en la codificación del PDF: salía «A?ngel» (UAT, 2-oct-2026). Y una
        # marca que aun así quede suelta se quita, no se cambia por una interrogación.
        s = "".join(c for c in unicodedata.normalize("NFC", s) if not unicodedata.combining(c))
        s = "".join(c if c.encode("cp1252", "ignore") else
                    (unicodedata.normalize("NFKD", c).encode("cp1252", "ignore").decode("cp1252")
                     or {"Ł": "L", "ł": "l", "Đ": "D", "đ": "d"}.get(c, "?")) for c in s)
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
    if ponerse_al_dia(p) == "trabajando":
        sys.exit(_ESPERA)
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
            "palabras": r["palabras"], "palabras_ia": r["palabras_ia"], "fuera_de_sesion": r["fuera_de_sesion"],
            "versiones_dejadas_atras": r["atras"], "previo_por": r["previo_por"],
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
            como = "Sin documento" if b["level"] != 6 else (
                "Lo que había de la IA, el autor lo ha declarado suyo" if r.get("declarado_de_ia")
                else "La IA no ha escrito en el manuscrito")
        elif b["level"] == 6:
            rv = r.get("revision")
            cuanto = pct(rv["sustituidas"], rv["de"]) if rv else pct(b["average_revision_ratio"], 1)
            como = f"El autor ha sustituido el {cuanto} de lo que metió la IA"
        elif b.get("partial_baseline"):
            como = f"Por el manuscrito previo, al {round(b['average_revision_ratio'] * 100)} %"
        elif b.get("from_manuscript"):
            como = "Redactado por la IA a partir del manuscrito del autor"
        else:
            como = f"{_parte(r, b)} de las palabras son del autor"
        d.fila([b["label"], b["max_points"], _n(b["earned_points"]), como], xs)
    d.espacio(8)

    if r["baseline"]["declared"]:
        d.reserva(70)
        d.texto("Manuscrito previo", 11, "F2", 0.05, tras=2)
        d.texto(f"El autor declaró el {fecha(r['baseline']['declared_at'] or '')} un manuscrito de "
                f"{r['baseline']['words']} palabras, escrito antes de usar HumanInk. La puntuación parte "
                "de esa declaración: la concepción del libro se le acredita porque el manuscrito la demuestra"
                + (f", en un {round((r['factor_base'] or 0) * 100)} %: sus palabras son pocas para el libro actual."
                   if (r["factor_base"] or 0) < 1 else ".")
                + (" Que ya existía antes de que la IA trabajase en el libro consta solo por la fecha del fichero."
                   if r.get("previo_por") == "la fecha del fichero" else ""), 9)
        d.texto(str(r["baseline"]["manuscript_hash"] or ""), 7, "F3", 0.35, tras=8)

    d.reserva(70)
    d.texto("Documentos que cuentan", 11, "F2", 0.05, tras=4)
    xs = [56, 262, 322, 377, 422]
    d.fila(["Documento", "Tipo", "Palabras", "Del autor", "Cómo se sabe"], xs, 8, "F2", 0.4)
    for doc in r["documentos"]:
        if doc["de_base"] and doc["tipo"] != "draft":
            tuyo = "—"
            como = "declarado: del manuscrito" if doc["atribucion"] == "declarado" else "la IA, del manuscrito"
        else:
            tuyo = pct(doc["humanas"], doc["palabras"])
            como = {"incierto": "sin atribuir: como IA", "declarado": "declarado por el autor"}.get(
                doc["atribucion"], _COMO.get(doc["atribucion"], doc["atribucion"]))
        d.fila([doc["document"], NOMBRE_TIPO.get(doc["tipo"], doc["tipo"]), doc["palabras"], tuyo, como], xs)
    d.espacio(4)
    d.texto(f"Palabras de la IA en estos documentos: {r['palabras_ia']} de {r['palabras']}."
            + (f" De lo que la IA ha escrito en el libro, {r['fuera_de_sesion']['palabras']} palabras fueron fuera de "
               "un colaborador de HumanInk (una orden directa en la conversación), en "
               f"{pl(r['fuera_de_sesion']['veces'], 'ocasión', 'ocasiones')}."
               if r["fuera_de_sesion"]["veces"] else ""), 9, tras=8)

    if r["atras"]:
        d.reserva(50)
        d.texto("Versiones dejadas atrás", 11, "F2", 0.05, tras=2)
        d.texto("En la carpeta hay versiones con más texto de la IA que la que cuenta, porque cuenta otra versión "
                "del mismo texto: " + "; ".join(f"{x['document']} ({x['palabras_ia']} palabras de la IA de "
                                                    f"{x['palabras']}; cuenta {x['cuenta']})" for x in r["atras"][:8])
                + ("…" if len(r["atras"]) > 8 else "") + ". Este certificado vale para las versiones que cuentan.", 9, tras=8)
    if r["colaboradores"]:
        d.reserva(50)
        d.texto("Colaboradores de HumanInk que han trabajado", 11, "F2", 0.05, tras=2)
        d.texto(", ".join(f"{k} ×{v}" for k, v in sorted(r["colaboradores"].items()))
                + ". Funcionan sobre Claude, de Anthropic.", 9, tras=8)

    if r["declaraciones"]:
        d.reserva(50)
        d.texto("Por declaración del autor (no medido)", 11, "F2", 0.05, tras=2)
        for x in r["declaraciones"]:
            d.texto(f"· {x['document']} — {x['que']} ({fecha(x['fecha'] or '')})"
                    + (" — contradice lo que había medido el registro" if x["contradice"] else
                       " — sobre texto que el registro contaba como de la IA" if x.get("sobre_ia") else ""), 9)
        d.espacio(8)
    if r["inciertos"]:
        d.reserva(50)
        d.texto("Sin atribución segura", 11, "F2", 0.05, tras=2)
        d.texto("Cambios que no se han podido atribuir con seguridad y cuentan como generados por la IA: "
                + "; ".join(f"{x} ({r['motivos'].get(x) or 'sin atribución segura'})" for x in r["inciertos"]) + ".",
                9, tras=8)

    d.reserva(150)
    d.texto("Qué acredita este documento, y qué no", 11, "F2", 0.05, tras=2)
    d.texto(f"Acredita el proceso registrado en la carpeta del libro desde el {fecha(r['primer_evento'] or '')}: "
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
    d.texto(f"Registro: {r['eventos']} eventos, del {fecha(r['primer_evento'] or '')} al "
            f"{fecha(r['ultimo_evento'] or '')} · Emitido el {fecha(cert['emitido'], hora=True)} · Fórmula {VERSION_HAS}",
            8, "F1", 0.3)
    d.texto("Huella del registro", 8, "F2", 0.3)
    d.texto(str(r["huella_registro"]), 7, "F3", 0.3)
    d.texto("Huella del certificado", 8, "F2", 0.3)
    d.texto(cert["huella_certificado"], 7, "F3", 0.3)

    # Con la fecha y la hora de aquí: dos certificados del mismo día no se pisan.
    salida = a.salida or os.path.join(
        p.raiz, f"Certificado AWAP (borrador) {fecha(cert['emitido'], hora=True).replace(':', '.')}.pdf")
    salida = os.path.abspath(os.path.expanduser(salida))
    with open(salida, "wb") as f:
        f.write(d.bytes(f"{titulo if len(titulo) <= 60 else titulo[:57] + '…'} · certificado AWAP, borrador local"))
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
    s.add_argument("--tipo", choices=tuple(k for k in NIVEL_DE if k != "revision"))
    s.add_argument("--confirmo", action="store_true"); s.set_defaults(f=cmd_declarar)
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
    for nombre in ("antes", "despues", "escrito"):
        s = sub.add_parser(nombre); s.add_argument("ruta"); s.set_defaults(f=cmd_gancho)
    s = sub.add_parser("fin"); s.add_argument("ruta"); s.add_argument("--colab", default="awos-unknown")
    s.add_argument("--nombre", default=""); s.add_argument("--modo", default="")
    s.add_argument("--modelo", default=""); s.set_defaults(f=cmd_fin)

    a = ap.parse_args(argv)
    if a.orden in ("antes", "despues", "escrito"):
        # Los ganchos: nunca dicen nada, nunca fallan, y cada libro al que tocan lleva su cerrojo.
        try:
            if a.ruta == "-":
                a.datos = json.load(sys.stdin)
                if not isinstance(a.datos, dict):
                    return 0
            cmd_gancho(a)
        except BaseException:
            pass
        return 0
    silenciosa = a.orden in ("inicio", "fin")
    if a.orden == "fin":
        # Cada libro que cierra, con su cerrojo. El cierre espera más que lo que tarda en caducar un
        # cerrojo muerto: si se pierde, la sesión se queda abierta.
        try:
            a.nombrada = raiz_de(a.ruta) or ""
            raices = raices_del_cierre(a.ruta)
            a.dudoso = sum(1 for r in raices if r != a.nombrada) > 1
            for raiz in raices:
                p = Proyecto(raiz)
                if not p.cerrar_paso(float(os.environ.get("AWAP_ESPERA") or CERROJO_VIEJO + 15)):
                    continue
                try:
                    a.raiz = raiz
                    cmd_fin(a)
                except BaseException:
                    pass
                finally:
                    p.abrir_paso()
        except BaseException:
            pass
        return 0
    # Una sola orden escribe en el registro a la vez: un gancho y un colaborador pueden coincidir.
    cerrojo = None
    if a.orden not in ("registro", "verificar", "iniciar"):
        raiz = raiz_de(getattr(a, "carpeta", None) or getattr(a, "ruta", None) or ".") \
            or (raiz_de(a.fichero) if getattr(a, "fichero", None) else None)
        if raiz:
            cerrojo = Proyecto(raiz)
            if not cerrojo.cerrar_paso(float(os.environ.get("AWAP_ESPERA") or 20)):
                cerrojo = None       # no es nuestro: no se toca al salir
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
            import errno
            por = {errno.EACCES: "no hay permiso", errno.EPERM: "no hay permiso", errno.EROFS: "es de solo lectura",
                   errno.ENOSPC: "el disco está lleno"}.get(e.errno, e.strerror or str(e))
            sys.exit(f"No puedo escribir en la carpeta del libro ({por}). Mira que esté conectada a la "
                     "conversación con permiso de escritura y que no sea de solo lectura.")
        return 0
    finally:
        if cerrojo:
            cerrojo.abrir_paso()


if __name__ == "__main__":
    # La salida, siempre en UTF-8: Windows la escribe en cp1252 y un «→» tumba el script (ver scripts/ooxml/_utf8.py).
    for _flujo in (sys.stdin, sys.stdout, sys.stderr):
        getattr(_flujo, "reconfigure", lambda **_: None)(encoding="utf-8", errors="backslashreplace")
    sys.exit(main())
