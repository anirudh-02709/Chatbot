import asyncio
import contextvars
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional, Union
from pydantic import BaseModel, Field

from app.models.tool import ToolResult, ToolExecutionRequest, ToolExecutionRecord
from app.tools.base import (
    ToolNotFoundError,
    ToolInputValidationError,
    ToolExecutionError,
    ToolTimeoutError,
    ExecutionLimitExceededError,
    RecursiveExecutionError,
)
from app.tools.registry import ToolRegistry, tool_registry

logger = logging.getLogger("chatbot.tools.executor")


class ToolExecutionPolicy(BaseModel):
    """Configuration policy governing tool execution limits and safeguards."""

    max_executions_per_session: int = Field(
        default=10,
        ge=1,
        description="Maximum cumulative tool executions allowed per session.",
    )
    default_timeout_seconds: float = Field(
        default=10.0,
        gt=0.0,
        description="Default timeout limit for asynchronous tool execution.",
    )


class ToolExecutionService:
    """
    Dedicated execution layer between agent orchestration and ToolRegistry.

    Responsibilities:
    - Verifies tool presence in the registry.
    - Validates arguments against tool schema / Pydantic models.
    - Dispatches asynchronous tool execution with timeouts.
    - Measures accurate execution duration in milliseconds.
    - Enforces execution limits and anti-recursion policies.
    - Catches all exceptions, returning structured ToolExecutionRecord
      so no tool failure can crash backend or chat streams.
    """

    def __init__(
        self,
        registry: Optional[ToolRegistry] = None,
        policy: Optional[ToolExecutionPolicy] = None,
    ):
        self.registry = registry or tool_registry
        self.policy = policy or ToolExecutionPolicy()
        self._execution_history: list[ToolExecutionRecord] = []
        self._execution_count: int = 0
        self._active_depth: contextvars.ContextVar[int] = contextvars.ContextVar(
            f"tool_execution_depth_{id(self)}", default=0
        )

    @property
    def execution_count(self) -> int:
        """Returns number of tool executions performed in current session."""
        return self._execution_count

    @property
    def execution_history(self) -> list[ToolExecutionRecord]:
        """Returns ordered history of all execution records for current session."""
        return list(self._execution_history)

    def reset_session(self) -> None:
        """Resets the execution counter and history for a new session."""
        self._execution_count = 0
        self._execution_history.clear()
        logger.info("Reset tool execution session state.")

    async def execute(
        self,
        request: Union[ToolExecutionRequest, dict[str, Any]],
        timeout_seconds: Optional[float] = None,
    ) -> ToolExecutionRecord:
        """
        Executes a tool request under strict execution policies.

        Args:
            request: A ToolExecutionRequest instance or dictionary.
            timeout_seconds: Optional timeout overriding default policy.

        Returns:
            ToolExecutionRecord containing execution ID, status, data, and timings.
        """
        t0 = time.perf_counter()
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Normalize request model
        if isinstance(request, dict):
            try:
                req = ToolExecutionRequest.model_validate(request)
            except Exception as e:
                elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
                record = ToolExecutionRecord(
                    execution_id=f"exec_{uuid.uuid4().hex[:12]}",
                    tool_name=request.get("tool_name", "unknown") if isinstance(request, dict) else "unknown",
                    arguments={},
                    success=False,
                    error=f"Malformed execution request: {e}",
                    error_type="ToolInputValidationError",
                    duration_ms=elapsed_ms,
                    timestamp=now_iso,
                )
                self._execution_history.append(record)
                return record
        else:
            req = request

        execution_id = req.execution_id or f"exec_{uuid.uuid4().hex[:12]}"

        # 2. Execution Policy: Maximum executions per session
        if self._execution_count >= self.policy.max_executions_per_session:
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            err_msg = (
                f"Execution policy violation: maximum limit of "
                f"{self.policy.max_executions_per_session} tool executions exceeded for this session."
            )
            logger.warning(f"Session execution limit reached for {req.tool_name} (ID {execution_id})")
            record = ToolExecutionRecord(
                execution_id=execution_id,
                tool_name=req.tool_name,
                arguments=req.arguments,
                success=False,
                error=err_msg,
                error_type="ExecutionLimitExceededError",
                duration_ms=elapsed_ms,
                timestamp=now_iso,
            )
            self._execution_history.append(record)
            return record

        # 3. Execution Policy: Anti-recursion guard
        current_depth = self._active_depth.get()
        if current_depth > 0:
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            err_msg = (
                f"Recursive execution policy violation: tool '{req.tool_name}' "
                "cannot invoke other tools through the execution layer."
            )
            logger.error(f"Blocked recursive execution attempt by '{req.tool_name}' (depth={current_depth})")
            record = ToolExecutionRecord(
                execution_id=execution_id,
                tool_name=req.tool_name,
                arguments=req.arguments,
                success=False,
                error=err_msg,
                error_type="RecursiveExecutionError",
                duration_ms=elapsed_ms,
                timestamp=now_iso,
            )
            self._execution_history.append(record)
            return record

        # 4. Tool Registry verification
        tool = self.registry.get(req.tool_name)
        if tool is None:
            self._execution_count += 1
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            err_msg = f"Tool '{req.tool_name}' is not registered in ToolRegistry."
            logger.warning(f"Rejected execution of unknown tool '{req.tool_name}'")
            record = ToolExecutionRecord(
                execution_id=execution_id,
                tool_name=req.tool_name,
                arguments=req.arguments,
                success=False,
                error=err_msg,
                error_type="ToolNotFoundError",
                duration_ms=elapsed_ms,
                timestamp=now_iso,
            )
            self._execution_history.append(record)
            return record

        # 5. Input argument validation
        try:
            validated_args = tool.validate_input(req.arguments)
        except ToolInputValidationError as e:
            self._execution_count += 1
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            logger.warning(f"Argument validation failed for tool '{req.tool_name}': {e}")
            record = ToolExecutionRecord(
                execution_id=execution_id,
                tool_name=req.tool_name,
                arguments=req.arguments,
                success=False,
                error=str(e),
                error_type="ToolInputValidationError",
                duration_ms=elapsed_ms,
                timestamp=now_iso,
            )
            self._execution_history.append(record)
            return record
        except Exception as e:
            self._execution_count += 1
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            logger.error(f"Unexpected validation error for '{req.tool_name}': {e}")
            record = ToolExecutionRecord(
                execution_id=execution_id,
                tool_name=req.tool_name,
                arguments=req.arguments,
                success=False,
                error=f"Argument validation error: {e}",
                error_type="ToolInputValidationError",
                duration_ms=elapsed_ms,
                timestamp=now_iso,
            )
            self._execution_history.append(record)
            return record

        # 6. Dispatched execution with timeout & recursion tracking
        self._execution_count += 1
        effective_timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else self.policy.default_timeout_seconds
        )

        depth_token = self._active_depth.set(current_depth + 1)
        raw_result: Optional[ToolResult] = None
        exec_error: Optional[str] = None
        exec_error_type: Optional[str] = None

        try:
            tool_coro = tool.execute(**validated_args)
            if effective_timeout > 0:
                raw_result = await asyncio.wait_for(tool_coro, timeout=effective_timeout)
            else:
                raw_result = await tool_coro

        except asyncio.TimeoutError:
            exec_error = f"Tool '{req.tool_name}' timed out after {effective_timeout}s."
            exec_error_type = "ToolTimeoutError"
            logger.error(f"Execution of tool '{req.tool_name}' timed out after {effective_timeout}s")

        except Exception as e:
            exec_error = f"Tool '{req.tool_name}' raised an error during execution: {e}"
            exec_error_type = type(e).__name__
            logger.exception(f"Exception during execution of tool '{req.tool_name}': {e}")

        finally:
            self._active_depth.reset(depth_token)

        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

        # 7. Construct execution record
        if exec_error:
            failure_result = ToolResult.fail(
                tool_name=req.tool_name,
                error=exec_error,
                error_type=exec_error_type,
                execution_time_ms=elapsed_ms,
                metadata={"execution_id": execution_id},
            )
            record = ToolExecutionRecord(
                execution_id=execution_id,
                tool_name=req.tool_name,
                arguments=req.arguments,
                success=False,
                result=failure_result,
                data=None,
                error=exec_error,
                error_type=exec_error_type,
                duration_ms=elapsed_ms,
                timestamp=now_iso,
            )
        else:
            if not isinstance(raw_result, ToolResult):
                raw_result = ToolResult.ok(
                    tool_name=req.tool_name,
                    data=raw_result,
                    execution_time_ms=elapsed_ms,
                    metadata={"execution_id": execution_id},
                )
            elif raw_result.execution_time_ms is None:
                raw_result.execution_time_ms = elapsed_ms

            record = ToolExecutionRecord(
                execution_id=execution_id,
                tool_name=req.tool_name,
                arguments=req.arguments,
                success=raw_result.success,
                result=raw_result,
                data=raw_result.data,
                error=raw_result.error,
                error_type=raw_result.error_type,
                duration_ms=elapsed_ms,
                timestamp=now_iso,
            )

        self._execution_history.append(record)
        return record

    async def execute_tool(
        self,
        tool_name: str,
        arguments: Optional[dict[str, Any]] = None,
        execution_id: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ) -> ToolExecutionRecord:
        """
        Convenience method to dispatch a tool execution by name and arguments.
        """
        request = ToolExecutionRequest(
            tool_name=tool_name,
            arguments=arguments or {},
            execution_id=execution_id,
        )
        return await self.execute(request=request, timeout_seconds=timeout_seconds)


# Global singleton instance
tool_execution_service = ToolExecutionService()
