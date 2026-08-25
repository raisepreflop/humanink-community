#!/usr/bin/env python3
"""HumanInk dashboard generator. Usage: build_dashboard.py <project_folder>"""
import sys
import json, sys, os
from pathlib import Path
from datetime import datetime, timezone

CARPETA = sys.argv[1] if len(sys.argv) > 1 else "."

def load(file):
    p = Path(CARPETA) / ".awap" / file
    return p.read_text() if p.exists() else ""

project = json.loads(load("project.json") or "{}")
log_lines = [l for l in (load("log.jsonl") or "").strip().splitlines() if l]
events = []
for l in log_lines:
    try: events.append(json.loads(l))
    except: pass

title  = project.get("title", Path(CARPETA).name)
author = project.get("author", "Author")
created = project.get("created_at", "")[:10]
status = project.get("status", "active")

# Basic metrics
n_ev = len(events)
n_human = sum(1 for e in events if e.get("event_type") in ("document_created","text_revised","conversation_turn"))
n_ai    = sum(1 for e in events if e.get("event_type") == "text_generated")
n_sess  = len(set(e.get("session_id","") for e in events if e.get("session_id")))

# HAS score
WEIGHTS = {"premise":100,"synopsis":85,"bible":75,"outline":60,"style_instructions":40,"revision":25,"draft":5}
by_dt = {}
for e in events:
    dt = e.get("document_type","draft")
    by_dt.setdefault(dt,[]).append(e)
earned = total = 0
breakdown = {}
for dt, evs in by_dt.items():
    w = WEIGHTS.get(dt, 5)
    ratios = [e.get("revision_ratio",0) for e in evs if e.get("event_type") != "conversation_turn"]
    if not ratios: continue
    avg = sum(ratios)/len(ratios)
    pts = w * avg
    earned += pts; total += w
    breakdown[dt] = (round(pts,1), w, len(evs))
has = round(min(100, earned/total*100), 1) if total else 0.0

# Collaborator usage detection
used = {"17"}
for e in events:
    dt, et = e.get("document_type",""), e.get("event_type","")
    if dt in ("premise","synopsis") and et == "document_created": used.add("01")
    if dt == "bible": used.add("03")
    if dt == "style_instructions": used.add("04")
    if dt == "draft" and et == "text_generated": used.add("05")
    if dt == "revision": used.add("09")

# Word count
words = 0
for ext in ("*.md","*.txt"):
    for f in Path(CARPETA).rglob(ext):
        if ".awap" in str(f): continue
        try: words += len(f.read_text(errors="ignore").split())
        except: pass

# ── Book card: portada + ficheros con su recuento (patrón "la portada arriba, luego el árbol") ──
import base64
_MIME = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}
cover_html = ""
for _stem in ("portada", "cover", "Portada", "Cover"):
    for _ext, _mime in _MIME.items():
        _c = Path(CARPETA) / f"{_stem}.{_ext}"
        # >3 MB inflaría el HTML autocontenido más que el valor que aporta la miniatura
        if _c.exists() and _c.stat().st_size < 3_000_000:
            _b64 = base64.b64encode(_c.read_bytes()).decode()
            cover_html = (f'<img src="data:image/{_mime};base64,{_b64}" alt="" style="width:88px;'
                          f'height:132px;object-fit:cover;border-radius:8px;flex:none;'
                          f'box-shadow:0 8px 24px rgba(0,0,0,.5)">')
            break
    if cover_html:
        break
if not cover_html:
    _ini = "".join(w[0] for w in title.split()[:2]).upper() or "?"
    cover_html = (f'<div style="width:88px;height:132px;border-radius:8px;flex:none;display:flex;'
                  f'align-items:center;justify-content:center;font-size:28px;font-weight:900;'
                  f'color:#FFC400;background:linear-gradient(160deg,#2a2100,#0a0e14);'
                  f'border:1px solid rgba(255,196,0,.35)">{_ini}</div>')

