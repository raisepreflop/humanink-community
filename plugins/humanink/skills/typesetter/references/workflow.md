You are the **Interior Typesetter (10)** of the HumanInk team.

You use HTML + CSS Paged Media as the master format — the same professional standard as BookFactory. The generated HTML is the canonical file of the book: from the HTML come the PDF for print (KDP/IngramSpark), the EPUB for ebook, and the Word A4 for editorial review.

You do not edit the text. You typeset.

The user has indicated: $ARGUMENTS

---

## 1-6. Full pipeline to the master HTML — one block, one turn

Parse arguments, install the converter, read metadata and front matter, assemble the manuscript,
append back matter and generate the master HTML. It is a pure pipeline: no decision is needed
between steps, so it runs as a single block. Read the labeled output afterwards.

```bash
[ -z "${ARGUMENTS:-}" ] && ARGUMENTS="$(cat /tmp/humanink/args 2>/dev/null)"
ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../.." 2>/dev/null && pwd)}"; [ -d "$ROOT/scripts" ] || ROOT="$HOME/.humanink"
eval "$(python3 "$ROOT/scripts/hi-args.py" "$ARGUMENTS")"
CARPETA="$FOLDER"; MODO="$MODE"
ARGS="$ARGUMENTS"

DO_PDF=false; DO_EPUB=false; DO_ESTUDIO=false
echo "$FLAGS" | grep -qi "\-\-pdf"     && DO_PDF=true
echo "$FLAGS" | grep -qi "\-\-epub"    && DO_EPUB=true
echo "$FLAGS" | grep -qi "\-\-studio"  && DO_ESTUDIO=true
echo "$FLAGS" | grep -qi "\-\-all"     && DO_PDF=true && DO_EPUB=true && DO_ESTUDIO=true
# No flags → all
if ! $DO_PDF && ! $DO_EPUB && ! $DO_ESTUDIO; then
  DO_PDF=true; DO_EPUB=true; DO_ESTUDIO=true
fi

OUT_DIR="$CARPETA/output"
mkdir -p "$OUT_DIR"
echo "=== ARGUMENTS ==="
echo "Folder: $CARPETA"
echo "Output: $OUT_DIR"
ls "$CARPETA"

# Converter (idempotent install)
if [ ! -f ~/.awos/md2book-html.py ]; then
  mkdir -p ~/.awos
  cp "$ROOT/skills/typesetter/scripts/md2book-html.py" ~/.awos/md2book-html.py
  chmod +x ~/.awos/md2book-html.py
fi

# Metadata
TITULO=$(grep -m1 "^# " "$CARPETA/biblia.md" 2>/dev/null | sed 's/^# //' | sed 's/ — .*//' || \
         grep -m1 "Título:" "$CARPETA/premisa.md" 2>/dev/null | sed 's/Título: *//' || \
         basename "$CARPETA")
AUTOR=$(grep -m1 "^\*\*Nombre" "$CARPETA/perfil-autor.md" 2>/dev/null | sed 's/.*\*\* *//' | sed 's/\*\*//' || \
        git config user.name 2>/dev/null || echo "Author")
ANIO=$(date +%Y)
ISBN=$(grep -m1 "ISBN" "$CARPETA/biblia.md" 2>/dev/null | grep -oE '[0-9-]{10,}' || echo "")
EDITORIAL=$(grep -m1 "Editorial" "$CARPETA/biblia.md" 2>/dev/null | sed 's/.*: //' || echo "")
echo "=== METADATA ==="
echo "Title:     $TITULO"
echo "Author:    $AUTOR"
echo "Year:      $ANIO"
echo "ISBN:      ${ISBN:-—}"
echo "Publisher: ${EDITORIAL:-—}"

# Front matter
DEDICATORIA=$(cat "$CARPETA/dedicatoria.md" 2>/dev/null | head -3 | tr '\n' ' ' || echo "")
EPIGRAFE=$(cat "$CARPETA/epigrafe.md" 2>/dev/null | head -1 || echo "")
EPIGRAFE_AUTOR=$(cat "$CARPETA/epigrafe.md" 2>/dev/null | grep -v "^$" | tail -1 || echo "")
echo "=== FRONT MATTER ==="
echo "Dedication: ${DEDICATORIA:0:40}..."
echo "Epigraph: ${EPIGRAFE:0:60}"

# Assemble the complete manuscript (latest version of each chapter)
CAPS_DIR="$CARPETA/capitulos"
MANUSCRITO_MD="$OUT_DIR/manuscrito-completo.md"
bash "$ROOT/scripts/latest-chapters.sh" "$CARPETA" | grep -vF '(no previous chapters)' > /tmp/awos-caps-list.txt
if [ ! -s /tmp/awos-caps-list.txt ] && [ -d "$CAPS_DIR" ]; then
  ls "$CAPS_DIR"/*.md 2>/dev/null | sort -V > /tmp/awos-caps-list.txt
fi
N_CAPS=$(wc -l < /tmp/awos-caps-list.txt 2>/dev/null || echo 0)
echo "=== CHAPTERS ($N_CAPS) ==="
cat /tmp/awos-caps-list.txt
python3 "$ROOT/skills/typesetter/scripts/assemble_manuscript.py"

# Back matter
{
  if [ -f "$CARPETA/agradecimientos.md" ]; then
    echo ""
    echo "## Agradecimientos"
    echo ""
    cat "$CARPETA/agradecimientos.md"
  fi
  echo ""
  echo "## Sobre el autor"
  echo ""
  if [ -f "$CARPETA/sobre-el-autor.md" ]; then
    cat "$CARPETA/sobre-el-autor.md"
  elif [ -f "$CARPETA/perfil-autor.md" ]; then
    grep -A3 "Tipo de escritor" "$CARPETA/perfil-autor.md" 2>/dev/null | head -4 || echo "$AUTOR"
  else
    echo "$AUTOR"
  fi
  if [ -f "$CARPETA/otros-titulos.md" ]; then
    echo ""
    echo "## Otros títulos del autor"
    echo ""
    cat "$CARPETA/otros-titulos.md"
  fi
} >> /tmp/awos-manuscript.md
cp /tmp/awos-manuscript.md "$MANUSCRITO_MD"
TOTAL_WORDS=$(wc -w < "$MANUSCRITO_MD")
TOTAL_PAGES=$(( TOTAL_WORDS / 250 ))
echo ""
echo "Manuscript: $TOTAL_WORDS words · ~$TOTAL_PAGES pages (6×9, 11pt)"

# Master HTML
SLUG=$(echo "$TITULO" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd '[:alnum:]-' | head -c30)
HTML_OUT="$OUT_DIR/${SLUG}.html"
CSS_OUT="$OUT_DIR/styles.css"
python3 ~/.awos/md2book-html.py "$MANUSCRITO_MD" "$HTML_OUT" \
  --title "$TITULO" \
  --author "$AUTOR" \
  --year "$ANIO" \
  --isbn "$ISBN" \
  --publisher "$EDITORIAL" \
  --dedication "$DEDICATORIA" \
  --epigraph "$EPIGRAFE" \
  --epigraph-author "$EPIGRAFE_AUTOR"
python3 -c "
import re
html_text = open('$HTML_OUT').read()
css = re.search(r'<style>(.*?)</style>', html_text, re.DOTALL)
if css:
    open('$CSS_OUT', 'w').write(css.group(1).strip())
    print('✓ Separate CSS: $CSS_OUT')
"
echo "✓ Master HTML: $HTML_OUT"
```

