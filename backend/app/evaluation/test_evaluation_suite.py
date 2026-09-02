"""
Goal 9 Task 1 — Evaluation Framework Test Suite.

Tests are deterministic and do not call Ollama or require indexed documents
(except where explicitly testing integration).
Run from backend/ directory:
    python -m app.evaluation.test_evaluation_suite
"""
import json
import sys
import statistics
from pathlib import Path

# ── Test helpers ──────────────────────────────────────────────────────────────
PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  [{PASS}] {name}")
    else:
        msg = f"  [{FAIL}] {name}" + (f": {detail}" if detail else "")
        print(msg)
        failures.append(name)


def section(title: str) -> None:
    print(f"\n{'-' * 60}")
    print(f"  {title}")
    print(f"{'-' * 60}")


# ─────────────────────────────────────────────────────────────────────────────
# 1. Dataset schema validation
# ─────────────────────────────────────────────────────────────────────────────

def test_dataset() -> None:
    section("1. Dataset Schema Validation")
    from app.evaluation.dataset import load_dataset, DATASET_VERSION, BenchmarkCase

    ds = load_dataset()
    check("dataset loads without errors", ds is not None)
    check("dataset_version exists", bool(ds.dataset_version))
    check("dataset_version matches constant", ds.dataset_version == DATASET_VERSION)
    check("total cases >= 30", len(ds.cases) >= 30, f"got {len(ds.cases)}")

    # Category counts
    by_cat = ds.by_category()
    check("factual >= 7", len(by_cat.get("factual", [])) >= 7)
    check("multi-chunk >= 5", len(by_cat.get("multi-chunk", [])) >= 5)
    check("multi-doc >= 4", len(by_cat.get("multi-doc", [])) >= 4)
    check("absent >= 4", len(by_cat.get("absent", [])) >= 4)
    check("injection >= 2", len(by_cat.get("injection", [])) >= 2)
    check("summarization >= 3", len(by_cat.get("summarization", [])) >= 3)
    check("comparison >= 3", len(by_cat.get("comparison", [])) >= 3)
    check("irrelevant >= 2", len(by_cat.get("irrelevant", [])) >= 2)

    # All cases have unique IDs
    ids = [c.id for c in ds.cases]
    check("all case IDs are unique", len(ids) == len(set(ids)))

    # All cases validate individually
    for case in ds.cases:
        try:
            case.validate()
        except ValueError as e:
            check(f"case {case.id} validates", False, str(e))
            continue
        check(f"case {case.id} validates", True)

    # get_case works
    c = ds.get_case("FACT-001")
    check("get_case('FACT-001') returns case", c is not None and c.id == "FACT-001")
    c2 = ds.get_case("NONEXISTENT")
    check("get_case('NONEXISTENT') returns None", c2 is None)

    # Invalid case raises ValueError
    bad = BenchmarkCase(
        id="",  # invalid
        category="factual",
        question="?",
        expected_facts=[],  # invalid
        ground_truth_markers=["abc"],
        corpus_docs=["file.txt"],
    )
    raised = False
    try:
        bad.validate()
    except ValueError:
        raised = True
    check("invalid case raises ValueError", raised)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Ground-truth marker approach
# ─────────────────────────────────────────────────────────────────────────────

def test_ground_truth_design() -> None:
    section("2. Ground-Truth Marker Design")
    from app.evaluation.dataset import load_dataset

    ds = load_dataset()

    # No case in retrieval-applicable categories has empty markers
    retrieval_cats = {"factual", "multi-chunk", "multi-doc", "summarization", "comparison"}
    for case in ds.cases:
        if case.category in retrieval_cats:
            check(
                f"{case.id} has ground_truth_markers",
                bool(case.ground_truth_markers),
                f"category={case.category}",
            )

    # Absent/irrelevant cases have empty markers (by design)
    for case in ds.cases:
        if case.category in ("absent", "irrelevant"):
            check(
                f"{case.id} has empty ground_truth_markers (absent/irrelevant)",
                len(case.ground_truth_markers) == 0,
            )

    # Corpus docs are specified for cases that need retrieval
    for case in ds.cases:
        if case.category in retrieval_cats:
            check(
                f"{case.id} has corpus_docs",
                bool(case.corpus_docs),
            )

    # Injection cases have absent_facts
    for case in ds.cases:
        if case.category in ("absent", "injection"):
            check(
                f"{case.id} has absent_facts for unsupported-claim checking",
                bool(case.absent_facts) or case.id == "INJECT-002",  # INJECT-002 tests non-injection
            )


# ─────────────────────────────────────────────────────────────────────────────
# 3. Retrieval metrics
# ─────────────────────────────────────────────────────────────────────────────

