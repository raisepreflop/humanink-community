#!/usr/bin/env python3
"""compose-kdp-wrap.py — Build a KDP paperback wrap PANEL BY PANEL at exact
print geometry, instead of stretching a pre-baked design.

Use this when the source design was built to the wrong internal measurements
(spine offset, baked-in barcode) or is too low-resolution. It composes:

  [ BACK COVER ]  [ SPINE ]  [ FRONT COVER ]

on a solid background, with:
  - the FRONT pasted from a crisp image (e.g. the ebook cover),
  - the SPINE re-rendered as crisp vertical text at the EXACT 0.305"-style width,
  - the BACK re-typeset as live text (head / subhead / body + author bio + logo),
  - the BARCODE area LEFT BLANK (KDP prints your ISBN barcode there).

Everything text is rendered at full DPI -> razor sharp. Designed for covers on a
solid background (the whole TAW design is on black, so panels join seamlessly).

Usage:
  python3 compose-kdp-wrap.py \
    --front "kindle-cover-kdp.jpg" \
    --content "back-cover.json" \
    --assets-dir "covers" \
    --pages 122 --paper cream --trim 6x9 --dpi 600 \
    --out "output/kdp-wrap" --slug the-augmented-writer \
    --template "kdp-template.png"      # optional, for the proof overlay
"""
import sys, json, argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONT_DIRS = ["/System/Library/Fonts/Supplemental", "/System/Library/Fonts",
             "/Library/Fonts", str(Path.home() / "Library/Fonts")]
def font_path(*names):
    for d in FONT_DIRS:
        for n in names:
            p = Path(d) / n
            if p.exists():
                return str(p)
    return None
# A clean humanist sans matches the TAW back cover; fall back gracefully.
SANS        = font_path("Helvetica.ttc", "Arial.ttf", "HelveticaNeue.ttc")
SANS_BOLD   = font_path("Helvetica.ttc", "Arial Bold.ttf", "Arial.ttf")
SANS_ITAL   = font_path("Arial Italic.ttf", "Helvetica.ttc")

SPINE_PER_PAGE = {"white": 0.002252, "cream": 0.0025, "color": 0.002347}
BLEED_IN, SAFE_IN = 0.125, 0.25

def hexc(c):
    c = c.lstrip("#"); return tuple(int(c[i:i+2], 16) for i in (0, 2, 4))

