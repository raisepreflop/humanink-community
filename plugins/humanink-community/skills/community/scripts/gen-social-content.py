#!/usr/bin/env python3
"""gen-social-content.py — Banner and carousel generator for social networks
Usage: python3 gen-social-content.py <folder> <type> <network> <format> [--brand brand-kit.json]
types: banner | carrusel | todos
networks: instagram | facebook | youtube
instagram formats: cuadrado|vertical|story|reel
facebook formats:  feed|story|cover
youtube formats:   thumbnail|shorts
"""
import sys, os, json, base64
from pathlib import Path

args = sys.argv[1:]
CARPETA  = Path(args[0]) if args else Path('.')
TIPO     = args[1] if len(args)>1 else 'banner'
RED      = args[2] if len(args)>2 else 'instagram'
FORMATO  = args[3] if len(args)>3 else 'cuadrado'
BRAND_F  = None
OUTPUT   = CARPETA / 'social' / RED

for i, a in enumerate(args):
    if a == '--brand' and i+1 < len(args): BRAND_F = Path(args[i+1])
    if a == '--output' and i+1 < len(args): OUTPUT = Path(args[i+1])

OUTPUT.mkdir(parents=True, exist_ok=True)

# ── Exact 2025 dimensions ────────────────────────────────────────────────
SIZES = {
    'instagram': {
        'cuadrado': (1080, 1080, '1:1'),
        'vertical': (1080, 1350, '4:5'),
        'story':    (1080, 1920, '9:16'),
        'reel':     (1080, 1920, '9:16'),
        'carrusel': (1080, 1080, '1:1'),
    },
    'facebook': {
        'feed':   (1200, 630, '16:9'),
        'cuadrado':(1080, 1080, '1:1'),
        'story':  (1080, 1920, '9:16'),
        'cover':  (820, 312, '2.63:1'),
    },
    'youtube': {
        'thumbnail': (1280, 720,  '16:9'),
        'banner':    (2560, 1440, '16:9'),
        'shorts':    (1080, 1920, '9:16'),
    }
}

w, h, ratio = SIZES.get(RED, {}).get(FORMATO, (1080, 1080, '1:1'))
scale = 0.35  # visual scale in the HTML (so it fits on screen)
vw = round(w * scale); vh = round(h * scale)

# ── Brand kit ────────────────────────────────────────────────────────────
brand = {
    'nombre':       'Autor',
    'color_primary': '#1a1a2e',
    'color_accent':  '#e94560',
    'color_bg':      '#ffffff',
    'color_text':    '#111111',
    'font_title':    'Playfair Display, Georgia, serif',
    'font_body':     'Lato, Helvetica, sans-serif',
    'logo_url':      '',
}
if BRAND_F and Path(BRAND_F).exists():
    try:
        bk = json.loads(Path(BRAND_F).read_text(encoding='utf-8'))
        brand.update(bk)
    except: pass
else:
    bk_path = CARPETA / 'brand-kit.json'
    if bk_path.exists():
        try:
            bk = json.loads(bk_path.read_text(encoding='utf-8'))
            brand.update(bk)
        except: pass

# ── Placeholder text per zone ──────────────────────────────────────────
hook = 'HOOK — The line that stops the scroll'
msg  = 'MESSAGE — The value this content delivers in one or two clear lines'
cta  = 'CTA — The action: "Download free", "Join", "Read the first chapter"'
slug = f'{RED}-{FORMATO}'

