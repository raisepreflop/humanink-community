#!/usr/bin/env python3
"""HumanInk help — a visual command cheat-sheet (reference, not a menu).
Usage: build_help.py <plugin_root>
Renders /tmp/humanink-help.html (on-brand) showing the collaborators ACTUALLY
installed in this tier, grouped by phase, with command + purpose + key flags.
Also prints a plain-text version to stdout (fallback)."""
import sys, os, json, re
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
# command namespace = the plugin's name (humanink, or humanink-brain when sold standalone)
NS = "humanink"
VERSION = ""
try:
    pj = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    NS = pj.get("name", NS)
    VERSION = pj.get("version", "")
except Exception:
    pass
if not VERSION:  # el hook de sesión deja aquí la versión espejada
    try:
        VERSION = (Path.home() / ".humanink" / ".mirror-version").read_text().strip()
    except Exception:
        pass
VER_TXT = f"v{VERSION}" if VERSION else "versión desconocida"
present = set()
sk = ROOT / "skills"
if sk.is_dir():
    present = {p.name for p in sk.iterdir() if p.is_dir()}

# ── De dónde salen los textos ────────────────────────────────────────────────────────────────
# Antes había aquí una tabla escrita a mano con el rol y el propósito de cada colaborador, EN
# INGLÉS, mientras el resto del plugin ya estaba en castellano. Y como toda lista paralela, se
# había quedado corta: faltaban 10 de los 29 skills del paquete (comparar, verificar, procedencia,
# projects, kdp-audit, agenda…), así que un tercio de los comandos no aparecía en la chuleta del
# autor. Es el mismo fallo que ya nos costó una versión en make-version.py.
#
# Ahora manda i18n/descriptions.es.json —la misma fuente que las descripciones de los SKILL.md— y
# la lista sale de los skills que REALMENTE hay en el paquete. Un colaborador nuevo aparece solo.
# Las descripciones tienen la forma «Rol — propósito…»: antes del guion va el rol, después el
# propósito, y nos quedamos con su primera frase para que la tarjeta no se desborde.
DESCR = {}
for cand in (ROOT / "i18n" / "descriptions.es.json",
             Path.home() / ".humanink" / "i18n" / "descriptions.es.json"):
    try:
        DESCR = json.loads(cand.read_text(encoding="utf-8"))
        break
    except Exception:
        continue

TOPE = 150   # la tarjeta de la chuleta; más allá deja de leerse de un vistazo


def _recortar(t, tope=TOPE):
    """Una frase que quepa en la tarjeta, cortada por palabra y sin dos puntos colgando.

    Las descripciones del i18n están escritas para que el modelo elija colaborador, así que
    algunas pasan de 300 caracteres. La chuleta es otra cosa: se lee de un vistazo.
    """
    t = " ".join(t.split())
    if len(t) <= tope:
        return t.rstrip(" ,;:")
    corte = t[:tope].rsplit(" ", 1)[0].rstrip(" ,;:")
    return corte + "…"


def rol_y_proposito(slug):
    """('Rol', 'propósito') a partir del i18n. Si no está, se apaña con el slug."""
    t = DESCR.get(slug, "")
    m = re.match(r"\s*([^—]{2,40}?)\s*—\s*(.+)", t, re.S)
    if not m:
        return (slug.replace("-", " ").capitalize(), _recortar(t))
    rol = m.group(1).strip()
    resto = " ".join(m.group(2).split())
    # Primera frase; si acaba en dos puntos, la de después la completa (queda colgando si no).
    trozos = re.split(r"(?<=[.:])\s+", resto)
    prop = trozos[0]
    if prop.endswith(":") and len(trozos) > 1:
        prop = prop + " " + trozos[1]
    prop = _recortar(prop)
    return (rol, prop[0].upper() + prop[1:] if prop else "")

