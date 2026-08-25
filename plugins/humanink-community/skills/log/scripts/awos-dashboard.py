#!/usr/bin/env python3
"""awos-dashboard.py — HumanInk system log (transaction trace), styled like /humanink:dashboard."""
import json
from pathlib import Path
from datetime import datetime, timezone

LOG_DIR  = Path.home() / ".awos" / "logs"
LOG_FILE = LOG_DIR / "awos-usage.jsonl"
OUT_FILE = LOG_DIR / "dashboard.html"

CMD = {
    'awos-autor':'author','awos-analista':'analyst','awos-coach':'coach','awos-estilo':'style',
    'awos-escritor':'ghostwriter','awos-editor':'editor','awos-lector':'reader','awos-beta':'beta',
    'awos-corrector':'copyeditor','awos-maquetador':'typesetter','awos-asesor':'agent',
    'awos-copywriter':'copywriter','awos-portadista':'cover','awos-community':'community',
    'awos-marketero':'ads','awos-humanizador':'humanizer','awos-auditor':'auditor',
}

def fmt_k(v):
    v = int(v or 0)
    return f"{v/1000:.1f}k" if v >= 1000 else str(v)

logs = []
if LOG_FILE.exists():
    for line in LOG_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line:
            try: logs.append(json.loads(line))
            except: pass

n     = len(logs)
tin   = sum(int(e.get("tokens_in",0)  or 0) for e in logs)
tout  = sum(int(e.get("tokens_out",0) or 0) for e in logs)
dprod = sum(int(e.get("docs_produced",0) or 0) for e in logs)
now   = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

rows = ""
for e in reversed(logs[-500:]):
    cid  = e.get("collaborator","")
    name = e.get("name") or cid
    cmd  = CMD.get(cid, cid)
    ts   = e.get("ts","")[:16].replace("T"," ")
    mode = e.get("mode","") or ""
    proj = e.get("project","")
    rows += (f'<tr><td class="ts">{ts}</td>'
             f'<td class="nm">{name}</td>'
             f'<td class="cmd">/humanink:{cmd} {mode}</td>'
             f'<td class="pj">{proj}</td>'
             f'<td class="num tin">{fmt_k(e.get("tokens_in",0))}</td>'
             f'<td class="num tout">{fmt_k(e.get("tokens_out",0))}</td>'
             f'<td class="num">{e.get("docs_uploaded",0)}</td>'
             f'<td class="num dp">{e.get("docs_produced",0)}</td></tr>')
if not rows:
    rows = '<tr><td colspan="8" class="empty">No transactions logged yet — run any collaborator and they will appear here.</td></tr>'

html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>HumanInk — System log</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ background:#0a0e14; color:#f0f4f8; font-family:'Inter',system-ui,sans-serif; min-height:100vh; }}
.topbar {{ background:#11161f; border-bottom:1px solid rgba(255,196,0,.12); padding:16px 32px; display:flex; align-items:center; justify-content:space-between; }}
.logo {{ font-size:22px; font-weight:900; letter-spacing:-.3px; }}
.logo .h {{ color:#f0f4f8; }} .logo .i {{ color:#FFC400; }} .logo .io {{ color:#27B6E3; font-weight:800; font-size:16px; }}
.sub {{ font-size:12px; color:#8a93a3; margin-top:2px; }}
.updated {{ font-size:12px; color:#6b7280; }}
.main {{ max-width:1040px; margin:0 auto; padding:36px 28px; }}
.stats {{ display:flex; gap:40px; margin-bottom:28px; }}
.stat-val {{ font-size:30px; font-weight:800; }}
.stat-label {{ font-size:12px; color:#8a93a3; margin-top:2px; }}
.section-title {{ font-size:14px; font-weight:800; letter-spacing:1.5px; text-transform:uppercase; color:#FFC400; margin:8px 0 16px; padding-bottom:8px; border-bottom:1px solid rgba(255,196,0,.18); }}
.logbox {{ background:#11161f; border:1px solid rgba(255,196,0,.12); border-radius:14px; overflow:auto; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
thead th {{ text-align:left; font-size:11px; letter-spacing:.06em; text-transform:uppercase; color:#8a93a3; font-weight:700; padding:12px 16px; border-bottom:1px solid #1f2937; }}
tbody td {{ padding:11px 16px; border-bottom:1px solid #161c27; white-space:nowrap; }}
tbody tr:last-child td {{ border-bottom:none; }}
tbody tr:hover {{ background:rgba(255,196,0,.03); }}
.ts {{ color:#6b7280; font-variant-numeric:tabular-nums; }}
.nm {{ font-weight:600; }}
.cmd {{ color:#FFC400; font-family:'SF Mono',ui-monospace,monospace; font-size:12px; }}
.pj {{ color:#8a93a3; }}
.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
.tin {{ color:#7DD3F0; }} .tout {{ color:#FFC400; }} .dp {{ color:#22c55e; font-weight:700; }}
.empty {{ text-align:center; color:#6b7280; padding:28px; }}
.footer {{ margin-top:28px; font-size:11px; color:#374151; text-align:center; }}
</style></head><body>
<div class="topbar">
  <div>
    <span class="logo"><span class="h">Human</span><span class="i">Ink</span><span class="io">.io</span></span>
    <div class="sub">System log · transaction trace</div>
  </div>
  <span class="updated">{now}</span>
</div>
<div class="main">
  <div class="stats">
    <div><div class="stat-val">{n:,}</div><div class="stat-label">Transactions</div></div>
    <div><div class="stat-val">{tin:,}</div><div class="stat-label">Tokens in</div></div>
    <div><div class="stat-val">{tout:,}</div><div class="stat-label">Tokens out</div></div>
    <div><div class="stat-val">{dprod:,}</div><div class="stat-label">Docs produced</div></div>
  </div>
  <div class="section-title">Transactions · every operation</div>
  <div class="logbox"><table>
    <thead><tr><th>Time (UTC)</th><th>Collaborator</th><th>Command</th><th>Project</th>
      <th style="text-align:right">Tok in</th><th style="text-align:right">Tok out</th>
      <th style="text-align:right">&uarr;Doc</th><th style="text-align:right">&darr;Doc</th></tr></thead>
    <tbody>{rows}</tbody>
  </table></div>
  <div class="footer">HumanInk · system log · ~/.awos/logs/awos-usage.jsonl · {n} entries</div>
</div>
</body></html>"""

OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
OUT_FILE.write_text(html, encoding="utf-8")
print(f"OK:{OUT_FILE}")
print(f"ENTRIES:{n}")