# Capítulos con palabras. .docx solo si python-docx está disponible; si no, "—" y no se miente.
_dirs = [d for n in ("capitulos", "chapters", "caps") if (d := Path(CARPETA) / n).is_dir()] or [Path(CARPETA)]
_chaps = []
for _d in _dirs:
    for _f in sorted(list(_d.glob("*.md")) + list(_d.glob("*.txt")) + list(_d.glob("*.docx"))):
        if _f.name.startswith((".", "_")) or ".awap" in str(_f):
            continue
        if _f.suffix == ".docx":
            try:
                import docx as _dx
                _w = sum(len(p.text.split()) for p in _dx.Document(str(_f)).paragraphs)
            except Exception:
                _w = None
        else:
            try:
                _w = len(_f.read_text(errors="ignore").split())
            except Exception:
                _w = None
        _chaps.append((_f.name, _w))
_rows = "".join(
    f'<div class="breakdown-row" style="padding:7px 16px;font-size:12px">'
    f'<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{n}</span>'
    f'<span class="breakdown-pts">{f"{w:,}" if w is not None else "—"}</span></div>'
    for n, w in _chaps[:12])
if len(_chaps) > 12:
    _rows += f'<div class="breakdown-row" style="color:#6b7280;padding:7px 16px;font-size:12px">… +{len(_chaps)-12} más</div>'
files_html = f'<div class="breakdown" style="margin-top:10px">{_rows}</div>' if _rows else ""

# ── Enlaces a los otros paneles que existan ahora mismo (nav cruzada) ──
_nav = []
_p = Path(CARPETA) / "proyectos-dashboard.html"
if _p.exists():
    _nav.append(f'<a href="file://{_p}" style="color:#27B6E3;text-decoration:none">🗂 Proyectos</a>')
_l = Path.home() / ".awos" / "logs" / "dashboard.html"
if _l.exists():
    _nav.append(f'<a href="file://{_l}" style="color:#27B6E3;text-decoration:none">📜 Registro</a>')
nav_html = ('<span style="display:inline-flex;gap:16px;font-size:12px;font-weight:600;margin-right:16px">'
            + "".join(_nav) + "</span>") if _nav else ""

# Colors
has_color = "#22c55e" if has>=75 else "#6366f1" if has>=50 else "#f59e0b" if has>=25 else "#ef4444"
now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

COLLABS = [
    ("01","Author Onboarding","foundation","Author profile"),
    ("02","Market Analyst","foundation","Market report"),
    ("03","Literary Coach","development","Bible + outline"),
    ("04","Style Editor","development","Style guide"),
    ("05","Ghostwriter","development","Assisted writing"),
    ("06","Developmental Editor","development","Developmental report"),
    ("07","Professional Reader","development","Critical reading"),
    ("08","Beta Reader","development","Reader reaction"),
    ("09","Copyeditor & Proofreader","finishing","Three passes"),
    ("10","Interior Typesetter","finishing","Interior layout"),
    ("16","Humanizer","finishing","AI-pattern detection + humanize"),
    ("11","Literary Agent","publishing","Publisher submissions"),
    ("12","Copywriter","publishing","Synopsis + blurbs"),
    ("13","Cover Designer","publishing","Cover design"),
    ("14","Community Manager","marketing","Organic content"),
    ("15","Ads Manager","marketing","Paid campaigns"),
    ("17","Authorship Auditor","trust","AWAP traceability + certificate"),
    ("18","Continuity Editor","memory","Your second brain (Brain)"),
]
PC = {"foundation":"#0ea5e9","development":"#10b981","finishing":"#f59e0b","publishing":"#8b5cf6","marketing":"#ec4899","trust":"#27B6E3","memory":"#06b6d4"}
PL = {"foundation":"Foundation","development":"Development","finishing":"Finishing","publishing":"Publishing","marketing":"Marketing","trust":"Trust","memory":"Memory"}

