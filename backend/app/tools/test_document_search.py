"""
Unit test suite for Goal 10.4: Document Search / RAG Tool.

Deterministic, mock-based unit tests independent of Ollama or network availability:
1. Successful retrieval with complete provenance (chunk_id, attachment_id, section_title, page_number, similarity_score, content, metadata)
2. Custom top_k handling and clamping (default=5, custom top_k=3, invalid top_k rejected)
3. Attachment filtering (attachment_ids, attachment_id, deduplication, and JIT indexing triggers)
4. Empty/whitespace query rejection (ToolInputValidationError)
5. Invalid parameters (top_k < 1 or top_k > 50)
6. No results handling (returns ToolResult.ok with chunks=[], result_count=0)
7. Missing attachment 404 handling (AttachmentNotFoundError with attachment IDs metadata)
8. Retrieval failure isolation (HTTPException, unexpected runtime errors returning ToolResult.fail)
9. Retrieval-only guarantee (no text generation, pure evidence retrieval)
10. ToolRegistry registration and get_definitions() export
11. Execution through ToolExecutionService (end-to-end tool execution record)
12. ToolExecutionService invalid arguments validation rejection
"""

import sys
import unittest
from pathlib import Path
from typing import Any, Optional
from fastapi import HTTPException

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parent.parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.models.retrieval import RetrievalResponse, RetrievalResult
from app.models.tool import ToolResult
from app.tools.base import ToolInputValidationError
from app.tools.registry import ToolRegistry, tool_registry
from app.tools.document_search import DocumentSearchTool, DocumentSearchInput, document_search_tool
from app.tools.executor import ToolExecutionService


# ─────────────────────────────────────────────────────────────────────────────
# Mocks
# ─────────────────────────────────────────────────────────────────────────────

class MockRetrievalService:
    """Mock RetrievalService that returns controlled RetrievalResponse objects."""

    def __init__(self, results: Optional[list[RetrievalResult]] = None, fail_with: Optional[Exception] = None):
        self.results = results if results is not None else []
        self.fail_with = fail_with
        self.search_calls: list[dict[str, Any]] = []

    async def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: Optional[float] = None,
        attachment_id: Optional[str] = None,
        attachment_ids: Optional[list[str]] = None,
    ) -> RetrievalResponse:
        self.search_calls.append({
            "query": query,
            "top_k": top_k,
            "min_score": min_score,
            "attachment_id": attachment_id,
            "attachment_ids": attachment_ids,
        })
        if self.fail_with:
            raise self.fail_with

        # Return up to top_k results
        returned_results = self.results[:top_k]
        return RetrievalResponse(
            query=query,
            model="mock-embed",
            dimensions=768,
            result_count=len(returned_results),
            results=returned_results,
        )


class MockRAGService:
    """Mock RAGService that tracks ensure_attachments_indexed calls."""

    def __init__(self, fail_with: Optional[Exception] = None):
        self.fail_with = fail_with
        self.indexed_calls: list[list[str]] = []

    async def ensure_attachments_indexed(self, attachment_ids: list[str]) -> None:
        self.indexed_calls.append(attachment_ids)
        if self.fail_with:
            raise self.fail_with


