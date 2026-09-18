from typing import Any, Optional
from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    """Structured result format for tool execution."""

    success: bool
    tool_name: str
    data: Any = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    execution_time_ms: Optional[float] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def ok(
        cls,
        tool_name: str,
        data: Any = None,
        execution_time_ms: Optional[float] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> "ToolResult":
        """Create a successful ToolResult."""
        return cls(
            success=True,
            tool_name=tool_name,
            data=data,
            error=None,
            error_type=None,
            execution_time_ms=execution_time_ms,
            metadata=metadata or {},
        )

    @classmethod
    def fail(
        cls,
        tool_name: str,
        error: str,
        error_type: Optional[str] = None,
        execution_time_ms: Optional[float] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> "ToolResult":
        """Create a failed ToolResult."""
        return cls(
            success=False,
            tool_name=tool_name,
            data=None,
            error=error,
            error_type=error_type,
            execution_time_ms=execution_time_ms,
            metadata=metadata or {},
        )


class ToolDefinition(BaseModel):
    """Schema representation of a tool capability."""

    name: str
    description: str
    parameters: dict[str, Any] = Field(
        default_factory=lambda: {"type": "object", "properties": {}}
    )


class ToolExecutionRequest(BaseModel):
    """Request model for dispatching a tool execution."""

    tool_name: str = Field(..., min_length=1, description="Name of the registered tool to execute.")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Arguments passed to the tool.")
    execution_id: Optional[str] = Field(
        default=None,
        description="Optional unique identifier for tracing this execution request.",
    )


class ToolExecutionRecord(BaseModel):
    """Execution record capturing the full context, parameters, and outcome of a tool execution."""

    execution_id: str
    tool_name: str
    arguments: dict[str, Any]
    success: bool
    result: Optional[ToolResult] = None
    data: Any = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    duration_ms: float
    timestamp: str

