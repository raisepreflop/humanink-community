"""
Genera el informe de análisis en markdown o JSON.
"""

import json
import difflib
from pathlib import Path

from metrics import TextMetrics


def _ai_level(score: float) -> str:
    if score >= 70:
        return "ALTO — muy probable texto IA sin editar"
    if score >= 45:
        return "MODERADO — marcas de IA presentes"
    if score >= 20:
        return "BAJO — texto con leve influencia IA"
    return "MUY BAJO — texto con voz humana dominante"


def _metric_line(label: str, value: float, low_is_good: bool = True) -> str:
    if low_is_good:
        icon = "✓" if value <= 0.5 else ("⚠" if value <= 0.75 else "✗")
    else:
        icon = "✓" if value >= 0.5 else ("⚠" if value >= 0.25 else "✗")
    return f"  {icon}  {label:<30} {value}"


def _inline_diff(original: str, humanized: str) -> str:
    """Diff de líneas entre original y humanizado."""
    orig_lines = original.splitlines(keepends=True)
    new_lines = humanized.splitlines(keepends=True)
    diff = difflib.unified_diff(orig_lines, new_lines, fromfile="original", tofile="humanizado", lineterm="")
    return "".join(diff)


def build_markdown(
    filename: str,
    metrics: TextMetrics,
    pattern_hits: list[dict],
    fragments: list[dict],
    humanized=None,  # list[dict] | None
) -> str:
    lines = []
    lines.append(f"# AI Parser Report — {Path(filename).name}\n")
    lines.append(f"## Score general: {metrics.overall_ai_score}/100 — {_ai_level(metrics.overall_ai_score)}\n")

    lines.append("## Métricas estadísticas\n")
    lines.append(f"  {'Palabras':<34} {metrics.word_count}")
    lines.append(f"  {'Frases':<34} {metrics.sentence_count}")
    lines.append(f"  {'Párrafos':<34} {metrics.paragraph_count}")
    lines.append("")
    lines.append(f"  {'Lexical Density':<34} {metrics.lexical_density}  (humano típico: 0.55–0.70)")
    lines.append(f"  {'Type-Token Ratio':<34} {metrics.ttr}  (humano típico: >0.55)")
    lines.append(f"  {'Longitud frase (media±σ)':<34} {metrics.sentence_length_mean} ± {metrics.sentence_length_std}")
    lines.append(f"  {'Burstiness':<34} {metrics.burstiness}  (humano: >0)")
    lines.append(f"  {'Similitud entre párrafos':<34} {metrics.paragraph_similarity}  (IA: >0.15)")
    lines.append(f"  {'Perplexidad aproximada':<34} {metrics.approx_perplexity}  (humano: >8)")
    lines.append(f"  {'Patrones AI (por 100 palabras)':<34} {metrics.ai_pattern_score}")
    lines.append(f"  {'Legibilidad Flesch':<34} {metrics.flesch_ease}")
    lines.append("")

    if pattern_hits:
        lines.append(f"## Patrones AI detectados ({len(pattern_hits)})\n")
        seen = {}
        for h in pattern_hits:
            key = h["description"]
            seen[key] = seen.get(key, 0) + 1
        for desc, count in sorted(seen.items(), key=lambda x: -x[1]):
            lines.append(f"  - {desc}: {count}x")
        lines.append("")

        lines.append("### Ejemplos de patrones encontrados\n")
        shown = set()
        for h in pattern_hits[:10]:
            if h["match"] not in shown:
                lines.append(f'  - "{h["match"]}" → {h["description"]}')
                shown.add(h["match"])
        lines.append("")

    if fragments:
        lines.append(f"## Fragmentos más AI-like (top {len(fragments)})\n")
        for i, f in enumerate(fragments, 1):
            preview = f["text"][:120].replace("\n", " ")
            lines.append(f"  {i}. [párrafo {f['paragraph_index']+1}] Score: {f['score']:.2f}")
            lines.append(f"     Razones: {', '.join(f['reasons'])}")
            lines.append(f"     Texto: \"{preview}...\"")
            lines.append("")

    if humanized:
        lines.append("## Humanización aplicada\n")
        for i, h in enumerate(humanized, 1):
            lines.append(f"### Fragmento {i} (párrafo {h['paragraph_index']+1})\n")
            diff = _inline_diff(h["text"], h["humanized"])
            if diff.strip():
                lines.append("```diff")
                lines.append(diff)
                lines.append("```")
            else:
                lines.append("*(sin cambios — fragmento ya aceptable)*")
            lines.append("")

    return "\n".join(lines)


def _score_color(score: float) -> str:
    if score >= 70:
        return "#e53e3e"
    if score >= 45:
        return "#dd6b20"
    if score >= 20:
        return "#d69e2e"
    return "#38a169"