def sample_bg(front_path):
    """Median colour of the front cover's LEFT edge — the exact black that meets
    the spine, so the composed panels join with no visible seam."""
    im = Image.open(front_path).convert("RGB")
    w, h = im.size
    strip = im.crop((0, 0, max(2, w // 40), h))
    px = sorted(strip.getdata(), key=lambda p: p[0] + p[1] + p[2])
    return px[len(px) // 2]

def key_out_black(logo, thr=30):
    """Make the logo's flat black background transparent without eating the
    (navy/gold) emblem — only near-pure-black pixels are removed."""
    logo = logo.convert("RGBA")
    out = []
    for r, g, b, a in logo.getdata():
        out.append((r, g, b, 0) if (r < thr and g < thr and b < thr) else (r, g, b, a))
    logo.putdata(out)
    return logo

def geometry(trim, pages, paper, dpi):
    pw, ph = (float(x) for x in trim.lower().split("x"))
    spine_in = round(pages * SPINE_PER_PAGE.get(paper, 0.0025), 4)
    wrap_w = round(2*pw + spine_in + 2*BLEED_IN, 4)
    wrap_h = round(ph + 2*BLEED_IN, 4)
    px = lambda i: int(round(i*dpi))
    return {
        "dpi": dpi, "page_w_in": pw, "page_h_in": ph, "spine_in": spine_in,
        "spine_mm": round(spine_in*25.4, 2), "wrap_w_in": wrap_w, "wrap_h_in": wrap_h,
        "wrap_w_mm": round(wrap_w*25.4, 2), "wrap_h_mm": round(wrap_h*25.4, 2),
        "W": px(wrap_w), "H": px(wrap_h), "bleed_px": px(BLEED_IN), "safe_px": px(SAFE_IN),
        "spine_px": px(spine_in), "spine_x0": px(BLEED_IN+pw), "spine_x1": px(BLEED_IN+pw+spine_in),
        "barcode_w_px": px(2.0), "barcode_h_px": px(1.2),
    }

# ── word-wrap helper ──────────────────────────────────────────────────────
def wrap_text(draw, text, font, max_w):
    lines = []
    for para in text.split("\n"):
        words, cur = para.split(" "), ""
        for w in words:
            t = (cur + " " + w).strip()
            if draw.textlength(t, font=font) <= max_w:
                cur = t
            else:
                if cur: lines.append(cur)
                cur = w
        lines.append(cur)
    return lines

def draw_block(draw, x, y, max_w, text, font, fill, leading, gap_after):
    for ln in wrap_text(draw, text, font, max_w):
        draw.text((x, y), ln, font=font, fill=fill)
        asc, desc = font.getmetrics()
        y += int((asc + desc) * leading)
    return y + gap_after

# ── front panel ───────────────────────────────────────────────────────────
def paste_front(canvas, g, front_path):
    fx0 = g["spine_x1"]
    fw, fh = g["W"] - fx0, g["H"]
    img = Image.open(front_path).convert("RGB")
    sw, sh = img.size
    scale = max(fw/sw, fh/sh)              # cover
    nw, nh = int(round(sw*scale)), int(round(sh*scale))
    img = img.resize((nw, nh), Image.LANCZOS)
    img = img.crop(((nw-fw)//2, (nh-fh)//2, (nw-fw)//2+fw, (nh-fh)//2+fh))
    canvas.paste(img, (fx0, 0))

# ── spine ─────────────────────────────────────────────────────────────────
def draw_spine(canvas, g, title, author, gold, cream):
    sp_w, H = g["spine_px"], g["H"]
    strip = Image.new("RGBA", (H, sp_w), (0, 0, 0, 0))
    d = ImageDraw.Draw(strip)
    fs = max(12, int(sp_w * 0.42))
    ft = ImageFont.truetype(SANS_BOLD or SANS, fs)
    fa = ImageFont.truetype(SANS_BOLD or SANS, int(fs*0.82))
    sep = "   |   "
    tw = d.textlength(title, font=ft) + d.textlength(sep, font=ft) + d.textlength(author, font=fa)
    x = (H - tw) // 2
    yb = (sp_w - fs) // 2
    d.text((x, yb), title, font=ft, fill=cream); x += d.textlength(title, font=ft)
    d.text((x, yb), sep, font=ft, fill=gold);    x += d.textlength(sep, font=ft)
    d.text((x, yb + int(fs*0.06)), author, font=fa, fill=gold)
    # English convention: spine reads TOP-TO-BOTTOM -> rotate clockwise (-90).
    strip = strip.rotate(-90, expand=True)
    canvas.paste(strip, (g["spine_x0"], 0), strip)

# ── back cover ────────────────────────────────────────────────────────────
def draw_back(canvas, g, c, assets_dir):
    pal = {k: hexc(v) for k, v in c["palette"].items()}
    d = ImageDraw.Draw(canvas)
    x0 = g["bleed_px"] + g["safe_px"]
    x1 = g["spine_x0"] - g["safe_px"]
    max_w = x1 - x0
    y = g["bleed_px"] + g["safe_px"]
    dpi = g["dpi"]
    pt = lambda p: int(round(p/72*dpi))          # points -> px
    f_head = ImageFont.truetype(SANS_BOLD or SANS, pt(17))
    f_sub  = ImageFont.truetype(SANS_BOLD or SANS, pt(11))
    f_body = ImageFont.truetype(SANS or SANS_BOLD, pt(10))
    f_bio  = ImageFont.truetype(SANS or SANS_BOLD, pt(8.5))

    for b in c["blocks"]:
        if b["type"] == "head":
            y = draw_block(d, x0, y, max_w, b["text"].upper(), f_head, pal["gold"], 1.12, pt(7))
            d.line([x0, y, x0 + pt(36), y], fill=pal["gold"], width=max(2, dpi//200)); y += pt(8)
        elif b["type"] == "subhead":
            y = draw_block(d, x0, y, max_w, b["text"].upper(), f_sub, pal["gold"], 1.2, pt(6))
        else:
            y = draw_block(d, x0, y, max_w, b["text"], f_body, pal["body"], 1.42, pt(9))

    # ── author bio block: anchor its BOTTOM above the barcode reserve ──
    logo_box = pt(64)
    tx = x0 + logo_box + pt(10)
    bio_w = x1 - tx
    asc, desc = f_bio.getmetrics()
    lh = int((asc + desc) * 1.34)
    bio_lines = wrap_text(d, c["bio"], f_bio, bio_w)
    bio_h = lh * len(bio_lines)
    barcode_top = g["H"] - g["bleed_px"] - g["safe_px"] - g["barcode_h_px"]
    block_h = max(bio_h, logo_box)
    block_top = barcode_top - pt(14) - block_h          # clears the barcode zone
    lp = Path(assets_dir) / c.get("logo", "")
    if lp.exists():
        logo = key_out_black(Image.open(lp))
        logo.thumbnail((logo_box, logo_box), Image.LANCZOS)
        canvas.paste(logo, (x0, block_top), logo)
    y = block_top
    for ln in bio_lines:
        d.text((tx, y), ln, font=f_bio, fill=pal["muted"]); y += lh

    # ── BARCODE RESERVE: leave a clean blank zone (KDP prints the ISBN here) ──
    bx1, by1 = g["spine_x0"] - g["safe_px"], g["H"] - g["bleed_px"] - g["safe_px"]
    bx0, by0 = bx1 - g["barcode_w_px"], by1 - g["barcode_h_px"]
    # paint with background so nothing bleeds into Amazon's barcode area
    d.rectangle([bx0, by0, bx1, by1], fill=pal["bg"])

# ── proof with guides ─────────────────────────────────────────────────────
def build_proof(final, g, template):
    pw = 1600; sc = pw/g["W"]; ph = int(round(g["H"]*sc))
    proof = final.resize((pw, ph), Image.LANCZOS).convert("RGB")
    if template and Path(template).exists():
        try:
            t = Image.open(template).convert("RGBA").resize((pw, ph), Image.LANCZOS); t.putalpha(85)
            proof = Image.alpha_composite(proof.convert("RGBA"), t).convert("RGB")
        except Exception as e: print("  (template overlay skipped:", e, ")")
    d = ImageDraw.Draw(proof); s = lambda v: int(round(v*sc))
    d.rectangle([s(g["bleed_px"]), s(g["bleed_px"]), pw-s(g["bleed_px"]), ph-s(g["bleed_px"])], outline=(255,40,40), width=2)
    d.line([s(g["spine_x0"]),0,s(g["spine_x0"]),ph], fill=(40,90,255), width=2)
    d.line([s(g["spine_x1"]),0,s(g["spine_x1"]),ph], fill=(40,90,255), width=2)
    sb = s(g["bleed_px"]+g["safe_px"])
    d.rectangle([sb, sb, s(g["spine_x0"])-s(g["safe_px"]), ph-sb], outline=(0,200,80), width=1)
    d.rectangle([s(g["spine_x1"])+s(g["safe_px"]), sb, pw-sb, ph-sb], outline=(0,200,80), width=1)
    bx1 = s(g["spine_x0"])-s(g["safe_px"]); by1 = ph-sb
    d.rectangle([bx1-s(g["barcode_w_px"]), by1-s(g["barcode_h_px"]), bx1, by1], outline=(255,210,0), width=2)
    return proof

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--front", required=True)
    ap.add_argument("--content", required=True)
    ap.add_argument("--assets-dir", default=".")
    ap.add_argument("--pages", type=int, required=True)
    ap.add_argument("--paper", default="cream", choices=["white","cream","color"])
    ap.add_argument("--trim", default="6x9")
    ap.add_argument("--dpi", type=int, default=600, choices=[300,600])
    ap.add_argument("--template")
    ap.add_argument("--out", default="./output")
    ap.add_argument("--slug", default="wrap")
    a = ap.parse_args()

    g = geometry(a.trim, a.pages, a.paper, a.dpi)
    c = json.loads(Path(a.content).read_text())
    # Match the background to the front cover's actual black -> seamless join.
    bg = sample_bg(a.front)
    c["palette"]["bg"] = "#%02X%02X%02X" % bg
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)

    print("="*64)
    print(f"  COMPOSE KDP WRAP · {a.trim} · {a.pages}pp · {a.paper}")
    print(f"  Canvas {g['W']}x{g['H']} @ {a.dpi}DPI · spine {g['spine_in']}\" ({g['spine_mm']}mm)")
    print("="*64)

    canvas = Image.new("RGB", (g["W"], g["H"]), bg)
    paste_front(canvas, g, a.front)
    draw_spine(canvas, g, c["spine_title"], c["spine_author"], hexc(c["palette"]["gold"]), hexc(c["palette"]["cream"]))
    draw_back(canvas, g, c, a.assets_dir)

    png = out / f"{a.slug}-wrap-final.png"
    pdf = out / f"{a.slug}-wrap-final.pdf"
    prf = out / f"{a.slug}-wrap-proof.png"
    canvas.save(png, "PNG")
    canvas.save(pdf, "PDF", resolution=a.dpi)
    build_proof(canvas, g, a.template).save(prf, "PNG")
    (out / f"{a.slug}-wrap-dimensiones.json").write_text(json.dumps(g, indent=2))

    print(f"  ✓ PDF   : {pdf}")
    print(f"  ✓ PNG   : {png}")
    print(f"  ✓ PROOF : {prf}")
    print(f"  ✓ Barcode area left BLANK for Amazon's ISBN.")
    print("="*64)

if __name__ == "__main__":
    main()
