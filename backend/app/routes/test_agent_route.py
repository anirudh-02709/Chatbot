"""
Unit test suite for the Agent API endpoint POST /api/agent/run.
"""

import sys
import unittest
from pathlib import Path
from typing import Any
from fastapi.testclient import TestClient

backend_root = Path(__file__).resolve().parent.parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.main import app
from app.routes.agent import get_agent
from app.agent.orchestrator import Agent
from app.tools.registry import ToolRegistry
from app.tools.executor import ToolExecutionService
from app.tools.calculator import calculator_tool
from app.agent.test_agent import MockEchoTool, MockFailingTool, MockLLMService


class TestAgentRoute(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

        # Isolated test tools and services
        self.registry = ToolRegistry()
        self.registry.register(calculator_tool)
        self.registry.register(MockEchoTool())
        self.registry.register(MockFailingTool())
        self.execution_service = ToolExecutionService(registry=self.registry)

    def tearDown(self):
        app.dependency_overrides.clear()

    def _create_mock_agent(self, responses: Any) -> Agent:
        mock_llm = MockLLMService(responses)
        return Agent(
            tool_registry=self.registry,
            execution_service=self.execution_service,
            ollama_service=mock_llm,
        )

    # 1. Valid direct answer
    def test_agent_run_direct_answer(self):
        agent = self._create_mock_agent(
            '{"type": "final_answer", "answer": "The speed of light is ~300,000 km/s."}'
        )
        app.dependency_overrides[get_agent] = lambda: agent

        res = self.client.post(
            "/api/agent/run",
            json={"message": "What is the speed of light?"},
        )

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["termination_reason"], "completed")
        self.assertEqual(data["answer"], "The speed of light is ~300,000 km/s.")
        self.assertEqual(data["iteration_count"], 1)
        self.assertEqual(len(data["tool_calls"]), 0)
        self.assertIsNotNone(data["total_duration_ms"])

    # 2. Single tool execution (calculator)
    def test_agent_run_single_tool_calculator(self):
        agent = self._create_mock_agent([
            '{"type": "tool_call", "tool_name": "calculator", "arguments": {"expression": "12 * 12"}}',
            '{"type": "final_answer", "answer": "12 * 12 is 144."}',
        ])
        app.dependency_overrides[get_agent] = lambda: agent

        res = self.client.post(
            "/api/agent/run",
            json={"message": "Calculate 12 * 12"},
        )

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["answer"], "12 * 12 is 144.")
        self.assertEqual(data["iteration_count"], 2)
        self.assertEqual(len(data["tool_calls"]), 1)
        tc = data["tool_calls"][0]
        self.assertEqual(tc["tool_name"], "calculator")
        self.assertEqual(tc["status"], "completed")
        self.assertTrue(tc["success"])
        self.assertEqual(tc["arguments"], {"expression": "12 * 12"})

    # 3. Multi-tool execution
    def test_agent_run_multi_tool(self):
        agent = self._create_mock_agent([
            '{"type": "tool_call", "tool_name": "calculator", "arguments": {"expression": "100 / 4"}}',
            '{"type": "tool_call", "tool_name": "mock_echo", "arguments": {"message": "Result is 25"}}',
            '{"type": "final_answer", "answer": "Computed 25 and confirmed."}',
        ])
        app.dependency_overrides[get_agent] = lambda: agent

        res = self.client.post(
            "/api/agent/run",
            json={"message": "Process and echo"},
        )

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["iteration_count"], 3)
        self.assertEqual(len(data["tool_calls"]), 2)
        self.assertEqual(data["tool_calls"][0]["tool_name"], "calculator")
        self.assertEqual(data["tool_calls"][1]["tool_name"], "mock_echo")

    # 4. Max iterations reached
    def test_agent_run_max_iterations(self):
        agent = self._create_mock_agent([
            f'{{"type": "tool_call", "tool_name": "calculator", "arguments": {{"expression": "{i} + 1"}}}}'
            for i in range(10)
        ])
        app.dependency_overrides[get_agent] = lambda: agent

        res = self.client.post(
            "/api/agent/run",
            json={"message": "Run forever", "max_iterations": 2},
        )

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "max_iterations_reached")
        self.assertEqual(data["termination_reason"], "max_iterations_reached")
        self.assertIn("maximum iteration limit", data["answer"])
        self.assertEqual(len(data["tool_calls"]), 2)

    # 5. Loop detected
    def test_agent_run_loop_detected(self):
        agent = self._create_mock_agent([
            '{"type": "tool_call", "tool_name": "mock_echo", "arguments": {"message": "same"}}',
            '{"type": "tool_call", "tool_name": "mock_echo", "arguments": {"message": "same"}}',
        ])
        app.dependency_overrides[get_agent] = lambda: agent

        res = self.client.post(
            "/api/agent/run",
            json={"message": "Repeat echo"},
        )

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "loop_detected")
        self.assertEqual(data["termination_reason"], "loop_detected")
        self.assertIn("repeated tool execution loop", data["answer"])
        self.assertEqual(len(data["tool_calls"]), 1)

    # 6. Malformed request validation
    def test_agent_run_validation_empty_message(self):
        res = self.client.post(
            "/api/agent/run",
            json={"message": "   "},
        )
        self.assertEqual(res.status_code, 422)

    def test_agent_run_validation_invalid_iterations(self):
        res = self.client.post(
            "/api/agent/run",
            json={"message": "test", "max_iterations": 0},
        )
        self.assertEqual(res.status_code, 422)

        res2 = self.client.post(
            "/api/agent/run",
            json={"message": "test", "max_iterations": 25},
        )
        self.assertEqual(res2.status_code, 422)

    # 7. Backend exception handling
    def test_agent_run_backend_exception(self):
        class CrashingAgent:
            async def run(self, **kwargs):
                raise RuntimeError("Unexpected backend crash")

        app.dependency_overrides[get_agent] = lambda: CrashingAgent()

        res = self.client.post(
            "/api/agent/run",
            json={"message": "Crash test"},
        )

        self.assertEqual(res.status_code, 500)
        self.assertIn("Agent execution failed", res.json()["detail"])

    # 8. Request with attachment IDs
    def test_agent_run_with_attachment_ids(self):
        captured_requests = []

        class InspectingAgent:
            async def run(self, user_request, **kwargs):
                captured_requests.append(user_request)
                from app.agent.models import AgentState, AgentStatus
                return AgentState(
                    request_id="req_test",
                    user_request=user_request,
                    status=AgentStatus.COMPLETED,
                    final_answer="Read attachment successfully.",
                )

        app.dependency_overrides[get_agent] = lambda: InspectingAgent()

        res = self.client.post(
            "/api/agent/run",
            json={
                "message": "Summarize this PDF",
                "attachment_ids": ["att_123", "att_456"],
            },
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(captured_requests), 1)
        self.assertIn("Summarize this PDF", captured_requests[0])
        self.assertIn("att_123, att_456", captured_requests[0])


if __name__ == "__main__":
    unittest.main()