def sample_retrieval_results() -> list[RetrievalResult]:
    """Helper returning sample chunk results with complete provenance."""
    return [
        RetrievalResult(
            chunk_id="chunk_qkd_001",
            attachment_id="att_quantum_doc",
            content="Quantum Key Distribution (QKD) relies on quantum entanglement and photon polarization.",
            similarity_score=0.8924,
            document_section_index=0,
            chunk_index=0,
            page_number=1,
            section_title="Introduction to QKD",
            metadata={"filename": "qkd_overview.pdf", "category": "cryptography"},
        ),
        RetrievalResult(
            chunk_id="chunk_qkd_002",
            attachment_id="att_quantum_doc",
            content="The BB84 protocol was developed by Charles Bennett and Gilles Brassard in 1984.",
            similarity_score=0.8105,
            document_section_index=1,
            chunk_index=1,
            page_number=2,
            section_title="BB84 Protocol",
            metadata={"filename": "qkd_overview.pdf", "category": "cryptography"},
        ),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Test Suite
# ─────────────────────────────────────────────────────────────────────────────

class TestDocumentSearchTool(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.mock_retrieval = MockRetrievalService(results=sample_retrieval_results())
        self.mock_rag = MockRAGService()
        self.tool = DocumentSearchTool(
            retrieval_svc=self.mock_retrieval,
            rag_svc=self.mock_rag,
        )

    # 1. Successful retrieval with complete provenance
    async def test_successful_retrieval_preserves_provenance(self):
        result = await self.tool.execute(query="quantum cryptography", top_k=5)

        self.assertTrue(result.success)
        self.assertEqual(result.tool_name, "document_search")
        self.assertIsNone(result.error)

        data = result.data
        self.assertEqual(data["query"], "quantum cryptography")
        self.assertEqual(data["result_count"], 2)
        self.assertEqual(len(data["chunks"]), 2)

        # Check complete provenance on retrieved chunk
        c0 = data["chunks"][0]
        self.assertEqual(c0["chunk_id"], "chunk_qkd_001")
        self.assertEqual(c0["attachment_id"], "att_quantum_doc")
        self.assertEqual(c0["section_title"], "Introduction to QKD")
        self.assertEqual(c0["document_section_index"], 0)
        self.assertEqual(c0["chunk_index"], 0)
        self.assertEqual(c0["page_number"], 1)
        self.assertAlmostEqual(c0["similarity_score"], 0.8924, places=4)
        self.assertIn("Quantum Key Distribution", c0["content"])
        self.assertEqual(c0["metadata"]["filename"], "qkd_overview.pdf")

        # Check metadata
        meta = result.metadata
        self.assertEqual(meta["query"], "quantum cryptography")
        self.assertEqual(meta["top_k"], 5)
        self.assertEqual(meta["result_count"], 2)
        self.assertAlmostEqual(meta["top_score"], 0.8924, places=4)
        self.assertEqual(meta["chunk_ids"], ["chunk_qkd_001", "chunk_qkd_002"])

    # 2. Custom top_k handling
    async def test_custom_top_k_parameter(self):
        result = await self.tool.execute(query="quantum", top_k=1)
        self.assertTrue(result.success)
        self.assertEqual(len(self.mock_retrieval.search_calls), 1)
        self.assertEqual(self.mock_retrieval.search_calls[0]["top_k"], 1)
        self.assertEqual(len(result.data["chunks"]), 1)

    async def test_default_top_k_is_five(self):
        result = await self.tool.execute(query="quantum")
        self.assertTrue(result.success)
        self.assertEqual(len(self.mock_retrieval.search_calls), 1)
        self.assertEqual(self.mock_retrieval.search_calls[0]["top_k"], 5)

    # 3. Attachment filtering and JIT indexing triggers
    async def test_attachment_ids_filtering(self):
        result = await self.tool.execute(
            query="protocols",
            attachment_ids=["att_doc_a", "att_doc_b"],
        )
        self.assertTrue(result.success)
        # Verify JIT indexing was triggered
        self.assertEqual(self.mock_rag.indexed_calls, [["att_doc_a", "att_doc_b"]])
        # Verify attachment_ids passed to retrieval service
        self.assertEqual(self.mock_retrieval.search_calls[0]["attachment_ids"], ["att_doc_a", "att_doc_b"])

    async def test_single_attachment_id_normalized(self):
        result = await self.tool.execute(
            query="protocols",
            attachment_id="att_doc_single",
        )
        self.assertTrue(result.success)
        self.assertEqual(self.mock_rag.indexed_calls, [["att_doc_single"]])
        self.assertEqual(self.mock_retrieval.search_calls[0]["attachment_ids"], ["att_doc_single"])

    async def test_combined_attachment_ids_deduplicated(self):
        result = await self.tool.execute(
            query="protocols",
            attachment_ids=["att_1", "att_2"],
            attachment_id="att_1",
        )
        self.assertTrue(result.success)
        self.assertEqual(self.mock_rag.indexed_calls, [["att_1", "att_2"]])
        self.assertEqual(self.mock_retrieval.search_calls[0]["attachment_ids"], ["att_1", "att_2"])

    # 4. Empty/whitespace query rejection
    async def test_empty_query_rejected(self):
        result = await self.tool.execute(query="")
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "ToolInputValidationError")
        self.assertIn("empty or whitespace", result.error)
        self.assertEqual(len(self.mock_retrieval.search_calls), 0)

    async def test_whitespace_only_query_rejected(self):
        result = await self.tool.execute(query="     ")
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "ToolInputValidationError")
        self.assertIn("empty or whitespace", result.error)
        self.assertEqual(len(self.mock_retrieval.search_calls), 0)

    # 5. Invalid top_k parameters
    async def test_top_k_less_than_one_rejected(self):
        result = await self.tool.execute(query="test", top_k=0)
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "ToolInputValidationError")
        self.assertIn("top_k must be between 1 and 50", result.error)

    async def test_top_k_greater_than_fifty_rejected(self):
        result = await self.tool.execute(query="test", top_k=51)
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "ToolInputValidationError")
        self.assertIn("top_k must be between 1 and 50", result.error)

    # 6. No results handling
    async def test_no_results_returns_empty_list(self):
        empty_retrieval = MockRetrievalService(results=[])
        tool = DocumentSearchTool(retrieval_svc=empty_retrieval, rag_svc=self.mock_rag)

        result = await tool.execute(query="nonexistent query")
        self.assertTrue(result.success)
        self.assertEqual(result.data["result_count"], 0)
        self.assertEqual(result.data["chunks"], [])
        self.assertEqual(result.metadata["top_score"], 0.0)
        self.assertEqual(result.metadata["chunk_ids"], [])

    # 7. Missing attachment 404 handling
    async def test_missing_attachment_404(self):
        failing_rag = MockRAGService(
            fail_with=HTTPException(status_code=404, detail="Attachment att_missing not found")
        )
        tool = DocumentSearchTool(retrieval_svc=self.mock_retrieval, rag_svc=failing_rag)

        result = await tool.execute(query="query", attachment_id="att_missing")
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "AttachmentNotFoundError")
        self.assertIn("404", result.error)
        self.assertIn("Attachment att_missing not found", result.error)
        self.assertEqual(result.metadata["attachment_ids"], ["att_missing"])

    # 8. Retrieval failure isolation
    async def test_retrieval_http_exception_handled(self):
        failing_retrieval = MockRetrievalService(
            fail_with=HTTPException(status_code=503, detail="Ollama embedding service unavailable")
        )
        tool = DocumentSearchTool(retrieval_svc=failing_retrieval, rag_svc=self.mock_rag)

        result = await tool.execute(query="quantum")
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "RetrievalServiceError")
        self.assertIn("503", result.error)
        self.assertIn("Ollama embedding service unavailable", result.error)

    async def test_unexpected_runtime_exception_handled(self):
        crashing_retrieval = MockRetrievalService(
            fail_with=RuntimeError("Vector index disk corrupted")
        )
        tool = DocumentSearchTool(retrieval_svc=crashing_retrieval, rag_svc=self.mock_rag)

        result = await tool.execute(query="quantum")
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "RuntimeError")
        self.assertIn("Vector index disk corrupted", result.error)

    # 9. Retrieval-only guarantee (pure evidence, no LLM answer generation)
    async def test_retrieval_only_guarantee(self):
        result = await self.tool.execute(query="quantum cryptography")
        self.assertTrue(result.success)
        # Ensure no answer/generation fields exist
        self.assertNotIn("answer", result.data)
        self.assertNotIn("response", result.data)
        self.assertNotIn("generated_text", result.data)
        self.assertIn("chunks", result.data)
        self.assertIn("result_count", result.data)

    # 10. Registry registration and schema definition
    def test_tool_registry_registration_and_definitions(self):
        registered = tool_registry.get("document_search")
        self.assertIsNotNone(registered)
        self.assertEqual(registered.name, "document_search")

        definitions = tool_registry.get_definitions()
        doc_def = next(
            (d for d in definitions if d.get("function", {}).get("name") == "document_search"),
            None,
        )
        self.assertIsNotNone(doc_def)
        fn = doc_def["function"]
        self.assertEqual(fn["name"], "document_search")
        schema = fn["parameters"]
        self.assertEqual(schema["type"], "object")
        self.assertIn("query", schema["properties"])
        self.assertIn("top_k", schema["properties"])
        self.assertIn("attachment_ids", schema["properties"])
        self.assertIn("attachment_id", schema["properties"])
        self.assertIn("query", schema["required"])

        # Also test to_definition()
        pydantic_def = registered.to_definition()
        self.assertEqual(pydantic_def.name, "document_search")
        self.assertEqual(pydantic_def.parameters, schema)

    # 11. Execution through ToolExecutionService
    async def test_execution_service_integration(self):
        registry = ToolRegistry()
        registry.register(self.tool)
        execution_service = ToolExecutionService(registry=registry)

        record = await execution_service.execute_tool(
            tool_name="document_search",
            arguments={"query": "quantum cryptography", "top_k": 2},
        )

        self.assertTrue(record.success)
        self.assertEqual(record.tool_name, "document_search")
        self.assertGreaterEqual(record.duration_ms, 0.0)
        self.assertTrue(record.execution_id.startswith("exec_"))
        self.assertEqual(record.data["result_count"], 2)
        self.assertEqual(len(record.data["chunks"]), 2)
        self.assertEqual(record.data["chunks"][0]["chunk_id"], "chunk_qkd_001")
        self.assertIsNotNone(record.result)
        self.assertEqual(record.result.data["result_count"], 2)

    # 12. Execution through ToolExecutionService with invalid arguments
    async def test_execution_service_validation_rejection(self):
        registry = ToolRegistry()
        registry.register(self.tool)
        execution_service = ToolExecutionService(registry=registry)

        # Missing required 'query'
        record = await execution_service.execute_tool(
            tool_name="document_search",
            arguments={"top_k": 5},
        )

        self.assertFalse(record.success)
        self.assertEqual(record.error_type, "ToolInputValidationError")
        self.assertIn("query", record.error)
        self.assertIn("Field required", record.error)


if __name__ == "__main__":
    unittest.main()
