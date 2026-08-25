#!/usr/bin/env bash
# SessionStart hook — mirror the plugin's scripts (and their assets/templates) to
# ~/.humanink/ so the skills can run them even in environments where the Bash tool
# cannot reach $CLAUDE_PLUGIN_ROOT/skills/.../scripts/ (e.g. the Cowork sandbox).
#
# Hooks DO receive $CLAUDE_PLUGIN_ROOT and DO have filesystem access, unlike the
# Bash tool inside Cowork. Each skill's ROOT resolver prefers $CLAUDE_PLUGIN_ROOT
# and falls back to ~/.humanink when the plugin scripts aren't readable, so this
# mirror is what makes the deterministic generators (wrap, EPUB, dashboard, help…)
# actually run inside Cowork instead of being reconstructed by hand.
set -u

SRC="${CLAUDE_PLUGIN_ROOT:-}"
[ -z "$SRC" ] && exit 0
# only mirror if we can actually read the plugin tree here
[ -d "$SRC/scripts" ] || [ -d "$SRC/skills" ] || exit 0

DEST="$HOME/.humanink"
mkdir -p "$DEST" 2>/dev/null || exit 0

# 1) repo-root shared helper scripts (hi-args, hi-context, md2docx, ai-parser, …)
if [ -d "$SRC/scripts" ]; then
  mkdir -p "$DEST/scripts"
  cp -R "$SRC/scripts/." "$DEST/scripts/" 2>/dev/null
fi

# 2) per-skill scripts, preserving any assets/ or templates/ subdirs they ship
if [ -d "$SRC/skills" ]; then
  for d in "$SRC"/skills/*/scripts; do
    [ -d "$d" ] || continue
    skill=$(basename "$(dirname "$d")")
    mkdir -p "$DEST/skills/$skill/scripts"
    cp -R "$d/." "$DEST/skills/$skill/scripts/" 2>/dev/null
  done
fi

# 3) stamp the mirrored version for diagnostics (/humanink:help can show it)
ver=$(python3 -c "import json,os,sys;print(json.load(open(os.path.join(sys.argv[1],'.claude-plugin','plugin.json')))['version'])" "$SRC" 2>/dev/null)
printf '%s\n' "${ver:-unknown}" > "$DEST/.mirror-version" 2>/dev/null

exit 0
