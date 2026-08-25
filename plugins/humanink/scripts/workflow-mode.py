#!/usr/bin/env python3
"""workflow-mode.py — entrega solo las partes del workflow que se van a ejecutar.

Los workflows grandes (coach 7 modos, agent/ads/community/cover/ghostwriter 4, analyst 3) se
cargaban enteros para ejecutar UN modo: el autor paga de su cuota los modos que no ha pedido.
Esto imprime el workflow sin los bloques de los modos no solicitados, conservando intacto todo lo
demás (cabecera, pasos comunes, pasada anti-slop, resumen, registro).

Uso:
    python3 workflow-mode.py <workflow.md> "<ARGUMENTS del usuario>"

OJO — los modos pueden ser ACUMULATIVOS: en agent/ads/community/cover varias banderas se combinan
y `--all` los ejecuta todos. Por eso se conservan TODOS los modos pedidos, no solo uno.

REGLA DE SEGURIDAD: ante cualquier duda (ningún modo reconocido, fichero sin modos, `--all`)
imprime el fichero COMPLETO y avisa por stderr. Perder instrucciones sería mucho peor que gastar
unos tokens de más.
"""
import re
import sys
from pathlib import Path

MODE_RE = re.compile(r"^(#{2,3})\s+.*\bMODE:\s*([\w-]+)", re.IGNORECASE)
HEAD_RE = re.compile(r"^(#{1,6})\s")
# El propio workflow declara su mapeo bandera→modo:  grep -qi "\-\-bible" && MODO="biblia"
MAP_RE = re.compile(r'grep\s+-qi\s+"\\?-\\?-([\w-]+)".*?MODO="([\w-]+)"')
DEFAULT_RE = re.compile(r'^\s*MODO="([\w-]+)"\s*(#.*)?$', re.MULTILINE)
# El escritor fantasma recibe el modo de hi-args.py, que lo nombra en español.
ES_EN = {"nuevo": "new", "reescribir": "rewrite", "seccion": "section", "insertar": "insert"}


def find_blocks(lines):
    """[(nivel, modo, inicio, fin)] de cada bloque de modo, ignorando lo de dentro de ```fences```."""
    fence, marks = False, []
    for i, line in enumerate(lines):
        if line.startswith("```"):
            fence = not fence
            continue
        if not fence and (m := MODE_RE.match(line)):
            marks.append((len(m.group(1)), m.group(2).lower(), i))

    blocks = []
    for level, mode, start in marks:
        end, fence2 = len(lines), False
        for j in range(start + 1, len(lines)):
            if lines[j].startswith("```"):
                fence2 = not fence2
                continue
            if fence2:
                continue
            h = HEAD_RE.match(lines[j])
            # Acaba en el siguiente encabezado de nivel igual o superior: así 'MODE: insert'
            # termina en '## 7. Anti-AISLOP pass', que es común a todos los modos.
            if h and len(h.group(1)) <= level:
                end = j
                break
        blocks.append((level, mode, start, end))
    return blocks


def wanted_modes(text, args, names):
    """Modos pedidos. Varias fuentes, porque cada workflow declara el suyo a su manera."""
    low = args.lower()
    if re.search(r"--all\b", low):
        return set(names)                      # --all ejecuta todos: no se filtra nada
    want = set()
    for flag, mode in MAP_RE.findall(text):    # mapeo explícito del propio workflow
        if re.search(rf"--{re.escape(flag)}\b", low):
            want.add(mode.lower())
    for n in names:                            # bandera que se llama igual que el modo
        if re.search(rf"--{re.escape(n)}\b", low):
            want.add(n)
    for es, en in ES_EN.items():               # modo en español (hi-args) → nombre inglés
        if re.search(rf"\b{es}\b|--{es}\b", low) and en in names:
            want.add(en)
        if re.search(rf"\b{en}\b", low) and en in names:
            want.add(en)
    if not want:                               # sin bandera: el modo por omisión del workflow
        if d := DEFAULT_RE.search(text):
            if d.group(1).lower() in names:
                want.add(d.group(1).lower())
    return want


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = Path(sys.argv[1]).expanduser()
    args = sys.argv[2] if len(sys.argv) > 2 else ""
    if not path.exists():
        sys.exit(f"No existe: {path}")
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    blocks = find_blocks(lines)

    def bail(reason):
        print(f"⚠️  {reason} — se carga el workflow completo.", file=sys.stderr)
        sys.stdout.write(text)
        sys.exit(0)

    if len(blocks) < 2:
        bail("Este workflow no está partido en modos")
    names = {b[1] for b in blocks}
    want = wanted_modes(text, args, names)
    if not want or want == names:
        bail(f"No se identifica un subconjunto de modos (disponibles: {', '.join(sorted(names))})")

    drop = {i for _, mode, s, e in blocks if mode not in want for i in range(s, e)}
    out = [l for i, l in enumerate(lines) if i not in drop]
    sys.stdout.write("\n".join(out) + "\n")
    saved = 100 - round(100 * len("\n".join(out)) / max(len(text), 1))
    print(f"✓ modos cargados: {', '.join(sorted(want))} ({saved}% menos contexto)", file=sys.stderr)


if __name__ == "__main__":
    main()
