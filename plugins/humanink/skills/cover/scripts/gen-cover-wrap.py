#!/usr/bin/env python3
"""gen-cover-wrap.py — Complete KDP 6x9" paperback wrap
Usage: python3 gen-cover-wrap.py <folder> <pages> [--paper white|cream|color] [--image cover.jpg] [--title T] [--author A]
"""
import sys, os, json, base64
from pathlib import Path

args = sys.argv[1:]
CARPETA = Path(args[0]) if args else Path('.')
PAGINAS = int(args[1]) if len(args) > 1 else 200
PAPEL = 'cream'
IMAGEN = None
TITULO_ARG = ''
AUTOR_ARG = ''
OUTPUT = CARPETA / 'output'

for i, a in enumerate(args):
    if a == '--paper'  and i+1 < len(args): PAPEL = args[i+1]
    if a == '--image'  and i+1 < len(args): IMAGEN = Path(args[i+1])
    if a == '--title'  and i+1 < len(args): TITULO_ARG = args[i+1]
    if a == '--author' and i+1 < len(args): AUTOR_ARG = args[i+1]
    if a == '--output' and i+1 < len(args): OUTPUT = Path(args[i+1])

OUTPUT.mkdir(parents=True, exist_ok=True)

# ── KDP calculation ──────────────────────────────────────────────────────
BLEED = 0.125
PAGE_W = 6.0
PAGE_H = 9.0
SAFE  = 0.25

SPINE_PP = {'white': 0.002252, 'cream': 0.0025, 'color': 0.002347}
spine_in = round(PAGINAS * SPINE_PP.get(PAPEL, 0.0025), 4)
total_w  = round((2 * PAGE_W) + spine_in + (2 * BLEED), 4)
total_h  = round(PAGE_H + (2 * BLEED), 4)

def mm(inches): return round(inches * 25.4, 2)

tw = mm(total_w);  th = mm(total_h)
bl = mm(BLEED);    sa = mm(SAFE)
pw = mm(PAGE_W);   ph = mm(PAGE_H)
sp = mm(spine_in)

# ── Texts ──────────────────────────────────────────────────────────────────
def read(p):
    try: return Path(p).read_text(encoding='utf-8')
    except: return ''

titulo = TITULO_ARG or 'BOOK TITLE'
autor  = AUTOR_ARG  or 'AUTHOR NAME'
blurb  = '...'
bio    = '...'
isbn   = ''

biblia = read(CARPETA / 'biblia.md')
for line in biblia.split('\n'):
    if line.startswith('# ') and not TITULO_ARG:
        titulo = line[2:].split('—')[0].strip(); break

for f in ['blurb-texto.txt', 'blurb.txt']:
    t = read(CARPETA / f)
    if t: blurb = t.strip()[:800]; break

for f in ['bio-texto.txt', 'bio.txt']:
    t = read(CARPETA / f)
    if t: bio = t.strip()[:400]; break

isbn = read(CARPETA / 'isbn.txt').strip() or 'ISBN 978-XX-XXXXX-XX-X'

# ── Image ──────────────────────────────────────────────────────────────────
img_tag = '<div class="img-placeholder"><span>COVER IMAGE</span></div>'
if IMAGEN and Path(IMAGEN).exists():
    ext  = Path(IMAGEN).suffix.lower()
    mime = 'image/jpeg' if ext in ['.jpg','.jpeg'] else 'image/png'
    b64  = base64.b64encode(Path(IMAGEN).read_bytes()).decode()
    img_tag = f'<img src="data:{mime};base64,{b64}" style="width:100%;height:100%;object-fit:cover;position:absolute;top:0;left:0;">'

# ── Spine font size ────────────────────────────────────────────────────────
spine_pt = max(5, min(9, round(spine_in * 25.4 * 0.55)))
spine_gap = max(1, round(spine_in * 25.4 * 0.2))

# ── Barcode ────────────────────────────────────────────────────────────────
bc_w = mm(2.0); bc_h = mm(1.2)

# ── Base colors (customized in --cover) ────────────────────────────────────
BG_DARK = '#1a1a2e'
BG_SPINE = '#16213e'
BG_FRONT = '#0f3460'

