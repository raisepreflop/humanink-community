#!/usr/bin/env python3
"""build_projects.py — pinta la cartera de proyectos del autor como un dashboard HTML.

Lee proyectos.json (lo mantiene el skill conversando con el autor) y escribe
proyectos-dashboard.html AUTOCONTENIDO (CSS + Gantt SVG inline, cero red): tarjetas por proyecto
con estado y próximo hito, y un Gantt con barras por hito y la línea de "hoy". Estética HumanInk
(fondo #0c1117, dorado #FFC400), la misma paleta que el dashboard AWAP.

Uso:  python3 build_projects.py <carpeta-con-proyectos.json>
      → escribe <carpeta>/proyectos-dashboard.html
"""
import base64
import datetime as dt
import html
import pathlib
import json
import os
import sys

GOLD, CYAN, BG, CARD, LINE, MUT, INK = "#FFC400", "#27B6E3", "#0c1117", "#11161f", "#1f2937", "#8a93a3", "#f0f4f8"
GREEN, RED, VIOLET = "#22c55e", "#ef4444", "#a78bfa"
ESTADOS = {"activo": GREEN, "pausado": GOLD, "terminado": MUT, "idea": VIOLET}



_MIME = {".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png", ".webp": "webp"}


def thumb(p, folder):
    """Miniatura del proyecto desde el campo opcional "portada". data-URI para no romper
    la autocontención del HTML. Si no hay o pesa demasiado, no se pinta nada: la tarjeta
    funciona igual."""
    rel = p.get("portada")
    if not rel:
        return ""
    f = pathlib.Path(rel).expanduser()
    if not f.is_absolute():
        f = pathlib.Path(folder) / rel
    if not f.exists() or f.stat().st_size > 2_000_000:
        return ""
    mime = _MIME.get(f.suffix.lower())
    if not mime:
        return ""
    b64 = base64.b64encode(f.read_bytes()).decode()
    return (f'<img src="data:image/{mime};base64,{b64}" alt="" style="width:40px;height:60px;'
            f'object-fit:cover;border-radius:5px;flex:none;margin-right:10px">')


def d(s):
    return dt.date.fromisoformat(str(s)[:10])


def gantt(proyectos, today, width=880, row_h=26):
    """Gantt SVG: una fila por hito, agrupadas por proyecto, con línea de hoy."""
    rows = []  # (proyecto, hito, inicio, fin, hecho)
    for p in proyectos:
        for h in p.get("hitos", []):
            try:
                rows.append((p["nombre"], h["nombre"], d(h["inicio"]), d(h["fin"]), h.get("hecho", False)))
            except Exception:
                continue  # hito sin fechas válidas: no rompe el Gantt, simplemente no se pinta
    if not rows:
        return f"<p style='color:{MUT}'>Sin hitos con fechas todavía — añádelos conversando.</p>"
    lo = min(r[2] for r in rows)
    hi = max(r[3] for r in rows)
    lo = min(lo, today) - dt.timedelta(days=3)
    hi = max(hi, today) + dt.timedelta(days=3)
    span = max((hi - lo).days, 1)
    pad_l = 230
    H = len(rows) * row_h + 34

    def x(day):
        return pad_l + (width - pad_l - 10) * (day - lo).days / span

    out = [f'<svg viewBox="0 0 {width} {H}" width="100%" style="max-width:{width}px">']
    # marcas de mes
    m = dt.date(lo.year, lo.month, 1)
    while m <= hi:
        if m >= lo:
            out.append(f'<line x1="{x(m):.0f}" y1="18" x2="{x(m):.0f}" y2="{H-8}" stroke="{LINE}"/>')
            out.append(f'<text x="{x(m)+3:.0f}" y="13" fill="{MUT}" font-size="10">{m.strftime("%b %y")}</text>')
        m = dt.date(m.year + (m.month == 12), (m.month % 12) + 1, 1)
    last_proj = None
    for i, (proj, hito, ini, fin, hecho) in enumerate(rows):
        y = 22 + i * row_h
        label = f"{proj} · {hito}" if proj != last_proj else f"    ↳ {hito}"
        last_proj = proj
        color = MUT if hecho else (RED if fin < today else GOLD)
        out.append(f'<text x="4" y="{y+12}" fill="{INK if not hecho else MUT}" font-size="11">{html.escape(label[:38])}</text>')
        x0, x1 = x(ini), max(x(fin), x(ini) + 4)
        out.append(f'<rect x="{x0:.0f}" y="{y+2}" width="{x1-x0:.0f}" height="{row_h-10}" rx="4" fill="{color}" opacity="{0.45 if hecho else 0.9}"><title>{html.escape(hito)}: {ini} → {fin}{" ✓" if hecho else ""}</title></rect>')
        if hecho:
            out.append(f'<text x="{x1+5:.0f}" y="{y+13}" fill="{GREEN}" font-size="11">✓</text>')
    # línea de hoy
    out.append(f'<line x1="{x(today):.0f}" y1="16" x2="{x(today):.0f}" y2="{H-8}" stroke="{CYAN}" stroke-width="2" stroke-dasharray="4 3"/>')
    out.append(f'<text x="{x(today)+4:.0f}" y="{H-12}" fill="{CYAN}" font-size="10" font-weight="700">hoy</text>')
    out.append("</svg>")
    return "".join(out)