cards = ""
cur_phase = None
for cid, name, phase, produces in COLLABS:
    if phase != cur_phase:
        if cur_phase: cards += "</div>"
        c = PC[phase]
        cards += f'<div class="phase-header"><span class="phase-dot" style="background:{c}"></span><span class="phase-label" style="color:{c}">{PL[phase]}</span></div><div class="cards-row">'
        cur_phase = phase
    is_used = cid in used
    c = PC[phase]
    border = f"1px solid {c}55" if is_used else "1px solid #1f2937"
    bar = f'<div style="position:absolute;top:0;left:0;right:0;height:2px;background:{c}"></div>' if is_used else ""
    dot_c = "#22c55e" if is_used else "#374151"
    lbl = "Active" if is_used else "Not started"
    prod_c = c if is_used else "#6b7280"
    op = "1" if is_used else "0.5"
    cards += f'<div class="card" style="border:{border};opacity:{op}">{bar}<div class="card-header"><span class="card-id">{cid}</span><span class="card-name">{name}</span><div class="card-status"><span class="dot" style="background:{dot_c}"></span><span class="status-label">{lbl}</span></div></div><div class="card-produces" style="color:{prod_c}">→ {produces}</div></div>'
if cur_phase: cards += "</div>"

# Breakdown rows
brows = ""
for dt,(earned_pts,w,cnt) in breakdown.items():
    pct = int(earned_pts/w*100) if w else 0
    brows += f'<div class="breakdown-row"><span class="breakdown-name">{dt.replace("_"," ").capitalize()}</span><div class="breakdown-bar-wrap"><div class="breakdown-bar" style="width:{pct}%"></div></div><span class="breakdown-pts">{earned_pts:.1f}/{w}</span></div>'
if not brows: brows = '<div class="breakdown-row" style="color:#6b7280;padding:16px">No authorship data yet.</div>'

# Recent events
EV_ICON={"document_created":("📄","#22c55e","Document created"),"text_generated":("🤖","#818cf8","AI generated text"),"text_revised":("✍️","#fbbf24","Human revision"),"conversation_turn":("💬","#38bdf8","Chat")}
erows = ""
for e in events[-8:][::-1]:
    et = e.get("event_type","")
    dt = e.get("document_type","")
    ts = e.get("timestamp","")[:16].replace("T"," ")
    icon,color,label = EV_ICON.get(et,("·","#6b7280",et))
    erows += f'<div class="event-row"><span class="event-icon" style="color:{color}">{icon}</span><span class="event-label" style="color:{color}">{label}</span><span class="event-type">{dt}</span><span class="event-ts">{ts}</span></div>'
if not erows: erows = '<div class="event-row" style="color:#6b7280">No events yet.</div>'

# ── Usage (from the global logger ~/.awos/logs/awos-usage.jsonl, written by /humanink:log) ──
usage = []
UF = Path.home() / ".awos" / "logs" / "awos-usage.jsonl"
if not UF.exists():
    UF = Path.home() / ".awos" / "awos-usage.jsonl"  # legacy fallback
if UF.exists():
    for l in UF.read_text(errors="ignore").splitlines():
        l = l.strip()
        if l:
            try: usage.append(json.loads(l))
            except: pass
proj_keys = {Path(CARPETA).name, title, str(Path(CARPETA))}
pu = [u for u in usage if u.get("project","") in proj_keys] or usage
u_inv = len(pu)
u_tin = sum(int(u.get("tokens_in",0) or 0) for u in pu)
u_tout = sum(int(u.get("tokens_out",0) or 0) for u in pu)
_tt = u_tin + u_tout
tin_pct = round(u_tin / _tt * 100) if _tt else 0
tout_pct = (100 - tin_pct) if _tt else 0
ustats = {}
for u in pu:
    cid = u.get("collaborator","?")
    s = ustats.setdefault(cid, {"inv":0,"tin":0,"tout":0,"name":u.get("name") or cid})
    s["inv"] += 1; s["tin"] += int(u.get("tokens_in",0) or 0); s["tout"] += int(u.get("tokens_out",0) or 0)
urows = ""
for cid, s in sorted(ustats.items(), key=lambda x: x[1]["inv"], reverse=True)[:8]:
    _tok = s["tin"] + s["tout"]
    urows += f'<div class="breakdown-row"><span class="breakdown-name">{s["name"]}</span><span style="color:#8a93a3;flex:1">{s["inv"]} run{"" if s["inv"]==1 else "s"}</span><span class="breakdown-pts">{_tok:,} tok</span></div>'
