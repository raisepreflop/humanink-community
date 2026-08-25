#!/usr/bin/env python3
"""gen-kdp-wrap.py — Mount a full-wrap cover design onto EXACT Amazon KDP
print dimensions and export a press-ready PDF + a QA proof.

The problem this solves: AI-generated / hand-made wrap designs are usually
saved at low resolution (e.g. 1463x1075 px ~ 116 DPI for a 6x9 wrap). KDP
requires 300 DPI. Placing such art "as is" — or via HTML->PDF — looks blurry
and the dimensions never line up with the spine fold. This script:

  1. Computes the EXACT wrap geometry from trim size + page count + paper
     (same math KDP uses), in pixels at the chosen DPI (default 600 -> integer
     pixels for 6x9: 7533 x 5550).
  2. Mounts the design at those exact pixels (no stretching unless asked),
     so the spine and bleed land where KDP expects them.
  3. Reports the design's *real* effective DPI and warns if it is below 300,
     so you know whether the source art must be regenerated bigger.
  4. Optionally re-renders the SPINE text as live vector-crisp text at full DPI
     (the most common "blurry text" offender).
  5. Exports:
       - <slug>-wrap-final.pdf  -> upload this to KDP (RGB, exact size, DPI tag)
       - <slug>-wrap-final.png  -> full-resolution flattened raster
       - <slug>-wrap-proof.png  -> downscaled, with KDP guides drawn
                                    (trim, spine fold, bleed, safe zone, barcode)

Usage:
  python3 gen-kdp-wrap.py --wrap "boceto.png" --pages 122 --paper cream \
      --trim 6x9 --out ./output --slug the-augmented-writer

Optional:
  --template "kdp-template.png"   overlay the Amazon template on the proof to
                                  visually confirm spine/bleed alignment
  --dpi 300|600                   output DPI (default 600)
  --fit auto|cover|contain|stretch  how to fit the design to exact dims
  --spine-text "TITLE | Author"   re-render crisp spine text on top
  --spine-color "#FFFFFF"
  --title "..." --author "..."    used for --spine-text if not given explicitly
"""
import sys, os, json, argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ── Fonts (macOS) ─────────────────────────────────────────────────────────
FONT_DIRS = [
    "/System/Library/Fonts/Supplemental",
    "/Library/Fonts", "/System/Library/Fonts",
    str(Path.home() / "Library/Fonts"),
]
def find_font(*names):
    for d in FONT_DIRS:
        for n in names:
            p = Path(d) / n
            if p.exists():
                return str(p)
    return None
SERIF       = find_font("Georgia.ttf", "Times New Roman.ttf", "Times.ttc")
SERIF_BOLD  = find_font("Georgia Bold.ttf", "Times New Roman Bold.ttf")
SERIF_ITAL  = find_font("Georgia Italic.ttf", "Times New Roman Italic.ttf")

# ── KDP geometry ──────────────────────────────────────────────────────────
SPINE_PER_PAGE = {"white": 0.002252, "cream": 0.0025, "color": 0.002347}
BLEED_IN = 0.125
SAFE_IN  = 0.25

def geometry(trim, pages, paper, dpi):
    pw, ph = (float(x) for x in trim.lower().split("x"))
    spine_in = round(pages * SPINE_PER_PAGE.get(paper, 0.0025), 4)
    wrap_w_in = round(2 * pw + spine_in + 2 * BLEED_IN, 4)
    wrap_h_in = round(ph + 2 * BLEED_IN, 4)
    px = lambda inch: int(round(inch * dpi))
    g = {
        "trim": trim, "pages": pages, "paper": paper, "dpi": dpi,
        "page_w_in": pw, "page_h_in": ph,
        "spine_in": spine_in, "spine_mm": round(spine_in * 25.4, 2),
        "wrap_w_in": wrap_w_in, "wrap_h_in": wrap_h_in,
        "wrap_w_mm": round(wrap_w_in * 25.4, 2), "wrap_h_mm": round(wrap_h_in * 25.4, 2),
        "bleed_in": BLEED_IN, "safe_in": SAFE_IN,
        # pixel canvas
        "W": px(wrap_w_in), "H": px(wrap_h_in),
        "bleed_px": px(BLEED_IN), "safe_px": px(SAFE_IN),
        "spine_px": px(spine_in),
        # x positions of the two spine folds (left edge of spine, right edge)
        "spine_x0": px(BLEED_IN + pw),
        "spine_x1": px(BLEED_IN + pw + spine_in),
        # barcode box 2.0 x 1.2 in, bottom-right of BACK cover
        "barcode_w_px": px(2.0), "barcode_h_px": px(1.2),
    }
    return g

