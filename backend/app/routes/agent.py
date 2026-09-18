import logging
from typing import Any, Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.agent.orchestrator import agent as global_agent, Agent
from app.agent.models import AgentStatus

logger = logging.getLogger("chatbot.routes.agent")

router = APIRouter(prefix="/api/agent", tags=["agent"])


def get_agent() -> Agent:
    return global_agent


class AgentRunRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User query or instruction for the autonomous agent.")
    mode: Optional[Literal["local_gemma", "omniroute"]] = Field(
        default=None,
        description="Optional generation backend mode ('local_gemma' or 'omniroute').",
    )
    max_iterations: Optional[int] = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum orchestration loop iterations allowed (1 to 20, default: 5).",
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="Optional conversation/thread identifier.",
    )
    attachment_ids: Optional[list[str]] = Field(
        default=None,
        description="Optional list of attachment identifiers available for retrieval.",
    )


class AgentToolCallMetadata(BaseModel):
    tool_name: str
    status: str  # "completed" | "failed"
    success: bool
    duration_ms: Optional[float] = None
    error_type: Optional[str] = None
    arguments: Optional[dict[str, Any]] = None


class AgentRunResponse(BaseModel):
    answer: str
    status: str
    termination_reason: Optional[str] = None
    iteration_count: int
    total_duration_ms: Optional[float] = None
    tool_calls: list[AgentToolCallMetadata] = Field(default_factory=list)


@router.post(
    "/run",
    response_model=AgentRunResponse,
    summary="Execute multi-step Agent request",
    response_description="Structured Agent response containing final answer and safe execution metadata",
)
async def run_agent_endpoint(
    request: AgentRunRequest,
    target_agent: Agent = Depends(get_agent),
) -> AgentRunResponse:
    """
    Executes a multi-step Agent run for a given user request.
    Returns the agent's final answer along with safe, sanitized operational metadata.
    """
    user_query = request.message.strip()
    if not user_query:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message prompt cannot be empty or whitespace.",
        )

    # Attach document references if provided
    effective_request = user_query
    if request.attachment_ids:
        clean_ids = [aid.strip() for aid in request.attachment_ids if aid and aid.strip()]
        if clean_ids:
            effective_request = f"{user_query}\n[Attached Document IDs: {', '.join(clean_ids)}]"

    logger.info(
        f"Processing agent run request: '{effective_request[:80]}...' "
        f"(mode={request.mode}, max_iterations={request.max_iterations})"
    )

    try:
        state = await target_agent.run(
            user_request=effective_request,
            max_iterations=request.max_iterations,
            mode=request.mode,
        )
    except Exception as e:
        logger.error(f"Unhandled exception during agent execution: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent execution failed: {type(e).__name__}: {e}",
        )

    # Map safe tool call metadata (NO chain of thought, NO API keys, NO secrets)
    tool_calls: list[AgentToolCallMetadata] = []
    for record in state.execution_records:
        tool_calls.append(
            AgentToolCallMetadata(
                tool_name=record.tool_name,
                status="completed" if record.success else "failed",
                success=record.success,
                duration_ms=round(record.duration_ms, 2) if record.duration_ms is not None else None,
                error_type=record.error_type,
                arguments=record.arguments,
            )
        )

    raw_status = state.status.value if hasattr(state.status, "value") else str(state.status)

    # Resolve display answer
    if state.final_answer:
        answer_text = state.final_answer
    elif raw_status == AgentStatus.MAX_ITERATIONS_REACHED.value:
        answer_text = (
            "The Agent reached the maximum iteration limit without producing a final answer. "
            "Please refine your prompt or inspect the activity log."
        )
    elif raw_status == AgentStatus.LOOP_DETECTED.value:
        answer_text = (
            "The Agent detected a repeated tool execution loop and stopped safely. "
            f"Detail: {state.error or 'Identical consecutive tool calls.'}"
        )
    elif raw_status == AgentStatus.ERROR.value:
        answer_text = f"Agent encountered an error: {state.error or 'Unknown orchestration failure.'}"
    else:
        answer_text = "No response generated."

    return AgentRunResponse(
        answer=answer_text,
        status=raw_status,
        termination_reason=state.termination_reason,
        iteration_count=state.iteration_count,
        total_duration_ms=state.total_duration_ms,
        tool_calls=tool_calls,
    )