# Metadatos ESTRUCTURALES (orden, fase, banderas). No son traducción: son la forma del producto.
# Un slug que no esté aquí NO desaparece — cae en «Herramientas» con orden «·».
META = {
    "author":      ("01", "Concepto",     ""),
    "analyst":     ("02", "Concepto",     ""),
    "coach":       ("03", "Escritura",    "--bible --outline"),
    "style":       ("04", "Escritura",    ""),
    "ghostwriter": ("05", "Escritura",    "--rewrite --section --insert"),
    "editor":      ("06", "Escritura",    ""),
    "reader":      ("07", "Escritura",    ""),
    "beta":        ("08", "Escritura",    ""),
    "copyeditor":  ("09", "Reescritura",  ""),
    "humanizer":   ("16", "Reescritura",  "--analyze --humanize --report"),
    "fase0":       ("·",  "Reescritura",  ""),
    "plan":        ("·",  "Reescritura",  ""),
    "pasada":      ("·",  "Reescritura",  ""),
    "bitacora":    ("·",  "Reescritura",  ""),
    "comparar":    ("·",  "Reescritura",  "--serie"),
    "verificar":   ("·",  "Reescritura",  ""),
    "typesetter":  ("10", "Publicación",  "--all --epub --pdf"),
    "agent":       ("11", "Publicación",  "--all"),
    "copywriter":  ("12", "Publicación",  "--all"),
    "cover":       ("13", "Publicación",  "--concepts --wrap --ebook"),
    "kdp-audit":   ("·",  "Publicación",  ""),
    "community":   ("14", "Marketing",    "--strategy --calendar --content"),
    "ads":         ("15", "Marketing",    "--strategy --run --optimize --report"),
    "auditor":     ("17", "Confianza",    "--status --report --certificate --official --citations"),
    "procedencia": ("·",  "Confianza",    ""),
    "awap-project":("·",  "Confianza",    ""),
    "awap-write":  ("·",  "Confianza",    ""),
    "awap-certificate": ("·", "Confianza", ""),
    "brain":       ("18", "Memoria",      ""),
    "dashboard":   ("·",  "Panel",        ""),
    "log":         ("·",  "Panel",        ""),
    "projects":    ("·",  "Panel",        ""),
    "agenda":      ("·",  "Panel",        ""),
    "help":        ("·",  "Panel",        ""),
}

PHASES = ["Concepto","Escritura","Reescritura","Publicación","Marketing","Confianza","Memoria","Panel","Herramientas"]
PC = {"Concepto":"#0ea5e9","Escritura":"#10b981","Reescritura":"#f59e0b","Publicación":"#8b5cf6",
      "Marketing":"#ec4899","Confianza":"#27B6E3","Memoria":"#06b6d4","Panel":"#FFC400",
      "Herramientas":"#94a3b8"}

items = []
for slug in sorted(present):
    num, phase, flags = META.get(slug, ("\u00b7", "Herramientas", ""))
    rol, prop = rol_y_proposito(slug)
    items.append((slug, num, rol, phase, prop, flags))
by_phase = {ph: [] for ph in PHASES}
for slug, num, role, phase, purpose, flags in items:
    by_phase[phase].append((num, slug, role, purpose, flags))

# El conector AWAP no se activa solo al instalar: Cowork pide un clic en Plugins → Connectors.
# Quien no lo sepa se topa con un error críptico la primera vez que use el auditor, así que el
# aviso va donde el autor mira primero. Solo aparece en los tiers que llevan auditor.
NEEDS_AWAP = "auditor" in present

# ---- plain text (stdout fallback) ----
print(f"HumanInk {VER_TXT} — tus comandos")
if NEEDS_AWAP:
    print("\n⚠️  Una sola vez: Plugins → HumanInk → Connectors → awap → Connect.")
    print("    Sin eso, el auditor y el certificado no pueden registrar tu autoría.")
    print("    El resto de colaboradores funcionan igualmente.")
for ph in PHASES:
    rows = by_phase[ph]
    if not rows: continue
    print(f"\n{ph}")
    for num, slug, role, purpose, flags in sorted(rows):
        f = f"   flags: {flags}" if flags else ""
        print(f"  {num}  /{NS}:{slug:<12} {role} — {purpose}{f}")

# ---- HTML ----
def esc(s): return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
sections = ""
for ph in PHASES:
    rows = by_phase[ph]
    if not rows: continue
    c = PC[ph]
    cards = ""
    for num, slug, role, purpose, flags in sorted(rows):
        fl = f'<span class="flags">{esc(flags)}</span>' if flags else ""
        cards += (f'<div class="row"><span class="num">{num}</span>'
                  f'<div class="mid"><div class="cmd">/{NS}:{slug}</div>'
                  f'<div class="role">{esc(role)}</div>'
                  f'<div class="purpose">{esc(purpose)} {fl}</div></div></div>')
    sections += (f'<div class="phase"><span class="dot" style="background:{c}"></span>'
                 f'<span class="plabel" style="color:{c}">{ph}</span></div><div class="grid">{cards}</div>')

