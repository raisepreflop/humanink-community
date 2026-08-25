#!/usr/bin/env python3
"""
md2book-html.py — HumanInk Typesetter v2.0
HTML + CSS Paged Media for KDP 6×9" publishing
Based on BookFactory phase-14-layout
"""
import sys, re, argparse, html
from pathlib import Path

# ─── CSS ────────────────────────────────────────────────────────
CSS = """
/* === HumanInk Book Layout — 6×9" KDP === */

@import url('https://fonts.googleapis.com/css2?family=Crimson+Text:ital,wght@0,400;0,600;1,400;1,600&display=swap');

/* Base page */
@page {
  size: 6in 9in;
  margin-top: 0.875in;
  margin-bottom: 0.875in;
}

/* Verso pages (even) — number on the left, book title centered */
@page :left {
  margin-left: 0.625in;
  margin-right: 0.875in;
  @bottom-left {
    content: counter(page);
    font-family: "Crimson Text", Georgia, serif;
    font-size: 9pt;
    color: #000;
  }
  @bottom-center {
    content: string(book-title);
    font-family: "Crimson Text", Georgia, serif;
    font-size: 9pt;
    font-style: italic;
    color: #000;
  }
}

/* Recto pages (odd) — chapter title centered, number on the right */
@page :right {
  margin-left: 0.875in;
  margin-right: 0.625in;
  @bottom-center {
    content: string(chapter-title);
    font-family: "Crimson Text", Georgia, serif;
    font-size: 9pt;
    font-style: italic;
    color: #000;
  }
  @bottom-right {
    content: counter(page);
    font-family: "Crimson Text", Georgia, serif;
    font-size: 9pt;
    color: #000;
  }
}

/* Blancas de cortesía: TOTALMENTE en blanco. Ya limpiaba los folios (bottom-*)
   pero NO las cornisas (top-*), así que una página vacía podía salir con el título
   del libro impreso arriba. Las genera el salto a impar; no se insertan a mano. */
@page :blank {
  @top-left      { content: none; }
  @top-center    { content: none; }
  @top-right     { content: none; }
  @bottom-left   { content: none; }
  @bottom-center { content: none; }
  @bottom-right  { content: none; }
}

/* First page of a chapter — no page number */
@page chapter-start {
  @bottom-left   { content: none; }
  @bottom-center { content: none; }
  @bottom-right  { content: none; }
}

/* Front matter (title page, copyright, dedication, epigraph) */
@page front-matter {
  @bottom-left   { content: none; }
  @bottom-center { content: none; }
  @bottom-right  { content: none; }
}

/* === BASE === */
body {
  font-family: "Crimson Text", Georgia, serif;
  font-size: 11pt;
  line-height: 1.4;
  color: #000;
  text-align: justify;
}

/* === FRONT MATTER === */

.page-title {
  page: front-matter;
  page-break-before: right;   /* legacy: universal */
  break-before: recto;        /* moderno: mismo efecto */
  page-break-after: always;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  min-height: 7in;
  text-align: center;
}

.page-title .book-title {
  font-size: 28pt;
  font-weight: 600;
  letter-spacing: 0.02em;
  margin-bottom: 0.5in;
  line-height: 1.2;
}

.page-title .book-author {
  font-size: 14pt;
  font-style: italic;
}

.page-title .book-publisher {
  position: absolute;
  bottom: 0.5in;
  font-size: 10pt;
  letter-spacing: 0.05em;
}

.page-copyright {
  page: front-matter;
  page-break-before: always;
  page-break-after: always;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  min-height: 7in;
  font-size: 9pt;
  line-height: 1.6;
  color: #333;
}

.page-dedication {
  page: front-matter;
  page-break-before: right;   /* legacy: universal */
  break-before: recto;        /* moderno: mismo efecto */
  page-break-after: always;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  min-height: 7in;
  text-align: center;
  font-style: italic;
  font-size: 12pt;
  line-height: 1.6;
}

.page-epigraph {
  page: front-matter;
  page-break-before: always;
  page-break-after: always;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: flex-end;
  min-height: 7in;
  text-align: right;
}

.page-epigraph blockquote {
  max-width: 3.5in;
  font-style: italic;
  font-size: 11pt;
  line-height: 1.5;
  margin: 0;
}

.page-epigraph .epigraph-attr {
  margin-top: 0.25in;
  font-size: 10pt;
  font-style: normal;
}

/* === CHAPTERS === */

.chapter {
  page-break-before: right;   /* legacy: universal */
  break-before: recto;        /* moderno: mismo efecto */
}

h1 {
  page: chapter-start;
  font-size: 20pt;
  font-weight: 400;
  font-style: normal;
  line-height: 1.2;
  text-align: center;
  letter-spacing: 0.04em;
  margin-top: 1in;
  margin-bottom: 0.5in;
  string-set: chapter-title content();
}

h2 {
  font-size: 13pt;
  font-weight: 600;
  text-align: center;
  margin-top: 1.5em;
  margin-bottom: 0.75em;
}

/* === PARAGRAPHS === */

p {
  margin: 0;
  text-indent: 0.3in;
  widows: 3;
  orphans: 3;
}

/* No indent after a title, separator, or at the start of a section */
h1 + p,
h2 + p,
.scene-break + p,
.chapter > p:first-of-type {
  text-indent: 0;
}

/* === DROP CAP === */
.drop-cap::first-letter {
  font-size: 3em;
  font-weight: 600;
  float: left;
  line-height: 0.75;
  margin-right: 0.06em;
  margin-top: 0.08em;
}

/* === SCENE BREAK === */
.scene-break {
  text-align: center;
  margin: 1em 0;
  text-indent: 0;
  font-size: 10pt;
  letter-spacing: 0.2em;
}

/* === BACK MATTER === */
.section-break {
  page-break-before: right;   /* legacy: universal */
  break-before: recto;        /* moderno: mismo efecto */
}

.section-title {
  font-size: 16pt;
  font-weight: 400;
  text-align: center;
  margin-top: 1in;
  margin-bottom: 0.5in;
  letter-spacing: 0.04em;
}

/* === TITLE FOR CSS STRING === */
#book-title-anchor {
  string-set: book-title content();
  display: none;
}
"""