def test_retrieval_metrics() -> None:
    section("3. Retrieval Metrics (Deterministic)")
    from app.evaluation import metrics as m

    relevant = {"c1", "c2", "c3"}
    retrieved_perfect = ["c1", "c2", "c3", "c4", "c5"]
    retrieved_partial = ["c4", "c1", "c5", "c6", "c7"]
    retrieved_none = ["c4", "c5", "c6"]

    # Recall@K
    check("recall@5 perfect = 1.0", abs(m.recall_at_k(retrieved_perfect, relevant, 5) - 1.0) < 1e-9)
    check("recall@5 partial = 0.333", abs(m.recall_at_k(retrieved_partial, relevant, 5) - 1/3) < 1e-6)
    check("recall@5 none = 0.0", m.recall_at_k(retrieved_none, relevant, 5) == 0.0)
    check("recall@5 empty relevant = 0.0", m.recall_at_k(retrieved_perfect, set(), 5) == 0.0)

    # Precision@K
    check("precision@5 perfect = 0.6", abs(m.precision_at_k(retrieved_perfect, relevant, 5) - 0.6) < 1e-9)
    check("precision@5 partial = 0.2", abs(m.precision_at_k(retrieved_partial, relevant, 5) - 0.2) < 1e-9)
    check("precision@5 none = 0.0", m.precision_at_k(retrieved_none, relevant, 5) == 0.0)
    check("precision@5 empty retrieved = 0.0", m.precision_at_k([], relevant, 5) == 0.0)

    # Hit Rate@K
    check("hit_rate@5 perfect = 1.0", m.hit_rate_at_k(retrieved_perfect, relevant, 5) == 1.0)
    check("hit_rate@5 partial = 1.0", m.hit_rate_at_k(retrieved_partial, relevant, 5) == 1.0)
    check("hit_rate@5 none = 0.0", m.hit_rate_at_k(retrieved_none, relevant, 5) == 0.0)
    check("hit_rate@5 empty relevant = 0.0", m.hit_rate_at_k(retrieved_perfect, set(), 5) == 0.0)

    # MRR
    check("mrr perfect first = 1.0", abs(m.mrr(retrieved_perfect, relevant) - 1.0) < 1e-9)
    check("mrr second = 0.5", abs(m.mrr(["c4", "c1"], relevant) - 0.5) < 1e-9)
    check("mrr third = 0.333", abs(m.mrr(["c4", "c5", "c1"], relevant) - 1/3) < 1e-6)
    check("mrr none = 0.0", m.mrr(["c4", "c5"], relevant) == 0.0)

    # Avg similarity
    check("avg_sim empty = 0.0", m.avg_similarity_score([]) == 0.0)
    check("avg_sim [0.8, 0.6] = 0.7", abs(m.avg_similarity_score([0.8, 0.6]) - 0.7) < 1e-9)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Answer quality metrics
# ─────────────────────────────────────────────────────────────────────────────

def test_answer_metrics() -> None:
    section("4. Answer Quality Metrics (Deterministic)")
    from app.evaluation import metrics as m

    # fact_coverage
    facts = ["Dr. Sarah Chen", "90 days", "4096 bits"]
    answer_full = "Dr. Sarah Chen led the group. The key size is 4096 bits. Rotation is 90 days."
    answer_partial = "Dr. Sarah Chen led the committee."
    answer_none = "The answer is unknown."

    check("fact_coverage full = 1.0", abs(m.fact_coverage(facts, answer_full) - 1.0) < 1e-9)
    check("fact_coverage partial = 0.333", abs(m.fact_coverage(facts, answer_partial) - 1/3) < 1e-6)
    check("fact_coverage none = 0.0", m.fact_coverage(facts, answer_none) == 0.0)
    check("fact_coverage empty facts = 0.0", m.fact_coverage([], answer_full) == 0.0)

    # groundedness — context contains "90 days" and "4096 bits" but NOT "Dr. Sarah Chen"
    context = "The key rotation period is 90 days. The algorithm uses 4096 bits for the key size."
    check(
        "groundedness partial = 0.667",
        abs(m.groundedness(facts, context) - 2/3) < 1e-6,
        f"got {m.groundedness(facts, context)}, facts={facts}",
    )
    check("groundedness empty context = 0.0", m.groundedness(facts, "") == 0.0)
    check("groundedness empty facts = 0.0", m.groundedness([], context) == 0.0)

    # unsupported_claim_rate
    absent = ["HKDF parameters", "salt length", "4096"]
    answer_with_claims = "The key derivation uses salt length of 256 bits and 4096 iterations."
    answer_clean = "I cannot find that information in the provided documents."
    check("unsupported_claim > 0 when claims present", m.unsupported_claim_rate(absent, answer_with_claims) > 0)
    check("unsupported_claim = 0 when no claims", m.unsupported_claim_rate(absent, answer_clean) == 0.0)
    check("unsupported_claim empty absent = 0.0", m.unsupported_claim_rate([], answer_with_claims) == 0.0)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Latency metrics
