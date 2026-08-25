#!/usr/bin/env bash
# HumanInk shared mid-flow checkpoint (silent ledger entry, no usage log).
# Usage: hi-checkpoint.sh <collab-slug> <mode> <artifact> <project-folder>
set -u
COLLAB="${1:-awos-unknown}"; MODE="${2:---}"; ARTIFACT="${3:-}"; CARPETA="${4:-$(pwd)}"
CARPETA="${CARPETA/#\~/$HOME}"
PY=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo python3)
SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$SELF_DIR/.." && pwd)}"
QC=$(ls ~/.awos/ai-parser/quickcheck.py 2>/dev/null || ls "$ROOT/scripts/ai-parser/quickcheck.py" 2>/dev/null | head -1)
[ -n "$QC" ] && "$PY" "$QC" --checkpoint "$COLLAB" "$MODE" "$ARTIFACT" --root "$CARPETA" --quiet 2>/dev/null || true
