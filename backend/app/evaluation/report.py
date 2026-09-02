"""
Report generator: serializes evaluation results to JSON and prints a human-readable summary.
"""
from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.evaluation.evaluator import CaseResult
from app.evaluation import metrics as m


def _safe_mean(vals: list[float]) -> float:
    return statistics.mean(vals) if vals else 0.0


class ReportGenerator:
    """Serializes a list of CaseResults into a structured JSON baseline report."""

    def save(self, output_path: Path, results: list[CaseResult]) -> dict[str, Any]:
        """
        Build the report dict, write it to output_path as JSON, and return it.
        """
        settings = get_settings()
        report = self._build_report(results, settings)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, default=str)
        return report

    def _build_report(self, results: list[CaseResult], settings: Any) -> dict[str, Any]:
        # ── Aggregate metrics ─────────────────────────────────────────────────
        retrieval_cases = [r for r in results if r.retrieval_applicable]
        all_cases = results

        agg_retrieval = {
            "recall_at_5": _safe_mean([r.recall_at_5 for r in retrieval_cases]),
            "precision_at_5": _safe_mean([r.precision_at_5 for r in retrieval_cases]),
            "hit_rate_at_5": _safe_mean([r.hit_rate_at_5 for r in retrieval_cases]),
            "mrr": _safe_mean([r.mrr_score for r in retrieval_cases]),
            "avg_similarity": _safe_mean(
                [r.avg_sim_score for r in all_cases if r.similarity_scores]
            ),
        }
        agg_answer = {
            "fact_coverage": _safe_mean([r.fact_coverage_score for r in all_cases]),
            "groundedness": _safe_mean(
                [r.groundedness_score for r in all_cases if r.retrieval_applicable]
            ),
            "unsupported_claim_rate": _safe_mean(
                [r.unsupported_claim_score for r in all_cases if r.absent_facts]
            ),
        }
        agg_latency = {
            "embedding_s": m.latency_stats([r.latencies.embedding_s for r in all_cases]),
            "retrieval_s": m.latency_stats([r.latencies.retrieval_s for r in all_cases]),
            "context_build_s": m.latency_stats([r.latencies.context_build_s for r in all_cases]),
            "generation_s": m.latency_stats([r.latencies.generation_s for r in all_cases]),
            "total_s": m.latency_stats([r.latencies.total_s for r in all_cases]),
        }

        # ── Per-category metrics ──────────────────────────────────────────────
        by_cat: dict[str, list[CaseResult]] = {}
        for r in results:
            by_cat.setdefault(r.category, []).append(r)

        per_category: dict[str, Any] = {}
        for cat, cat_results in by_cat.items():
            cat_retrieval = [r for r in cat_results if r.retrieval_applicable]
            per_category[cat] = {
                "case_count": len(cat_results),
                "retrieval": {
                    "recall_at_5": _safe_mean([r.recall_at_5 for r in cat_retrieval]),
                    "precision_at_5": _safe_mean([r.precision_at_5 for r in cat_retrieval]),
                    "hit_rate_at_5": _safe_mean([r.hit_rate_at_5 for r in cat_retrieval]),
                    "mrr": _safe_mean([r.mrr_score for r in cat_retrieval]),
                },
                "answer": {
                    "fact_coverage": _safe_mean([r.fact_coverage_score for r in cat_results]),
                    "groundedness": _safe_mean(
                        [r.groundedness_score for r in cat_results if r.retrieval_applicable]
                    ),
                },
            }

        # ── Per-case results ──────────────────────────────────────────────────
        per_case = []
        for r in results:
            per_case.append(
                {
                    "id": r.case_id,
                    "category": r.category,
                    "question": r.question,
                    "retrieval_applicable": r.retrieval_applicable,
                    "expected_facts": r.expected_facts,
                    "retrieved_chunk_ids": r.retrieved_chunk_ids,
                    "relevant_chunk_ids": sorted(r.relevant_chunk_ids),
                    "retrieval_metrics": {
                        "recall_at_5": r.recall_at_5,
                        "precision_at_5": r.precision_at_5,
                        "hit_rate_at_5": r.hit_rate_at_5,
                        "mrr": r.mrr_score,
                        "avg_similarity": r.avg_sim_score,
                    },
                    "answer_metrics": {
                        "fact_coverage": r.fact_coverage_score,
                        "groundedness": r.groundedness_score,
                        "unsupported_claim_rate": r.unsupported_claim_score,
                    },
                    "latencies_s": {
                        "embedding": r.latencies.embedding_s,
                        "retrieval": r.latencies.retrieval_s,
                        "context_build": r.latencies.context_build_s,
                        "generation": r.latencies.generation_s,
                        "total": r.latencies.total_s,
                    },
                    "answer_preview": r.answer[:300] + ("..." if len(r.answer) > 300 else ""),
                    "notes": r.notes,
                }
            )

        return {
            "evaluation_timestamp": datetime.now(timezone.utc).isoformat(),
            "configuration": {
                "chat_model": settings.model_name,
                "embedding_model": settings.embedding_model,
                "embedding_dimensions": settings.embedding_dimensions,
                "chunk_size": settings.default_chunk_size,
                "chunk_overlap": settings.default_chunk_overlap,
                "rag_enabled": settings.rag_enabled,
                "rag_top_k": settings.rag_top_k,
                "rag_min_score": settings.rag_min_score,
                "rag_max_context_characters": settings.rag_max_context_characters,
                "similarity_top_k": settings.similarity_top_k,
                "similarity_min_score": settings.similarity_min_score,
            },
            "dataset_version": results[0].notes if False else None,  # filled below
            "total_cases": len(results),
            "aggregate_metrics": {
                "retrieval": agg_retrieval,
                "answer_quality": agg_answer,
                "latency": agg_latency,
            },
            "per_category_metrics": per_category,
            "per_case_results": per_case,
        }

    def print_summary(self, report: dict[str, Any], dataset_version: str) -> None:
        """Print a concise human-readable evaluation summary."""
        cfg = report["configuration"]
        agg = report["aggregate_metrics"]
        ret = agg["retrieval"]
        ans = agg["answer_quality"]
        lat = agg["latency"]

        print()
        print("=" * 62)
        print(f"  Evaluation: Goal 9 Baseline  |  Dataset: {dataset_version}")
        print("=" * 62)
        print(f"  Cases: {report['total_cases']}")
        print(f"  Model: {cfg['chat_model']}  |  Embeddings: {cfg['embedding_model']}")
        print()
        print("  Retrieval (cases with ground-truth chunks)")
        print(f"    Hit Rate@5:     {ret['hit_rate_at_5'] * 100:.1f}%")
        print(f"    Recall@5:       {ret['recall_at_5'] * 100:.1f}%")
        print(f"    Precision@5:    {ret['precision_at_5'] * 100:.1f}%")
        print(f"    MRR:            {ret['mrr']:.3f}")
        print(f"    Avg Similarity: {ret['avg_similarity']:.3f}")
        print()
        print("  Answer Quality")
        print(f"    Fact Coverage:      {ans['fact_coverage'] * 100:.1f}%")
        print(f"    Groundedness:       {ans['groundedness'] * 100:.1f}%")
        print(f"    Unsupported Claims: {ans['unsupported_claim_rate'] * 100:.1f}%")
        print()
        print("  Latency (mean across all cases)")
        print(f"    Embedding:    {lat['embedding_s']['mean'] * 1000:.0f} ms")
        print(f"    Retrieval:    {lat['retrieval_s']['mean'] * 1000:.0f} ms")
        print(f"    RAG Build:    {lat['context_build_s']['mean'] * 1000:.0f} ms")
        print(f"    Generation:   {lat['generation_s']['mean']:.2f} s")
        print(f"    Total E2E:    {lat['total_s']['mean']:.2f} s")
        print("=" * 62)
        print()

        by_cat = report.get("per_category_metrics", {})
        if by_cat:
            print("  Per-Category Summary")
            print(f"  {'Category':<16} {'Cases':>5} {'Hit@5':>7} {'FC':>6} {'Ground':>7}")
            print("  " + "-" * 47)
            for cat, cat_data in sorted(by_cat.items()):
                hit = cat_data["retrieval"]["hit_rate_at_5"] * 100
                fc = cat_data["answer"]["fact_coverage"] * 100
                gs = cat_data["answer"]["groundedness"] * 100
                print(
                    f"  {cat:<16} {cat_data['case_count']:>5} "
                    f"{hit:>6.1f}% {fc:>5.1f}% {gs:>6.1f}%"
                )
            print()

    def print_comparison(self, baseline: dict[str, Any], optimized: dict[str, Any]) -> None:
        """Print a structured comparison table between baseline and optimized evaluation runs."""
        b_agg = baseline["aggregate_metrics"]
        o_agg = optimized["aggregate_metrics"]

        b_ret, o_ret = b_agg["retrieval"], o_agg["retrieval"]
        b_ans, o_ans = b_agg["answer_quality"], o_agg["answer_quality"]
        b_lat, o_lat = b_agg["latency"], o_agg["latency"]

        def diff_pct(o_val: float, b_val: float) -> str:
            d = (o_val - b_val) * 100
            sign = "+" if d > 0 else ""
            return f"{sign}{d:.1f}%"

        def diff_num(o_val: float, b_val: float, precision: int = 3) -> str:
            d = o_val - b_val
            sign = "+" if d > 0 else ""
            return f"{sign}{d:.{precision}f}"

        def diff_time(o_val: float, b_val: float) -> str:
            d = o_val - b_val
            sign = "+" if d > 0 else ""
            return f"{sign}{d:.2f} s"

        print()
        print("=" * 66)
        print("  Goal 9 Task 2 — Baseline vs Optimized Comparison Report")
        print("=" * 66)
        print(f"  {'Metric':<22} | {'Baseline':>10} | {'Optimized':>10} | {'Change':>10}")
        print("  " + "-" * 62)
        print(
            f"  {'Hit Rate@5':<22} | {b_ret['hit_rate_at_5']*100:>9.1f}% | {o_ret['hit_rate_at_5']*100:>9.1f}% | {diff_pct(o_ret['hit_rate_at_5'], b_ret['hit_rate_at_5']):>10}"
        )
        print(
            f"  {'Recall@5':<22} | {b_ret['recall_at_5']*100:>9.1f}% | {o_ret['recall_at_5']*100:>9.1f}% | {diff_pct(o_ret['recall_at_5'], b_ret['recall_at_5']):>10}"
        )
        print(
            f"  {'Precision@5':<22} | {b_ret['precision_at_5']*100:>9.1f}% | {o_ret['precision_at_5']*100:>9.1f}% | {diff_pct(o_ret['precision_at_5'], b_ret['precision_at_5']):>10}"
        )
        print(
            f"  {'MRR':<22} | {b_ret['mrr']:>10.3f} | {o_ret['mrr']:>10.3f} | {diff_num(o_ret['mrr'], b_ret['mrr']):>10}"
        )
        print(
            f"  {'Avg Similarity':<22} | {b_ret['avg_similarity']:>10.3f} | {o_ret['avg_similarity']:>10.3f} | {diff_num(o_ret['avg_similarity'], b_ret['avg_similarity']):>10}"
        )
        print("  " + "-" * 62)
        print(
            f"  {'Fact Coverage':<22} | {b_ans['fact_coverage']*100:>9.1f}% | {o_ans['fact_coverage']*100:>9.1f}% | {diff_pct(o_ans['fact_coverage'], b_ans['fact_coverage']):>10}"
        )
        print(
            f"  {'Groundedness':<22} | {b_ans['groundedness']*100:>9.1f}% | {o_ans['groundedness']*100:>9.1f}% | {diff_pct(o_ans['groundedness'], b_ans['groundedness']):>10}"
        )
        print(
            f"  {'Unsupported Claims':<22} | {b_ans['unsupported_claim_rate']*100:>9.1f}% | {o_ans['unsupported_claim_rate']*100:>9.1f}% | {diff_pct(o_ans['unsupported_claim_rate'], b_ans['unsupported_claim_rate']):>10}"
        )
        print("  " + "-" * 62)
        print(
            f"  {'Embedding Latency':<22} | {b_lat['embedding_s']['mean']*1000:>8.0f} ms | {o_lat['embedding_s']['mean']*1000:>8.0f} ms | {diff_num((o_lat['embedding_s']['mean'] - b_lat['embedding_s']['mean'])*1000, 0, 0):>7} ms"
        )
        print(
            f"  {'Retrieval Latency':<22} | {b_lat['retrieval_s']['mean']*1000:>8.0f} ms | {o_lat['retrieval_s']['mean']*1000:>8.0f} ms | {diff_num((o_lat['retrieval_s']['mean'] - b_lat['retrieval_s']['mean'])*1000, 0, 0):>7} ms"
        )
        print(
            f"  {'RAG Build Latency':<22} | {b_lat['context_build_s']['mean']*1000:>8.0f} ms | {o_lat['context_build_s']['mean']*1000:>8.0f} ms | {diff_num((o_lat['context_build_s']['mean'] - b_lat['context_build_s']['mean'])*1000, 0, 0):>7} ms"
        )
        print(
            f"  {'Generation Latency':<22} | {b_lat['generation_s']['mean']:>8.2f} s | {o_lat['generation_s']['mean']:>8.2f} s | {diff_time(o_lat['generation_s']['mean'], b_lat['generation_s']['mean']):>10}"
        )
        print(
            f"  {'Total E2E Latency':<22} | {b_lat['total_s']['mean']:>8.2f} s | {o_lat['total_s']['mean']:>8.2f} s | {diff_time(o_lat['total_s']['mean'], b_lat['total_s']['mean']):>10}"
        )
        print("=" * 66)
        print()

    def print_three_way_comparison(
        self,
        baseline: dict[str, Any],
        optimized: dict[str, Any],
        grounded: dict[str, Any],
    ) -> None:
        """Print a structured 3-way comparison table: Baseline vs Optimized vs Grounded."""
        b_agg = baseline["aggregate_metrics"]
        o_agg = optimized["aggregate_metrics"]
        g_agg = grounded["aggregate_metrics"]

        b_ret, o_ret, g_ret = b_agg["retrieval"], o_agg["retrieval"], g_agg["retrieval"]
        b_ans, o_ans, g_ans = b_agg["answer_quality"], o_agg["answer_quality"], g_agg["answer_quality"]
        b_lat, o_lat, g_lat = b_agg["latency"], o_agg["latency"], g_agg["latency"]

        def diff_pct(g_val: float, b_val: float) -> str:
            d = (g_val - b_val) * 100
            sign = "+" if d > 0 else ""
            return f"{sign}{d:.1f}%"

        def diff_num(g_val: float, b_val: float, precision: int = 3) -> str:
            d = g_val - b_val
            sign = "+" if d > 0 else ""
            return f"{sign}{d:.{precision}f}"

        print()
        print("=" * 78)
        print("  Goal 9 — Three-Way Evaluation Progress (Baseline -> Optimized -> Grounded)")
        print("=" * 78)
        print(f"  {'Metric':<22} | {'Baseline':>10} | {'Optimized':>10} | {'Grounded':>10} | {'Total Gain':>10}")
        print("  " + "-" * 74)
        print(
            f"  {'Hit Rate@5':<22} | {b_ret['hit_rate_at_5']*100:>9.1f}% | {o_ret['hit_rate_at_5']*100:>9.1f}% | {g_ret['hit_rate_at_5']*100:>9.1f}% | {diff_pct(g_ret['hit_rate_at_5'], b_ret['hit_rate_at_5']):>10}"
        )
        print(
            f"  {'Recall@5':<22} | {b_ret['recall_at_5']*100:>9.1f}% | {o_ret['recall_at_5']*100:>9.1f}% | {g_ret['recall_at_5']*100:>9.1f}% | {diff_pct(g_ret['recall_at_5'], b_ret['recall_at_5']):>10}"
        )
        print(
            f"  {'Precision@5':<22} | {b_ret['precision_at_5']*100:>9.1f}% | {o_ret['precision_at_5']*100:>9.1f}% | {g_ret['precision_at_5']*100:>9.1f}% | {diff_pct(g_ret['precision_at_5'], b_ret['precision_at_5']):>10}"
        )
        print(
            f"  {'MRR':<22} | {b_ret['mrr']:>10.3f} | {o_ret['mrr']:>10.3f} | {g_ret['mrr']:>10.3f} | {diff_num(g_ret['mrr'], b_ret['mrr']):>10}"
        )
        print(
            f"  {'Avg Similarity':<22} | {b_ret['avg_similarity']:>10.3f} | {o_ret['avg_similarity']:>10.3f} | {g_ret['avg_similarity']:>10.3f} | {diff_num(g_ret['avg_similarity'], b_ret['avg_similarity']):>10}"
        )
        print("  " + "-" * 74)
        print(
            f"  {'Fact Coverage':<22} | {b_ans['fact_coverage']*100:>9.1f}% | {o_ans['fact_coverage']*100:>9.1f}% | {g_ans['fact_coverage']*100:>9.1f}% | {diff_pct(g_ans['fact_coverage'], b_ans['fact_coverage']):>10}"
        )
        print(
            f"  {'Groundedness':<22} | {b_ans['groundedness']*100:>9.1f}% | {o_ans['groundedness']*100:>9.1f}% | {g_ans['groundedness']*100:>9.1f}% | {diff_pct(g_ans['groundedness'], b_ans['groundedness']):>10}"
        )
        print(
            f"  {'Unsupported Claims':<22} | {b_ans['unsupported_claim_rate']*100:>9.1f}% | {o_ans['unsupported_claim_rate']*100:>9.1f}% | {g_ans['unsupported_claim_rate']*100:>9.1f}% | {diff_pct(g_ans['unsupported_claim_rate'], b_ans['unsupported_claim_rate']):>10}"
        )
        print("  " + "-" * 74)
        print(
            f"  {'Embedding Latency':<22} | {b_lat['embedding_s']['mean']*1000:>8.0f} ms | {o_lat['embedding_s']['mean']*1000:>8.0f} ms | {g_lat['embedding_s']['mean']*1000:>8.0f} ms | {diff_num((g_lat['embedding_s']['mean'] - b_lat['embedding_s']['mean'])*1000, 0, 0):>7} ms"
        )
        print(
            f"  {'Retrieval Latency':<22} | {b_lat['retrieval_s']['mean']*1000:>8.0f} ms | {o_lat['retrieval_s']['mean']*1000:>8.0f} ms | {g_lat['retrieval_s']['mean']*1000:>8.0f} ms | {diff_num((g_lat['retrieval_s']['mean'] - b_lat['retrieval_s']['mean'])*1000, 0, 0):>7} ms"
        )
        print(
            f"  {'RAG Build Latency':<22} | {b_lat['context_build_s']['mean']*1000:>8.0f} ms | {o_lat['context_build_s']['mean']*1000:>8.0f} ms | {g_lat['context_build_s']['mean']*1000:>8.0f} ms | {diff_num((g_lat['context_build_s']['mean'] - b_lat['context_build_s']['mean'])*1000, 0, 0):>7} ms"
        )
        print(
            f"  {'Generation Latency':<22} | {b_lat['generation_s']['mean']:>8.2f} s | {o_lat['generation_s']['mean']:>8.2f} s | {g_lat['generation_s']['mean']:>8.2f} s | {diff_num(g_lat['generation_s']['mean'] - b_lat['generation_s']['mean'], 2):>8} s"
        )
        print(
            f"  {'Total E2E Latency':<22} | {b_lat['total_s']['mean']:>8.2f} s | {o_lat['total_s']['mean']:>8.2f} s | {g_lat['total_s']['mean']:>8.2f} s | {diff_num(g_lat['total_s']['mean'] - b_lat['total_s']['mean'], 2):>8} s"
        )
        print("=" * 78)
        print()
