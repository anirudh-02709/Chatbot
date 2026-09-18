"""
Agent data models for Goal 10.7: Agent Orchestration Foundation.

Defines:
- AgentDecisionType: Enum representing decision actions (FINAL_ANSWER vs TOOL_CALL)
- AgentStatus: Enum representing agent lifecycle states
- AgentDecision: Structured model of an LLM's decision
- AgentState: Explicit in-memory state tracking the orchestration flow
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.tool import ToolResult, ToolExecutionRecord


class AgentDecisionType(str, Enum):
    """Types of decisions an Agent can make in response to a user request."""
    FINAL_ANSWER = "final_answer"
    TOOL_CALL = "tool_call"


class AgentStatus(str, Enum):
    """Lifecycle states of an agent execution request."""
    INITIALIZED = "initialized"
    DECIDING = "deciding"
    STEP_COMPLETED = "step_completed"
    COMPLETED = "completed"
    MAX_ITERATIONS_REACHED = "max_iterations_reached"
    LOOP_DETECTED = "loop_detected"
    ERROR = "error"


class AgentDecision(BaseModel):
    """Structured decision produced by the LLM via the model-to-tool protocol."""

    type: AgentDecisionType = Field(
        ...,
        description="Type of decision: 'final_answer' to respond directly or 'tool_call' to request a tool.",
    )
    answer: Optional[str] = Field(
        default=None,
        description="The final answer text when type is 'final_answer'.",
    )
    tool_name: Optional[str] = Field(
        default=None,
        description="The name of the requested tool when type is 'tool_call'.",
    )
    tool_arguments: Optional[dict[str, Any]] = Field(
        default=None,
        description="The structured argument payload for the requested tool.",
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Concise operational rationale or category. Not hidden chain-of-thought.",
    )
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional confidence score (0.0 to 1.0) if explicitly reported.",
    )

    model_config = ConfigDict(
        use_enum_values=True,
        extra="ignore",
    )


class AgentState(BaseModel):
    """
    Explicit, serializable state representation for an agent execution session.
    Tracks user request, model decisions, tool calls, tool results, and status.
    """

    request_id: str = Field(
        ...,
        description="Unique identifier for tracing this agent request lifecycle.",
    )
    user_request: str = Field(
        ...,
        description="The original user query or task prompt.",
    )
    current_decision: Optional[AgentDecision] = Field(
        default=None,
        description="The latest decision produced by the model.",
    )
    tool_calls: list[dict[str, Any]] = Field(
        default_factory=list,
        description="History of tool call requests generated during orchestration.",
    )
    tool_results: list[ToolResult] = Field(
        default_factory=list,
        description="History of structured ToolResult objects received.",
    )
    execution_records: list[ToolExecutionRecord] = Field(
        default_factory=list,
        description="Full audit records of tool executions from ToolExecutionService.",
    )
    iteration_count: int = Field(
        default=0,
        ge=0,
        description="Number of orchestration steps executed.",
    )
    final_answer: Optional[str] = Field(
        default=None,
        description="The completed final response text once resolved.",
    )
    status: AgentStatus = Field(
        default=AgentStatus.INITIALIZED,
        description="Current operational status of the agent session.",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error description if status is 'error'.",
    )
    decisions: list[AgentDecision] = Field(
        default_factory=list,
        description="Chronological history of all decisions made by the agent.",
    )
    observations: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Chronological history of tool observations returned to the agent.",
    )
    max_iterations: int = Field(
        default=5,
        ge=1,
        description="Maximum orchestration loop iterations allowed.",
    )
    termination_reason: Optional[str] = Field(
        default=None,
        description="Detailed termination category: completed, max_iterations_reached, loop_detected, error.",
    )
    total_duration_ms: Optional[float] = Field(
        default=None,
        description="Total wall-clock duration of the agent loop in milliseconds.",
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="UTC timestamp when the session was created.",
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="UTC timestamp when the session was last modified.",
    )

    model_config = ConfigDict(
        use_enum_values=True,
    )

    def mark_updated(self) -> None:
        """Updates the updated_at timestamp."""
        self.updated_at = datetime.now(timezone.utc).isoformat()