# ─────────────────────────────────────────────────────────────────────────────

def test_latency_metrics() -> None:
    section("5. Latency Metrics")
    from app.evaluation import metrics as m

    vals = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    stats = m.latency_stats(vals)

    required_keys = {"mean", "median", "p95", "p99", "min", "max", "count"}
    check("latency_stats has all required keys", required_keys <= set(stats.keys()))
    check("latency_stats mean = 0.55", abs(stats["mean"] - 0.55) < 1e-9)
    check("latency_stats min = 0.1", abs(stats["min"] - 0.1) < 1e-9)
    check("latency_stats max = 1.0", abs(stats["max"] - 1.0) < 1e-9)
    check("latency_stats count = 10", stats["count"] == 10)
    check("latency_stats p95 <= max", stats["p95"] <= stats["max"])
    check("latency_stats p99 >= p95", stats["p99"] >= stats["p95"])

    empty_stats = m.latency_stats([])
    check("empty latency_stats has all keys", required_keys <= set(empty_stats.keys()))
    check("empty latency_stats mean = 0.0", empty_stats["mean"] == 0.0)
    check("empty latency_stats count = 0", empty_stats["count"] == 0)

    # Verify CaseLatenices has all 5 timing fields
    from app.evaluation.evaluator import CaseLatenices
    lat = CaseLatenices()
    required_fields = {"embedding_s", "retrieval_s", "context_build_s", "generation_s", "total_s"}
    actual_fields = set(vars(lat).keys())
    check("CaseLatenices has all 5 timing fields", required_fields <= actual_fields)


# ─────────────────────────────────────────────────────────────────────────────
# 6. CaseEvaluator
# ─────────────────────────────────────────────────────────────────────────────

def test_evaluator() -> None:
    section("6. CaseEvaluator")
    from app.evaluation.dataset import load_dataset
    from app.evaluation.evaluator import CaseEvaluator, CaseLatenices

    ds = load_dataset()
    case = ds.get_case("FACT-001")

    evaluator = CaseEvaluator()
    result = evaluator.evaluate(
        case=case,
        relevant_chunk_ids={"chk_att_abc_s0_c0"},
        retrieved_chunk_ids=["chk_att_abc_s0_c0", "chk_att_abc_s1_c0"],
        similarity_scores=[0.9, 0.7],
        rag_context="Dr. Sarah Chen led the QES standardization working group.",
        answer="Dr. Sarah Chen was the chair of the QES standardization group.",
        latencies=CaseLatenices(embedding_s=0.1, retrieval_s=0.2, context_build_s=0.05, generation_s=5.0, total_s=5.35),
    )

    check("result.case_id matches", result.case_id == "FACT-001")
    check("result.category matches", result.category == "factual")
    check("recall_at_5 = 1.0 (one relevant hit)", abs(result.recall_at_5 - 1.0) < 1e-9)
    check("hit_rate_at_5 = 1.0", result.hit_rate_at_5 == 1.0)
    check("mrr_score = 1.0 (first position)", result.mrr_score == 1.0)
    check("fact_coverage > 0 (Dr. Sarah Chen in answer)", result.fact_coverage_score > 0)
    check("groundedness > 0 (Dr. Sarah Chen in context)", result.groundedness_score > 0)
    check("latencies stored", result.latencies.generation_s == 5.0)
    check("retrieval_applicable = True (has relevant chunks)", result.retrieval_applicable)


# ─────────────────────────────────────────────────────────────────────────────
# 7. Report schema
# ─────────────────────────────────────────────────────────────────────────────

