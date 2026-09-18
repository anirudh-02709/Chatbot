from app.models.tool import (
    ToolResult,
    ToolDefinition,
    ToolExecutionRequest,
    ToolExecutionRecord,
)
from app.tools.base import (
    BaseTool,
    ToolError,
    DuplicateToolError,
    ToolNotFoundError,
    ToolInputValidationError,
    ToolExecutionError,
    ToolExecutionPolicyError,
    ExecutionLimitExceededError,
    RecursiveExecutionError,
    ToolTimeoutError,
)
from app.tools.registry import ToolRegistry, tool_registry
from app.tools.calculator import (
    CalculatorTool,
    calculator_tool,
    CalculatorInput,
    evaluate_math_expression,
)
from app.tools.document_search import (
    DocumentSearchTool,
    document_search_tool,
    DocumentSearchInput,
)
from app.tools.executor import (
    ToolExecutionPolicy,
    ToolExecutionService,
    tool_execution_service,
)

# Automatically register built-in tools with the global registry
tool_registry.register(calculator_tool)
tool_registry.register(document_search_tool)

__all__ = [
    "BaseTool",
    "ToolResult",
    "ToolDefinition",
    "ToolExecutionRequest",
    "ToolExecutionRecord",
    "ToolRegistry",
    "tool_registry",
    "CalculatorTool",
    "calculator_tool",
    "CalculatorInput",
    "evaluate_math_expression",
    "DocumentSearchTool",
    "document_search_tool",
    "DocumentSearchInput",
    "ToolExecutionPolicy",
    "ToolExecutionService",
    "tool_execution_service",
    "ToolError",
    "DuplicateToolError",
    "ToolNotFoundError",
    "ToolInputValidationError",
    "ToolExecutionError",
    "ToolExecutionPolicyError",
    "ExecutionLimitExceededError",
    "RecursiveExecutionError",
    "ToolTimeoutError",
]



