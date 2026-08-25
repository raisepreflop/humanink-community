#!/usr/bin/env bash
# AWOS — quality gate posterior a la escritura (advisory-only, nunca bloquea).
#
# PostToolUse sobre Write|Edit: si el fichero escrito parece un capítulo
# (capitulos/*.md o cap-*.md), corre la auditoría mecánica de iParser
# (quickcheck.py: integridad, placeholders, anáforas, banlist, patrones IA)
# y devuelve los avisos a Claude como contexto adicional. Sale SIEMPRE con 0.

set -u

PYTHON=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo python3)
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
QC="$PLUGIN_ROOT/scripts/ai-parser/quickcheck.py"

[ -f "$QC" ] || exit 0

# El JSON del evento llega por stdin; se pasa al Python vía entorno
# (el heredoc ocupa el stdin del intérprete).
AWOS_HOOK_INPUT=$(cat 2>/dev/null || true)
export AWOS_HOOK_INPUT
[ -z "$AWOS_HOOK_INPUT" ] && exit 0

"$PYTHON" - "$QC" <<'PY' || true
import json, os, re, subprocess, sys
from pathlib import Path

qc = sys.argv[1]
try:
    data = json.loads(os.environ.get("AWOS_HOOK_INPUT", "") or "{}")
except Exception:
    sys.exit(0)

fp = (data.get("tool_input") or {}).get("file_path") or ""
if not fp:
    sys.exit(0)
p = Path(fp)

# ¿Parece un capítulo? carpeta capitulos/ o nombre cap-NN*.md|txt
es_cap = (
    p.suffix.lower() in (".md", ".txt", ".markdown")
    and (any(part.lower() == "capitulos" for part in p.parts)
         or re.match(r"cap[-_ ]?\d", p.name.lower()) is not None)
)
if not es_cap or not p.is_file():
    sys.exit(0)

try:
    out = subprocess.run(
        [sys.executable, qc, str(p), "--voz"],
        capture_output=True, text=True, timeout=30,
    ).stdout.strip()
except Exception:
    sys.exit(0)

if "⚠" in out:
    contexto = (
        "[HumanInk monitor — mechanical findings on the chapter just saved. "
        "Design-principle Layer 2: relay them to the writer as a BRIEF PROFESSIONAL "
        "SUGGESTION in the voice of the relevant collaborator — never as system errors — "
        "and make clear they can ignore it and keep writing. Speak to the writer in "
        "English. The monitor emits these signal tags; map each to a voice: "
        "CANON → Developmental Editor (06) (e.g. \"I see a 'Matias' without the accent on "
        "L42 — unify it with 'Matías'?\"); PATRONES IA / PROHIBIDAS / EN VIGILANCIA → "
        "Humanizer (16); ANÁFORA / TIPOGRAFÍA / PLACEHOLDERS → Copyeditor (09); "
        "ESCALETA → Literary Coach (03); DERIVA DE VOZ → Style Editor (04); "
        "INTEGRIDAD → a direct technical note (file corruption, not craft). "
        "If there are several findings, group them into 2-3 sentences, not a bureaucratic list.]\n"
        + out
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": contexto,
        }
    }, ensure_ascii=False))
sys.exit(0)
PY

# Pase lo que pase dentro, este hook jamás bloquea la escritura.
exit 0
