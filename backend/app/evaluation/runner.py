"""
Evaluation runner for Goal 9.

Usage:
    python -m app.evaluation.runner

The runner:
1. Loads and validates the benchmark dataset.
2. Prepares the evaluation corpus (uploads & indexes documents idempotently).
3. Resolves ground-truth markers to actual chunk IDs from the current corpus.
4. Runs every benchmark case end-to-end through the real assistant pipeline.
5. Aggregates metrics and saves backend/evaluation/results/baseline.json.
6. Prints a concise human-readable summary.

The runner deliberately does NOT modify production vector store data. It uses
a separate evaluation-specific attachment registry so evaluation documents can
be reindexed independently without polluting normal conversation history.
"""
from __future__ import annotations

import asyncio
import json
import logging
import shutil
import time
from pathlib import Path
from typing import Optional

# ── Evaluation imports ───────────────────────────────────────────────────────
from app.evaluation.dataset import BenchmarkCase, BenchmarkDataset, load_dataset
from app.evaluation.evaluator import CaseEvaluator, CaseLatenices, CaseResult
from app.evaluation.report import ReportGenerator
from app.evaluation.metrics import _normalize

# ── Production service imports (read-only usage) ─────────────────────────────
from app.config import get_settings
from app.services.document_processor import DocumentProcessingService
from app.services.document_chunker import DocumentChunker
from app.services.vector_index_service import VectorIndexService
from app.services.retrieval_service import RetrievalService
from app.services.rag_service import RAGService
from app.services.ollama import OllamaService
from app.models.chat import ChatMessage

logger = logging.getLogger("chatbot.evaluation.runner")

CORPUS_DIR = Path(__file__).resolve().parent / "corpus"
RESULTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "evaluation" / "results"
EVAL_REGISTRY_PATH = Path(__file__).resolve().parent / "_eval_registry.json"

# Maps corpus filename -> attachment_id (persisted between runner invocations)
EvalRegistry = dict[str, str]