def _score_label(score: float) -> str:
    if score >= 70:
        return "ALTO"
    if score >= 45:
        return "MODERADO"
    if score >= 20:
        return "BAJO"
    return "MUY BAJO"


def _bar(value: float, max_val: float, color: str = "#58a6ff") -> str:
    pct = min(100, (value / max_val) * 100) if max_val else 0
    return (
        f'<div class="bar-track">'
        f'<div class="bar-fill" style="background:{color};width:{pct:.1f}%"></div>'
        f'</div>'
    )


def _diff_html(original: str, humanized: str) -> str:
    orig_words = original.split()
    new_words = humanized.split()
    sm = difflib.SequenceMatcher(None, orig_words, new_words)
    result = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            result.append(" ".join(orig_words[i1:i2]))
        elif tag == "replace":
            result.append(f'<del>{" ".join(orig_words[i1:i2])}</del> '
                          f'<ins>{" ".join(new_words[j1:j2])}</ins>')
        elif tag == "delete":
            result.append(f'<del>{" ".join(orig_words[i1:i2])}</del>')
        elif tag == "insert":
            result.append(f'<ins>{" ".join(new_words[j1:j2])}</ins>')
    return " ".join(result)


def build_html(
    filename: str,
    metrics: TextMetrics,
    pattern_hits: list[dict],
    fragments: list[dict],
    humanized=None,  # list[dict] | None
) -> str:
    score = metrics.overall_ai_score
    color = _score_color(score)
    label = _score_label(score)
    fname = Path(filename).name

    # Gauge arc SVG (semicircle)
    angle = (score / 100) * 180
    import math
    rad = math.radians(180 - angle)
    cx, cy, r = 100, 100, 70
    x = cx + r * math.cos(rad)
    y = cy - r * math.sin(rad)
    large = 1 if angle > 180 else 0

    # Pattern frequency table
    pattern_freq = {}
    for h in pattern_hits:
        pattern_freq[h["description"]] = pattern_freq.get(h["description"], 0) + 1
    pattern_rows = ""
    for desc, cnt in sorted(pattern_freq.items(), key=lambda x: -x[1]):
        pattern_rows += f"""
        <tr>
          <td>{desc}</td>
          <td style="text-align:center;font-weight:700;color:#f85149">{cnt}x</td>
          <td style="width:120px">{_bar(cnt, 5, "#f85149")}</td>
        </tr>"""

    # Pattern chips
    examples_html = ""
    shown = set()
    for h in pattern_hits[:14]:
        if h["match"] not in shown:
            shown.add(h["match"])
            examples_html += f'<span class="chip">«{h["match"]}» <span class="chip-sub">{h["description"]}</span></span>'

    # Fragment cards
    frags_html = ""
    for i, f in enumerate(fragments, 1):
        preview = f["text"][:300].replace("<", "&lt;").replace(">", "&gt;")
        reasons = ", ".join(f["reasons"])
        score_pct = min(100, f["score"] * 100)
        frags_html += f"""
        <div class="frag-card">
          <div class="frag-header">
            <span class="frag-title">Párrafo {f['paragraph_index']+1}</span>
            <span class="frag-score">Score: {f['score']:.3f}</span>
          </div>
          <div style="margin-bottom:8px">{_bar(score_pct, 100, "#f85149")}</div>
          <div class="frag-reasons">⚑ {reasons}</div>
          <div class="frag-text">«{preview}…»</div>
        </div>"""

    # Humanized diffs
    human_html = ""
    if humanized:
        for i, h in enumerate(humanized, 1):
            diff = _diff_html(h["text"], h["humanized"])
            human_html += f"""
            <div class="diff-card">
              <div class="diff-title">Párrafo {h['paragraph_index']+1} — Humanizado</div>
              <div class="diff-body">{diff}</div>
            </div>"""
        human_section = f"""
        <div class="card">
          <h2>Humanización aplicada</h2>
          <div class="legend">
            <del>tachado</del> = eliminado &nbsp;&nbsp;
            <ins>subrayado</ins> = reescrito
          </div>
          {human_html}
        </div>"""
    else:
        human_section = ""

    # Metric rows
    def mrow(label, value, ref, good):
        icon = "✓" if good else "⚠"
        ic = "var(--accent-ok)" if good else "var(--accent-warn)"
        return f"""<tr>
          <td>{label}</td>
          <td>{value}</td>
          <td>{ref}</td>
          <td style="font-size:15px;color:{ic}">{icon}</td>
        </tr>"""

    metrics_rows = (
        mrow("Palabras", f"{metrics.word_count:,}", "—", True) +
        mrow("Frases", f"{metrics.sentence_count:,}", "—", True) +
        mrow("Párrafos", f"{metrics.paragraph_count:,}", "—", True) +
        mrow("Lexical Density", metrics.lexical_density, "humano: 0.55–0.70", 0.55 <= metrics.lexical_density <= 0.70) +
        mrow("Type-Token Ratio", metrics.ttr, "humano: >0.55", metrics.ttr >= 0.55) +
        mrow("Long. frase media ± σ", f"{metrics.sentence_length_mean} ± {metrics.sentence_length_std}", "varianza alta = humano", metrics.sentence_length_std > 8) +
        mrow("Burstiness", metrics.burstiness, "humano: >0", metrics.burstiness > 0) +
        mrow("Similitud párrafos", metrics.paragraph_similarity, "IA: >0.15", metrics.paragraph_similarity < 0.15) +
        mrow("Perplexidad aprox.", metrics.approx_perplexity, "humano: >8", metrics.approx_perplexity > 8) +
        mrow("Patrones IA / 100w", metrics.ai_pattern_score, "menor = mejor", metrics.ai_pattern_score < 1.0) +
        mrow("Flesch Reading Ease", metrics.flesch_ease, "30–60 = literario", 30 <= metrics.flesch_ease <= 70)
    )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Parser — {fname}</title>
