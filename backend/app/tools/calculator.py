import ast
import math
from typing import Any, Union
from pydantic import BaseModel, Field

from app.models.tool import ToolResult
from app.tools.base import BaseTool

MAX_EXPRESSION_LENGTH = 500
MAX_AST_NODES = 100
MAX_EXPONENT = 1000

# Whitelisted mathematical constants
SAFE_CONSTANTS: dict[str, float] = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
}

# Whitelisted deterministic mathematical functions
SAFE_FUNCTIONS: dict[str, Any] = {
    "sqrt": math.sqrt,
    "abs": abs,
    "round": round,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "floor": math.floor,
    "ceil": math.ceil,
}


def evaluate_math_expression(expression: str) -> Union[int, float]:
    """
    Safely evaluates a mathematical expression using an AST whitelist.

    Strict security guarantees:
    - No unrestricted eval/exec.
    - No attribute access (e.g. `obj.__class__` or `math.sqrt`).
    - No imports or access to built-in namespaces.
    - Strict node limits to prevent ReDoS / CPU exhaustion.
    - Exponent bounds checking to prevent memory denial of service.

    Raises:
        ValueError: If expression is invalid, unsupported, or violates security constraints.
        ZeroDivisionError: If division or modulo by zero is attempted.
        OverflowError: If calculation exceeds numeric range.
    """
    clean_expr = expression.strip() if expression else ""
    if not clean_expr:
        raise ValueError("Mathematical expression cannot be empty.")

    if len(clean_expr) > MAX_EXPRESSION_LENGTH:
        raise ValueError(
            f"Expression exceeds maximum length of {MAX_EXPRESSION_LENGTH} characters "
            f"(got {len(clean_expr)})."
        )

    try:
        tree = ast.parse(clean_expr, mode="eval")
    except SyntaxError as se:
        raise ValueError(f"Malformed mathematical expression: {se.msg}") from se

    # Enforce AST node count ceiling to prevent deeply nested resource exhaustion
    node_count = sum(1 for _ in ast.walk(tree))
    if node_count > MAX_AST_NODES:
        raise ValueError(
            f"Expression is too complex ({node_count} AST nodes; maximum allowed is {MAX_AST_NODES})."
        )

    def _eval_node(node: ast.AST) -> Union[int, float]:
        if isinstance(node, ast.Expression):
            return _eval_node(node.body)

        # Numbers
        elif isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise ValueError(
                    f"Unsupported literal '{node.value}' of type {type(node.value).__name__}. "
                    "Only numeric literals are allowed."
                )
            return node.value

        # Named constants (pi, e, tau)
        elif isinstance(node, ast.Name):
            if node.id in SAFE_CONSTANTS:
                return SAFE_CONSTANTS[node.id]
            raise ValueError(
                f"Unsupported variable or constant: '{node.id}'. "
                f"Supported constants: {', '.join(sorted(SAFE_CONSTANTS.keys()))}"
            )

        # Unary operators (+, -)
        elif isinstance(node, ast.UnaryOp):
            operand = _eval_node(node.operand)
            if isinstance(node.op, ast.UAdd):
                return +operand
            elif isinstance(node.op, ast.USub):
                return -operand
            else:
                raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")

        # Binary operators (+, -, *, /, //, %, **)
        elif isinstance(node, ast.BinOp):
            left = _eval_node(node.left)
            right = _eval_node(node.right)

            if isinstance(node.op, ast.Add):
                return left + right
            elif isinstance(node.op, ast.Sub):
                return left - right
            elif isinstance(node.op, ast.Mult):
                return left * right
            elif isinstance(node.op, ast.Div):
                if right == 0:
                    raise ZeroDivisionError("Division by zero.")
                return left / right
            elif isinstance(node.op, ast.FloorDiv):
                if right == 0:
                    raise ZeroDivisionError("Floor division by zero.")
                return left // right
            elif isinstance(node.op, ast.Mod):
                if right == 0:
                    raise ZeroDivisionError("Modulo by zero.")
                return left % right
            elif isinstance(node.op, ast.Pow):
                # Guard against huge power calculations that freeze CPU / allocate GBs of RAM
                if abs(right) > MAX_EXPONENT:
                    raise ValueError(
                        f"Exponent {right} exceeds safe limit of {MAX_EXPONENT}."
                    )
                if abs(left) > 1e6 and right > 50:
                    raise OverflowError("Result exceeds calculation capacity.")
                result = left ** right
                if isinstance(result, complex):
                    raise ValueError("Complex numbers are not supported.")
                return result
            else:
                raise ValueError(f"Unsupported binary operator: {type(node.op).__name__}")

        # Function calls (e.g. sqrt(144), sin(pi / 2))
        elif isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError(
                    "Unsupported function call syntax. Attribute access or nested calls are not permitted."
                )

            func_name = node.func.id
            if func_name not in SAFE_FUNCTIONS:
                raise ValueError(
                    f"Unsupported function: '{func_name}'. "
                    f"Supported functions: {', '.join(sorted(SAFE_FUNCTIONS.keys()))}"
                )

            if node.keywords:
                raise ValueError(f"Keyword arguments are not permitted in '{func_name}()'.")

            args = [_eval_node(arg) for arg in node.args]
            func = SAFE_FUNCTIONS[func_name]

            try:
                result = func(*args)
            except (ValueError, TypeError, OverflowError, ZeroDivisionError) as e:
                raise ValueError(f"Math error in '{func_name}()': {e}") from e

            if isinstance(result, complex):
                raise ValueError("Complex numbers are not supported.")

            return result

        else:
            raise ValueError(
                f"Unsupported syntax: {type(node).__name__} is not permitted."
            )

    return _eval_node(tree)


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Input Model & Tool Abstraction
# ─────────────────────────────────────────────────────────────────────────────

