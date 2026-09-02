"""
Deterministic evaluation metrics for Goal 9.
No I/O, no LLM calls — all functions are pure.
"""
from __future__ import annotations

import re
import statistics
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Retrieval Metrics
# ─────────────────────────────────────────────────────────────────────────────

def recall_at_k(
    retrieved_ids: list[str],
    relevant_ids: set[str],
    k: Optional[int] = None,
) -> float:
    """
    Recall@K = |relevant ∩ retrieved[:K]| / |relevant|

    Returns 0.0 when relevant_ids is empty (undefined by convention).
    """
    if not relevant_ids:
        return 0.0
    top = retrieved_ids[:k] if k is not None else retrieved_ids
    hit_count = sum(1 for rid in top if rid in relevant_ids)
    return hit_count / len(relevant_ids)


def precision_at_k(
    retrieved_ids: list[str],
    relevant_ids: set[str],
    k: Optional[int] = None,
) -> float:
    """
    Precision@K = |relevant ∩ retrieved[:K]| / |retrieved[:K]|

    Returns 0.0 when retrieved list is empty.
    """
    top = retrieved_ids[:k] if k is not None else retrieved_ids
    if not top:
        return 0.0
    hit_count = sum(1 for rid in top if rid in relevant_ids)
    return hit_count / len(top)


def hit_rate_at_k(
    retrieved_ids: list[str],
    relevant_ids: set[str],
    k: Optional[int] = None,
) -> float:
    """
    Hit Rate@K = 1.0 if at least one relevant chunk appears in retrieved[:K], else 0.0

    Returns 0.0 when relevant_ids is empty.
    """
    if not relevant_ids:
        return 0.0
    top = retrieved_ids[:k] if k is not None else retrieved_ids
    return 1.0 if any(rid in relevant_ids for rid in top) else 0.0


def mrr(
    retrieved_ids: list[str],
    relevant_ids: set[str],
) -> float:
    """
    Mean Reciprocal Rank — reciprocal of the rank of the first relevant result.

    MRR = 1/rank_of_first_relevant, or 0.0 if none found.
    """
    for i, rid in enumerate(retrieved_ids, start=1):
        if rid in relevant_ids:
            return 1.0 / i
    return 0.0


def avg_similarity_score(scores: list[float]) -> float:
    """Average similarity score across retrieved results. Returns 0.0 for empty list."""
    return statistics.mean(scores) if scores else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Answer Quality Metrics
# ─────────────────────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Lowercase + collapse whitespace/punctuation for fuzzy matching."""
    return re.sub(r"[\s\W]+", " ", text.lower()).strip()


def _fact_found_in_text(fact: str, text: str) -> bool:
    """
    Lexical fact-coverage check.

    Returns True when the normalized fact appears as a whole token sequence
    in the normalized answer text.

    Limitation: This is a lexical heuristic, NOT semantic truth verification.
    Short facts like "1.3" may match unrelated numbers. All matches should be
    manually inspected for edge cases.
    """
    norm_fact = _normalize(fact)
    norm_text = _normalize(text)
    # Require the fact to appear as a token-bounded substring
    # Use word-boundary-ish check: fact surrounded by non-alnum or at edges
    pattern = r"(?<![a-z0-9])" + re.escape(norm_fact) + r"(?![a-z0-9])"
    return bool(re.search(pattern, norm_text))


def fact_coverage(
    expected_facts: list[str],
    answer: str,
) -> float:
    """
    Lexical fact-coverage heuristic.

    Returns the fraction of expected_facts found in the answer text.

    NOTE: This is a lexical heuristic, not a semantic truth verifier.
    """
    if not expected_facts:
        return 0.0
    matched = sum(1 for f in expected_facts if _fact_found_in_text(f, answer))
    return matched / len(expected_facts)


def groundedness(
    expected_facts: list[str],
    context: str,
) -> float:
    """
    Groundedness = fraction of expected_facts that can be found in the retrieved context.

    A fact is 'grounded' when the expected fact appears lexically in the RAG context
    passed to the model. This measures whether the retrieval pipeline surfaced the
    required information, NOT whether the model used it correctly.
    """
    if not expected_facts or not context:
        return 0.0
    grounded_count = sum(1 for f in expected_facts if _fact_found_in_text(f, context))
    return grounded_count / len(expected_facts)


def unsupported_claim_rate(
    absent_facts: list[str],
    answer: str,
) -> float:
    """
    Conservative unsupported-claim heuristic for absent/injection cases.

    Returns the fraction of `absent_facts` that appear in the answer.
    A higher rate indicates the model fabricated corpus-specific claims.

    IMPORTANT LIMITATION: This is a narrow keyword-match heuristic.
    It can only detect claims we anticipated in advance (listed as absent_facts).
    It is NOT a complete hallucination detector — do not treat it as one.
    Scores should be interpreted as a lower-bound estimate of unsupported claims.
    """
    if not absent_facts:
        return 0.0
    fabricated = sum(1 for f in absent_facts if _fact_found_in_text(f, answer))
    return fabricated / len(absent_facts)


# ─────────────────────────────────────────────────────────────────────────────
# Latency Metrics
# ─────────────────────────────────────────────────────────────────────────────

def latency_stats(values: list[float]) -> dict[str, float]:
    """
    Compute summary latency statistics from a list of measurements (seconds or ms).

    Returns: mean, median, p95, p99, min, max.
    """
    if not values:
        return {
            "mean": 0.0,
            "median": 0.0,
            "p95": 0.0,
            "p99": 0.0,
            "min": 0.0,
            "max": 0.0,
            "count": 0,
        }
    sorted_vals = sorted(values)
    n = len(sorted_vals)

    def percentile(p: float) -> float:
        idx = (p / 100) * (n - 1)
        lo = int(idx)
        hi = min(lo + 1, n - 1)
        frac = idx - lo
        return sorted_vals[lo] + frac * (sorted_vals[hi] - sorted_vals[lo])

    return {
        "mean": statistics.mean(values),
        "median": statistics.median(sorted_vals),
        "p95": percentile(95),
        "p99": percentile(99),
        "min": sorted_vals[0],
        "max": sorted_vals[-1],
        "count": n,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Aggregate helpers
# ─────────────────────────────────────────────────────────────────────────────

def aggregate_metric(values: list[float]) -> dict[str, float]:
    """Simple mean/min/max aggregate for a list of metric values."""
    if not values:
        return {"mean": 0.0, "min": 0.0, "max": 0.0, "count": 0}
    return {
        "mean": statistics.mean(values),
        "min": min(values),
        "max": max(values),
        "count": len(values),
    }