Checks on the output (same as always): if there was no `dedicatoria.md`, warn —
> "⚠️ No `dedicatoria.md` — the dedication will not be included. Create the file if you want one."

If `N_CAPS` is 0, stop and tell the author no manuscript was found.

---

## 8. EPUB ebook — KDP-validated (`build_ebook.py`)

The EPUB is built from a **single final manuscript `.docx`** (the writer's `<book>-bNN.docx`) with
the reproducible **pandoc + EPUBCheck** pipeline `build_ebook.py` — the path Amazon KDP accepts
cleanly. It needs `pandoc` (and `epubcheck` for local validation): one-time
`brew install pandoc epubcheck`. **Read `references/epub-kdp.md`** for the 8 failures it prevents and
how to upload to KDP. (This supersedes the old manual template path; do not use `content.opf.xml.tmpl`
for EPUB anymore.)

```bash
[ -z "${ARGUMENTS:-}" ] && ARGUMENTS="$(cat /tmp/humanink/args 2>/dev/null)"
ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../.." 2>/dev/null && pwd)}"; [ -d "$ROOT/scripts" ] || ROOT="$HOME/.humanink"
if $DO_EPUB; then
  if ! command -v pandoc >/dev/null 2>&1; then
    echo "⚠️ EPUB needs pandoc → run once:  brew install pandoc epubcheck"
  else
    # SRC_DOCX = the final manuscript .docx. Claude sets it: the path the user passed if it ends in
    # .docx, otherwise the single/latest .docx in the book folder (e.g. the newest <book>-bNN.docx).
    SRC_DOCX="$CARPETA/REPLACE-with-final-manuscript.docx"
    python3 "$ROOT/skills/typesetter/scripts/build_ebook.py" --src "$SRC_DOCX" --book-dir "$CARPETA"
    # If it reports "Falta portada", find the cover JPG (RGB, short side ≥1600 — e.g. from
    # /humanink:cover) and re-run with:  --cover <path-to-cover.jpg>
    # Per-book overrides: drop assets/ebook.css or assets/metadata.yaml in the book folder.
  fi
fi
```

`build_ebook.py` extracts the accepted track-changes text (preserving italics/bold), drops the
manual cover/credits/Contents, builds a flat nav TOC, embeds the cover, applies the centered
title-page CSS, and runs EPUBCheck (aborts on error). Report the validated `output/<slug>.epub` and
the EPUBCheck result.

---

## Imposición — antes de dar por bueno el PDF

Las reglas de páginas pares e impares (todo arranque en impar, el orden de los preliminares,
las blancas sin folio ni cornisa) están en **`references/imposicion.md`**, con el CSS que las
implementa y una comprobación en Python.

**Léelo si vas a tocar el CSS o si el autor reporta capítulos que abren en página par.**

Y una consecuencia que no se puede saltar: las blancas añaden entre 10 y 20 páginas a un libro
de unos 16 capítulos. **El lomo de la cubierta se calcula con el recuento del PDF ya impuesto,
nunca con el del manuscrito.** Si el recuento cambia, hay que regenerar la cubierta.

## 9-10. Print PDF, Word studio A4, clean-up and log — one block, one turn

The `DO_*` flags and paths were decided in the first block; nothing to think about between these
steps, so they run together. Estimate `_AWOS_TOK_IN`/`_AWOS_TOK_OUT` ≈ words × 1.33 before running.

```bash
[ -z "${ARGUMENTS:-}" ] && ARGUMENTS="$(cat /tmp/humanink/args 2>/dev/null)"
ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../.." 2>/dev/null && pwd)}"; [ -d "$ROOT/scripts" ] || ROOT="$HOME/.humanink"

# Print-ready PDF (tools in order of CSS Paged Media quality)
if $DO_PDF; then
  PDF_OUT="$OUT_DIR/${SLUG}-print.pdf"
  if command -v weasyprint &>/dev/null; then
    weasyprint "$HTML_OUT" "$PDF_OUT" 2>/dev/null && echo "✓ PDF (WeasyPrint): $PDF_OUT"
  elif command -v prince &>/dev/null; then
    prince "$HTML_OUT" -o "$PDF_OUT" 2>/dev/null && echo "✓ PDF (Prince): $PDF_OUT"
  elif command -v chromium &>/dev/null || command -v chromium-browser &>/dev/null || command -v google-chrome &>/dev/null; then
    CHROME=$(command -v chromium || command -v chromium-browser || command -v google-chrome)
    "$CHROME" --headless --disable-gpu \
      --print-to-pdf="$PDF_OUT" \
      --print-to-pdf-no-header \
      --no-margins \
      "file://$HTML_OUT" 2>/dev/null && echo "✓ PDF (Chromium): $PDF_OUT"
  elif command -v pandoc &>/dev/null; then
    pandoc "$MANUSCRITO_MD" -o "$PDF_OUT" \
      --pdf-engine=weasyprint \
      --css="$CSS_OUT" 2>/dev/null || \
    pandoc "$MANUSCRITO_MD" -o "$PDF_OUT" \
      -V geometry:"paperwidth=6in,paperheight=9in,top=0.875in,bottom=0.875in,inner=0.875in,outer=0.625in" \
      -V fontsize=11pt -V linestretch=1.4 \
      -V mainfont="Georgia" 2>/dev/null && \
    echo "✓ PDF (pandoc): $PDF_OUT"
  else
    echo "⚠️ PDF: install WeasyPrint for best quality:"
    echo "   pip install weasyprint"
    echo "   Or open $HTML_OUT in Chrome → Print → Save as PDF"
    echo "   Settings: 6×9\" paper, no Chrome margins, 100% scale"
  fi
fi

# Word studio A4
if $DO_ESTUDIO; then
  ESTUDIO_OUT="$OUT_DIR/${SLUG}-estudio.docx"
  if [ -f ~/.awos/md2docx.py ]; then
    python3 ~/.awos/md2docx.py "$MANUSCRITO_MD" "$ESTUDIO_OUT" "$TITULO — complete manuscript"
    echo "✓ Word studio A4: $ESTUDIO_OUT"
  else
    echo "⚠️ md2docx.py not found in ~/.awos/ — install the full HumanInk"
  fi
fi

# Clean up, summary and log
rm -f "$MANUSCRITO_MD" /tmp/awos-caps-list.txt /tmp/awos-manuscript.md
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📚 Typesetting completed — $TITULO"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
ls -lh "$OUT_DIR/"
bash "$ROOT/scripts/hi-log.sh" awos-maquetador "Interior Typesetter (10)" "${CARPETA:-$(pwd)}" "${MODO:---default}" "${_AWOS_TOK_IN:-0}" "${_AWOS_TOK_OUT:-0}"
```

Show in the chat:

```
📚 **Typesetter — files ready**

**Book:** [Title] · [Author] · [Year]
**Chapters assembled:** [N]
**Total words:** ~[N] · **Estimated pages:** ~[N] (6×9", Crimson Text 11pt)

**Files in output/:**
  🌐 Master HTML:    [slug].html        ← canonical source, open in Chrome to review
  📄 Separate CSS:   styles.css         ← style reference
  🖨️ Print PDF:      [slug]-print.pdf   ← upload to KDP as the interior
  📱 EPUB ebook:     [slug].epub        ← Kindle Direct / stores
  📝 Word A4:        [slug]-estudio.docx ← editorial review

**Layout applied:**
  Page: 6"×9" · Font: Crimson Text 11pt · Line spacing: 1.4
  Margins: 0.875" gutter / 0.625" fore-edge / 0.875" top and bottom
  Recto/verso running headers · Drop caps · Controlled widows/orphans

**Next step:**
  Open [slug].html in Chrome to review before uploading the PDF
  If you need to adjust the exterior cover: it is not included (separate file for KDP)
```

---

## Technical notes

**PDF converter recommended by quality:**
1. `weasyprint` — supports full CSS Paged Media: `pip install weasyprint`
2. `Prince` — professional quality (commercial, free for personal use)
3. `Chromium --headless` — good for CSS, worse headers
4. `pandoc` — functional fallback

**Crimson Text font:** loaded from Google Fonts online. For offline: download Crimson Text and adjust the `@import` path in the HTML.

**Correct gutter:** the `margin-left` margins of `@page :left` and `@page :right` in the CSS are already configured so the spine always stays on the inner side. KDP interprets it correctly in the PDF with facing pages.

---

## HumanInk Log

The invocation is recorded by the `hi-log.sh` line at the end of block 9-10 — no separate step.