# ── Fit the design to exact pixels ────────────────────────────────────────
def fit_design(src, W, H, mode):
    sw, sh = src.size
    tgt_ratio, src_ratio = W / H, sw / sh
    if mode == "auto":
        mode = "stretch" if abs(tgt_ratio - src_ratio) < 0.012 else "cover"
    if mode == "stretch":
        return src.resize((W, H), Image.LANCZOS), mode
    if mode == "cover":
        scale = max(W / sw, H / sh)
        nw, nh = int(round(sw * scale)), int(round(sh * scale))
        r = src.resize((nw, nh), Image.LANCZOS)
        left, top = (nw - W) // 2, (nh - H) // 2
        return r.crop((left, top, left + W, top + H)), mode
    # contain
    scale = min(W / sw, H / sh)
    nw, nh = int(round(sw * scale)), int(round(sh * scale))
    r = src.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGB", (W, H), (0, 0, 0))
    canvas.paste(r, ((W - nw) // 2, (H - nh) // 2))
    return canvas, mode

# ── Crisp spine text overlay ──────────────────────────────────────────────
def draw_spine(base, g, text, color):
    """Render text on a transparent strip the size of the spine, rotate it,
    and paste it centered on the spine band. Reads bottom-to-top."""
    sp_w, sp_h = g["spine_px"], g["H"]
    # before rotation the strip is laid out horizontally: width=H, height=spine
    strip = Image.new("RGBA", (sp_h, sp_w), (0, 0, 0, 0))
    d = ImageDraw.Draw(strip)
    # font size ~ 55% of spine thickness, capped
    fs = max(12, int(sp_w * 0.5))
    font = ImageFont.truetype(SERIF_BOLD or SERIF, fs)
    bb = d.textbbox((0, 0), text, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    d.text(((sp_h - tw) // 2 - bb[0], (sp_w - th) // 2 - bb[1]), text,
           font=font, fill=color)
    strip = strip.rotate(90, expand=True)  # now (spine_w, H), reads bottom->top
    base.paste(strip, (g["spine_x0"], 0), strip)
    return base

# ── QA proof with KDP guides ──────────────────────────────────────────────
def build_proof(final, g, template_path):
    proof_w = 1600
    scale = proof_w / g["W"]
    proof_h = int(round(g["H"] * scale))
    proof = final.resize((proof_w, proof_h), Image.LANCZOS).convert("RGB")
    if template_path and Path(template_path).exists():
        try:
            tpl = Image.open(template_path).convert("RGBA").resize((proof_w, proof_h), Image.LANCZOS)
            tpl.putalpha(90)
            proof = Image.alpha_composite(proof.convert("RGBA"), tpl).convert("RGB")
        except Exception as e:
            print(f"  (template overlay skipped: {e})")
    d = ImageDraw.Draw(proof)
    s = lambda v: int(round(v * scale))
    RED, BLUE, GREEN, YEL = (255,40,40), (40,90,255), (0,200,80), (255,210,0)
    # bleed border (outer trim line)
    d.rectangle([s(g["bleed_px"]), s(g["bleed_px"]),
                 proof_w - s(g["bleed_px"]), proof_h - s(g["bleed_px"])],
                outline=RED, width=2)
    # spine folds
    d.line([s(g["spine_x0"]), 0, s(g["spine_x0"]), proof_h], fill=BLUE, width=2)
    d.line([s(g["spine_x1"]), 0, s(g["spine_x1"]), proof_h], fill=BLUE, width=2)
    # safe zone (trim + safe) on the two panels
    sb = s(g["bleed_px"] + g["safe_px"])
    d.rectangle([sb, sb, s(g["spine_x0"]) - s(g["safe_px"]), proof_h - sb],
                outline=GREEN, width=1)
    d.rectangle([s(g["spine_x1"]) + s(g["safe_px"]), sb, proof_w - sb, proof_h - sb],
                outline=GREEN, width=1)
    # barcode box (bottom-right of BACK cover = right edge of back panel = spine_x0)
    bx1 = s(g["spine_x0"]) - s(g["safe_px"])
    by1 = proof_h - sb
    bx0 = bx1 - s(g["barcode_w_px"])
    by0 = by1 - s(g["barcode_h_px"])
    d.rectangle([bx0, by0, bx1, by1], outline=YEL, width=2)
    return proof

# ── Main ──────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wrap", required=True, help="full-wrap design image (the boceto)")
    ap.add_argument("--template", help="Amazon KDP template PNG (for proof overlay)")
    ap.add_argument("--pages", type=int, required=True)
    ap.add_argument("--paper", default="cream", choices=["white", "cream", "color"])
    ap.add_argument("--trim", default="6x9")
    ap.add_argument("--dpi", type=int, default=600, choices=[300, 600])
    ap.add_argument("--fit", default="auto", choices=["auto", "cover", "contain", "stretch"])
    ap.add_argument("--out", default="./output")
    ap.add_argument("--slug", default="wrap")
    ap.add_argument("--sharpen", action="store_true", help="unsharp mask to recover edges after upscale")
    ap.add_argument("--spine-text", default="")
    ap.add_argument("--spine-color", default="#FFFFFF")
    ap.add_argument("--title", default="")
    ap.add_argument("--author", default="")
    a = ap.parse_args()

    g = geometry(a.trim, a.pages, a.paper, a.dpi)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)

    src = Image.open(a.wrap).convert("RGB")
    sw, sh = src.size
    eff_dpi = sw / g["wrap_w_in"]          # real resolution of the design
    eff_dpi_h = sh / g["wrap_h_in"]

    print("=" * 64)
    print(f"  KDP WRAP  ·  {a.trim}  ·  {a.pages} pp  ·  {a.paper} paper")
    print("=" * 64)
    print(f"  Target wrap : {g['wrap_w_in']}\" x {g['wrap_h_in']}\"  "
          f"({g['wrap_w_mm']}mm x {g['wrap_h_mm']}mm)")
    print(f"  Spine       : {g['spine_in']}\" ({g['spine_mm']}mm)")
    print(f"  Canvas      : {g['W']} x {g['H']} px @ {a.dpi} DPI")
    print(f"  Source art  : {sw} x {sh} px  ->  effective {eff_dpi:.0f} DPI")
    if min(eff_dpi, eff_dpi_h) < 300:
        print(f"  ⚠ SOURCE IS BELOW 300 DPI ({min(eff_dpi,eff_dpi_h):.0f}). It will be")
        print(f"    upscaled {a.dpi/eff_dpi:.1f}x. For crisp print, regenerate the art")
        print(f"    at >= {g['W']}x{g['H']} px (or re-render text via --spine-text).")
    else:
        print(f"  ✓ Source meets 300 DPI.")

    # fit to exact pixels
    final, used = fit_design(src, g["W"], g["H"], a.fit)
    print(f"  Fit mode    : {used}")
    if a.sharpen:
        final = final.filter(ImageFilter.UnsharpMask(radius=2.0, percent=90, threshold=2))
        print("  Sharpen     : unsharp mask applied")

    # optional crisp spine text
    spine_txt = a.spine_text or (f"{a.title}   |   {a.author}".strip(" |") if (a.title or a.author) else "")
    if spine_txt:
        col = a.spine_color
        col = tuple(int(col.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
        final = draw_spine(final, g, spine_txt, col)
        print(f"  Spine text  : '{spine_txt}' (crisp overlay)")

    # exports
    png_path = out / f"{a.slug}-wrap-final.png"
    pdf_path = out / f"{a.slug}-wrap-final.pdf"
    proof_path = out / f"{a.slug}-wrap-proof.png"
    json_path = out / f"{a.slug}-wrap-dimensiones.json"

    final.save(png_path, "PNG")
    final.save(pdf_path, "PDF", resolution=a.dpi)   # DPI tag => exact physical size
    proof = build_proof(final, g, a.template)
    proof.save(proof_path, "PNG")
    json_path.write_text(json.dumps({**g, "source_eff_dpi": round(min(eff_dpi, eff_dpi_h), 1),
                                     "fit": used}, indent=2))

    print("-" * 64)
    print(f"  ✓ PDF   (upload to KDP): {pdf_path}")
    print(f"  ✓ PNG   (full res)     : {png_path}")
    print(f"  ✓ PROOF (with guides)  : {proof_path}")
    print(f"  ✓ JSON  (dimensions)   : {json_path}")
    print("=" * 64)

if __name__ == "__main__":
    main()
