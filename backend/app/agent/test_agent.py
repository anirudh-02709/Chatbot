"""
Unit test suite for Goal 10.7: Agent Orchestration Foundation.

Tests:
1. Decision parsing: Valid final-answer (raw JSON)
2. Decision parsing: Valid final-answer in markdown code fence
3. Decision parsing: Valid tool-call
4. Decision parsing: Malformed JSON rejection
5. Decision parsing: Missing decision type rejection
6. Decision parsing: Unknown decision type rejection
7. Decision parsing: Unknown tool rejection against valid tools set
8. Decision parsing: Malformed arguments (non-dict) rejection
9. Agent state: Initial state creation and attributes
10. Agent state: Iteration tracking and timestamp updates
11. Orchestration: Direct answer path (no tool executed, status COMPLETED)
12. Orchestration: Calculator tool call via ToolExecutionService
13. Orchestration: Document search tool call via ToolExecutionService
14. Orchestration: Web search tool call via ToolExecutionService
15. Orchestration: Data analysis tool call via ToolExecutionService
16. Orchestration: Tool execution failure handled cleanly (status ERROR, no crash)
17. Orchestration: Decision parsing failure handled cleanly (status ERROR, no crash)
18. Prompts: System prompt formatting contains registered tools and schema
"""

import sys
import unittest
from pathlib import Path
from typing import Any, Optional

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parent.parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.agent.models import AgentDecisionType, AgentStatus, AgentDecision, AgentState
from app.agent.parser import parse_agent_decision, DecisionParsingError, extract_json_payload
from app.agent.prompts import build_agent_system_prompt
from app.agent.orchestrator import Agent
from app.models.tool import ToolResult
from app.tools.base import BaseTool
from app.tools.registry import ToolRegistry
from app.tools.executor import ToolExecutionService


# ─────────────────────────────────────────────────────────────────────────────
# Mock LLM Service & Mock Tools
# ─────────────────────────────────────────────────────────────────────────────

class MockLLMService:
    """Mock LLM Service returning predetermined responses without network calls."""

    def __init__(self, response_text: str = ""):
        self.response_text = response_text
        self.calls: list[dict[str, Any]] = []

    async def generate_response(
        self,
        messages: list[Any],
        system_prompt: Optional[str] = None,
        mode: Optional[str] = None,
        temperature: float = 0.0,
    ) -> str:
        self.calls.append({
            "messages": messages,
            "system_prompt": system_prompt,
            "mode": mode,
            "temperature": temperature,
        })
        return self.response_text


class MockEchoTool(BaseTool):
    """Simple mock tool for testing."""

    name = "mock_echo"
    description = "Echoes input text back."
    parameters_schema = {
        "type": "object",
        "properties": {
            "message": {"type": "string"},
        },
        "required": ["message"],
    }

    async def execute(self, message: str, **kwargs: Any) -> ToolResult:
        return ToolResult.ok(tool_name=self.name, data={"echo": message})


class MockFailingTool(BaseTool):
    """Tool that returns a failure result."""

    name = "mock_failing"
    description = "Intentionally fails."
    parameters_schema = {"type": "object", "properties": {}}

    async def execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult.fail(tool_name=self.name, error="Simulated tool failure", error_type="ToolError")


# ─────────────────────────────────────────────────────────────────────────────
# Test Suite
# ─────────────────────────────────────────────────────────────────────────────