def build(folder):
    src = os.path.join(folder, "proyectos.json")
    with open(src, encoding="utf-8") as f:
        data = json.load(f)
    proyectos = data.get("proyectos", data if isinstance(data, list) else [])
    today = dt.date.today()

    cards = []
    for p in proyectos:
        est = str(p.get("estado", "activo")).lower()
        color = ESTADOS.get(est, MUT)
        pend = [h for h in p.get("hitos", []) if not h.get("hecho")]
        try:
            pend.sort(key=lambda h: d(h["fin"]))
        except Exception:
            pass
        nxt = pend[0] if pend else None
        nxt_html = (f'<div style="font-size:12px;color:{MUT};margin-top:6px">Próximo hito: '
                    f'<span style="color:{INK}">{html.escape(nxt["nombre"])}</span> · {html.escape(str(nxt.get("fin","")))}</div>'
                    if nxt else f'<div style="font-size:12px;color:{GREEN};margin-top:6px">Sin hitos pendientes ✓</div>')
        done = sum(1 for h in p.get("hitos", []) if h.get("hecho"))
        total = len(p.get("hitos", []))
        cards.append(
            f'<div style="background:{CARD};border:1px solid {LINE};border-radius:14px;padding:16px 18px;flex:1;min-width:240px;display:flex">'
            + thumb(p, folder) +
            f'<div style="flex:1;min-width:0">'
            f'<div style="display:flex;justify-content:space-between;align-items:center">'
            f'<div style="font-weight:800;font-size:15px">{html.escape(p.get("nombre","—"))}</div>'
            f'<span style="font-size:11px;font-weight:700;color:{color};border:1px solid {color};border-radius:999px;padding:2px 10px">{html.escape(est)}</span></div>'
            f'<div style="font-size:12px;color:{MUT};margin-top:4px">{html.escape(p.get("area",""))} · hitos {done}/{total}</div>'
            f'{nxt_html}'
            + (f'<div style="font-size:12px;color:{MUT};margin-top:6px">{html.escape(p["notas"])}</div>' if p.get("notas") else "")
            + '</div></div>')

    page = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Proyectos — HumanInk</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:{BG};color:{INK};font-family:-apple-system,system-ui,'Segoe UI',sans-serif;padding:24px}}
.wrap{{max-width:940px;margin:0 auto}}</style></head><body><div class="wrap">
<div style="display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:8px;margin-bottom:18px">
<div style="font-size:22px;font-weight:900">Cartera de proyectos <span style="color:{GOLD}">· HumanInk</span></div>
<div style="font-size:12px;color:{MUT}">{today.isoformat()} · se actualiza conversando</div></div>
<div style="display:flex;gap:14px;flex-wrap:wrap;margin-bottom:18px">{"".join(cards)}</div>
<div style="background:{CARD};border:1px solid {LINE};border-radius:14px;padding:18px 20px">
<div style="font-weight:700;margin-bottom:12px">Gantt <span style="font-size:12px;color:{MUT};font-weight:400">· barras = hitos · <span style="color:{CYAN}">línea = hoy</span> · <span style="color:{RED}">rojo = vencido</span></span></div>
{gantt(proyectos, today)}</div>
<div style="text-align:center;color:#374151;font-size:11px;margin-top:20px">HumanInk · /humanink:projects · edita conversando y el panel se regenera</div>
</div></body></html>"""
    out = os.path.join(folder, "proyectos-dashboard.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"✓ {out}")
    return out


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else ".")
