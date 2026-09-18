"""
Unit test suite for Goal 10.1: Tool Architecture Foundation.

Tests:
1. Tool registration and duplicate prevention
2. Tool lookup (get, get_or_raise, has)
3. Listing tools and definitions
4. Asynchronous execution returning structured ToolResult
5. Unknown tool handling (structured result & exception)
6. Input validation (schema and Pydantic args_model)
7. Execution error handling (exceptions caught and structured)
8. Unregistration and registry clearing
"""

import sys
import unittest
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parent.parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.models.tool import ToolResult, ToolDefinition
from app.tools.base import (
    BaseTool,
    DuplicateToolError,
    ToolNotFoundError,
    ToolInputValidationError,
    ToolExecutionError,
)
from app.tools.registry import ToolRegistry


# ─────────────────────────────────────────────────────────────────────────────
# Test Fixtures & Mock Tools
# ─────────────────────────────────────────────────────────────────────────────

class MockEchoArgs(BaseModel):
    message: str = Field(..., description="Message to echo")
    repeat: int = Field(default=1, ge=1, le=10, description="Repetition count")


class MockEchoTool(BaseTool):
    name = "mock_echo"
    description = "Repeats an input message a specified number of times."
    parameters_schema = {
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "Message to echo"},
            "repeat": {"type": "integer", "description": "Repetition count"},
        },
        "required": ["message"],
    }
    args_model = MockEchoArgs

    async def execute(self, **kwargs: Any) -> ToolResult:
        message = kwargs.get("message", "")
        repeat = kwargs.get("repeat", 1)
        output = " ".join([message] * repeat)
        return ToolResult.ok(
            tool_name=self.name,
            data={"echo": output, "count": repeat},
            metadata={"source": "test"},
        )


