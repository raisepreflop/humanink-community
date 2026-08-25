#!/usr/bin/env python3
"""quickcheck.py — Monitor mecánico de AWOS (Capa 1: silencioso, sin LLM, sin tokens).

Principios de diseño AWOS: los scripts CUENTAN, los agentes JUZGAN. Este script
nunca bloquea (exit 0 siempre) y cada aviso lleva localización exacta (línea) y,
donde aplica, una propuesta — material para que el colaborador pertinente lo
comunique como consejo profesional ignorable (Capa 2).

Chequeos sobre un capítulo:
  INTEGRIDAD    bytes NUL, UTF-8 inválido (única voz técnica permitida)
  PLACEHOLDERS  [TBD], [PENDIENTE], {{...}}, <<...>>, XXX — con línea
  ANÁFORA       3+ frases seguidas con el mismo arranque — con línea
  TIPOGRAFÍA    exceso de rayas/exclamaciones por 1000 palabras — líneas top
  PROHIBIDAS    estilo/prohibidas.md evolutiva [VIGILADA]→[DURA]→[RETIRADA] — con líneas
  CANON         deriva de nombres (entity-canon.md, distancia ≤2) y recurrentes
                sin registrar — con líneas
  PATRONES IA   muletillas IA vía patterns.py (motor iParser) — top con líneas
  ESCALETA      monitor: capítulos escritos > capítulos en escaleta → DERIVA

Modos adicionales:
  --voz                          ledger de huella de voz (.awos/voz-ledger.csv) + deriva
  --checkpoint COLAB "ACCIÓN" [ARTEFACTO]
                                 appendea fila al project-checkpoint.md del proyecto
                                 verificando en disco el artefacto (patrón Write→ls→Yes)

Uso:
  python3 quickcheck.py capitulo.md [--voz] [--quiet]
  python3 quickcheck.py --checkpoint awos-escritor "cap-07 v2 escrito" ruta/cap-07-v2.docx [--root proyecto]
"""
from __future__ import annotations

import bisect
import csv
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

try:
    from patterns import scan_text  # iParser: 100+ patrones IA en español
    from metrics import (
        _tokenize_words, _split_sentences, type_token_ratio,
        sentence_stats, burstiness,
    )
except Exception:  # pragma: no cover — el monitor jamás rompe la sesión
    scan_text = None

PLACEHOLDER_RE = re.compile(
    r"\[(?:TBD|PENDIENTE|TODO|FIXME|COMPLETAR)\]|\{\{[^}]{0,60}\}\}|<<[^>]{0,60}>>|\bXXX+\b",
    re.IGNORECASE,
)
MARCAS_PROYECTO = ("capitulos", "biblia.docx", "biblia.md", "escaleta.docx",
                   "escaleta.md", "estilo", ".awap")


# ───────────────────────── utilidades de proyecto ─────────────────────────

def project_root(path: Path) -> Path:
    for parent in [path.parent, *path.parent.parents]:
        try:
            names = {p.name for p in parent.iterdir()}
        except OSError:
            break
        if names & set(MARCAS_PROYECTO):
            return parent
        if parent == Path.home():
            break
    return path.parent


def _line_starts(text: str) -> list[int]:
    starts = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            starts.append(i + 1)
    return starts


def _line_of(offset: int, starts: list[int]) -> int:
    return bisect.bisect_right(starts, offset)


def _lineas_de(term: str, low_text: str, starts: list[int], maxn: int = 3) -> str:
    """Devuelve 'L12, L40' para las primeras apariciones de term."""
    out, start = [], 0
    tl = term.lower()
    while len(out) < maxn:
        i = low_text.find(tl, start)
        if i < 0:
            break
        lin = f"L{_line_of(i, starts)}"
        if lin not in out:
            out.append(lin)
        start = i + len(tl)
    return ", ".join(out)


def cargar_banlist(root: Path) -> tuple[list[str], list[str]]:
    """estilo/prohibidas.md evolutiva. Línea sin prefijo = [DURA]. Devuelve (duras, vigiladas)."""
    duras: list[str] = []
    vigiladas: list[str] = []
    for cand in (root / "estilo" / "prohibidas.md", root / "prohibidas.md"):
        if not cand.is_file():
            continue
        try:
            lines = cand.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return [], []
        for ln in lines:
            t = ln.strip().lstrip("-* ").strip()
            if not t or t.startswith("#"):
                continue
            up = t.upper()
            if up.startswith("[RETIRADA]"):
                continue
            if up.startswith("[VIGILADA]"):
                vigiladas.append(t[t.index("]") + 1:].strip())
            elif up.startswith("[DURA]"):
                duras.append(t[t.index("]") + 1:].strip())
            else:
                duras.append(t)
        break
    return duras, vigiladas


