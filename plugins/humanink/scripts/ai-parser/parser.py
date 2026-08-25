#!/usr/bin/env python3
"""
AI Parser — Analizador estadístico-semántico y humanizador de ficción IA.

Uso:
  python parser.py texto.docx
  python parser.py texto.docx --humanize --top 5
  python parser.py texto.docx --style mi_estilo.md --humanize
  python parser.py texto.docx --format json
  python parser.py texto.txt   (también acepta .txt y .md)
"""

import argparse
import re
import sys
from pathlib import Path


def load_text(filepath: str) -> str:
    path = Path(filepath)
    if not path.exists():
        print(f"Error: no se encuentra el archivo '{filepath}'", file=sys.stderr)
        sys.exit(1)

    suffix = path.suffix.lower()
    if suffix == ".docx":
        try:
            from docx import Document
        except ImportError:
            print("Error: instala python-docx → pip install python-docx", file=sys.stderr)
            sys.exit(1)
        doc = Document(filepath)
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())

    if suffix in (".txt", ".md"):
        return path.read_text(encoding="utf-8")

    print(f"Error: formato no soportado '{suffix}'. Usa .docx, .txt o .md", file=sys.stderr)
    sys.exit(1)


def load_style(style_path):  # str | None
    if not style_path:
        return None
    p = Path(style_path)
    if not p.exists():
        print(f"Advertencia: no se encuentra el archivo de estilo '{style_path}'", file=sys.stderr)
        return None
    return p.read_text(encoding="utf-8")


def extract_paragraph_fragments(text: str, pattern_hits: list[dict]) -> list[dict]:
    """
    Divide el texto en párrafos y puntúa cada uno por presencia de patrones AI.
    Devuelve lista ordenada por score descendente.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if len(p.strip()) > 20]

    fragments = []
    for i, para in enumerate(paragraphs):
        para_start = text.find(para)
        para_end = para_start + len(para)

        hits_in_para = [
            h for h in pattern_hits
            if para_start <= h["start"] < para_end
        ]

        if not hits_in_para:
            continue

        score = sum(h["weight"] for h in hits_in_para) / max(len(para.split()), 1) * 10
        reasons = list({h["description"] for h in hits_in_para})

        fragments.append({
            "text": para,
            "paragraph_index": i,
            "score": round(score, 3),
            "reasons": reasons,
            "pattern_hits": hits_in_para,
        })

    return sorted(fragments, key=lambda f: f["score"], reverse=True)


def main():
    parser = argparse.ArgumentParser(
        description="Analiza y humaniza texto de ficción generado por IA"
    )
    parser.add_argument("file", help="Archivo a analizar (.docx, .txt, .md)")
    parser.add_argument(
        "--humanize", action="store_true",
        help="Reescribir los fragmentos más AI-like con Claude API"
    )
    parser.add_argument(
        "--top", type=int, default=5, metavar="N",
        help="Número de fragmentos a humanizar (default: 5)"
    )
    parser.add_argument(
        "--style", metavar="FILE",
        help="Archivo con instrucciones de estilo para la humanización"
    )
    parser.add_argument(
        "--format", choices=["markdown", "json", "html"], default="html",
        help="Formato de salida (default: html)"
    )
    parser.add_argument(
        "--output", "-o", metavar="FILE",
        help="Guardar informe en archivo (default: stdout)"
    )
    parser.add_argument(
        "--model", default="claude-sonnet-4-6",
        help="Modelo Claude para humanización (default: claude-sonnet-4-6)"
    )
    args = parser.parse_args()

    # Importaciones locales (después de validar args)
    from patterns import scan_text
    from metrics import analyze
    from report import build_markdown, build_json

    print(f"Analizando: {args.file}", file=sys.stderr)

    text = load_text(args.file)
    style_instructions = load_style(args.style)

    print(f"  {len(text.split())} palabras cargadas", file=sys.stderr)

    # Análisis estadístico
    pattern_hits = scan_text(text)
    metrics = analyze(text, pattern_hits)
    fragments = extract_paragraph_fragments(text, pattern_hits)

    print(f"  Score AI: {metrics.overall_ai_score}/100", file=sys.stderr)
    print(f"  Patrones detectados: {len(pattern_hits)}", file=sys.stderr)
    print(f"  Fragmentos AI-like: {len(fragments)}", file=sys.stderr)

    # Humanización (opcional)
    humanized = None
    if args.humanize and fragments:
        from humanizer import humanize_top_fragments
        print(f"\nHumanizando top {args.top} fragmentos...", file=sys.stderr)
        humanized = humanize_top_fragments(
            fragments,
            top_n=args.top,
            style_instructions=style_instructions,
            model=args.model,
        )
        print(f"  {len(humanized)} fragmentos reescritos", file=sys.stderr)

    # Generar informe
    top_for_report = fragments[:args.top]
    if args.format == "json":
        output = build_json(args.file, metrics, pattern_hits, top_for_report, humanized)
        ext = ".json"
    elif args.format == "html":
        from report import build_html
        output = build_html(args.file, metrics, pattern_hits, top_for_report, humanized)
        ext = ".html"
    else:
        output = build_markdown(args.file, metrics, pattern_hits, top_for_report, humanized)
        ext = ".md"

    if args.output:
        out_path = Path(args.output)
    elif args.format == "html":
        # Guardar junto al fichero original con sufijo -ai-report.html
        src = Path(args.file)
        out_path = src.parent / f"{src.stem}-ai-report.html"
    else:
        out_path = None

    if out_path:
        out_path.write_text(output, encoding="utf-8")
        print(f"\nInforme guardado en: {out_path}", file=sys.stderr)
        if args.format == "html":
            import subprocess
            subprocess.Popen(["open", str(out_path)])
            print("Abriendo en el navegador...", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