class MockFailingTool(BaseTool):
    name = "mock_failing"
    description = "A mock tool that deliberately raises a runtime error."
    parameters_schema = {
        "type": "object",
        "properties": {
            "should_fail": {"type": "boolean"},
        },
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        raise RuntimeError("Simulated internal tool crash")


class MockSchemaOnlyTool(BaseTool):
    name = "mock_schema_only"
    description = "A tool using schema validation without Pydantic args_model."
    parameters_schema = {
        "type": "object",
        "properties": {
            "city": {"type": "string"},
            "days": {"type": "integer"},
        },
        "required": ["city"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult.ok(
            tool_name=self.name,
            data={"city": kwargs.get("city"), "days": kwargs.get("days", 1)},
        )


# ─────────────────────────────────────────────────────────────────────────────
# Test Suite
# ─────────────────────────────────────────────────────────────────────────────

class TestToolArchitecture(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.registry = ToolRegistry()
        self.echo_tool = MockEchoTool()
        self.failing_tool = MockFailingTool()
        self.schema_tool = MockSchemaOnlyTool()

    # 1. Registration
    def test_tool_registration(self):
        self.assertEqual(len(self.registry.list_tools()), 0)
        self.registry.register(self.echo_tool)
        self.assertEqual(len(self.registry.list_tools()), 1)
        self.assertTrue(self.registry.has("mock_echo"))

    def test_duplicate_registration_raises_error(self):
        self.registry.register(self.echo_tool)
        with self.assertRaises(DuplicateToolError) as ctx:
            self.registry.register(self.echo_tool)
        self.assertIn("already registered", str(ctx.exception))

    def test_duplicate_registration_overwrite_allowed(self):
        self.registry.register(self.echo_tool)
        # Should not raise when overwrite=True
        self.registry.register(self.echo_tool, overwrite=True)
        self.assertEqual(len(self.registry.list_tools()), 1)

    def test_invalid_tool_registration(self):
        with self.assertRaises(TypeError):
            self.registry.register("not_a_tool")  # type: ignore

    # 2. Lookup
    def test_tool_lookup(self):
        self.registry.register(self.echo_tool)
        tool = self.registry.get("mock_echo")
        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "mock_echo")

        # Non-existent
        self.assertIsNone(self.registry.get("non_existent"))

    def test_get_or_raise(self):
        self.registry.register(self.echo_tool)
        self.assertEqual(self.registry.get_or_raise("mock_echo").name, "mock_echo")

        with self.assertRaises(ToolNotFoundError):
            self.registry.get_or_raise("unknown_tool")

    # 3. Listing and Definitions
    def test_listing_tools_and_definitions(self):
        self.registry.register(self.echo_tool)
        self.registry.register(self.failing_tool)

        names = self.registry.list_tool_names()
        self.assertEqual(sorted(names), ["mock_echo", "mock_failing"])

        definitions = self.registry.get_definitions()
        self.assertEqual(len(definitions), 2)
        echo_def = next(d for d in definitions if d["function"]["name"] == "mock_echo")
        self.assertEqual(echo_def["type"], "function")
        self.assertIn("message", echo_def["function"]["parameters"]["properties"])

    # 4. Successful Asynchronous Execution
    async def test_async_execution_success(self):
        self.registry.register(self.echo_tool)
        result = await self.registry.execute("mock_echo", {"message": "hello", "repeat": 3})

        self.assertIsInstance(result, ToolResult)
        self.assertTrue(result.success)
        self.assertEqual(result.tool_name, "mock_echo")
        self.assertEqual(result.data["echo"], "hello hello hello")
        self.assertIsNone(result.error)
        self.assertIsNotNone(result.execution_time_ms)
        self.assertGreaterEqual(result.execution_time_ms, 0.0)

    # 5. Unknown Tool Handling
    async def test_unknown_tool_returns_failure_result(self):
        result = await self.registry.execute("non_existent_tool", {"foo": "bar"})
        self.assertIsInstance(result, ToolResult)
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "ToolNotFoundError")
        self.assertIn("not registered", result.error)

    async def test_unknown_tool_raises_when_requested(self):
        with self.assertRaises(ToolNotFoundError):
            await self.registry.execute("non_existent_tool", raise_on_error=True)

    # 6. Input Validation
    async def test_input_validation_missing_required_pydantic(self):
        self.registry.register(self.echo_tool)
        result = await self.registry.execute("mock_echo", {})  # Missing required 'message'
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "ToolInputValidationError")
        self.assertIn("message", result.error)

    async def test_input_validation_invalid_type_pydantic(self):
        self.registry.register(self.echo_tool)
        result = await self.registry.execute("mock_echo", {"message": "hi", "repeat": "invalid_int"})
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "ToolInputValidationError")

    async def test_input_validation_schema_only_missing_required(self):
        self.registry.register(self.schema_tool)
        result = await self.registry.execute("mock_schema_only", {"days": 3})  # Missing 'city'
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "ToolInputValidationError")
        self.assertIn("city", result.error)

    async def test_input_validation_schema_only_invalid_type(self):
        self.registry.register(self.schema_tool)
        result = await self.registry.execute("mock_schema_only", {"city": "Paris", "days": True})  # boolean instead of int
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "ToolInputValidationError")

    async def test_input_validation_raises_when_requested(self):
        self.registry.register(self.echo_tool)
        with self.assertRaises(ToolInputValidationError):
            await self.registry.execute("mock_echo", {}, raise_on_error=True)

    # 7. Tool Execution Failure
    async def test_tool_execution_failure_handled_gracefully(self):
        self.registry.register(self.failing_tool)
        result = await self.registry.execute("mock_failing", {})
        self.assertIsInstance(result, ToolResult)
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "ToolExecutionError")
        self.assertIn("Simulated internal tool crash", result.error)
        self.assertIsNotNone(result.execution_time_ms)

    async def test_tool_execution_failure_raises_when_requested(self):
        self.registry.register(self.failing_tool)
        with self.assertRaises(ToolExecutionError):
            await self.registry.execute("mock_failing", {}, raise_on_error=True)

    # 8. Unregister and Clear
    def test_unregister_and_clear(self):
        self.registry.register(self.echo_tool)
        self.assertTrue(self.registry.has("mock_echo"))

        unregistered = self.registry.unregister("mock_echo")
        self.assertTrue(unregistered)
        self.assertFalse(self.registry.has("mock_echo"))

        self.assertFalse(self.registry.unregister("non_existent"))

        self.registry.register(self.echo_tool)
        self.registry.register(self.failing_tool)
        self.assertEqual(len(self.registry.list_tools()), 2)
        self.registry.clear()
        self.assertEqual(len(self.registry.list_tools()), 0)


def run_tests():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestToolArchitecture)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
