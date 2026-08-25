# EPUB → Amazon KDP — gotchas & upload (Typesetter)

The EPUB is built by `scripts/build_ebook.py` (DOCX → pandoc → EPUBCheck). **Validate locally with
EPUBCheck before uploading** — never trial-and-error on the KDP website.

## Requirements (one-time, macOS)
```bash
brew install pandoc epubcheck      # epubcheck pulls in Java (Temurin)
pip3 install python-docx pillow
```
Without EPUBCheck the EPUB still builds, but validation is skipped — don't upload unvalidated.

## The 8 failures it prevents (don't repeat them)
| # | Symptom in KDP | Cause | How the pipeline avoids it |
|---|---|---|---|
| 1 | "couldn't convert your **HTML** file" | the print-layout `.html` was uploaded | upload the `.epub` from `output/` — never the HTML |
| 2 | "cover: JPG/TIFF only" | a PNG was uploaded as cover | cover is **embedded** in the EPUB; use `covers/kindle-cover-kdp.jpg` (RGB, 1600×2560) |
| 3 | "table of contents missing" | the DOCX TOC isn't detected | EPUB only — the `nav`/`ncx` **is** the device TOC |
| 4 | "spelling: Turnitin" | false positive (a real brand) | ignore that KDP notice |
| 5 | wrong language / metadata | pandoc grabbed `<dc:language>C</dc:language>` from the locale | `metadata.yaml` pins `lang: en` |
| 6 | italics/bold lost | the old extractor flattened to plain text | the script preserves `*italics*`/`**bold**` per run |
| 7 | duplicated title/cover + a ghost TOC entry | the DOCX front-matter was included | the script drops everything before the 1st heading |
| 8 | title/subtitle **not centered** on the title page | `<p>` inherited justify + indent | `ebook.css` centers `section.titlepage` and its `.title/.subtitle/.author/.date` |

## Uploading to KDP (and why the file sometimes "doesn't appear")
1. KDP → your book → **"Kindle eBook manuscript" → "Upload manuscript"** → pick the `.epub` from `output/`.
2. **If the upload dialog doesn't show the file** (even though Finder does):
   ```bash
   cp "<book>/output/<slug>.epub" ~/Desktop/<Clean-Title>.epub
   xattr -d com.apple.quarantine ~/Desktop/<Clean-Title>.epub 2>/dev/null
   ```
   (Folders with spaces/accents and the quarantine attribute can hide it in the picker.) In the
   macOS dialog, set any file-type dropdown to *"All files"*. Confirm it's a real EPUB:
   `file <file>.epub` → must say `EPUB document`.

The paperback wrap cover and commercial metadata (blurb, keywords, categories) are separate KDP
steps (see `/humanink:cover`, `/humanink:copywriter`).

## Verification checklist (before trusting an EPUB)
```bash
epubcheck output/<slug>.epub        # 0 fatal / 0 errors / 0 warnings
```
- `mimetype` is the first zip entry and equals `application/epub+zip`.
- `nav.xhtml` + `.ncx` exist; nav entries = number of book sections.
- `<dc:language>` is correct (not `C`).
- a cover image is embedded (in `EPUB/media/`) and `cover` is set in the `.opf` metadata.
- `<em>`/`<strong>` present if the source had italics/bold.