<style>
  :root {{
    --bg:          #0d1117;
    --bg-card:     #161b22;
    --bg-card-alt: #1c2128;
    --bg-row:      #1c2128;
    --border:      #30363d;
    --border-h2:   #21262d;
    --text:        #e6edf3;
    --text-muted:  #7d8590;
    --text-dim:    #484f58;
    --accent-ok:   #3fb950;
    --accent-warn: #d29922;
    --accent-red:  #f85149;
    --accent-blue: #58a6ff;
    --del-bg:      rgba(248,81,73,.18);
    --del-fg:      #ffa198;
    --ins-bg:      rgba(63,185,80,.18);
    --ins-fg:      #56d364;
    --bar-track:   #21262d;
    --shadow:      0 1px 3px rgba(0,0,0,.4);
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Inter', sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.5;
  }}
  .container {{ max-width: 900px; margin: 0 auto; padding: 32px 20px; }}

  .card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 24px;
    margin-bottom: 20px;
    box-shadow: var(--shadow);
  }}

  h1 {{ font-size: 20px; font-weight: 700; color: var(--text); margin-bottom: 2px; letter-spacing: -.3px; }}
  h2 {{
    font-size: 14px; font-weight: 600; text-transform: uppercase;
    letter-spacing: .08em; color: var(--text-muted);
    margin-bottom: 16px; padding-bottom: 10px;
    border-bottom: 1px solid var(--border-h2);
  }}

  .filename {{ color: var(--text-muted); font-size: 12px; font-family: 'SF Mono', monospace; margin-bottom: 22px; }}

  /* Gauge area */
  .gauge-wrap {{ display: flex; align-items: center; gap: 28px; flex-wrap: wrap; }}
  .gauge-info {{ display: flex; flex-direction: column; gap: 6px; }}
  .gauge-score {{ font-size: 32px; font-weight: 800; letter-spacing: -1px; }}
  .gauge-desc {{ color: var(--text-muted); font-size: 13px; max-width: 280px; }}
  .stats-pills {{ display: flex; gap: 10px; margin-top: 10px; flex-wrap: wrap; }}
  .pill {{
    background: var(--bg-card-alt); border: 1px solid var(--border);
    border-radius: 20px; padding: 4px 12px;
    font-size: 12px; color: var(--text-muted);
  }}

  /* Table */
  table {{ width: 100%; border-collapse: collapse; }}
  thead th {{
    padding: 8px 12px; text-align: left;
    font-size: 11px; font-weight: 600; text-transform: uppercase;
    letter-spacing: .06em; color: var(--text-dim);
    border-bottom: 1px solid var(--border);
  }}
  tbody tr {{ border-bottom: 1px solid var(--border-h2); transition: background .1s; }}
  tbody tr:last-child {{ border-bottom: none; }}
  tbody tr:hover {{ background: var(--bg-row); }}
  td {{ padding: 10px 12px; font-size: 13px; }}
  td:first-child {{ color: var(--text-muted); }}
  td:nth-child(2) {{ font-weight: 600; font-family: 'SF Mono', 'Fira Code', monospace; color: var(--text); }}
  td:nth-child(3) {{ color: var(--text-dim); font-size: 12px; }}

  /* Bar */
  .bar-track {{
    background: var(--bar-track); border-radius: 4px; height: 6px; width: 100%;
  }}
  .bar-fill {{ height: 6px; border-radius: 4px; }}

  /* Pattern chips */
  .chips {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 14px; }}
  .chip {{
    background: rgba(248,81,73,.12); border: 1px solid rgba(248,81,73,.25);
    color: var(--del-fg); border-radius: 20px;
    padding: 3px 10px; font-size: 12px;
  }}
  .chip-sub {{ color: var(--text-dim); font-size: 11px; margin-left: 4px; }}

  /* Fragment cards */
  .frag-card {{
    background: var(--bg-card-alt); border: 1px solid var(--border);
    border-radius: 8px; padding: 14px; margin-bottom: 10px;
  }}
  .frag-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }}
  .frag-title {{ font-size: 13px; font-weight: 600; color: var(--text); }}
  .frag-score {{
    background: rgba(248,81,73,.15); color: var(--del-fg);
    border-radius: 12px; padding: 2px 10px; font-size: 12px; font-weight: 700;
  }}
  .frag-reasons {{ font-size: 11px; color: var(--text-dim); margin-bottom: 8px; }}
  .frag-text {{
    background: var(--bg); border-left: 3px solid var(--border);
    padding: 10px 14px; border-radius: 0 6px 6px 0;
    font-size: 13px; color: var(--text-muted);
    font-style: italic; line-height: 1.7;
  }}

  /* Diff */
  .diff-card {{
    background: var(--bg-card-alt); border: 1px solid rgba(63,185,80,.25);
    border-radius: 8px; padding: 16px; margin-bottom: 14px;
  }}
  .diff-title {{ font-weight: 600; color: var(--ins-fg); font-size: 13px; margin-bottom: 12px; }}
  .diff-body {{ line-height: 1.9; font-size: 14px; color: var(--text); }}
  del {{
    background: var(--del-bg); color: var(--del-fg);
    padding: 1px 4px; border-radius: 3px; text-decoration: line-through;
  }}
  ins {{
    background: var(--ins-bg); color: var(--ins-fg);
    padding: 1px 4px; border-radius: 3px; text-decoration: none;
  }}
  .legend {{ font-size: 12px; color: var(--text-dim); margin-bottom: 14px; }}

  .footer {{ text-align: center; padding: 20px; color: var(--text-dim); font-size: 11px; }}
