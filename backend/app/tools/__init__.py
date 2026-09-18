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
from app.tools.web_search_providers import (
    BaseWebSearchProvider,
    WebSearchResultItem,
    TavilySearchProvider,
    BraveSearchProvider,
    WebSearchProviderError,
    WebSearchNotConfiguredError,
    WebSearchTimeoutError,
    WebSearchHttpError,
    WebSearchNetworkError,
    WebSearchMalformedResponseError,
    create_search_provider,
)
from app.tools.web_search import (
    WebSearchTool,
    web_search_tool,
    WebSearchInput,
)
from app.tools.data_analysis import (
    DataAnalysisTool,
    data_analysis_tool,
    DataAnalysisInput,
    DataAnalysisError,
    EmptyDatasetError,
    MalformedDataError,
    ColumnNotFoundError,
    InvalidConditionError,
    ResourceLimitExceededError,
)
from app.tools.executor import (
    ToolExecutionPolicy,
    ToolExecutionService,
    tool_execution_service,
)

# Automatically register built-in tools with the global registry
tool_registry.register(calculator_tool)
tool_registry.register(document_search_tool)
tool_registry.register(web_search_tool)
tool_registry.register(data_analysis_tool)

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
    "WebSearchTool",
    "web_search_tool",
    "WebSearchInput",
    "DataAnalysisTool",
    "data_analysis_tool",
    "DataAnalysisInput",
    "DataAnalysisError",
    "EmptyDatasetError",
    "MalformedDataError",
    "ColumnNotFoundError",
    "InvalidConditionError",
    "ResourceLimitExceededError",
    "BaseWebSearchProvider",
    "WebSearchResultItem",
    "TavilySearchProvider",
    "BraveSearchProvider",
    "create_search_provider",
    "WebSearchProviderError",
    "WebSearchNotConfiguredError",
    "WebSearchTimeoutError",
    "WebSearchHttpError",
    "WebSearchNetworkError",
    "WebSearchMalformedResponseError",
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