# ── HTML banner ──────────────────────────────────────────────────────────
def make_banner():
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Banner {RED} {FORMATO} — {w}×{h}px</title>
<style>
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ width:{vw}px; height:{vh}px; font-family:{brand['font_body']}; overflow:hidden; background:#eee; }}
.card {{
  width:{vw}px; height:{vh}px; position:relative; overflow:hidden;
  background:{brand['color_primary']};
}}
.bg-texture {{
  position:absolute; inset:0;
  background:linear-gradient(135deg,{brand['color_primary']} 0%,#2a2a5e 60%,{brand['color_accent']}22 100%);
}}
/* HOOK zone — top 20% */
.zone-hook {{
  position:absolute; top:0; left:0; right:0;
  height:20%; padding:{round(vh*0.03)}px {round(vw*0.06)}px;
  display:flex; align-items:center;
  background:{brand['color_accent']}22;
  border-bottom:2px solid {brand['color_accent']};
}}
.hook-text {{
  font-family:{brand['font_title']}; font-weight:700;
  font-size:{round(vw*0.045)}px; color:white; line-height:1.2;
  text-transform:uppercase; letter-spacing:0.02em;
}}
/* MESSAGE zone — central 55% */
.zone-msg {{
  position:absolute; top:20%; left:0; right:0;
  height:55%; padding:{round(vh*0.04)}px {round(vw*0.06)}px;
  display:flex; flex-direction:column; justify-content:center;
}}
.msg-text {{
  font-family:{brand['font_body']}; font-size:{round(vw*0.038)}px;
  color:rgba(255,255,255,0.9); line-height:1.5; margin-bottom:{round(vh*0.02)}px;
}}
.author-tag {{
  font-size:{round(vw*0.028)}px; color:{brand['color_accent']};
  letter-spacing:0.1em; text-transform:uppercase; font-style:italic;
}}
/* CTA zone — bottom 25% */
.zone-cta {{
  position:absolute; bottom:0; left:0; right:0;
  height:25%; padding:{round(vh*0.025)}px {round(vw*0.06)}px;
  background:linear-gradient(to top,rgba(0,0,0,0.7),transparent);
  display:flex; align-items:center; justify-content:space-between;
}}
.cta-btn {{
  background:{brand['color_accent']}; color:white;
  padding:{round(vh*0.025)}px {round(vw*0.06)}px;
  font-family:{brand['font_body']}; font-size:{round(vw*0.032)}px;
  font-weight:700; letter-spacing:0.05em; text-transform:uppercase;
  border:none; border-radius:4px; white-space:nowrap;
}}
.cta-social {{
  font-size:{round(vw*0.025)}px; color:rgba(255,255,255,0.6);
  font-style:italic;
}}
/* Zone guides (in preview) */
.zone-label {{
  position:absolute; right:4px;
  font-size:9px; color:rgba(255,255,0,0.5);
  font-family:monospace; pointer-events:none;
}}
.lbl-hook {{ top:{round(vh*0.05)}px; }}
.lbl-msg  {{ top:{round(vh*0.4)}px; }}
.lbl-cta  {{ bottom:{round(vh*0.1)}px; }}
/* Size info */
.size-badge {{
  position:absolute; top:4px; left:4px; padding:2px 5px;
  background:rgba(0,0,0,0.5); color:#fff; font-size:9px; font-family:monospace;
  border-radius:2px;
}}
</style>
</head>
<body>
<div class="card">
  <div class="bg-texture"></div>
  <div class="zone-hook">
    <div class="hook-text">{hook}</div>
  </div>
  <div class="zone-msg">
    <div class="msg-text">{msg}</div>
    <div class="author-tag">— {brand['nombre']}</div>
  </div>
  <div class="zone-cta">
    <button class="cta-btn">{cta}</button>
    <div class="cta-social">@{brand.get('handle', brand['nombre'].lower().replace(' ','_'))}</div>
  </div>
  <div class="size-badge">{w}×{h} · {RED} {FORMATO}</div>
  <div class="zone-label lbl-hook">HOOK</div>
  <div class="zone-label lbl-msg">MESSAGE</div>
  <div class="zone-label lbl-cta">CTA</div>
</div>
</body>
</html>"""

# ── HTML carousel (slide N of N) ──────────────────────────────────────────
def make_carousel_slide(n, total, texto_slide, tipo_slide='contenido'):
    colores = {
        'portada':  brand['color_primary'],
        'contenido': '#0f3460',
        'cierre':   brand['color_accent'],
    }
    bg = colores.get(tipo_slide, '#0f3460')
    is_last = (n == total)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Slide {n}/{total} — {RED}</title>
<style>
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ width:{vw}px; height:{vh}px; font-family:{brand['font_body']}; overflow:hidden; }}
.slide {{
  width:{vw}px; height:{vh}px; position:relative; overflow:hidden;
  background:{bg};
}}
.slide-bg {{ position:absolute;inset:0;
  background:linear-gradient(150deg,{bg} 0%,{bg}cc 100%); }}
.slide-num {{
  position:absolute; top:{round(vh*0.04)}px; right:{round(vw*0.05)}px;
  font-size:{round(vw*0.03)}px; color:rgba(255,255,255,0.4); font-family:monospace;
}}
.slide-content {{
  position:absolute; inset:0;
  padding:{round(vh*0.08)}px {round(vw*0.07)}px;
  display:flex; flex-direction:column; justify-content:center;
}}
.slide-label {{
  font-size:{round(vw*0.028)}px; color:{brand['color_accent']};
  text-transform:uppercase; letter-spacing:0.1em; margin-bottom:{round(vh*0.02)}px;
}}
.slide-text {{
  font-family:{brand['font_title']}; font-size:{round(vw*0.052)}px;
  color:white; line-height:1.25; font-weight:700;
}}
.slide-sub {{
  font-size:{round(vw*0.034)}px; color:rgba(255,255,255,0.75);
  line-height:1.4; margin-top:{round(vh*0.025)}px;
}}
.slide-cta {{
  margin-top:{round(vh*0.04)}px;
  background:{brand['color_accent']}; color:white;
  padding:{round(vh*0.022)}px {round(vw*0.05)}px;
  font-size:{round(vw*0.032)}px; font-weight:700;
  text-transform:uppercase; letter-spacing:0.05em; display:inline-block;
}}
.progress {{
  position:absolute; bottom:0; left:0; right:0; height:3px;
  background:rgba(255,255,255,0.15);
}}
.progress-fill {{
  height:100%; width:{round(n/total*100)}%;
  background:{brand['color_accent']};
  transition:width 0.3s;
}}
</style>
</head>
<body>
<div class="slide">
  <div class="slide-bg"></div>
  <div class="slide-num">{n}/{total}</div>
  <div class="slide-content">
    <div class="slide-label">{'HOOK →' if n==1 else 'CTA' if is_last else f'POINT {n-1}'}</div>
    <div class="slide-text">{texto_slide}</div>
    {'<div class="slide-sub">Swipe to discover more →</div>' if n==1 else ''}
    {'<div class="slide-cta">' + cta + '</div>' if is_last else ''}
  </div>
  <div class="progress"><div class="progress-fill"></div></div>
</div>
</body>
</html>"""

# ── Generate files ────────────────────────────────────────────────────────
if TIPO in ['banner', 'todos']:
    banner_html = OUTPUT / f'banner-{slug}.html'
    banner_html.write_text(make_banner(), encoding='utf-8')
    print(f"✓ Banner: {banner_html}")
    print(f"  Final size: {w}×{h}px · Preview scaled to {round(scale*100)}%")

if TIPO in ['carrusel', 'todos']:
    slides_dir = OUTPUT / f'carrusel-{slug}'
    slides_dir.mkdir(exist_ok=True)
    slide_textos = [
        hook,
        'POINT 1 — First reason / first tip / first step',
        'POINT 2 — Second reason / second tip / second step',
        'POINT 3 — Third reason / third tip / third step',
        'POINT 4 — Optional fourth point or deeper dive',
        cta,
    ]
    for i, txt in enumerate(slide_textos, 1):
        tipo = 'portada' if i==1 else 'cierre' if i==len(slide_textos) else 'contenido'
        slide_file = slides_dir / f'slide-{i:02d}.html'
        slide_file.write_text(make_carousel_slide(i, len(slide_textos), txt, tipo), encoding='utf-8')
    print(f"✓ Carousel: {slides_dir}/ ({len(slide_textos)} slides)")

print(f"""
📱 To export as a PNG/JPG image:
   Chromium: chromium --headless --screenshot={OUTPUT}/banner-{slug}.png --window-size={w},{h} {OUTPUT}/banner-{slug}.html
   or: open in Chrome → DevTools → Device toolbar → Custom {w}×{h} → Screenshot
   or: Chrome extension "GoFullPage" or "Awesome Screenshot"

📐 Specifications {RED} {FORMATO}:
   Dimensions: {w} × {h} px · Ratio: {ratio}
   Max size: 30 MB (PNG) · 8 MB (JPG)
   Color depth: RGB (not CMYK)
""")