# ─────────────────────────────────────────────────────────────────────────────
# Registry helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_registry() -> EvalRegistry:
    if EVAL_REGISTRY_PATH.exists():
        try:
            return json.loads(EVAL_REGISTRY_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_registry(registry: EvalRegistry) -> None:
    EVAL_REGISTRY_PATH.write_text(json.dumps(registry, indent=2), encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Corpus preparation
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_binary_corpus() -> None:
    """Generate PDF and DOCX corpus files if not present."""
    pdf_path = CORPUS_DIR / "financial_summary.pdf"
    docx_path = CORPUS_DIR / "architecture_spec.docx"

    if not pdf_path.exists():
        logger.info("Generating evaluation corpus PDF...")
        from app.evaluation.corpus._generate_pdf import generate_financial_pdf
        generate_financial_pdf(pdf_path)
        logger.info(f"Generated: {pdf_path}")

    if not docx_path.exists():
        logger.info("Generating evaluation corpus DOCX...")
        from app.evaluation.corpus._generate_docx import generate_architecture_docx
        generate_architecture_docx(docx_path)
        logger.info(f"Generated: {docx_path}")


def _upload_corpus_file(filename: str, settings: object) -> str:
    """
    Copy a corpus file into the production upload storage and return a new attachment_id.
    This mimics what the file upload endpoint does, bypassing FastAPI for evaluation.
    """
    import uuid as _uuid

    src = CORPUS_DIR / filename
    if not src.exists():
        raise FileNotFoundError(f"Corpus file not found: {src}")

    backend_root = Path(__file__).resolve().parent.parent.parent
    storage_path = (backend_root / settings.upload_dir).resolve()
    storage_path.mkdir(parents=True, exist_ok=True)

    ext = src.suffix.lower()
    attachment_id = f"att_{_uuid.uuid4().hex[:16]}"
    dest = storage_path / f"{attachment_id}{ext}"
    shutil.copy2(src, dest)
    logger.info(f"Uploaded corpus file '{filename}' -> {attachment_id}")
    return attachment_id


async def _index_corpus_file(attachment_id: str) -> None:
    """Index (parse -> chunk -> embed -> store) an evaluation corpus attachment."""
    index_svc = VectorIndexService()
    await index_svc.index_attachment(attachment_id)
    logger.info(f"Indexed corpus attachment {attachment_id}")


async def prepare_corpus(dataset: BenchmarkDataset) -> dict[str, str]:
    """
    Upload and index all corpus documents referenced in the dataset (idempotent).

    Returns a mapping: corpus_filename -> attachment_id.
    """
    settings = get_settings()
    registry = _load_registry()

    # Collect all unique corpus filenames referenced by the dataset
    all_filenames: set[str] = set()
    for case in dataset.cases:
        for fname in case.corpus_docs:
            all_filenames.add(fname)

    _ensure_binary_corpus()

    for fname in sorted(all_filenames):
        if fname in registry:
            # Verify the stored file still exists on disk
            backend_root = Path(__file__).resolve().parent.parent.parent
            storage_path = (backend_root / settings.upload_dir).resolve()
            att_id = registry[fname]
            ext = Path(fname).suffix.lower()
            stored_file = storage_path / f"{att_id}{ext}"
            if stored_file.exists():
                logger.info(f"Corpus '{fname}' already uploaded as {att_id} — reusing.")
                continue
            else:
                logger.info(f"Corpus '{fname}' attachment missing on disk — re-uploading.")

        # Upload and index
        att_id = _upload_corpus_file(fname, settings)
        registry[fname] = att_id
        await _index_corpus_file(att_id)

    _save_registry(registry)
    logger.info(f"Corpus ready: {registry}")
    return dict(registry)


# ─────────────────────────────────────────────────────────────────────────────
# Ground-truth resolution
# ─────────────────────────────────────────────────────────────────────────────

def resolve_ground_truth(
    case: BenchmarkCase,
    filename_to_att_id: dict[str, str],
) -> set[str]:
    """
    Resolve case.ground_truth_markers to actual chunk IDs by scanning the
    chunks of the relevant corpus documents.

    Strategy: for each marker, any chunk whose content contains the marker
    (case-insensitive substring) is considered a ground-truth relevant chunk.

    Returns the set of resolved chunk IDs. Empty set means retrieval metrics
    are not applicable (absent / irrelevant cases).
    """
    if not case.ground_truth_markers:
        return set()

    settings = get_settings()
    processor = DocumentProcessingService(settings=settings)
    chunker = DocumentChunker(settings=settings)

    relevant_ids: set[str] = set()

    for fname in case.corpus_docs:
        att_id = filename_to_att_id.get(fname)
        if not att_id:
            logger.warning(f"Corpus file '{fname}' not in registry — skipping ground-truth resolution.")
            continue

        try:
            parsed = processor.process_attachment(att_id)
        except Exception as e:
            logger.warning(f"Could not parse {att_id} for ground-truth resolution: {e}")
            continue

        chunks_resp = chunker.chunk_document(parsed)

        for chunk in chunks_resp.chunks:
            norm_chunk = _normalize(chunk.content)
            for marker in case.ground_truth_markers:
                if _normalize(marker) in norm_chunk:
                    relevant_ids.add(chunk.id)
                    break  # No need to check other markers for this chunk

    if not relevant_ids and case.ground_truth_markers:
        logger.warning(
            f"Case {case.id}: No chunks resolved for markers {case.ground_truth_markers}. "
            "Retrieval metrics will be 0."
        )

    return relevant_ids


# ─────────────────────────────────────────────────────────────────────────────
# Single-case execution
# ─────────────────────────────────────────────────────────────────────────────

async def run_case(
    case: BenchmarkCase,
    filename_to_att_id: dict[str, str],
    relevant_chunk_ids: set[str],
    retrieval_svc: RetrievalService,
    rag_svc: RAGService,
    ollama_svc: OllamaService,
) -> CaseResult:
    """Execute one benchmark case and return its scored result."""
    settings = get_settings()
    evaluator = CaseEvaluator()
    latencies = CaseLatenices()

    # Determine attachment IDs to scope retrieval
    scoped_att_ids: Optional[list[str]] = None
    if case.corpus_docs:
        scoped_att_ids = [
            filename_to_att_id[f]
            for f in case.corpus_docs
            if f in filename_to_att_id
        ] or None

    # ── 1. Retrieval ──────────────────────────────────────────────────────────
    t0 = time.perf_counter()
    retrieved_chunk_ids: list[str] = []
    similarity_scores: list[float] = []

    try:
        t_emb_start = time.perf_counter()
        res = await retrieval_svc.search(
            query=case.question,
            top_k=settings.rag_top_k,
            min_score=0.0,  # Use 0 for evaluation to see all candidates
            attachment_ids=scoped_att_ids,
        )
        latencies.embedding_s = time.perf_counter() - t_emb_start
        retrieved_chunk_ids = [r.chunk_id for r in res.results]
        similarity_scores = [r.similarity_score for r in res.results]
    except Exception as e:
        logger.warning(f"Retrieval failed on case {case.id}: {e}")

    latencies.retrieval_s = time.perf_counter() - t0

    # ── 2. RAG context ────────────────────────────────────────────────────────
    t_rag = time.perf_counter()
    rag_results = await rag_svc.retrieve_context(
        query=case.question,
        attachment_ids=scoped_att_ids,
    )
    rag_context_str, _ = rag_svc.build_rag_context_block(rag_results)
    rag_context = rag_context_str or ""
    latencies.context_build_s = time.perf_counter() - t_rag

    # ── 3. Generation ─────────────────────────────────────────────────────────
    t_gen = time.perf_counter()
    user_msg = ChatMessage(role="user", content=case.question)
    answer_chunks: list[str] = []
    try:
        async for sse_frame in ollama_svc.stream_chat(
            messages=[user_msg],
            rag_context=rag_context if rag_context else None,
        ):
            # SSE format: "event: <type>\ndata: <json>\n\n"
            # Only collect chunks from 'content' events (skip thinking/start/complete)
            import json as _json
            current_event = None
            for line in sse_frame.splitlines():
                if line.startswith("event:"):
                    current_event = line[6:].strip()
                elif line.startswith("data:") and current_event == "content":
                    raw = line[5:].strip()
                    try:
                        data = _json.loads(raw)
                        if "chunk" in data:
                            answer_chunks.append(data["chunk"])
                    except Exception:
                        pass
    except Exception as e:
        logger.error(f"Generation failed for case {case.id}: {e}")

    answer = "".join(answer_chunks).strip()
    latencies.generation_s = time.perf_counter() - t_gen
    latencies.total_s = latencies.retrieval_s + latencies.context_build_s + latencies.generation_s

    return evaluator.evaluate(
        case=case,
        relevant_chunk_ids=relevant_chunk_ids,
        retrieved_chunk_ids=retrieved_chunk_ids,
        similarity_scores=similarity_scores,
        rag_context=rag_context,
        answer=answer,
        latencies=latencies,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Main runner
# ─────────────────────────────────────────────────────────────────────────────

async def run_evaluation(output_filename: str = "optimized.json") -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("=" * 60)
    logger.info(f" Goal 9 Evaluation Runner — Starting ({output_filename})")
    logger.info("=" * 60)

    # ── 1. Load dataset ───────────────────────────────────────────────────────
    logger.info("Loading benchmark dataset...")
    dataset = load_dataset()
    logger.info(f"Loaded {len(dataset.cases)} cases  |  version: {dataset.dataset_version}")

    # ── 2. Prepare corpus ─────────────────────────────────────────────────────
    logger.info("Preparing evaluation corpus (upload + index)...")
    filename_to_att_id = await prepare_corpus(dataset)

    # ── 3. Resolve ground-truth chunk IDs ────────────────────────────────────
    logger.info("Resolving ground-truth markers to chunk IDs...")
    case_ground_truth: dict[str, set[str]] = {}
    for case in dataset.cases:
        gt_ids = resolve_ground_truth(case, filename_to_att_id)
        case_ground_truth[case.id] = gt_ids
        logger.info(
            f"  {case.id}: {len(gt_ids)} relevant chunks resolved"
            f"{f' from {len(case.ground_truth_markers)} markers' if case.ground_truth_markers else ''}"
        )

    # ── 4. Create shared service instances ────────────────────────────────────
    settings = get_settings()
    retrieval_svc = RetrievalService(settings=settings)
    rag_svc = RAGService(settings=settings)
    ollama_svc = OllamaService(settings=settings)

    # ── 5. Execute benchmark cases ────────────────────────────────────────────
    results: list[CaseResult] = []
    total = len(dataset.cases)

    for i, case in enumerate(dataset.cases, start=1):
        logger.info(f"[{i:02d}/{total}] Running {case.id} ({case.category}): {case.question[:60]}...")
        result = await run_case(
            case=case,
            filename_to_att_id=filename_to_att_id,
            relevant_chunk_ids=case_ground_truth[case.id],
            retrieval_svc=retrieval_svc,
            rag_svc=rag_svc,
            ollama_svc=ollama_svc,
        )
        results.append(result)
        logger.info(
            f"    FC={result.fact_coverage_score:.2f}  "
            f"Ground={result.groundedness_score:.2f}  "
            f"Hit@5={result.hit_rate_at_5:.2f}  "
            f"Gen={result.latencies.generation_s:.1f}s"
        )

    # ── 6. Save report ────────────────────────────────────────────────────────
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RESULTS_DIR / output_filename
    reporter = ReportGenerator()
    report = reporter.save(output_path, results)
    # Inject dataset version into report
    report["dataset_version"] = dataset.dataset_version
    with open(output_path, "w", encoding="utf-8") as fh:
        import json as _json
        _json.dump(report, fh, indent=2, default=str)

    logger.info(f"Report saved: {output_path}")

    # ── 7. Print summary and comparison against baseline ─────────────────────
    reporter.print_summary(report, dataset.dataset_version)

    baseline_path = RESULTS_DIR / "baseline.json"
    optimized_path = RESULTS_DIR / "optimized.json"

    if baseline_path.exists() and optimized_path.exists() and output_filename == "grounded.json":
        try:
            import json as _json
            baseline_report = _json.loads(baseline_path.read_text(encoding="utf-8"))
            optimized_report = _json.loads(optimized_path.read_text(encoding="utf-8"))
            reporter.print_three_way_comparison(baseline_report, optimized_report, report)
        except Exception as e:
            logger.warning(f"Could not load reports for 3-way comparison: {e}")
    elif baseline_path.exists() and output_filename != "baseline.json":
        try:
            import json as _json
            baseline_report = _json.loads(baseline_path.read_text(encoding="utf-8"))
            reporter.print_comparison(baseline_report, report)
        except Exception as e:
            logger.warning(f"Could not load baseline.json for comparison: {e}")


def main() -> None:
    import sys
    output_file = "grounded.json"
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output_file = sys.argv[idx + 1]
    asyncio.run(run_evaluation(output_filename=output_file))


if __name__ == "__main__":
    main()

