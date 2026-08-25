"""
Humanizador: usa Claude API para reescribir fragmentos AI-like.
"""

import os
import anthropic

_DEFAULT_STYLE = """Eres un editor literario especializado en narrativa española contemporánea de alto nivel.
Tu función es reescribir fragmentos de ficción eliminando marcas de texto generado por IA,
preservando el sentido y la voz narrativa original.

Principios estéticos de referencia (estilo DUOC): Auster/Krasznahorkai.
- Frases largas con sintaxis compleja pero fluida, nunca enumerativa
- Vocabulario preciso, evitar comodines abstractos
- Eliminar transiciones de ensayo y conectores formulaicos
- El narrador observa, no comenta ni evalúa explícitamente
- Preferir lo concreto y sensorial sobre lo abstracto y conceptual
- No hay conclusiones explícitas: el lector infiere"""

_CLIENT = None  # anthropic.Anthropic | None


def _client() -> anthropic.Anthropic:
    global _CLIENT
    if _CLIENT is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY no está configurada.\n"
                "Ejecútalo con: ANTHROPIC_API_KEY=sk-... python parser.py archivo.docx --humanize"
            )
        _CLIENT = anthropic.Anthropic(api_key=api_key)
    return _CLIENT


def humanize_fragment(
    fragment: str,
    reasons: list[str],
    style_instructions=None,  # str | None
    model: str = "claude-sonnet-4-6",
) -> str:
    """
    Reescribe un fragmento eliminando marcas AI específicas.
    Devuelve el texto humanizado.
    """
    system = style_instructions or _DEFAULT_STYLE
    reasons_text = ", ".join(reasons) if reasons else "marcas genéricas de IA"

    prompt = (
        f"Reescribe el siguiente fragmento de ficción eliminando estas marcas de IA detectadas: {reasons_text}.\n\n"
        "Instrucciones:\n"
        "- Mantén exactamente la misma información narrativa y el mismo tono\n"
        "- No añadas personajes, acciones ni información nueva\n"
        "- Devuelve SOLO el fragmento reescrito, sin explicaciones ni comentarios\n"
        "- Si el fragmento ya es aceptable, devuélvelo sin cambios\n\n"
        f"---\n{fragment}"
    )

    response = _client().messages.create(
        model=model,
        max_tokens=2000,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text.strip()


def humanize_top_fragments(
    fragments: list[dict],
    top_n: int = 5,
    style_instructions=None,  # str | None
    model: str = "claude-sonnet-4-6",
) -> list[dict]:
    """
    Recibe lista de fragmentos con score AI, humaniza los top_n más altos.
    Cada fragmento: {text, score, paragraph_index, reasons, ...}
    Devuelve lista con campo 'humanized' añadido.
    """
    sorted_frags = sorted(fragments, key=lambda f: f.get("score", 0), reverse=True)
    to_process = sorted_frags[:top_n]

    results = []
    for frag in to_process:
        reasons = frag.get("reasons", [])
        humanized = humanize_fragment(
            frag["text"],
            reasons=reasons,
            style_instructions=style_instructions,
            model=model,
        )
        results.append({**frag, "humanized": humanized})

    return results