class CalculatorInput(BaseModel):
    """Input argument model for the Calculator tool."""

    expression: str = Field(
        ...,
        min_length=1,
        max_length=MAX_EXPRESSION_LENGTH,
        description="The mathematical expression to evaluate (e.g. '25 * 4', 'sqrt(144)', 'sin(pi / 2)').",
    )


class CalculatorTool(BaseTool):
    """
    Deterministic mathematical evaluation tool.

    Safely evaluates arithmetic expressions, standard constants (pi, e, tau),
    and common mathematical functions (sqrt, abs, round, sin, cos, tan, log,
    log10, exp, floor, ceil) using an AST whitelist with strict resource limits.
    """

    name = "calculator"
    description = (
        "Safely evaluates mathematical expressions supporting arithmetic operators "
        "(+, -, *, /, //, %, **), constants (pi, e, tau), and standard math functions "
        "(sqrt, abs, round, sin, cos, tan, log, log10, exp, floor, ceil)."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": (
                    "The mathematical expression to evaluate (e.g. '25 * 4', 'sqrt(144)', 'sin(pi / 2)')."
                ),
            }
        },
        "required": ["expression"],
    }
    args_model = CalculatorInput

    async def execute(self, expression: str, **kwargs: Any) -> ToolResult:
        """
        Asynchronously evaluates the mathematical expression.
        Returns a structured ToolResult with the calculation output and metadata.
        """
        try:
            val = evaluate_math_expression(expression)
            return ToolResult.ok(
                tool_name=self.name,
                data={
                    "expression": expression,
                    "result": val,
                    "result_type": type(val).__name__,
                },
                metadata={
                    "expression": expression,
                    "result_type": type(val).__name__,
                },
            )
        except Exception as e:
            return ToolResult.fail(
                tool_name=self.name,
                error=str(e),
                error_type=type(e).__name__,
                metadata={"expression": expression},
            )


# Global singleton instance
calculator_tool = CalculatorTool()
