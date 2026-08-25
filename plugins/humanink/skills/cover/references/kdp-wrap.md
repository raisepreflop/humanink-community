# KDP paperback wrap — exact dimensions (Cover Designer)

The wrap (back + spine + front, one image) must be at the **exact** Amazon KDP print geometry:
`(2 × cover width + spine + 2 × bleed) × (cover height + 2 × bleed)`, at 300/600 DPI. The spine width
is **derived** from trim + page count + paper thickness — never guessed. Only **Pillow** is needed.

## Why it used to "look bad"
Two stacked reasons: **(1) the source art is low-resolution** (AI/hand-made wraps are often saved
small, e.g. 1463×1075 ≈ 117 DPI for 6×9) and **(2) HTML→PDF rendering blurs text and never aligns
the spine fold.** The golden rule: **never bake text into a low-resolution raster** — text must
render at 300 DPI. `compose` fixes both; `mount` fixes only the page size.

## Two methods
- **compose (RECOMMENDED, KDP-valid)** — `scripts/compose-kdp-wrap.py`. Builds the wrap **panel by
  panel** at exact coordinates: a crisp FRONT image, the SPINE and BACK re-rendered as **live text**
  at full DPI, and the **barcode area left blank** for Amazon's ISBN. Use whenever the source art has
  the wrong spine offset, a baked-in barcode, or low resolution. Best on a solid background (panels
  join seamlessly).
- **mount (fallback)** — `scripts/gen-kdp-wrap.py`. Stretches a finished flat wrap onto the exact
  outer dimensions. Fixes the page size but **cannot** fix an internal spine offset or a baked
  barcode. Only when the art was already built to exact KDP geometry.

> Lesson on *The Augmented Writer*: mounting produced a perfect 12.555×9.25" page, but KDP still
> showed it wrong because the boceto's spine was offset and the barcode was baked in. `compose` fixed
> both.

## Geometry facts
- At **600 DPI a 6×9 wrap = 7533 × 5550 px** (integer, no rounding); at 300 DPI = 3766 × 2775 px.
- Paper thickness per page: white `0.002252"`, cream `0.0025"`, color `0.002347"`.
- The PDF physical size is set via the DPI tag → exact by construction (no WeasyPrint/Inkscape).

## Read the proof (`<slug>-wrap-proof.png`) — verify 4 guides
- **Red** = trim line (cut). Nothing important crosses it.
- **Blue** = the two spine folds. They must bracket the design's spine band. If they don't, the art's
  spine is off by the delta — tell the author to rebuild the art at the script's reported spine width.
- **Green** = safe zones. All text/logos sit inside them.
- **Yellow** = barcode area (bottom-right of the back). Keep it clear — Amazon overlays its own
  barcode from the ISBN you assign; never draw your own there.

## Report resolution honestly
If the script reports **< 300 DPI**, say so plainly: the PDF is dimensionally perfect but soft.
Options, best to worst:
1. **Regenerate the art at native size** (≥ the reported px, e.g. 7533×5550). For text-heavy backs,
   use `compose` so the back/spine are live text, not a baked raster.
2. **Swap a higher-res front** (the ebook cover 1600×2560 is ~261 DPI on a 6×9 front).
3. **Stopgap AI upscale** (`--sharpen`, or Real-ESRGAN/Topaz) to 7533×5550, accepting soft edges.

## Outputs (in `--out`)
- `<slug>-wrap-final.pdf` → **upload this to KDP** (RGB, exact size, DPI-tagged; KDP converts to CMYK).
- `<slug>-wrap-final.png` → full-resolution flattened raster.
- `<slug>-wrap-proof.png` → downscaled proof with the KDP guides drawn.
- `<slug>-wrap-dimensiones.json` → all measurements.

Upload at KDP → Paperback Content → Cover → "Upload your own cover file".
