"""
Case evaluator: scores a single BenchmarkCase given retrieval and generation outputs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.evaluation.dataset import BenchmarkCase
from app.evaluation import metrics as m


@dataclass
class CaseLatenices:
    """Individual timing breakdowns in seconds."""
    embedding_s: float = 0.0
    retrieval_s: float = 0.0
    context_build_s: float = 0.0
    generation_s: float = 0.0
    total_s: float = 0.0


@dataclass
class CaseResult:
    """Complete evaluation result for a single benchmark case."""
    case_id: str
    category: str
    question: str

    # --- Inputs ---
    expected_facts: list[str]
    absent_facts: list[str]
    relevant_chunk_ids: set[str]  # ground-truth chunk IDs resolved at setup
    ground_truth_markers: list[str]

    # --- Retrieval ---
    retrieved_chunk_ids: list[str]
    similarity_scores: list[float]
    rag_context: str  # the actual context block passed to the model

    # --- Generated answer ---
    answer: str

    # --- Retrieval metrics ---
    recall_at_5: float = 0.0
    precision_at_5: float = 0.0
    hit_rate_at_5: float = 0.0
    mrr_score: float = 0.0
    avg_sim_score: float = 0.0

    # --- Answer quality metrics ---
    fact_coverage_score: float = 0.0
    groundedness_score: float = 0.0
    unsupported_claim_score: float = 0.0

    # --- Latency ---
    latencies: CaseLatenices = field(default_factory=CaseLatenices)

    # --- Flags ---
    retrieval_applicable: bool = True
    """
    False for absent/irrelevant cases where no ground-truth chunks exist.
    Retrieval metrics are skipped for these.
    """
    notes: str = ""


class CaseEvaluator:
    """Evaluates a single BenchmarkCase deterministically."""

    def evaluate(
        self,
        case: BenchmarkCase,
        relevant_chunk_ids: set[str],
        retrieved_chunk_ids: list[str],
        similarity_scores: list[float],
        rag_context: str,
        answer: str,
        latencies: CaseLatenices,
    ) -> CaseResult:
        """
        Score a benchmark case.

        Parameters
        ----------
        case:
            The benchmark case being evaluated.
        relevant_chunk_ids:
            Ground-truth chunk IDs resolved from case.ground_truth_markers.
        retrieved_chunk_ids:
            Chunk IDs actually returned by retrieval (ordered by rank).
        similarity_scores:
            Similarity scores corresponding to retrieved_chunk_ids.
        rag_context:
            The full RAG context string passed to the model.
        answer:
            The model's generated answer.
        latencies:
            Timing breakdown.
        """
        retrieval_applicable = bool(relevant_chunk_ids)
        k = 5

        # Retrieval metrics (skip when ground truth is empty)
        if retrieval_applicable:
            r5 = m.recall_at_k(retrieved_chunk_ids, relevant_chunk_ids, k)
            p5 = m.precision_at_k(retrieved_chunk_ids, relevant_chunk_ids, k)
            h5 = m.hit_rate_at_k(retrieved_chunk_ids, relevant_chunk_ids, k)
            mrr_val = m.mrr(retrieved_chunk_ids, relevant_chunk_ids)
        else:
            r5 = p5 = h5 = mrr_val = 0.0

        avg_sim = m.avg_similarity_score(similarity_scores)
        fc = m.fact_coverage(case.expected_facts, answer)
        gs = m.groundedness(case.expected_facts, rag_context)
        ucr = m.unsupported_claim_rate(case.absent_facts, answer)

        return CaseResult(
            case_id=case.id,
            category=case.category,
            question=case.question,
            expected_facts=case.expected_facts,
            absent_facts=case.absent_facts,
            relevant_chunk_ids=relevant_chunk_ids,
            ground_truth_markers=case.ground_truth_markers,
            retrieved_chunk_ids=retrieved_chunk_ids,
            similarity_scores=similarity_scores,
            rag_context=rag_context,
            answer=answer,
            recall_at_5=r5,
            precision_at_5=p5,
            hit_rate_at_5=h5,
            mrr_score=mrr_val,
            avg_sim_score=avg_sim,
            fact_coverage_score=fc,
            groundedness_score=gs,
            unsupported_claim_score=ucr,
            latencies=latencies,
            retrieval_applicable=retrieval_applicable,
            notes=case.notes,
        )