class TestAgentOrchestration(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        # Create dedicated isolated registry and execution service for testing
        self.registry = ToolRegistry()
        self.echo_tool = MockEchoTool()
        self.failing_tool = MockFailingTool()
        self.registry.register(self.echo_tool)
        self.registry.register(self.failing_tool)

        self.execution_service = ToolExecutionService(registry=self.registry)

    # 1. Decision parsing: Valid final-answer (raw JSON)
    def test_parse_valid_final_answer_raw_json(self):
        raw = '{"type": "final_answer", "answer": "The capital of France is Paris."}'
        decision = parse_agent_decision(raw)

        self.assertEqual(decision.type, AgentDecisionType.FINAL_ANSWER)
        self.assertEqual(decision.answer, "The capital of France is Paris.")
        self.assertIsNone(decision.tool_name)
        self.assertIsNone(decision.tool_arguments)

    # 2. Decision parsing: Valid final-answer in markdown code fence
    def test_parse_valid_final_answer_code_fence(self):
        raw = (
            "Here is my response:\n"
            "```json\n"
            '{\n  "type": "final_answer",\n  "answer": "Quantum computing utilizes superposition."\n}\n'
            "```\n"
            "Hope this helps!"
        )
        decision = parse_agent_decision(raw)

        self.assertEqual(decision.type, AgentDecisionType.FINAL_ANSWER)
        self.assertEqual(decision.answer, "Quantum computing utilizes superposition.")

    # 3. Decision parsing: Valid tool-call
    def test_parse_valid_tool_call(self):
        raw = (
            '{"type": "tool_call", "tool_name": "mock_echo", '
            '"arguments": {"message": "hello world"}, "reasoning": "echo input"}'
        )
        decision = parse_agent_decision(raw, valid_tools={"mock_echo"})

        self.assertEqual(decision.type, AgentDecisionType.TOOL_CALL)
        self.assertEqual(decision.tool_name, "mock_echo")
        self.assertEqual(decision.tool_arguments, {"message": "hello world"})
        self.assertEqual(decision.reasoning, "echo input")
        self.assertIsNone(decision.answer)

    # 4. Decision parsing: Malformed JSON rejection
    def test_parse_malformed_json_rejected(self):
        raw = '{"type": "final_answer", "answer": "incomplete...'
        with self.assertRaises(DecisionParsingError):
            parse_agent_decision(raw)

    # 5. Decision parsing: Missing decision type rejection
    def test_parse_missing_type_rejected(self):
        raw = '{"answer": "Missing type"}'
        with self.assertRaises(DecisionParsingError):
            parse_agent_decision(raw)

    # 6. Decision parsing: Unknown decision type rejection
    def test_parse_unknown_type_rejected(self):
        raw = '{"type": "explore_universe", "data": 123}'
        with self.assertRaises(DecisionParsingError):
            parse_agent_decision(raw)

    # 7. Decision parsing: Unknown tool rejection
    def test_parse_unknown_tool_rejected(self):
        raw = '{"type": "tool_call", "tool_name": "unregistered_tool", "arguments": {}}'
        with self.assertRaises(DecisionParsingError) as ctx:
            parse_agent_decision(raw, valid_tools={"mock_echo"})
        self.assertIn("is not registered", str(ctx.exception))

    # 8. Decision parsing: Malformed arguments rejection
    def test_parse_malformed_arguments_rejected(self):
        raw = '{"type": "tool_call", "tool_name": "mock_echo", "arguments": "not_a_dict"}'
        with self.assertRaises(DecisionParsingError) as ctx:
            parse_agent_decision(raw, valid_tools={"mock_echo"})
        self.assertIn("must be a dictionary", str(ctx.exception))

    # 9. Agent state: Initial state creation
    def test_create_state(self):
        agent = Agent(tool_registry=self.registry, execution_service=self.execution_service)
        state = agent.create_state("Explain quantum key distribution")

        self.assertTrue(state.request_id.startswith("req_"))
        self.assertEqual(state.user_request, "Explain quantum key distribution")
        self.assertEqual(state.status, AgentStatus.INITIALIZED)
        self.assertEqual(state.iteration_count, 0)
        self.assertEqual(len(state.tool_calls), 0)
        self.assertEqual(len(state.execution_records), 0)
        self.assertIsNotNone(state.created_at)

    # 10. Agent state: Iteration tracking and update
    async def test_state_iteration_tracking(self):
        mock_llm = MockLLMService('{"type": "final_answer", "answer": "Paris"}')
        agent = Agent(
            tool_registry=self.registry,
            execution_service=self.execution_service,
            ollama_service=mock_llm,
        )

        state = agent.create_state("Capital of France")
        self.assertEqual(state.iteration_count, 0)

        updated_state = await agent.run_step("Capital of France", state=state)
        self.assertEqual(updated_state.iteration_count, 1)
        self.assertEqual(updated_state.status, AgentStatus.COMPLETED)
        self.assertEqual(updated_state.final_answer, "Paris")

    # 11. Orchestration: Direct answer path
    async def test_direct_answer_orchestration(self):
        mock_llm = MockLLMService('{"type": "final_answer", "answer": "Direct answer without tools."}')
        agent = Agent(
            tool_registry=self.registry,
            execution_service=self.execution_service,
            ollama_service=mock_llm,
        )

        state = await agent.run_step("Hello assistant")

        self.assertEqual(state.status, AgentStatus.COMPLETED)
        self.assertEqual(state.final_answer, "Direct answer without tools.")
        self.assertEqual(len(state.tool_calls), 0)
        self.assertEqual(len(state.execution_records), 0)
        self.assertIsNone(state.error)

    # 12. Orchestration: Calculator tool call via ToolExecutionService
    async def test_calculator_tool_call_orchestration(self):
        from app.tools.calculator import calculator_tool

        reg = ToolRegistry()
        reg.register(calculator_tool)
        exec_svc = ToolExecutionService(registry=reg)

        mock_llm = MockLLMService(
            '{"type": "tool_call", "tool_name": "calculator", "arguments": {"expression": "25 * 4"}}'
        )
        agent = Agent(tool_registry=reg, execution_service=exec_svc, ollama_service=mock_llm)

        state = await agent.run_step("Calculate 25 * 4")

        self.assertEqual(state.status, AgentStatus.STEP_COMPLETED)
        self.assertEqual(len(state.tool_calls), 1)
        self.assertEqual(state.tool_calls[0]["tool_name"], "calculator")
        self.assertEqual(len(state.execution_records), 1)
        self.assertTrue(state.execution_records[0].success)
        self.assertEqual(state.execution_records[0].data["result"], 100)
        self.assertEqual(len(state.tool_results), 1)
        self.assertTrue(state.tool_results[0].success)

    # 13. Orchestration: Document search tool call via ToolExecutionService
    async def test_document_search_tool_call_orchestration(self):
        from app.tools.document_search import DocumentSearchTool
        from app.models.retrieval import RetrievalResponse, RetrievalResult

        class MockRetrieval:
            async def search(self, **kwargs):
                return RetrievalResponse(
                    query=kwargs.get("query", ""),
                    model="mock",
                    dimensions=768,
                    result_count=1,
                    results=[
                        RetrievalResult(
                            chunk_id="c1",
                            attachment_id="a1",
                            content="QKD uses quantum physics.",
                            similarity_score=0.9,
                            document_section_index=0,
                            chunk_index=0,
                        )
                    ],
                )

        doc_tool = DocumentSearchTool(retrieval_svc=MockRetrieval())
        reg = ToolRegistry()
        reg.register(doc_tool)
        exec_svc = ToolExecutionService(registry=reg)

        mock_llm = MockLLMService(
            '{"type": "tool_call", "tool_name": "document_search", "arguments": {"query": "QKD"}}'
        )
        agent = Agent(tool_registry=reg, execution_service=exec_svc, ollama_service=mock_llm)

        state = await agent.run_step("Find documents about QKD")

        self.assertEqual(state.status, AgentStatus.STEP_COMPLETED)
        self.assertEqual(len(state.execution_records), 1)
        self.assertTrue(state.execution_records[0].success)
        self.assertEqual(state.execution_records[0].data["result_count"], 1)

    # 14. Orchestration: Web search tool call via ToolExecutionService
    async def test_web_search_tool_call_orchestration(self):
        from app.tools.web_search import WebSearchTool
        from app.tools.web_search_providers import BaseWebSearchProvider, WebSearchResultItem

        class MockWebProvider(BaseWebSearchProvider):
            name = "mock_web"
            def is_configured(self):
                return True
            async def search(self, query, max_results=5):
                return [
                    WebSearchResultItem(
                        title="Quantum News",
                        url="https://news.example.com",
                        snippet="Breakthrough in quantum key distribution.",
                        source="news.example.com",
                        rank=1,
                    )
                ]

        web_tool = WebSearchTool(provider=MockWebProvider())
        reg = ToolRegistry()
        reg.register(web_tool)
        exec_svc = ToolExecutionService(registry=reg)

        mock_llm = MockLLMService(
            '{"type": "tool_call", "tool_name": "web_search", "arguments": {"query": "quantum news"}}'
        )
        agent = Agent(tool_registry=reg, execution_service=exec_svc, ollama_service=mock_llm)

        state = await agent.run_step("Search web for quantum news")

        self.assertEqual(state.status, AgentStatus.STEP_COMPLETED)
        self.assertEqual(len(state.execution_records), 1)
        self.assertTrue(state.execution_records[0].success)
        self.assertEqual(state.execution_records[0].data["result_count"], 1)

    # 15. Orchestration: Data analysis tool call via ToolExecutionService
    async def test_data_analysis_tool_call_orchestration(self):
        from app.tools.data_analysis import data_analysis_tool

        reg = ToolRegistry()
        reg.register(data_analysis_tool)
        exec_svc = ToolExecutionService(registry=reg)

        mock_llm = MockLLMService(
            '{"type": "tool_call", "tool_name": "data_analysis", "arguments": {'
            '"operation": "describe", "data": [{"x": 10, "y": 20}, {"x": 30, "y": 40}]}}'
        )
        agent = Agent(tool_registry=reg, execution_service=exec_svc, ollama_service=mock_llm)

        state = await agent.run_step("Analyze this table")

        self.assertEqual(state.status, AgentStatus.STEP_COMPLETED)
        self.assertEqual(len(state.execution_records), 1)
        self.assertTrue(state.execution_records[0].success)
        self.assertEqual(state.execution_records[0].data["row_count"], 2)

    # 16. Orchestration: Tool execution failure handled cleanly
    async def test_tool_execution_failure_handled_cleanly(self):
        mock_llm = MockLLMService(
            '{"type": "tool_call", "tool_name": "mock_failing", "arguments": {}}'
        )
        agent = Agent(tool_registry=self.registry, execution_service=self.execution_service, ollama_service=mock_llm)

        state = await agent.run_step("Execute failing tool")

        self.assertEqual(state.status, AgentStatus.ERROR)
        self.assertIn("Simulated tool failure", state.error)
        self.assertEqual(len(state.execution_records), 1)
        self.assertFalse(state.execution_records[0].success)

    # 17. Orchestration: Decision parsing failure handled cleanly
    async def test_decision_parsing_failure_handled_cleanly(self):
        mock_llm = MockLLMService("I am a model that ignores JSON instructions.")
        agent = Agent(tool_registry=self.registry, execution_service=self.execution_service, ollama_service=mock_llm)

        state = await agent.run_step("Test query")

        self.assertEqual(state.status, AgentStatus.ERROR)
        self.assertIn("Could not locate valid JSON", state.error)

    # 18. Prompts: System prompt formatting contains registered tools
    def test_build_agent_system_prompt(self):
        defs = self.registry.get_definitions()
        prompt = build_agent_system_prompt(defs)

        self.assertIn("mock_echo", prompt)
        self.assertIn("mock_failing", prompt)
        self.assertIn("final_answer", prompt)
        self.assertIn("tool_call", prompt)


if __name__ == "__main__":
    unittest.main()
