#!/usr/bin/env python3
"""Assemble the manuscript markdown from the chapter list.

Reads the chapter paths from /tmp/awos-caps-list.txt (one per line),
extracts text from .docx (via raw XML) or reads .md verbatim, and writes
the combined markdown to /tmp/awos-manuscript.md.
"""
import zipfile, re, sys
from pathlib import Path

caps_file = open('/tmp/awos-caps-list.txt').read().strip().split('\n')
output_parts = []

for cap_path in caps_file:
    cap_path = cap_path.strip()
    if not cap_path:
        continue
    p = Path(cap_path)
    if not p.exists():
        continue

    if p.suffix == '.docx':
        try:
            z = zipfile.ZipFile(str(p))
            xml = z.read('word/document.xml').decode('utf-8', errors='replace')
            # Extract text by paragraphs, preserving breaks
            paras = re.findall(r'<w:p[ >].*?</w:p>', xml, re.DOTALL)
            texts = []
            for para in paras:
                runs = re.findall(r'<w:t[^>]*>([^<]*)</w:t>', para)
                text = ''.join(runs).strip()
                if text:
                    texts.append(text)
            # The first paragraph is usually the chapter title
            if texts:
                # Detect whether the first paragraph is a chapter title
                first = texts[0]
                if first.lower().startswith('capítulo') or first.lower().startswith('capitulo') or len(first) < 80:
                    output_parts.append(f'# {first}')
                    output_parts.extend(texts[1:])
                else:
                    # Use the file name as the title
                    slug = p.stem.replace('-v1','').replace('-v2','').replace('-v3','').replace('-v4','').replace('-v5','')
                    num = ''.join(filter(str.isdigit, slug))
                    output_parts.append(f'# Capítulo {int(num) if num else slug}')
                    output_parts.extend(texts)
        except Exception as e:
            output_parts.append(f'# [Error reading {p.name}: {e}]')
    elif p.suffix == '.md':
        output_parts.append(p.read_text(encoding='utf-8'))

    output_parts.append('')  # blank line between chapters

Path('/tmp/awos-caps-list.txt').parent.joinpath('awos-manuscript.md').write_text(
    '\n'.join(output_parts), encoding='utf-8')
print(f'✓ {len([x for x in output_parts if x.startswith("# ")])} chapters processed')
