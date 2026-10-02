#!/usr/bin/env python3
"""compose-kdp-wrap.py — el wrap de KDP de la skill cover. El código vive en scripts/ooxml/kdp_wrap.py
(el motor que también empaqueta el Editor Studio); esto solo lo busca y lo ejecuta con los mismos
argumentos. Ver `kdp_wrap.py --help` y references/kdp-wrap.md."""
import sys
from pathlib import Path

# La salida, siempre en UTF-8: Windows la escribe en cp1252 y un «→» tumba el script (ver scripts/ooxml/_utf8.py).
for _flujo in (sys.stdin, sys.stdout, sys.stderr):
    getattr(_flujo, "reconfigure", lambda **_: None)(encoding="utf-8", errors="backslashreplace")

for d in (Path(__file__).resolve().parents[3] / "scripts" / "ooxml",   # el plugin
          Path.home() / ".humanink" / "scripts" / "ooxml"):             # la copia de Cowork
    if (d / "kdp_wrap.py").is_file():
        sys.path.insert(0, str(d))
        break
else:
    sys.exit("✗ No encuentro kdp_wrap.py (scripts/ooxml del plugin). Reinstala HumanInk.")

import kdp_wrap
kdp_wrap.main()
