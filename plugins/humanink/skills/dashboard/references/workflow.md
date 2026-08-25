Generates and shows the live HumanInk HTML dashboard for the given project.

The user wrote: $ARGUMENTS

## 1. Determine the project folder

If the user gave a path, use it; otherwise use the current folder. Then verify the project exists:

```bash
[ -z "${ARGUMENTS:-}" ] && ARGUMENTS="$(cat /tmp/humanink/args 2>/dev/null)"
CARPETA="${ARGUMENTS:-.}"; CARPETA="${CARPETA/#\~/$HOME}"
echo "Folder: $CARPETA"
[ -f "$CARPETA/.awap/project.json" ] && echo "OK" || echo "NO_INIT"
```

If the output is `NO_INIT`, respond and stop:
> "This folder has no HumanInk project. Write your premise and synopsis first, then `/humanink:coach [folder]`."

## 2. Generate and show the dashboard

### Primary path — `awap_dashboard` MCP tool (deterministic, works in Cowork)

Call the MCP tool `mcp__plugin_humanink_awap__awap_dashboard` (no arguments — it uses
the active AWAP project). This reads the **real** SQLite data (`.awap/awap.db`) plus the
global usage log, computes the authoritative HAS via the engine, and returns JSON with:

- `html` — the full dashboard HTML (already written to `<project>/.awap/dashboard.html`)
- `title`, `has`, `events`, `sessions`, `collaborators_used`

This path is **deterministic** and needs no shell — prefer it everywhere, especially in
Cowork where the Python script's sandbox can't run.

Take the returned `html`, write it to `/tmp/awos-dashboard.html`, and open it:

```bash
cat /tmp/awos-dashboard.html   # only if you wrote it there; otherwise pass html directly
```

Call the preview tool of this environment (`mcp__Claude_Browser__preview_start`; older builds named it `mcp__Claude_Preview__preview_start`) with `name: "humanink-dashboard"` and the
`html` returned by the tool (write it to `/tmp/awos-dashboard.html` first if your preview
step reads from disk).

> If the active project differs from the requested folder, call `awap_set_project` with
> the folder first, then `awap_dashboard`.

### Fallback path — Python `build_dashboard.py` (only if the MCP tool is unavailable)

The Python generator is a **fallback**: use it only if `awap_dashboard` is not available.
It needs a reachable shell, so it does **not** work in Cowork. The MCP path above is the
deterministic, Cowork-friendly option and should be tried first.

```bash
[ -z "${ARGUMENTS:-}" ] && ARGUMENTS="$(cat /tmp/humanink/args 2>/dev/null)"
CARPETA="${ARGUMENTS:-.}"; CARPETA="${CARPETA/#\~/$HOME}"
ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../.." 2>/dev/null && pwd)}"; [ -d "$ROOT/scripts" ] || ROOT="$HOME/.humanink"
python3 "$ROOT/skills/dashboard/scripts/build_dashboard.py" "$CARPETA"
cat /tmp/awos-dashboard.html
```

Then call the preview tool of this environment (`mcp__Claude_Browser__preview_start`; older builds named it `mcp__Claude_Preview__preview_start`) with `name: "humanink-dashboard"` and the
HTML you just read.

## 3. Chat summary

Use the `title`/`has`/`sessions`/`events`/`collaborators_used` values from the MCP tool's
JSON (or the generator's `TITLE:`/`HAS:`/`SESSIONS:`/`EVENTS:`/`USED:` output lines in the
fallback), and show:

```
🎛️ **[TITLE]**
HAS Score: [HAS]/100 · Sessions: [SESSIONS] · Events: [EVENTS]
Active collaborators: [USED] / 18
```

If HAS < 30, add:
> 💡 Low score. Document your premise and synopsis first — they weigh most in your authorship.
