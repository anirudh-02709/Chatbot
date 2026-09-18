"""
Unit test suite for Goal 10.2: Calculator Tool.

Tests:
1. Basic arithmetic operations (+, -, *, /, //, %)
2. Operator precedence and nested parentheses
3. Exponentiation (**) and exponent safety limits
4. Mathematical constants (pi, e, tau)
5. Supported math functions (sqrt, abs, round, sin, cos, tan, log, log10, exp, floor, ceil)
6. Division and modulo by zero handling
7. Math domain errors (sqrt of negative, log of zero/negative)
8. Malformed expressions syntax handling
9. Security & injection defenses:
   - __import__
   - Attribute access (obj.attr, .__class__)
   - Subscripting (obj[0])
   - String literals and concatenation
   - Undeclared variables
   - Comprehensions and lambdas
10. Resource limits:
   - Maximum expression length (>500 chars)
   - Maximum AST node limit (>100 nodes)
11. Structured ToolResult (success and failure payloads)
12. Global ToolRegistry integration and LLM schema definitions
"""

import math
import sys
import unittest
from pathlib import Path

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parent.parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.models.tool import ToolResult
from app.tools import (
    tool_registry,
    CalculatorTool,
    calculator_tool,
    evaluate_math_expression,
)


class TestCalculatorTool(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.tool = CalculatorTool()

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Basic Arithmetic
    # ─────────────────────────────────────────────────────────────────────────
    def test_basic_addition(self):
        self.assertEqual(evaluate_math_expression("25 + 75"), 100)

    def test_basic_subtraction(self):
        self.assertEqual(evaluate_math_expression("100 - 45"), 55)

    def test_basic_multiplication(self):
        self.assertEqual(evaluate_math_expression("25 * 4"), 100)

    def test_basic_division(self):
        self.assertEqual(evaluate_math_expression("20 / 4"), 5.0)

    def test_floor_division(self):
        self.assertEqual(evaluate_math_expression("7 // 2"), 3)

    def test_modulo(self):
        self.assertEqual(evaluate_math_expression("10 % 3"), 1)

    def test_unary_operators(self):
        self.assertEqual(evaluate_math_expression("-42"), -42)
        self.assertEqual(evaluate_math_expression("+15"), 15)
        self.assertEqual(evaluate_math_expression("-(-10)"), 10)

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Operator Precedence & Parentheses
    # ─────────────────────────────────────────────────────────────────────────
    def test_operator_precedence(self):
        self.assertEqual(evaluate_math_expression("2 + 3 * 4"), 14)
        self.assertEqual(evaluate_math_expression("(2 + 3) * 4"), 20)

    def test_nested_parentheses(self):
        self.assertEqual(evaluate_math_expression("((100 + 50) / 3) * 2"), 100.0)

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Exponentiation & Safety Bounds
    # ─────────────────────────────────────────────────────────────────────────
    def test_exponentiation(self):
        self.assertEqual(evaluate_math_expression("2 ** 10"), 1024)
        self.assertEqual(evaluate_math_expression("4 ** 0.5"), 2.0)
        self.assertEqual(evaluate_math_expression("5 ** 0"), 1)

    def test_exponent_limit_protection(self):
        # Exponent above 1000 must be rejected
        with self.assertRaises(ValueError) as ctx:
            evaluate_math_expression("2 ** 1001")
        self.assertIn("exceeds safe limit", str(ctx.exception))

    def test_large_base_power_overflow_guard(self):
        with self.assertRaises(OverflowError):
            evaluate_math_expression("10000000 ** 60")

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Mathematical Constants
    # ─────────────────────────────────────────────────────────────────────────
    def test_constants(self):
        self.assertAlmostEqual(evaluate_math_expression("pi"), math.pi)
        self.assertAlmostEqual(evaluate_math_expression("e"), math.e)
        self.assertAlmostEqual(evaluate_math_expression("tau"), math.tau)
        self.assertAlmostEqual(evaluate_math_expression("2 * pi"), 2 * math.pi)

    # ─────────────────────────────────────────────────────────────────────────
    # 5. Mathematical Functions
    # ─────────────────────────────────────────────────────────────────────────
    def test_sqrt(self):
        self.assertEqual(evaluate_math_expression("sqrt(144)"), 12.0)
        self.assertEqual(evaluate_math_expression("sqrt(0)"), 0.0)

    def test_abs(self):
        self.assertEqual(evaluate_math_expression("abs(-42)"), 42)
        self.assertEqual(evaluate_math_expression("abs(42)"), 42)

    def test_round(self):
        self.assertEqual(evaluate_math_expression("round(3.14159, 2)"), 3.14)
        self.assertEqual(evaluate_math_expression("round(3.7)"), 4)

    def test_trigonometric_functions(self):
        self.assertAlmostEqual(evaluate_math_expression("sin(pi / 2)"), 1.0)
        self.assertAlmostEqual(evaluate_math_expression("cos(0)"), 1.0)
        self.assertAlmostEqual(evaluate_math_expression("tan(0)"), 0.0)

    def test_logarithmic_functions(self):
        self.assertAlmostEqual(evaluate_math_expression("log(e)"), 1.0)
        self.assertAlmostEqual(evaluate_math_expression("log10(100)"), 2.0)
        self.assertAlmostEqual(evaluate_math_expression("log(8, 2)"), 3.0)

    def test_exp_floor_ceil(self):
        self.assertAlmostEqual(evaluate_math_expression("exp(0)"), 1.0)
        self.assertEqual(evaluate_math_expression("floor(3.9)"), 3)
        self.assertEqual(evaluate_math_expression("ceil(3.1)"), 4)

    # ─────────────────────────────────────────────────────────────────────────
    # 6. Division and Modulo by Zero
    # ─────────────────────────────────────────────────────────────────────────
    def test_division_by_zero(self):
        with self.assertRaises(ZeroDivisionError):
            evaluate_math_expression("10 / 0")

    def test_floor_division_by_zero(self):
        with self.assertRaises(ZeroDivisionError):
            evaluate_math_expression("10 // 0")

    def test_modulo_by_zero(self):
        with self.assertRaises(ZeroDivisionError):
            evaluate_math_expression("10 % 0")

    # ─────────────────────────────────────────────────────────────────────────
    # 7. Math Domain Errors
    # ─────────────────────────────────────────────────────────────────────────
    def test_math_domain_errors(self):
        with self.assertRaises(ValueError):
            evaluate_math_expression("sqrt(-1)")

        with self.assertRaises(ValueError):
            evaluate_math_expression("log(0)")

        with self.assertRaises(ValueError):
            evaluate_math_expression("log(-5)")

    # ─────────────────────────────────────────────────────────────────────────
    # 8. Malformed Expressions
    # ─────────────────────────────────────────────────────────────────────────
    def test_malformed_expressions(self):
        with self.assertRaises(ValueError):
            evaluate_math_expression("2 + * 3")

        with self.assertRaises(ValueError):
            evaluate_math_expression("((5 + 2)")

        with self.assertRaises(ValueError):
            evaluate_math_expression("")

        with self.assertRaises(ValueError):
            evaluate_math_expression("   ")

    # ─────────────────────────────────────────────────────────────────────────
    # 9. Security & Injection Defenses
    # ─────────────────────────────────────────────────────────────────────────
    def test_reject_import(self):
        with self.assertRaises(ValueError):
            evaluate_math_expression("__import__('os').system('dir')")

    def test_reject_attribute_access(self):
        with self.assertRaises(ValueError) as ctx:
            evaluate_math_expression("().__class__.__bases__[0].__subclasses__()")
        self.assertIn("not permitted", str(ctx.exception))

    def test_reject_module_attribute_call(self):
        with self.assertRaises(ValueError):
            evaluate_math_expression("math.sqrt(16)")

    def test_reject_arbitrary_strings(self):
        with self.assertRaises(ValueError) as ctx:
            evaluate_math_expression("'hello' + 'world'")
        self.assertIn("Only numeric literals are allowed", str(ctx.exception))

    def test_reject_unsupported_variables(self):
        with self.assertRaises(ValueError) as ctx:
            evaluate_math_expression("x + 1")
        self.assertIn("Unsupported variable or constant: 'x'", str(ctx.exception))

    def test_reject_unsupported_functions(self):
        with self.assertRaises(ValueError) as ctx:
            evaluate_math_expression("eval('2 + 2')")
        self.assertIn("Unsupported function: 'eval'", str(ctx.exception))

    def test_reject_list_comprehensions(self):
        with self.assertRaises(ValueError):
            evaluate_math_expression("[x for x in range(10)]")

    # ─────────────────────────────────────────────────────────────────────────
    # 10. Resource Limits
    # ─────────────────────────────────────────────────────────────────────────
    def test_max_expression_length(self):
        oversized = "1 + " * 200 + "1"  # > 600 characters
        with self.assertRaises(ValueError) as ctx:
            evaluate_math_expression(oversized)
        self.assertIn("exceeds maximum length", str(ctx.exception))

    def test_max_ast_nodes(self):
        # 45 additions = ~91 nodes; 60 additions = ~121 nodes
        sprawling = " + ".join(["1"] * 60)
        with self.assertRaises(ValueError) as ctx:
            evaluate_math_expression(sprawling)
        self.assertIn("too complex", str(ctx.exception))

    # ─────────────────────────────────────────────────────────────────────────
    # 11. Structured ToolResult (Asynchronous Execution)
    # ─────────────────────────────────────────────────────────────────────────
    async def test_execute_success_result(self):
        result = await self.tool.execute(expression="(100 + 50) / 3")
        self.assertIsInstance(result, ToolResult)
        self.assertTrue(result.success)
        self.assertEqual(result.tool_name, "calculator")
        self.assertEqual(result.data["result"], 50.0)
        self.assertEqual(result.data["result_type"], "float")
        self.assertEqual(result.metadata["expression"], "(100 + 50) / 3")
        self.assertIsNone(result.error)

    async def test_execute_failure_result_division_by_zero(self):
        result = await self.tool.execute(expression="5 / 0")
        self.assertIsInstance(result, ToolResult)
        self.assertFalse(result.success)
        self.assertEqual(result.tool_name, "calculator")
        self.assertIsNone(result.data)
        self.assertEqual(result.error_type, "ZeroDivisionError")
        self.assertIn("Division by zero", result.error)

    async def test_execute_failure_result_syntax_error(self):
        result = await self.tool.execute(expression="5 + * 2")
        self.assertIsInstance(result, ToolResult)
        self.assertFalse(result.success)
        self.assertIn("Malformed mathematical expression", result.error)

    # ─────────────────────────────────────────────────────────────────────────
    # 12. Registry Integration
    # ─────────────────────────────────────────────────────────────────────────
    def test_calculator_registered_in_global_registry(self):
        self.assertTrue(tool_registry.has("calculator"))
        tool = tool_registry.get("calculator")
        self.assertIsInstance(tool, CalculatorTool)

    def test_calculator_schema_in_definitions(self):
        definitions = tool_registry.get_definitions()
        calc_def = next((d for d in definitions if d["function"]["name"] == "calculator"), None)
        self.assertIsNotNone(calc_def)
        self.assertEqual(calc_def["type"], "function")
        self.assertIn("expression", calc_def["function"]["parameters"]["properties"])
        self.assertIn("expression", calc_def["function"]["parameters"]["required"])

    async def test_execute_via_registry(self):
        result = await tool_registry.execute("calculator", {"expression": "sqrt(144) + 8"})
        self.assertTrue(result.success)
        self.assertEqual(result.data["result"], 20.0)
        self.assertIsNotNone(result.execution_time_ms)
        self.assertGreater(result.execution_time_ms, 0.0)


def run_tests():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCalculatorTool)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
