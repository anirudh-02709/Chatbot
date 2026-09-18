"""
Unit test suite for Goal 10.3: Tool Execution Layer.

Tests:
1. Successful calculator execution through execution layer
2. Unknown tool rejection (structured failure record with ToolNotFoundError)
3. Invalid arguments rejection (structured failure record with ToolInputValidationError)
4. Tool execution runtime failure isolation (no backend crash)
5. Execution timing measurement (duration_ms > 0)
6. Execution/request ID propagation and auto-generation
7. Maximum execution limit enforcement (ExecutionLimitExceededError)
8. Per-tool timeout enforcement (ToolTimeoutError)
9. Recursive execution prevention (RecursiveExecutionError)
10. Multiple sequential executions and session tracking
11. Unregistered tool rejection
12. Session reset functionality
"""

import asyncio
import sys
import unittest
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parent.parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.models.tool import (
    ToolResult,
    ToolExecutionRequest,
    ToolExecutionRecord,
)
from app.tools.base import BaseTool
from app.tools.registry import ToolRegistry
from app.tools.calculator import CalculatorTool
from app.tools.executor import (
    ToolExecutionPolicy,
    ToolExecutionService,
)


# ─────────────────────────────────────────────────────────────────────────────
# Test Mock Tools
# ─────────────────────────────────────────────────────────────────────────────

class SlowMockTool(BaseTool):
    """Tool that sleeps to trigger timeout testing."""
    name = "slow_tool"
    description = "Sleeps for specified duration."
    parameters_schema = {
        "type": "object",
        "properties": {
            "duration": {"type": "number"},
        },
        "required": ["duration"],
    }

    async def execute(self, duration: float = 0.5, **kwargs: Any) -> ToolResult:
        await asyncio.sleep(duration)
        return ToolResult.ok(tool_name=self.name, data={"slept": duration})


class CrashingMockTool(BaseTool):
    """Tool that raises an unexpected runtime exception."""
    name = "crashing_tool"
    description = "Intentionally crashes with unhandled exception."
    parameters_schema = {"type": "object", "properties": {}}

    async def execute(self, **kwargs: Any) -> ToolResult:
        raise RuntimeError("Simulated unhandled internal service crash")


class RecursiveMockTool(BaseTool):
    """Tool that maliciously attempts to invoke another tool through the execution layer."""
    name = "recursive_tool"
    description = "Attempts to call the execution service recursively."
    parameters_schema = {"type": "object", "properties": {}}

    def __init__(self, execution_service: ToolExecutionService):
        self.execution_service = execution_service

    async def execute(self, **kwargs: Any) -> ToolResult:
        # Attempt recursive execution
        rec_record = await self.execution_service.execute_tool("calculator", {"expression": "1 + 1"})
        return ToolResult.ok(tool_name=self.name, data={"recursive_record": rec_record.model_dump()})


# ─────────────────────────────────────────────────────────────────────────────
# Test Suite
# ─────────────────────────────────────────────────────────────────────────────

