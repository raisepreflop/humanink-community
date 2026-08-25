"""
Métricas estadístico-semánticas para detectar texto generado por IA.
Todas son locales (sin LLM ni GPU).
"""

import re
import math
from collections import Counter
from typing import NamedTuple

import textstat


class TextMetrics(NamedTuple):
    word_count: int
    sentence_count: int
    paragraph_count: int
    lexical_density: float       # tokens léxicos / total tokens
    ttr: float                   # type-token ratio
    sentence_length_mean: float
    sentence_length_std: float
    burstiness: float            # (std - mean) / (std + mean)
    paragraph_similarity: float  # similitud estructural entre párrafos [0,1]
    approx_perplexity: float     # perplexidad aproximada por n-gramas
    ai_pattern_score: float      # suma ponderada de patrones AI / 100 palabras
    flesch_ease: float           # legibilidad Flesch (adaptado ES)
    overall_ai_score: float      # score compuesto [0–100], mayor = más AI


# Palabras funcionales en español (excluidas del lexical density)
_FUNCTION_WORDS = {
    "de", "la", "el", "en", "y", "a", "los", "del", "se", "las", "por",
    "un", "para", "con", "una", "su", "al", "lo", "como", "más", "pero",
    "sus", "le", "ya", "o", "este", "sí", "porque", "esta", "entre",
    "cuando", "muy", "sin", "sobre", "también", "me", "hasta", "hay",
    "donde", "quien", "desde", "todo", "nos", "durante", "todos", "uno",
    "les", "ni", "contra", "otros", "ese", "eso", "ante", "ellos", "e",
    "esto", "mí", "antes", "algunos", "qué", "unos", "yo", "otro", "otras",
    "otra", "él", "tanto", "esa", "estos", "mucho", "quienes", "nada",
    "muchos", "cual", "sea", "poco", "ella", "estar", "estas", "alguno",
    "alguna", "que", "es", "fue", "son", "ha", "era", "no", "te", "tu",
    "mi", "si", "he", "han", "had", "ser", "tiene", "había", "tenía",
    "están", "está", "fueron", "ser", "haber",
}


def _tokenize_words(text: str) -> list[str]:
    return re.findall(r"\b[a-záéíóúüñA-ZÁÉÍÓÚÜÑ]{2,}\b", text)


def _split_sentences(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?…])\s+", text.strip())
    return [s for s in sentences if len(s.split()) >= 2]


def _split_paragraphs(text: str) -> list[str]:
    paras = re.split(r"\n\s*\n", text.strip())
    return [p.strip() for p in paras if len(p.strip()) > 20]


def lexical_density(words: list[str]) -> float:
    if not words:
        return 0.0
    content = [w for w in words if w.lower() not in _FUNCTION_WORDS]
    return len(content) / len(words)


def type_token_ratio(words: list[str]) -> float:
    if not words:
        return 0.0
    return len(set(w.lower() for w in words)) / len(words)


def sentence_stats(sentences: list[str]) -> tuple[float, float]:
    lengths = [len(s.split()) for s in sentences]
    if not lengths:
        return 0.0, 0.0
    mean = sum(lengths) / len(lengths)
    variance = sum((l - mean) ** 2 for l in lengths) / len(lengths)
    return mean, math.sqrt(variance)


def burstiness(mean: float, std: float) -> float:
    """Índice de burstiness de Cox-Lewis. Humano > 0, IA ~0 o negativo."""
    denom = std + mean
    if denom == 0:
        return 0.0
    return (std - mean) / denom


def paragraph_similarity(paragraphs: list[str]) -> float:
    """
    Similitud estructural media entre párrafos consecutivos.
    Usa Jaccard sobre bigramas de función de palabras.
    Un valor alto indica que la IA repite las mismas estructuras.
    """
    if len(paragraphs) < 2:
        return 0.0

    def bigrams(text: str) -> set[tuple[str, str]]:
        words = re.findall(r"\b\w+\b", text.lower())
        return set(zip(words, words[1:]))

    scores = []
    for a, b in zip(paragraphs, paragraphs[1:]):
        bg_a = bigrams(a)
        bg_b = bigrams(b)
        union = bg_a | bg_b
        if not union:
            continue
        scores.append(len(bg_a & bg_b) / len(union))

    return sum(scores) / len(scores) if scores else 0.0


