Show the HumanInk command cheat-sheet for whatever collaborators are installed in this plugin.

## 1. Render the cheat-sheet

Run the generator. **`$ROOT` must be this plugin's install directory** — the folder you read this
`workflow.md` from (its `../..`). If `$CLAUDE_PLUGIN_ROOT` is empty, substitute that absolute path
yourself (you know it — it's where this file lives):

```bash
[ -z "${ARGUMENTS:-}" ] && ARGUMENTS="$(cat /tmp/humanink/args 2>/dev/null)"
ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../.." 2>/dev/null && pwd)}"; [ -d "$ROOT/scripts" ] || ROOT="$HOME/.humanink"
python3 "$ROOT/skills/help/scripts/build_help.py" "$ROOT"
```

The script prints a plain-text list of the commands (which you can show directly in chat) and
writes the on-brand HTML cheat-sheet to `/tmp/humanink-help.html`.

If the script can't be found (the path didn't resolve), **don't give up** — re-run it with the real
plugin path: the directory two levels up from this `workflow.md`. As a last resort, present the
plain-text command list yourself (every collaborator installed here, grouped by phase, with its
`/<plugin>:<name>` command and one-line purpose).

## 2. Show it — BOTH things, always

**a) In the chat**: present the plain-text command list the script printed, exactly as it came
(starting with the `HumanInk vX.Y.Z — your commands` line, so the writer always knows which version
they have installed). Do not summarise it away — the commands are the point of this command.

**b) In a panel**: read `/tmp/humanink-help.html` and open it with `mcp__Claude_Preview__preview_start`
(`name: "humanink-help"`). If that tool doesn't exist in this environment, say so in one line and
give the writer the file path so they can open it themselves — the chat list above already did the
important part.

## 3. Close

Remind the writer, in one line: **you choose** — type any command (optionally with a project path
and flags), nothing is forced. Point to `user-manual.md` for the full step-by-step guide, and to
`/humanink:dashboard` to see their project's live status.