class TestToolExecutionService(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.registry = ToolRegistry()
        self.calc_tool = CalculatorTool()
        self.slow_tool = SlowMockTool()
        self.crash_tool = CrashingMockTool()

        self.registry.register(self.calc_tool)
        self.registry.register(self.slow_tool)
        self.registry.register(self.crash_tool)

        self.policy = ToolExecutionPolicy(
            max_executions_per_session=5,
            default_timeout_seconds=2.0,
        )
        self.service = ToolExecutionService(
            registry=self.registry,
            policy=self.policy,
        )

    # 1. Successful Calculator Execution
    async def test_calculator_execution_success(self):
        record = await self.service.execute_tool(
            tool_name="calculator",
            arguments={"expression": "25 * 4"},
        )
        self.assertIsInstance(record, ToolExecutionRecord)
        self.assertTrue(record.success)
        self.assertEqual(record.tool_name, "calculator")
        self.assertEqual(record.data["result"], 100)
        self.assertIsNone(record.error)
        self.assertIsNotNone(record.result)
        self.assertTrue(record.result.success)
        self.assertGreaterEqual(record.duration_ms, 0.0)
        self.assertTrue(record.execution_id.startswith("exec_"))

    # 2. Unknown Tool Rejection
    async def test_unknown_tool_rejection(self):
        record = await self.service.execute_tool(
            tool_name="non_existent_tool",
            arguments={"param": "value"},
        )
        self.assertIsInstance(record, ToolExecutionRecord)
        self.assertFalse(record.success)
        self.assertEqual(record.tool_name, "non_existent_tool")
        self.assertEqual(record.error_type, "ToolNotFoundError")
        self.assertIn("not registered", record.error)
        self.assertEqual(self.service.execution_count, 1)

    # 3. Invalid Arguments Rejection
    async def test_invalid_arguments_missing_required(self):
        # Calculator requires 'expression'
        record = await self.service.execute_tool(
            tool_name="calculator",
            arguments={},
        )
        self.assertFalse(record.success)
        self.assertEqual(record.error_type, "ToolInputValidationError")
        self.assertIn("expression", record.error)
        self.assertEqual(self.service.execution_count, 1)

    async def test_invalid_arguments_type_error(self):
        record = await self.service.execute_tool(
            tool_name="calculator",
            arguments={"expression": 12345},  # Int instead of string
        )
        self.assertFalse(record.success)
        self.assertEqual(record.error_type, "ToolInputValidationError")

    # 4. Tool Execution Failure Isolation (No Crash)
    async def test_tool_crash_isolation(self):
        record = await self.service.execute_tool(
            tool_name="crashing_tool",
            arguments={},
        )
        self.assertIsInstance(record, ToolExecutionRecord)
        self.assertFalse(record.success)
        self.assertEqual(record.error_type, "RuntimeError")
        self.assertIn("Simulated unhandled internal service crash", record.error)
        self.assertIsNotNone(record.result)
        self.assertFalse(record.result.success)

    # 5. Execution Timing Measurement
    async def test_execution_timing(self):
        record = await self.service.execute_tool(
            tool_name="calculator",
            arguments={"expression": "sqrt(144) + sin(pi / 2)"},
        )
        self.assertTrue(record.success)
        self.assertGreater(record.duration_ms, 0.0)
        self.assertEqual(record.data["result"], 13.0)

    # 6. Execution ID Propagation
    async def test_custom_execution_id(self):
        custom_id = "agent_turn_42_calc_1"
        request = ToolExecutionRequest(
            tool_name="calculator",
            arguments={"expression": "2 ** 8"},
            execution_id=custom_id,
        )
        record = await self.service.execute(request)
        self.assertEqual(record.execution_id, custom_id)
        self.assertEqual(record.data["result"], 256)

    # 7. Maximum Execution Limit Enforcement
    async def test_max_execution_limit_exceeded(self):
        # Policy limit is 5 executions
        for i in range(5):
            rec = await self.service.execute_tool("calculator", {"expression": f"{i} + 1"})
            self.assertTrue(rec.success)

        self.assertEqual(self.service.execution_count, 5)

        # 6th execution should be blocked by policy
        blocked_rec = await self.service.execute_tool("calculator", {"expression": "99 + 1"})
        self.assertFalse(blocked_rec.success)
        self.assertEqual(blocked_rec.error_type, "ExecutionLimitExceededError")
        self.assertIn("maximum limit of 5", blocked_rec.error)
        # Count should remain at 5 because it was rejected before entering
        self.assertEqual(self.service.execution_count, 5)

    # 8. Per-Tool Timeout Enforcement
    async def test_per_tool_timeout(self):
        # slow_tool sleeps for 0.5s; call with timeout of 0.05s
        record = await self.service.execute_tool(
            tool_name="slow_tool",
            arguments={"duration": 0.5},
            timeout_seconds=0.05,
        )
        self.assertFalse(record.success)
        self.assertEqual(record.error_type, "ToolTimeoutError")
        self.assertIn("timed out after 0.05s", record.error)

    # 9. Anti-Recursion Prevention
    async def test_prevent_recursive_execution(self):
        rec_tool = RecursiveMockTool(execution_service=self.service)
        self.registry.register(rec_tool)

        record = await self.service.execute_tool("recursive_tool", {})
        self.assertTrue(record.success)
        nested_rec_data = record.data["recursive_record"]
        self.assertFalse(nested_rec_data["success"])
        self.assertEqual(nested_rec_data["error_type"], "RecursiveExecutionError")
        self.assertIn("Recursive execution policy violation", nested_rec_data["error"])

    # 10. Multiple Sequential Executions & History Tracking
    async def test_multiple_sequential_executions(self):
        self.assertEqual(len(self.service.execution_history), 0)

        expressions = ["1 + 1", "2 * 3", "sqrt(16)"]
        expected_answers = [2, 6, 4.0]

        for expr, expected in zip(expressions, expected_answers):
            rec = await self.service.execute_tool("calculator", {"expression": expr})
            self.assertTrue(rec.success)
            self.assertEqual(rec.data["result"], expected)

        self.assertEqual(self.service.execution_count, 3)
        history = self.service.execution_history
        self.assertEqual(len(history), 3)
        self.assertEqual([r.data["result"] for r in history], [2, 6, 4.0])

    # 11. Confirmation That Arbitrary Tools Cannot Be Executed
    async def test_arbitrary_unregistered_tool_blocked(self):
        arbitrary_names = ["os_exec", "eval", "python", "bash", "system"]
        for name in arbitrary_names:
            rec = await self.service.execute_tool(name, {"cmd": "dir"})
            self.assertFalse(rec.success)
            self.assertEqual(rec.error_type, "ToolNotFoundError")

    # 12. Session Reset
    async def test_reset_session(self):
        await self.service.execute_tool("calculator", {"expression": "10 * 10"})
        self.assertEqual(self.service.execution_count, 1)
        self.assertEqual(len(self.service.execution_history), 1)

        self.service.reset_session()
        self.assertEqual(self.service.execution_count, 0)
        self.assertEqual(len(self.service.execution_history), 0)


def run_tests():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestToolExecutionService)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