def approx_perplexity(words: list[str]) -> float:
    """
    Perplexidad aproximada por modelo de bigramas con suavizado Laplace.
    Mayor perplexidad = texto más impredecible = potencialmente más humano.
    Esta función usa sólo el texto analizado como corpus (no requiere modelo externo).
    """
    if len(words) < 4:
        return 0.0

    lower = [w.lower() for w in words]
    unigrams = Counter(lower)
    bigrams_c = Counter(zip(lower, lower[1:]))
    vocab_size = len(unigrams)

    log_prob = 0.0
    count = 0
    for (w1, w2), freq in bigrams_c.items():
        p = (freq + 1) / (unigrams[w1] + vocab_size)  # Laplace smoothing
        log_prob += -math.log2(p) * freq
        count += freq

    if count == 0:
        return 0.0
    return 2 ** (log_prob / count)


def compute_ai_pattern_score(pattern_hits: list[dict], word_count: int) -> float:
    """Score ponderado de patrones AI normalizado por cada 100 palabras."""
    if word_count == 0:
        return 0.0
    raw = sum(h["weight"] for h in pattern_hits)
    return (raw / word_count) * 100


def overall_ai_score(
    ld: float,
    ttr: float,
    burst: float,
    para_sim: float,
    pattern_score: float,
    perplexity: float,
) -> float:
    """
    Score compuesto [0–100]. Mayor valor = más AI-like.

    Heurística calibrada empíricamente para español literario:
    - TTR bajo → repetición de vocabulario
    - Burstiness bajo → ritmo monótono
    - Para_sim alto → repetición de estructura
    - Pattern_score alto → clichés AI
    - Perplexidad baja → texto predecible
    """
    # Normalizar cada métrica a un sub-score [0–1] donde 1 = máximo AI
    ttr_score = max(0.0, 1.0 - (ttr / 0.6))              # TTR ideal humano ~0.6+
    burst_score = max(0.0, 1.0 - ((burst + 1) / 2))       # burstiness [-1,1] → invertir
    para_score = min(1.0, para_sim * 3)                    # sim >0.33 ya es sospechoso
    pattern_s = min(1.0, pattern_score / 5.0)              # 5 patrones/100w = max
    perp_score = max(0.0, 1.0 - (perplexity / 12.0))      # perp >12 = impredecible

    weights = {
        "ttr": 0.20,
        "burst": 0.15,
        "para": 0.20,
        "pattern": 0.35,
        "perp": 0.10,
    }

    score = (
        weights["ttr"] * ttr_score
        + weights["burst"] * burst_score
        + weights["para"] * para_score
        + weights["pattern"] * pattern_s
        + weights["perp"] * perp_score
    )

    return round(score * 100, 1)


def analyze(text: str, pattern_hits: list[dict]) -> TextMetrics:
    words = _tokenize_words(text)
    sentences = _split_sentences(text)
    paragraphs = _split_paragraphs(text)

    ld = lexical_density(words)
    ttr = type_token_ratio(words)
    mean, std = sentence_stats(sentences)
    burst = burstiness(mean, std)
    para_sim = paragraph_similarity(paragraphs)
    perp = approx_perplexity(words)
    pattern_s = compute_ai_pattern_score(pattern_hits, len(words))

    flesch = textstat.flesch_reading_ease(text)

    ai_score = overall_ai_score(ld, ttr, burst, para_sim, pattern_s, perp)

    return TextMetrics(
        word_count=len(words),
        sentence_count=len(sentences),
        paragraph_count=len(paragraphs),
        lexical_density=round(ld, 3),
        ttr=round(ttr, 3),
        sentence_length_mean=round(mean, 1),
        sentence_length_std=round(std, 1),
        burstiness=round(burst, 3),
        paragraph_similarity=round(para_sim, 3),
        approx_perplexity=round(perp, 2),
        ai_pattern_score=round(pattern_s, 2),
        flesch_ease=round(flesch, 1),
        overall_ai_score=ai_score,
    )