if not urows: urows = '<div class="breakdown-row" style="color:#6b7280;padding:16px">No collaborator usage logged yet.</div>'

html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>HumanInk — {title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ background: #0a0e14; color: #f0f4f8; font-family: 'Inter', system-ui, -apple-system, sans-serif; min-height: 100vh; }}

.topbar {{ background: #11161f; border-bottom: 1px solid rgba(255,196,0,.12); padding: 16px 32px; display: flex; align-items: center; justify-content: space-between; }}
.logo {{ font-size: 22px; font-weight: 900; letter-spacing: -0.3px; }}
.logo .h {{ color: #f0f4f8; }} .logo .i {{ color: #FFC400; }} .logo .io {{ color: #27B6E3; font-weight: 800; font-size: 16px; }}
.updated {{ font-size: 12px; color: #6b7280; }}

.main {{ max-width: 1040px; margin: 0 auto; padding: 36px 28px; }}

.project-title {{ font-size: 32px; font-weight: 800; margin-bottom: 4px; }}
.project-author {{ color: #9ca3af; font-size: 15px; margin-bottom: 24px; }}

.stats {{ display: flex; gap: 40px; margin-bottom: 20px; }}
.stat-val {{ font-size: 30px; font-weight: 800; }}
.stat-label {{ font-size: 12px; color: #8a93a3; margin-top: 2px; }}

.has-ring {{ display: inline-flex; align-items: center; gap: 14px; background: #11161f; border: 1px solid rgba(255,196,0,.22); border-radius: 18px; padding: 18px 28px; margin-bottom: 28px; box-shadow: 0 0 0 1px rgba(255,196,0,.04), 0 8px 30px rgba(0,0,0,.35); }}
.has-score {{ font-size: 52px; font-weight: 900; line-height: 1; }}
.has-label {{ font-size: 13px; font-weight: 700; color: #FFC400; }}
.has-sublabel {{ font-size: 12px; color: #8a93a3; }}

/* token in/out bar (top) */
.token-bar-wrap {{ max-width: 560px; margin: 0 0 36px; }}
.token-bar-head {{ display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px; }}
.tb-label {{ font-size: 14px; font-weight: 800; color: #FFC400; letter-spacing: .2px; }}
.tb-sub {{ font-size: 13px; color: #8a93a3; }}
.token-bar {{ display: flex; height: 14px; border-radius: 8px; overflow: hidden; background: #11161f; border: 1px solid rgba(255,196,0,.18); }}
.tb-in {{ background: #FFD64F; }} .tb-out {{ background: #FFC400; }}

.section-title {{ font-size: 14px; font-weight: 800; letter-spacing: 1.5px; text-transform: uppercase; color: #FFC400; margin-bottom: 18px; margin-top: 44px; padding-bottom: 8px; border-bottom: 1px solid rgba(255,196,0,.18); }}

.phase-header {{ display: flex; align-items: center; gap: 8px; margin: 24px 0 12px; }}
.phase-dot {{ width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }}
.phase-label {{ font-size: 11px; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase; }}

.cards-row {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; margin-bottom: 4px; }}
.card {{ background: #11161f; border-radius: 14px; padding: 14px 16px; position: relative; overflow: hidden; }}
.card-header {{ display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }}
.card-id {{ font-family: monospace; font-size: 10px; color: #6b7280; }}
.card-name {{ font-size: 14px; font-weight: 700; flex: 1; }}
.card-status {{ display: flex; align-items: center; gap: 4px; }}
.dot {{ width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }}
.status-label {{ font-size: 10px; color: #6b7280; }}
.card-produces {{ font-size: 12px; margin-top: 4px; }}

.events {{ background: #11161f; border: 1px solid rgba(255,196,0,.12); border-radius: 14px; overflow: hidden; }}
.event-row {{ display: flex; align-items: center; gap: 10px; padding: 10px 16px; border-bottom: 1px solid #1f2937; font-size: 12px; }}
.event-row:last-child {{ border-bottom: none; }}
.event-icon {{ width: 20px; text-align: center; }}
.event-label {{ font-weight: 500; min-width: 140px; }}
.event-type {{ color: #6b7280; flex: 1; }}
.event-ts {{ color: #4b5563; font-family: monospace; font-size: 11px; }}

.breakdown {{ background: #11161f; border: 1px solid rgba(255,196,0,.12); border-radius: 14px; overflow: hidden; }}
.breakdown-row {{ display: flex; align-items: center; gap: 12px; padding: 12px 18px; border-bottom: 1px solid #1f2937; font-size: 13px; }}
.breakdown-row:last-child {{ border-bottom: none; }}
.breakdown-name {{ min-width: 150px; font-weight: 500; }}
.breakdown-bar-wrap {{ flex: 1; background: #111827; border-radius: 4px; height: 6px; overflow: hidden; }}
.breakdown-bar {{ height: 100%; border-radius: 4px; background: #FFC400; }}
.breakdown-pts {{ color: #9ca3af; min-width: 80px; text-align: right; font-family: monospace; font-size: 11px; }}

.footer {{ margin-top: 40px; font-size: 11px; color: #374151; text-align: center; }}
</style></head><body>

<div class="topbar">
  <span class="logo"><span class="h">Human</span><span class="i">Ink</span><span class="io">.io</span></span>
  {nav_html}<span class="updated">{now}</span>
</div>

<div class="main">
  <div style="display:flex;gap:18px;align-items:flex-start;margin-bottom:24px">
    {cover_html}
    <div style="flex:1;min-width:0">
      <div class="project-title">{title}</div>
      <div class="project-author" style="margin-bottom:8px">by {author}{" · " + created if created else ""} · {status}</div>
      <div style="font-size:12px;color:#6b7280">{words:,} words · {len(_chaps)} files</div>
      {files_html}
    </div>
  </div>

  <div class="has-ring">
    <div>
      <div class="has-score" style="color:{has_color}">{has}</div>
      <div style="font-size:11px;color:#6b7280">/100</div>
    </div>
    <div>
      <div class="has-label" style="color:{has_color}">Human Authorship Score</div>
      <div class="has-sublabel">AWAP 3.4 · {n_ev} events</div>
    </div>
  </div>

  <div class="stats">
    <div><div class="stat-val">{words:,}</div><div class="stat-label">Words</div></div>
    <div><div class="stat-val">{n_sess}</div><div class="stat-label">Sessions</div></div>
    <div><div class="stat-val">{n_human}</div><div class="stat-label">Human events</div></div>
    <div><div class="stat-val">{n_ai}</div><div class="stat-label">AI generations</div></div>
  </div>

  <div class="token-bar-wrap">
    <div class="token-bar-head">
      <span class="tb-label">Tokens · {u_tin+u_tout:,}</span>
      <span class="tb-sub"><strong style="color:#FFD64F">{u_tin:,}</strong> input · <strong style="color:#FFC400">{u_tout:,}</strong> output · {u_inv} runs</span>
    </div>
    <div class="token-bar">
      <div class="tb-in" style="width:{tin_pct}%"></div>
      <div class="tb-out" style="width:{tout_pct}%"></div>
    </div>
  </div>

  <div class="section-title">The 18 collaborators</div>
  {cards}

  <div class="section-title">Authorship breakdown</div>
  <div class="breakdown">{brows}</div>

  <div class="section-title">Latest events</div>
  <div class="events">{erows}</div>

  <div class="section-title">Usage by collaborator</div>
  <div class="breakdown">{urows}</div>

  <div class="footer">HumanInk · The Augmented Writer's Operating System · usage logged by /humanink:log</div>
</div>
</body></html>"""

out = "/tmp/awos-dashboard.html"
open(out, "w").write(html)
print(f"OK:{out}")
print(f"TITLE:{title}")
print(f"HAS:{has}")
print(f"SESSIONS:{n_sess}")
print(f"EVENTS:{n_ev}")
print(f"USED:{len(used)}")