# ─── Parse Markdown ────────────────────────────────────────────
def escape(t):
    return html.escape(t)

def inline(text):
    """Converts inline markdown to HTML."""
    text = escape(text)
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', text)
    text = re.sub(r'\*\*(.+?)\*\*',     r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*',          r'<em>\1</em>', text)
    text = re.sub(r'_(.+?)_',            r'<em>\1</em>', text)
    return text

def md_to_html_body(md_text, title='', author='', year='2025',
                    isbn='', publisher='', dedication='',
                    epigraph='', epigraph_attr=''):
    lines = md_text.split('\n')
    blocks = []
    buf = []

    for line in lines:
        stripped = line.strip()
        if stripped == '':
            if buf:
                blocks.append(('p', ' '.join(buf)))
                buf = []
        elif stripped.startswith('# '):
            if buf: blocks.append(('p', ' '.join(buf))); buf = []
            blocks.append(('h1', stripped[2:]))
        elif stripped.startswith('## '):
            if buf: blocks.append(('p', ' '.join(buf))); buf = []
            blocks.append(('h2', stripped[3:]))
        elif stripped.startswith('### '):
            if buf: blocks.append(('p', ' '.join(buf))); buf = []
            blocks.append(('h3', stripped[4:]))
        elif stripped in ('---', '***', '* * *', '—'):
            if buf: blocks.append(('p', ' '.join(buf))); buf = []
            blocks.append(('sep', ''))
        else:
            buf.append(stripped)

    if buf:
        blocks.append(('p', ' '.join(buf)))

    html_parts = []

    # ─ Hidden title for CSS string-set
    html_parts.append(f'<span id="book-title-anchor">{escape(title)}</span>')

    # ─ Front matter
    if title:
        pub_html = f'<p class="book-publisher">{escape(publisher)}</p>' if publisher else ''
        html_parts.append(f'''
<div class="page-title">
  <p class="book-title">{escape(title)}</p>
  <p class="book-author">{escape(author)}</p>
  {pub_html}
</div>''')

    # Copyright
    if title and author:
        isbn_line = f'<p>ISBN: {escape(isbn)}</p>' if isbn else ''
        html_parts.append(f'''
<div class="page-copyright">
  <p>© {year}, {escape(author)}</p>
  <p>&nbsp;</p>
  <p>All rights reserved. No part of this publication may be reproduced,<br>
  distributed or transmitted in any form without the prior written permission of the author.</p>
  <p>&nbsp;</p>
  {isbn_line}
  <p>Published through Amazon KDP</p>
  <p>Printed in Spain</p>
</div>''')

    # Dedication
    if dedication:
        html_parts.append(f'''
<div class="page-dedication">
  <p>{escape(dedication)}</p>
</div>''')

    # Epigraph
    if epigraph:
        attr_html = f'<p class="epigraph-attr">— {escape(epigraph_attr)}</p>' if epigraph_attr else ''
        html_parts.append(f'''
<div class="page-epigraph">
  <blockquote>
    <p>"{escape(epigraph)}"</p>
    {attr_html}
  </blockquote>
</div>''')

    # ─ Book body
    in_chapter = False
    first_para_in_chapter = False

    for typ, content in blocks:
        if typ == 'h1':
            if in_chapter:
                html_parts.append('</div>')
            html_parts.append(f'<div class="chapter">')
            html_parts.append(f'<h1>{inline(content)}</h1>')
            in_chapter = True
            first_para_in_chapter = True

        elif typ == 'h2':
            html_parts.append(f'<h2>{inline(content)}</h2>')
            first_para_in_chapter = True

        elif typ == 'h3':
            html_parts.append(f'<h3>{inline(content)}</h3>')
            first_para_in_chapter = True

        elif typ == 'sep':
            html_parts.append('<p class="scene-break">✦</p>')
            first_para_in_chapter = True

        elif typ == 'p':
            if first_para_in_chapter:
                html_parts.append(f'<p class="drop-cap">{inline(content)}</p>')
                first_para_in_chapter = False
            else:
                html_parts.append(f'<p>{inline(content)}</p>')

    if in_chapter:
        html_parts.append('</div>')

    return '\n'.join(html_parts)

def generate_html(md_text, **meta):
    body = md_to_html_body(md_text, **meta)
    title = meta.get('title', 'Book')
    author = meta.get('author', '')
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(title)}</title>
  <style>
{CSS}
  </style>
</head>
<body>
{body}
</body>
</html>'''

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input',  help='Markdown of the complete manuscript')
    parser.add_argument('output', help='Output .html file')
    parser.add_argument('--title',           default='')
    parser.add_argument('--author',          default='')
    parser.add_argument('--year',            default='2025')
    parser.add_argument('--isbn',            default='')
    parser.add_argument('--publisher',       default='')
    parser.add_argument('--dedication',      default='')
    parser.add_argument('--epigraph',        default='')
    parser.add_argument('--epigraph-author', default='', dest='epigraph_attr')
    args = parser.parse_args()

    md = Path(args.input).read_text(encoding='utf-8')
    out = generate_html(md,
        title=args.title, author=args.author, year=args.year,
        isbn=args.isbn, publisher=args.publisher,
        dedication=args.dedication, epigraph=args.epigraph,
        epigraph_attr=args.epigraph_attr)

    Path(args.output).write_text(out, encoding='utf-8')
    print(f'✓ Book HTML saved: {args.output}')

if __name__ == '__main__':
    main()