</style>
</head>
<body>
<div class="container">

  <!-- HEADER -->
  <div class="card">
    <h1>AI Parser Report</h1>
    <div class="filename">{fname}</div>
    <div class="gauge-wrap">
      <svg width="190" height="106" viewBox="0 0 200 110">
        <path d="M 30 100 A 70 70 0 0 1 170 100" fill="none" stroke="#21262d" stroke-width="12" stroke-linecap="round"/>
        <path d="M 30 100 A 70 70 0 0 1 {x:.2f} {y:.2f}" fill="none" stroke="{color}" stroke-width="12" stroke-linecap="round" opacity=".9"/>
        <text x="100" y="86" text-anchor="middle" font-size="30" font-weight="800" fill="{color}" font-family="-apple-system,sans-serif">{score}</text>
        <text x="100" y="102" text-anchor="middle" font-size="10" fill="#484f58" font-family="-apple-system,sans-serif">/ 100</text>
      </svg>
      <div class="gauge-info">
        <div class="gauge-score" style="color:{color}">{label}</div>
        <div class="gauge-desc">{_ai_level(score)}</div>
        <div class="stats-pills">
          <span class="pill">📄 {metrics.word_count:,} palabras</span>
          <span class="pill">⚑ {len(pattern_hits)} patrones</span>
          <span class="pill">🔍 {len(fragments)} fragmentos</span>
        </div>
      </div>
    </div>
  </div>

  <!-- MÉTRICAS -->
  <div class="card">
    <h2>Métricas estadísticas</h2>
    <table>
      <thead><tr>
        <th>Métrica</th><th>Valor</th><th>Referencia</th><th></th>
      </tr></thead>
      <tbody>{metrics_rows}</tbody>
    </table>
  </div>

  <!-- PATRONES -->
  {'<div class="card"><h2>Patrones AI detectados (' + str(len(pattern_hits)) + ')</h2><table><thead><tr><th>Patrón</th><th>Veces</th><th style="width:140px">Frecuencia</th></tr></thead><tbody>' + pattern_rows + '</tbody></table><div class="chips">' + examples_html + '</div></div>' if pattern_hits else ''}

  <!-- FRAGMENTOS -->
  {'<div class="card"><h2>Fragmentos más AI-like</h2>' + frags_html + '</div>' if fragments else ''}

  <!-- HUMANIZACIÓN -->
  {human_section}

  <div class="footer">AI Parser · {fname}</div>
</div>
</body>
</html>"""


def build_json(
    filename: str,
    metrics: TextMetrics,
    pattern_hits: list[dict],
    fragments: list[dict],
    humanized=None,  # list[dict] | None
) -> str:
    data = {
        "file": filename,
        "metrics": metrics._asdict(),
        "ai_level": _ai_level(metrics.overall_ai_score),
        "pattern_hits": pattern_hits,
        "top_fragments": fragments,
        "humanized": humanized or [],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)