# ── HTML ─────────────────────────────────────────────────────────────────
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Wrap — {titulo}</title>
<style>
@page {{ size: {tw}mm {th}mm; margin: 0; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ width:{tw}mm; height:{th}mm; font-family:Georgia,serif; color:#111; overflow:hidden; background:#ddd; }}

/* ── Horizontal wrap ── */
.wrap {{ display:flex; width:{tw}mm; height:{th}mm; position:relative; }}

/* ── Back cover ── */
.back {{
  width:{mm(PAGE_W+BLEED)}mm; height:{th}mm;
  background:{BG_DARK}; flex-shrink:0; position:relative; overflow:hidden;
}}
.back-content {{
  position:absolute;
  top:{mm(BLEED+SAFE)}mm; left:{mm(BLEED+SAFE)}mm;
  right:{sa}mm; bottom:{mm(BLEED+SAFE+1.4)}mm;
}}
.back-blurb {{
  font-size:9pt; line-height:1.55; color:#efefef;
  text-align:justify; margin-bottom:5mm; white-space:pre-line;
}}
.back-bio {{
  font-size:8pt; line-height:1.4; color:#ccc; font-style:italic;
  border-top:0.2mm solid rgba(255,255,255,0.25); padding-top:3mm;
}}
.barcode {{
  position:absolute;
  bottom:{mm(BLEED+SAFE)}mm; right:{sa}mm;
  width:{bc_w}mm; height:{bc_h}mm;
  background:white; padding:1.5mm;
  display:flex; flex-direction:column; align-items:center; justify-content:space-between;
}}
.barcode-lines {{
  width:100%; height:75%; flex-shrink:0;
  background:repeating-linear-gradient(
    to right,
    #000 0,#000 0.8mm, white 0.8mm,white 1.2mm,
    #000 1.2mm,#000 1.6mm, white 1.6mm,white 2.4mm,
    #000 2.4mm,#000 2.6mm, white 2.6mm,white 3.6mm
  );
}}
.barcode-isbn {{ font-size:5pt; color:#111; text-align:center; }}

/* ── Spine ── */
.spine {{
  width:{sp}mm; height:{th}mm;
  background:{BG_SPINE}; flex-shrink:0;
  display:flex; align-items:center; justify-content:center; overflow:hidden;
}}
.spine-inner {{
  transform:rotate(90deg); white-space:nowrap;
  display:flex; align-items:center; gap:{spine_gap}mm;
  color:white; font-size:{spine_pt}pt; letter-spacing:0.05em;
}}
.spine-title {{ font-weight:bold; text-transform:uppercase; }}
.spine-sep {{ opacity:0.4; }}
.spine-autor {{ font-style:italic; opacity:0.8; }}

/* ── Front cover ── */
.front {{
  width:{mm(PAGE_W+BLEED)}mm; height:{th}mm;
  background:{BG_FRONT}; flex-shrink:0; position:relative; overflow:hidden;
}}
.img-placeholder {{
  width:100%; height:100%;
  background:linear-gradient(135deg,#1a1a4e 0%,#2d2d7a 50%,#4a1a6e 100%);
  display:flex; align-items:center; justify-content:center;
}}
.img-placeholder span {{
  color:rgba(255,255,255,0.25); font-size:12pt;
  text-transform:uppercase; letter-spacing:0.2em; text-align:center; padding:5mm;
}}
.front-gradient {{
  position:absolute; bottom:0; left:0; right:0;
  height:40%; padding:{bl}mm {mm(SAFE+BLEED)}mm {mm(SAFE+BLEED)}mm;
  background:linear-gradient(to top,rgba(0,0,0,0.88) 0%,transparent 100%);
  display:flex; flex-direction:column; justify-content:flex-end;
}}
.front-titulo {{
  font-size:22pt; font-weight:bold; color:white;
  text-transform:uppercase; letter-spacing:0.04em; line-height:1.1;
  margin-bottom:2.5mm; text-shadow:0 2px 6px rgba(0,0,0,0.9);
}}
.front-autor {{
  font-size:10pt; color:rgba(255,255,255,0.82);
  letter-spacing:0.12em; text-transform:uppercase; font-style:italic;
}}

/* ── Guides ── */
.guide-bleed {{
  position:absolute; top:0; left:0; right:0; bottom:0;
  border:{bl}mm solid rgba(255,50,50,0.35); pointer-events:none; z-index:200;
}}
.guide-spine-left {{
  position:absolute; top:0; bottom:0;
  left:{mm(PAGE_W+BLEED)}mm; width:0.1mm;
  background:rgba(0,0,255,0.4); z-index:200;
}}
.guide-spine-right {{
  position:absolute; top:0; bottom:0;
  left:{mm(PAGE_W+BLEED+spine_in)}mm; width:0.1mm;
  background:rgba(0,0,255,0.4); z-index:200;
}}
.draft-mark {{
  position:absolute; top:50%; left:50%;
  transform:translate(-50%,-50%) rotate(-30deg);
  font-size:42pt; color:rgba(255,0,0,0.04);
  font-weight:bold; white-space:nowrap; z-index:50; pointer-events:none;
}}
</style>
</head>
<body>
<div class="wrap">

  <!-- BACK COVER -->
  <div class="back">
    <div class="back-content">
      <div class="back-blurb">{blurb}</div>
      <div class="back-bio">{bio}</div>
    </div>
    <div class="barcode">
      <div class="barcode-lines"></div>
      <div class="barcode-isbn">{isbn}</div>
    </div>
  </div>

  <!-- SPINE -->
  <div class="spine">
    <div class="spine-inner">
      <span class="spine-title">{titulo}</span>
      <span class="spine-sep">|</span>
      <span class="spine-autor">{autor}</span>
    </div>
  </div>

  <!-- FRONT COVER -->
  <div class="front">
    {img_tag}
    <div class="front-gradient">
      <div class="front-titulo">{titulo}</div>
      <div class="front-autor">{autor}</div>
    </div>
  </div>

</div>

<!-- Visual guides — REMOVE THIS LAYER FROM THE FINAL DESIGN -->
<div class="guide-bleed"></div>
<div class="guide-spine-left"></div>
<div class="guide-spine-right"></div>
<div class="draft-mark">DRAFT</div>

</body>
</html>"""

out_html = OUTPUT / 'wrap-completo.html'
out_html.write_text(html, encoding='utf-8')
print(f"✓ HTML: {out_html}")

info = {
    'titulo': titulo, 'paginas': PAGINAS, 'papel': PAPEL,
    'spine_pulgadas': spine_in, 'spine_mm': sp,
    'total_w_pulgadas': total_w, 'total_h_pulgadas': total_h,
    'total_w_mm': tw, 'total_h_mm': th,
    'back_w_mm': pw, 'front_w_mm': pw, 'bleed_mm': bl,
    'safe_mm': sa, 'barcode_w_mm': bc_w, 'barcode_h_mm': bc_h,
}
(OUTPUT / 'wrap-dimensiones.json').write_text(json.dumps(info, indent=2, ensure_ascii=False))
print(f"✓ Dimensions: {OUTPUT / 'wrap-dimensiones.json'}")

try:
    from weasyprint import HTML as WH
    out_pdf = OUTPUT / 'wrap-completo.pdf'
    WH(filename=str(out_html)).write_pdf(str(out_pdf))
    print(f"✓ PDF: {out_pdf}")
except ImportError:
    print(f"\n⚠ WeasyPrint not installed: pip install weasyprint")
    print(f"  Alternative: open {out_html} in Chrome → Print → Save as PDF")
    print(f"  Custom size: {tw}mm × {th}mm | No margins | 100% scale")

print(f"""
📐 Wrap dimensions:
   Front / Back cover  : {pw}mm × {mm(PAGE_H)}mm (6" × 9")
   Spine               : {sp}mm ({spine_in}")  [{PAGINAS} pages · {PAPEL} paper]
   Total wrap          : {tw}mm × {th}mm ({total_w}" × {total_h}")
   Bleed               : {bl}mm (0.125")
   Safe zone           : {sa}mm (0.25") from the trim
   Barcode             : {bc_w}mm × {bc_h}mm (2" × 1.2")
""")