def test_report_schema() -> None:
    section("7. Report Schema")
    from app.evaluation.dataset import load_dataset
    from app.evaluation.evaluator import CaseEvaluator, CaseLatenices
    from app.evaluation.report import ReportGenerator
    import tempfile

    ds = load_dataset()
    evaluator = CaseEvaluator()
    results = []
    for case in ds.cases[:3]:
        results.append(
            evaluator.evaluate(
                case=case,
                relevant_chunk_ids=set(),
                retrieved_chunk_ids=[],
                similarity_scores=[],
                rag_context="",
                answer="Test answer.",
                latencies=CaseLatenices(),
            )
        )

    reporter = ReportGenerator()
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "test_baseline.json"
        report = reporter.save(out, results)

        check("baseline.json written", out.exists())

        with open(out, encoding="utf-8") as fh:
            loaded = json.load(fh)

        required_top = {
            "evaluation_timestamp",
            "configuration",
            "total_cases",
            "aggregate_metrics",
            "per_category_metrics",
            "per_case_results",
        }
        check(
            "report has all required top-level keys",
            required_top <= set(loaded.keys()),
            f"missing: {required_top - set(loaded.keys())}",
        )

        required_config = {
            "chat_model", "embedding_model", "embedding_dimensions",
            "chunk_size", "chunk_overlap", "rag_enabled", "rag_top_k",
            "rag_min_score", "similarity_top_k",
        }
        check(
            "configuration snapshot has required keys",
            required_config <= set(loaded["configuration"].keys()),
        )

        agg = loaded["aggregate_metrics"]
        check("aggregate_metrics has retrieval", "retrieval" in agg)
        check("aggregate_metrics has answer_quality", "answer_quality" in agg)
        check("aggregate_metrics has latency", "latency" in agg)

        lat = agg["latency"]
        for key in ("embedding_s", "retrieval_s", "context_build_s", "generation_s", "total_s"):
            check(f"latency.{key} exists in report", key in lat)

        check("per_case_results is a list", isinstance(loaded["per_case_results"], list))
        if loaded["per_case_results"]:
            per_case_keys = {"id", "category", "retrieval_metrics", "answer_metrics", "latencies_s"}
            check(
                "per-case result has required keys",
                per_case_keys <= set(loaded["per_case_results"][0].keys()),
            )


# ─────────────────────────────────────────────────────────────────────────────
# 8. Reproducibility
# ─────────────────────────────────────────────────────────────────────────────

def test_reproducibility() -> None:
    section("8. Reproducibility")
    from app.evaluation.dataset import load_dataset, DATASET_VERSION

    # Loading twice should produce identical case IDs and versions
    ds1 = load_dataset()
    ds2 = load_dataset()

    check("same dataset version across two loads", ds1.dataset_version == ds2.dataset_version)
    check("same dataset version == constant", ds1.dataset_version == DATASET_VERSION)
    ids1 = [c.id for c in ds1.cases]
    ids2 = [c.id for c in ds2.cases]
    check("same case order and IDs across two loads", ids1 == ids2)

    # Markers are stable (no randomness)
    for c1, c2 in zip(ds1.cases, ds2.cases):
        check(
            f"{c1.id} ground_truth_markers are stable",
            c1.ground_truth_markers == c2.ground_truth_markers,
        )


# ─────────────────────────────────────────────────────────────────────────────
# 9. Corpus files exist
# ─────────────────────────────────────────────────────────────────────────────

def test_corpus_files() -> None:
    section("9. Corpus Files")
    corpus_dir = Path(__file__).parent / "corpus"
    text_files = [
        "quantum_cryptography.md",
        "project_atlas.txt",
        "climate_report.json",
        "employee_directory.csv",
    ]
    for fname in text_files:
        path = corpus_dir / fname
        check(f"corpus/{fname} exists", path.exists())
        check(f"corpus/{fname} is non-empty", path.stat().st_size > 100 if path.exists() else False)

    gen_files = ["_generate_pdf.py", "_generate_docx.py"]
    for fname in gen_files:
        check(f"corpus/{fname} exists", (corpus_dir / fname).exists())

    # Verify specific corpus facts are present in the text files
    qc = (corpus_dir / "quantum_cryptography.md").read_text(encoding="utf-8")
    check("QES key size 4096 in corpus", "4096" in qc)
    check("Dr. Sarah Chen in corpus", "Dr. Sarah Chen" in qc)
    check("90 days in corpus", "90 days" in qc)

    pa = (corpus_dir / "project_atlas.txt").read_text(encoding="utf-8")
    check("$2,400,000 in project atlas", "$2,400,000" in pa)
    check("Marcus Webb in project atlas", "Marcus Webb" in pa)

    cr = (corpus_dir / "climate_report.json").read_text(encoding="utf-8")
    check("425.3 in climate report", "425.3" in cr)
    check("1.3 in climate report", "1.3" in cr)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n" + "=" * 60)
    print("  Goal 9 Task 1 — Evaluation Framework Test Suite")
    print("=" * 60)

    test_corpus_files()
    test_dataset()
    test_ground_truth_design()
    test_retrieval_metrics()
    test_answer_metrics()
    test_latency_metrics()
    test_evaluator()
    test_report_schema()
    test_reproducibility()

    print("\n" + "=" * 60)
    if failures:
        print(f"  FAILED: {len(failures)} test(s)")
        for f in failures:
            print(f"    x {f}")
        print("=" * 60)
        sys.exit(1)
    else:
        print(f"  ALL TESTS PASSED ({sum(1 for _ in [])})")
        print("  ALL EVALUATION FRAMEWORK TESTS PASSED")
        print("=" * 60)


if __name__ == "__main__":
    main()
