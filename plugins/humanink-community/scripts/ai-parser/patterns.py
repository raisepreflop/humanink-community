"""
Patrones lingüísticos característicos de texto generado por IA en español literario.
Organizados por categoría para facilitar el diagnóstico específico.
"""

import re

# (patron, descripcion, peso)
AI_PATTERNS: list[tuple[str, str, float]] = [
    # --- Transiciones genéricas de ensayo ---
    (r"\ben el ámbito de\b", "transición genérica de ensayo", 1.0),
    (r"\bes fundamental destacar\b", "fórmula evaluativa", 1.0),
    (r"\bcabe mencionar que\b", "transición burocrática", 1.0),
    (r"\bcabe señalar que\b", "transición burocrática", 1.0),
    (r"\bsin lugar a dudas\b", "énfasis formulaico", 0.8),
    (r"\ben definitiva\b", "cierre formulaico", 0.6),
    (r"\bes importante destacar\b", "fórmula evaluativa", 1.0),
    (r"\bes importante mencionar\b", "fórmula evaluativa", 1.0),
    (r"\bvale la pena mencionar\b", "transición burocrática", 0.9),
    (r"\bno es casualidad que\b", "retórica formulaica", 0.8),

    # --- Conectores de ensayo sobreusados ---
    (r"\ben este sentido\b", "conector de ensayo", 0.7),
    (r"\ben este contexto\b", "conector de ensayo", 0.7),
    (r"\ben este marco\b", "conector de ensayo", 0.7),
    (r"\bde esta manera\b", "conector consecutivo genérico", 0.6),
    (r"\bde este modo\b", "conector consecutivo genérico", 0.6),
    (r"\ba su vez\b", "conector aditivo plano", 0.4),
    (r"\bpor otra parte\b", "contraste formulaico", 0.5),
    (r"\bpor otro lado\b", "contraste formulaico", 0.5),
    (r"\ben consecuencia\b", "consecutivo de ensayo", 0.6),
    (r"\ben síntesis\b", "cierre de ensayo", 0.7),

    # --- Estructuras paralelas artificiales ---
    (r"no solo.{3,80}sino también", "estructura paralela binaria", 0.9),
    (r"por un lado.{3,100}por otro lado", "contraste paralelo simétrico", 0.9),
    (r"tanto.{3,60}como.{3,60}también", "enumeración tripartita", 0.7),

    # --- Verbos comodín abstractos ---
    (r"\bevidenciar\b", "verbo abstracto comodín", 0.8),
    (r"\babarcar\b", "verbo abstracto comodín", 0.7),
    (r"\babordar\b", "verbo abstracto comodín", 0.6),
    (r"\bplasmar\b", "verbo abstracto comodín", 0.8),
    (r"\bvisibilizar\b", "verbo abstracto comodín", 0.9),
    (r"\bpotenciar\b", "verbo abstracto comodín", 0.7),
    (r"\bgenerar un impacto\b", "frase de impacto hueca", 1.0),
    (r"\bgenera un espacio\b", "frase abstracta hueca", 1.0),

    # --- Aperturas de párrafo formulaicas ---
    (r"^Así,\s", "apertura formulaica", 0.8),
    (r"^Así pues,\s", "apertura formulaica", 0.8),
    (r"^De esta manera,\s", "apertura formulaica", 0.8),
    (r"^En este sentido,\s", "apertura formulaica", 0.9),
    (r"^En definitiva,\s", "apertura formulaica de cierre", 0.9),
    (r"^Cabe destacar que\s", "apertura evaluativa", 1.0),
    (r"^Es importante señalar\s", "apertura evaluativa", 1.0),
    (r"^Sin embargo,\s", "contraste de apertura", 0.4),  # bajo: es legítimo

    # --- Hipérboles y énfasis de chatbot ---
    (r"\bfundamental\b", "adjetivo evaluativo sobreusado", 0.3),
    (r"\bcrucial\b", "adjetivo evaluativo sobreusado", 0.4),
    (r"\btrascendental\b", "adjetivo evaluativo sobreusado", 0.6),
    (r"\bprofundo impacto\b", "frase de impacto hueca", 0.8),
    (r"\bhonda reflexión\b", "cliché introspectivo", 0.7),

    # --- Cierre de párrafo de ensayo en ficción ---
    (r"\besto nos lleva a\b", "transición meta-narrativa", 0.8),
    (r"\besto nos muestra que\b", "conclusión explícita innecesaria", 0.9),
    (r"\bnos invita a reflexionar\b", "fórmula de conclusión", 1.0),
    (r"\bnos lleva a preguntarnos\b", "fórmula de conclusión", 1.0),
]


def scan_text(text: str) -> list[dict]:
    """
    Devuelve lista de coincidencias: {pattern, description, weight, match, position}.
    """
    hits = []
    for pattern, description, weight in AI_PATTERNS:
        for m in re.finditer(pattern, text, flags=re.IGNORECASE | re.MULTILINE):
            hits.append({
                "pattern": pattern,
                "description": description,
                "weight": weight,
                "match": m.group(0),
                "start": m.start(),
                "end": m.end(),
            })
    return hits