html = f"""<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">
<title>HumanInk — comandos</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0a0e14;color:#f0f4f8;font-family:'Inter',system-ui,sans-serif;min-height:100vh}}
.topbar{{background:#11161f;border-bottom:1px solid rgba(255,196,0,.12);padding:16px 32px}}
.logo{{font-size:22px;font-weight:900;letter-spacing:-.3px}}
.logo .h{{color:#f0f4f8}}.logo .i{{color:#FFC400}}.logo .io{{color:#27B6E3;font-weight:800;font-size:16px}}
.sub{{font-size:13px;color:#8a93a3;margin-top:2px}}
.main{{max-width:1040px;margin:0 auto;padding:28px}}
.phase{{display:flex;align-items:center;gap:8px;margin:26px 0 12px}}
.dot{{width:8px;height:8px;border-radius:50%}}
.plabel{{font-size:12px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:10px}}
.row{{display:flex;gap:12px;background:#11161f;border:1px solid #1f2937;border-radius:12px;padding:13px 15px}}
.num{{font-family:ui-monospace,monospace;font-size:11px;color:#6b7280;min-width:18px}}
.mid{{flex:1}}
.cmd{{font-family:ui-monospace,monospace;font-size:14px;font-weight:700;color:#FFC400}}
.role{{font-size:12px;color:#cbd5e1;font-weight:600;margin:1px 0 3px}}
.purpose{{font-size:12px;color:#8a93a3;line-height:1.4}}
.flags{{font-family:ui-monospace,monospace;font-size:11px;color:#27B6E3}}
.foot{{color:#374151;font-size:11px;text-align:center;padding:24px}}
.hint{{color:#8a93a3;font-size:13px;margin-top:4px}}
.builds{{background:#11161f;border:1px solid rgba(255,196,0,.22);border-radius:14px;padding:16px 18px;margin-top:26px}}
.btitle{{font-size:14px;font-weight:800;color:#FFC400;margin-bottom:6px}}
.btext{{font-size:13px;color:#cbd5e1;line-height:1.55}}
.btext code{{background:#0a0e14;color:#FFC400;padding:1px 6px;border-radius:5px;font-size:12px}}
</style></head><body>
<div class="topbar"><span class="logo"><span class="h">Human</span><span class="i">Ink</span><span class="io">.io</span></span>
<div class="sub">Tus comandos — escribe uno en Cowork. Eliges tú; nada es obligatorio.</div></div>
{'<div style="background:#1a1408;border:1px solid #FFC400;border-radius:10px;padding:12px 16px;margin:0 0 18px;font-size:13px;line-height:1.5"><b style="color:#FFC400">Una sola vez, antes de usar el auditor:</b> Plugins → HumanInk → <b>Connectors</b> → <b>awap</b> → <b>Connect</b>.<br><span style="opacity:.75">Sin eso, el auditor y el certificado no pueden registrar tu autoría. El resto de colaboradores funcionan igualmente.</span></div>' if NEEDS_AWAP else ''}
<div class="main">{sections}
<div class="builds">
  <div class="btitle">📚 Cómo guardar tu manuscrito — el sistema de versiones</div>
  <div class="btext">Guarda el <b>manuscrito entero en un solo fichero, numerado hacia arriba</b>:
    <code>Mi-novela-v01.docx</code> → <code>v02</code> → <code>v03</code>… una versión nueva por sesión.
    Es lo que hace segura la <b>reescritura quirúrgica</b>: el colaborador lee la novela completa antes
    de tocar una línea, encuentra todos los cabos sueltos de una pasada y comprueba la coherencia
    contra el libro de verdad, no contra fragmentos recompuestos. Y cada versión es una foto entera a
    la que puedes volver.
    <br>Un fichero por capítulo (<code>capitulos/cap-01-v1.docx</code>) también se detecta — solo
    pierdes la vista del manuscrito completo.</div>
</div>
<div class="hint">Truco: añade la ruta del proyecto, p. ej. <b style="color:#FFC400">/{NS}:coach ~/mi-novela --bible</b>. Guía completa: user-manual.md</div>
</div>
<div class="foot">HumanInk <b style="color:#FFC400">{VER_TXT}</b> · humanink.io · {len(items)} comandos en este plugin</div>
</body></html>"""
out = "/tmp/humanink-help.html"
open(out, "w").write(html)
print(f"\nOK:{out}")
print(f"COUNT:{len(items)}")
