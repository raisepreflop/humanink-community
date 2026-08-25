#!/usr/bin/env python3
"""prose_stats.py — estilometría objetiva de un manuscrito, calculada, no estimada.

Existe porque varios colaboradores (lector profesional, editor de estilo, editor de desarrollo,
lector beta, corrector) pedían al modelo que contase a mano longitudes de frase, porcentajes de
diálogo o adverbios: trabajo determinista, caro en tokens y con margen de error. Esto lo calcula
en local y el modelo solo lo interpreta.

Uso:
    python3 prose_stats.py <fichero.md|.txt|.docx> [--json]

Salida legible por defecto; --json para encadenar.
"""
import json
import re
import statistics
import sys
from pathlib import Path

# Diálogo en español: raya (—), comillas latinas («») o inglesas ("").
_DIALOGUE_START = re.compile(r'^\s*(—|–|-\s|«|"|“)')
_SENT_SPLIT = re.compile(r'(?<=[.!?…])\s+|\n{2,}')
_WORD = re.compile(r"\b[\wáéíóúüñÁÉÍÓÚÜÑ']+\b", re.UNICODE)
# Adverbios de modo: -mente (español) y -ly (inglés), para manuscritos en cualquiera de los dos.
_ADVERB = re.compile(r"\b\w+(mente|ly)\b", re.IGNORECASE | re.UNICODE)
_PARENTHETICAL = re.compile(r"[—–(:;]|\.\.\.|…")
_CHAPTER = re.compile(r'^\s*(#{1,3}\s|cap[íi]tulo\b|chapter\b)', re.IGNORECASE | re.MULTILINE)
_SCENE_BREAK = re.compile(r'^\s*(\*\s*\*\s*\*|---|—{3,}|###)\s*$', re.MULTILINE)


def read_text(path: Path) -> str:
    if path.suffix.lower() == ".docx":
        try:
            import docx
        except ImportError:
            sys.exit("Falta python-docx para leer .docx: pip install python-docx")
        return "\n".join(p.text for p in docx.Document(str(path)).paragraphs)
    return path.read_text(encoding="utf-8", errors="ignore")


def analyze(text: str) -> dict:
    lines = [l for l in text.splitlines()]
    sentences = [s.strip() for s in _SENT_SPLIT.split(text) if s.strip()]
    lengths = [len(_WORD.findall(s)) for s in sentences]
    lengths = [n for n in lengths if n > 0]
    words = _WORD.findall(text)
    total = len(words)

    if not lengths:
        return {"error": "sin frases analizables"}

    short = sum(1 for n in lengths if n <= 8)
    long_ = sum(1 for n in lengths if n >= 25)
    medium = len(lengths) - short - long_

    dialogue_lines = sum(1 for l in lines if l.strip() and _DIALOGUE_START.match(l))
    prose_lines = sum(1 for l in lines if l.strip())

    return {
        "total_words": total,
        "sentences": len(lengths),
        "chapters": len(_CHAPTER.findall(text)),
        "scene_breaks": len(_SCENE_BREAK.findall(text)),
        "sentence_length": {
            "mean": round(statistics.mean(lengths), 1),
            "median": round(statistics.median(lengths), 1),
            "std": round(statistics.pstdev(lengths), 1) if len(lengths) > 1 else 0.0,
            "min": min(lengths),
            "max": max(lengths),
        },
        "sentence_mix_pct": {
            "short_le8": round(100 * short / len(lengths), 1),
            "medium_9_24": round(100 * medium / len(lengths), 1),
            "long_ge25": round(100 * long_ / len(lengths), 1),
        },
        "adverbs_mente_ly_per_1000": round(1000 * len(_ADVERB.findall(text)) / total, 1) if total else 0.0,
        "parentheticals_per_1000": round(1000 * len(_PARENTHETICAL.findall(text)) / total, 1) if total else 0.0,
        "dialogue_pct_of_lines": round(100 * dialogue_lines / prose_lines, 1) if prose_lines else 0.0,
    }


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    path = Path(args[0]).expanduser()
    if not path.exists():
        sys.exit(f"No existe: {path}")
    data = analyze(read_text(path))

    if "--json" in sys.argv:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    s, mix = data["sentence_length"], data["sentence_mix_pct"]
    print(f"MEDICIÓN OBJETIVA — {path.name}")
    print(f"  Palabras: {data['total_words']:,} · frases: {data['sentences']:,} · "
          f"capítulos detectados: {data['chapters']} · cortes de escena: {data['scene_breaks']}")
    print(f"  Longitud de frase — media {s['mean']} · mediana {s['median']} · "
          f"desv. {s['std']} · rango {s['min']}–{s['max']}")
    print(f"  Mezcla — cortas (≤8) {mix['short_le8']}% · medias {mix['medium_9_24']}% · "
          f"largas (≥25) {mix['long_ge25']}%")
    print(f"  Adverbios -mente/-ly por mil: {data['adverbs_mente_ly_per_1000']}")
    print(f"  Incisos (raya, paréntesis, dos puntos) por mil: {data['parentheticals_per_1000']}")
    print(f"  Diálogo: {data['dialogue_pct_of_lines']}% de las líneas")


if __name__ == "__main__":
    main()