def cargar_canon(root: Path) -> dict[str, set[str]]:
    """entity-canon.md (nombre del design-doc; canon.md como legado): tabla |Nombre|Alias|…|."""
    canon: dict[str, set[str]] = {}
    for cand in (root / "entity-canon.md", root / "canon.md",
                 root / "estilo" / "entity-canon.md", root / "estilo" / "canon.md"):
        if not cand.is_file():
            continue
        try:
            lines = cand.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return {}
        for ln in lines:
            if not ln.strip().startswith("|"):
                continue
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if not cells or not cells[0] or set(cells[0]) <= {"-", " ", ":"}:
                continue
            if cells[0].lower() in ("nombre canónico", "nombre", "canónico", "entidad"):
                continue
            alias = set()
            if len(cells) > 1 and cells[1] and cells[1] not in ("—", "-"):
                alias = {a.strip() for a in re.split(r"[,;·]", cells[1]) if a.strip()}
            canon[cells[0]] = alias
        break
    return canon


def _edit1(a: str, b: str) -> bool:
    """True si a≠b y distancia de edición ≤ 2 (deriva tipo Matías→Matias)."""
    if a == b:
        return False
    la, lb = len(a), len(b)
    if abs(la - lb) > 2 or min(la, lb) < 4:
        return False
    prev = list(range(lb + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        if min(cur) > 2:
            return False
        prev = cur
    return prev[lb] <= 2


# ───────────────────────────── chequeo principal ─────────────────────────────

def chequear(path: Path, quiet: bool) -> list[str]:
    avisos: list[str] = []
    raw = path.read_bytes()

    # INTEGRIDAD
    if b"\x00" in raw:
        avisos.append("INTEGRIDAD: el fichero contiene bytes NUL (posible corrupción de escritura)")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        avisos.append("INTEGRIDAD: el fichero no es UTF-8 válido")
        text = raw.decode("utf-8", errors="replace")

    starts = _line_starts(text)
    low = text.lower()
    words = _tokenize_words(text) if scan_text else re.findall(r"\w+", low)
    n_words = max(len(words), 1)

    # PLACEHOLDERS (con línea)
    ph = [(m.group(0), _line_of(m.start(), starts)) for m in PLACEHOLDER_RE.finditer(text)]
    if ph:
        muestra = " · ".join(f"L{l}: {p}" for p, l in ph[:4])
        avisos.append(f"PLACEHOLDERS: {len(ph)} sin resolver — {muestra}"
                      " → sustituir antes de cerrar el capítulo")

    # ANÁFORA (3+ frases seguidas mismo arranque, con línea del inicio de la racha)
    sent_iter = [(m.group(0), m.start()) for m in
                 re.finditer(r"[^.!?…\n]+[.!?…]?", text) if m.group(0).strip()]
    arranques = []
    for s, off in sent_iter:
        m = re.match(r"\W*([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)", s)
        arranques.append(((m.group(1).lower() if m else ""), off))
    racha, peor, peor_pal, peor_off = 1, 1, "", 0
    for i in range(1, len(arranques)):
        if arranques[i][0] and arranques[i][0] == arranques[i - 1][0]:
            racha += 1
            if racha > peor:
                peor, peor_pal = racha, arranques[i][0]
                peor_off = arranques[i - racha + 1][1]
        else:
            racha = 1
    if peor >= 3:
        avisos.append(f"ANÁFORA L{_line_of(peor_off, starts)}: {peor} frases seguidas "
                      f"empiezan por «{peor_pal}» → variar arranques o fusionar frases")

    # TIPOGRAFÍA (con las primeras líneas afectadas)
    rayas = text.count("—") + text.count("--")
    excl = text.count("!")
    if rayas / n_words * 1000 > 12:
        avisos.append(f"TIPOGRAFÍA ({_lineas_de('—', text, starts)}…): {rayas} rayas "
                      f"({rayas / n_words * 1000:.0f}/1000 palabras) → revisar abuso de incisos")
    if excl / n_words * 1000 > 8:
        avisos.append(f"TIPOGRAFÍA ({_lineas_de('!', text, starts)}…): {excl} exclamaciones "
                      f"({excl / n_words * 1000:.0f}/1000 palabras)")

    # PROHIBIDAS / EN VIGILANCIA (con líneas)
    root = project_root(path)
    duras, vigiladas = cargar_banlist(root)
    f_duras = [f"«{t}»×{low.count(t.lower())} ({_lineas_de(t, low, starts)})"
               for t in duras if low.count(t.lower())]
    if f_duras:
        avisos.append("PROHIBIDAS: " + ", ".join(f_duras[:5]) + " → sustituir (lista del autor)")
    f_vig = [f"«{t}»×{low.count(t.lower())} ({_lineas_de(t, low, starts)})"
             for t in vigiladas if low.count(t.lower())]
    if f_vig:
        avisos.append("EN VIGILANCIA: " + ", ".join(f_vig[:5]))

    # CANON (deriva y no-registrados, con líneas)
    canon = cargar_canon(root)
    if canon:
        validos = set()
        for nombre, alias in canon.items():
            validos.update(w.lower() for w in nombre.split())
            for a in alias:
                validos.update(w.lower() for w in a.split())
        candidatos: dict[str, list[int]] = {}
        for m in re.finditer(r"(?<![.!?…»\"]\s)(?<![—¡¿])(?<!^)\b([A-ZÁÉÍÓÚÑ][a-záéíóúüñ]{3,})\b", text):
            candidatos.setdefault(m.group(1), []).append(m.start())
        derivas, desconocidos = [], []
        for w, offs in candidatos.items():
            wl = w.lower()
            if wl in validos:
                continue
            _ls = []
            for o in offs:
                _l = f"L{_line_of(o, starts)}"
                if _l not in _ls:
                    _ls.append(_l)
                if len(_ls) >= 3:
                    break
            lin = ", ".join(_ls)
            cerca = next((v for v in sorted(validos, key=len, reverse=True)
                          if _edit1(wl, v)), None)
            if cerca:
                derivas.append(f"«{w}» ({lin}) → ¿unificar con «{cerca.capitalize()}»?")
            elif len(offs) >= 3:
                desconocidos.append(f"«{w}»×{len(offs)} ({lin})")
        if derivas:
            avisos.append("CANON deriva de nombre: " + " · ".join(derivas[:4]))
        if desconocidos:
            avisos.append("CANON sin registrar: " + ", ".join(desconocidos[:4])
                          + " → añadir a entity-canon.md (/awos-coach --biblia-delta)")

    # PATRONES IA (top con líneas)
    if scan_text is not None:
        hits = scan_text(text)
        dens = len(hits) / n_words * 1000
        if hits and dens > 2.0:
            top: dict[str, list[int]] = {}
            for h in hits:
                top.setdefault(h["description"], []).append(h.get("start", 0))
            ejemplos = " · ".join(
                f"{k}×{len(v)} ({', '.join(f'L{_line_of(o, starts)}' for o in v[:2])})"
                for k, v in sorted(top.items(), key=lambda kv: -len(kv[1]))[:3])
            avisos.append(f"PATRONES IA: {len(hits)} coincidencias ({dens:.1f}/1000) — "
                          f"{ejemplos} → /awos:awos-humanizador {path.name}")

    # ESCALETA (monitor conservador: solo deriva mecánicamente demostrable)
    esc = root / "escaleta.md"
    if esc.is_file():
        try:
            esc_caps = len(re.findall(r"^###\s*Cap\.", esc.read_text(encoding="utf-8", errors="ignore"), re.M))
            escritos = {re.sub(r"-v\d+$", "", p.stem)
                        for p in (root / "capitulos").glob("cap-*")
                        if p.suffix.lower() in (".md", ".docx", ".txt")}
            if esc_caps and len(escritos) > esc_caps:
                avisos.append(f"ESCALETA DERIVA: {len(escritos)} capítulos escritos pero la "
                              f"escaleta prevé {esc_caps} → ampliar escaleta o replantear cierre "
                              f"(/awos-coach --revision)")
        except OSError:
            pass

    if not quiet:
        if avisos:
            print(f"⚠ AWOS monitor — {path.name}:")
            for a in avisos:
                print(f"  • {a}")
        else:
            print(f"✓ AWOS monitor — {path.name}: limpio")
    return avisos


# ───────────────────────────── ledger de voz ─────────────────────────────

def registrar_voz(path: Path, quiet: bool) -> None:
    if scan_text is None:
        return
    text = path.read_text(encoding="utf-8", errors="ignore")
    words = _tokenize_words(text)
    sentences = _split_sentences(text)
    if not words or not sentences:
        return
    ttr = type_token_ratio(words)
    media, desv = sentence_stats(sentences)
    burst = burstiness(media, desv)
    lineas = [ln for ln in text.splitlines() if ln.strip()]
    dialogo = sum(1 for ln in lineas if ln.lstrip().startswith(("—", "«", '"', "“")))
    pct_dial = dialogo / max(len(lineas), 1) * 100

    root = project_root(path)
    ledger_dir = root / ".awos"
    ledger_dir.mkdir(exist_ok=True)
    ledger = ledger_dir / "voz-ledger.csv"
    campos = ["capitulo", "palabras", "ttr", "frase_media",
              "frase_desv", "burstiness", "pct_dialogo"]
    previas = []
    if ledger.exists():
        try:
            previas = [r for r in csv.DictReader(ledger.open(encoding="utf-8"))
                       if r.get("capitulo") != path.stem]
        except OSError:
            previas = []
    fila = dict(zip(campos, [path.stem, len(words), f"{ttr:.3f}", f"{media:.1f}",
                             f"{desv:.1f}", f"{burst:.3f}", f"{pct_dial:.0f}"]))
    with ledger.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        for r in previas:
            w.writerow(r)
        w.writerow(fila)

    try:
        filas = list(csv.DictReader(ledger.open(encoding="utf-8")))
    except OSError:
        return
    if len(filas) >= 4:
        prev = filas[-6:-1] if len(filas) > 5 else filas[:-1]
        def media_de(k): return sum(float(r[k]) for r in prev) / len(prev)
        act = filas[-1]
        derivas = []
        if abs(float(act["frase_media"]) - media_de("frase_media")) > media_de("frase_media") * 0.30:
            derivas.append("longitud de frase")
        if abs(float(act["ttr"]) - media_de("ttr")) > 0.08:
            derivas.append("riqueza léxica (TTR)")
        if abs(float(act["pct_dialogo"]) - media_de("pct_dialogo")) > 20:
            derivas.append("proporción de diálogo")
        if derivas and not quiet:
            print(f"⚠ DERIVA DE VOZ en {path.stem}: cambia {', '.join(derivas)} "
                  f"respecto a los {len(prev)} capítulos previos (ver .awos/voz-ledger.csv)")
    if not quiet:
        print(f"✓ Voz registrada en {ledger}")


# ─────────────────────── project-checkpoint (Capa 1) ───────────────────────

CHECKPOINT_HEADER = """<!-- schema: 1 · project-checkpoint AWOS — registro silencioso, no editar a mano -->
# Registro del proyecto

| fecha | colaborador | acción | artefacto | verificado |
|---|---|---|---|---|
"""


def checkpoint(args: list[str], quiet: bool) -> None:
    """--checkpoint COLAB "ACCIÓN" [ARTEFACTO] [--root DIR]
    Verifica el artefacto EN DISCO (patrón Write→ls→Yes) y appendea la fila."""
    root = None
    if "--root" in args:
        i = args.index("--root")
        root = Path(args[i + 1]).expanduser()
        args = args[:i] + args[i + 2:]
    colab = args[0] if args else "desconocido"
    accion = args[1] if len(args) > 1 else ""
    artefacto = args[2] if len(args) > 2 else ""

    if artefacto and root is None:
        root = project_root(Path(artefacto).expanduser())
    root = root or Path.cwd()

    verificado = "—"
    if artefacto:
        p = Path(artefacto).expanduser()
        verificado = "sí" if p.exists() and (p.is_dir() or p.stat().st_size > 0) else "NO"

    cp = root / "project-checkpoint.md"
    nuevo = not cp.exists()
    with cp.open("a", encoding="utf-8") as f:
        if nuevo:
            f.write(CHECKPOINT_HEADER)
        fecha = time.strftime("%Y-%m-%d %H:%M")
        art = Path(artefacto).name if artefacto else "—"
        f.write(f"| {fecha} | {colab} | {accion} | {art} | {verificado} |\n")
    if not quiet:
        estado = "✓" if verificado in ("sí", "—") else "⚠ artefacto NO verificado en disco"
        print(f"{estado} checkpoint: {colab} · {accion}")


# ───────────────────────────────── main ─────────────────────────────────

def main() -> int:
    args = sys.argv[1:]
    quiet = "--quiet" in args
    args = [a for a in args if a != "--quiet"]

    if args and args[0] == "--checkpoint":
        try:
            checkpoint(args[1:], quiet)
        except Exception as e:
            if not quiet:
                print(f"checkpoint: aviso interno ({e})")
        return 0

    voz = "--voz" in args
    files = [a for a in args if not a.startswith("--")]
    if not files:
        print("uso: quickcheck.py <fichero.md> [--voz] [--quiet] | --checkpoint COLAB ACCIÓN [ARTEFACTO]")
        return 0
    path = Path(files[0]).expanduser()
    if not path.is_file() or path.suffix.lower() not in (".md", ".txt", ".markdown"):
        return 0
    try:
        chequear(path, quiet)
        if voz:
            registrar_voz(path, quiet)
    except Exception as e:  # el monitor jamás rompe la sesión del escritor
        if not quiet:
            print(f"quickcheck: aviso interno ({e})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
