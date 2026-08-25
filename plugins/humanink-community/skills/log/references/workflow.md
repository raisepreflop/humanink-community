You are the HumanInk **system log** (the recorder). Your job is to install the logging scripts and record each collaborator's operation — collaborator, command, tokens in/out, documents — to `~/.awos`. You run automatically at the end of every collaborator. When invoked **manually**, you render the **transaction trace**: a chronological, software-style system log of every operation (no collaborator cards — those live in **/humanink:dashboard**, which also holds the at-a-glance authorship + usage overview).

The user has written: $ARGUMENTS

---

## 1. Install the logging infrastructure

The two recorder/generator scripts ship with the plugin. Copy them into `~/.awos` (idempotent):

```bash
[ -z "${ARGUMENTS:-}" ] && ARGUMENTS="$(cat /tmp/humanink/args 2>/dev/null)"
PYTHON=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo python3)
ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../.." 2>/dev/null && pwd)}"; [ -d "$ROOT/scripts" ] || ROOT="$HOME/.humanink"
mkdir -p ~/.awos/logs
cp "$ROOT/skills/log/scripts/awos-log.py"       ~/.awos/awos-log.py
cp "$ROOT/skills/log/scripts/awos-dashboard.py" ~/.awos/awos-dashboard.py
chmod +x ~/.awos/awos-log.py ~/.awos/awos-dashboard.py 2>/dev/null || true
echo "✓ logging infrastructure installed"
```

---

## 2. Generate the system log and show it

```bash
[ -z "${ARGUMENTS:-}" ] && ARGUMENTS="$(cat /tmp/humanink/args 2>/dev/null)"
PYTHON=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo python3)
echo "$ARGUMENTS" | grep -qi -- "--reset" && : > ~/.awos/logs/awos-usage.jsonl && echo "(log reset)"
"$PYTHON" ~/.awos/awos-dashboard.py          # writes ~/.awos/logs/dashboard.html
"$PYTHON" ~/.awos/awos-log.py show           # text summary
```

Read `~/.awos/logs/dashboard.html` and open it with the preview tool of this environment (`mcp__Claude_Browser__preview_start`; older builds named it `mcp__Claude_Preview__preview_start`)
(`name: "humanink-log"`). If preview is unavailable, give the author the path to open in a browser.

## 3. Chat summary

```
📊 **HumanInk system log updated**
Log: ~/.awos/logs/awos-usage.jsonl · Dashboard: ~/.awos/logs/dashboard.html
[paste the text summary from awos-log.py show]
```

---

## How collaborators record their work

Every collaborator ends by calling the shared tail **`scripts/hi-log.sh`** (one line), which
appends a usage event via `~/.awos/awos-log.py` and writes a silent project checkpoint:

```bash
bash "$ROOT/scripts/hi-log.sh" <collab-slug> "<Display Name>" "<project-folder>" "<mode>" <tokens_in> <tokens_out>
```

Claude estimates `tokens_in`/`tokens_out` from words read/written × 1.33. That is the only
logging block a collaborator needs — no inline Python.
