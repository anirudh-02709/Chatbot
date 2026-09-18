"""
Agent Orchestrator for Goal 10.7: Agent Orchestration Foundation.

Coordinates user requests, LLM decisions, and the single tool execution boundary.
Does NOT execute tools directly; all executions pass through ToolExecutionService.
"""

import logging
import time
import uuid
from typing import Any, Optional

from app.agent.models import AgentDecision, AgentDecisionType, AgentState, AgentStatus
from app.agent.parser import parse_agent_decision, DecisionParsingError
from app.agent.prompts import build_agent_system_prompt, build_agent_messages, format_tool_observation
from app.models.chat import ChatMessage
from app.models.tool import ToolExecutionRecord
from app.services.ollama import OllamaService
from app.tools.registry import ToolRegistry, tool_registry as global_tool_registry
from app.tools.executor import ToolExecutionService, tool_execution_service as global_execution_service

logger = logging.getLogger("chatbot.agent.orchestrator")

DEFAULT_MAX_ITERATIONS = 5
DEFAULT_MAX_REPEATED_CALLS = 1


class Agent:
    """
    Agent Orchestrator coordinating user requests, LLM decision making,
    and tool execution through ToolExecutionService.
    """

    def __init__(
        self,
        tool_registry: Optional[ToolRegistry] = None,
        execution_service: Optional[ToolExecutionService] = None,
        ollama_service: Optional[OllamaService] = None,
    ):
        self.tool_registry = tool_registry or global_tool_registry
        self.execution_service = execution_service or global_execution_service
        self._ollama_service = ollama_service

    @property
    def ollama_service(self) -> OllamaService:
        if self._ollama_service is None:
            self._ollama_service = OllamaService()
        return self._ollama_service

    def create_state(self, user_request: str) -> AgentState:
        """Initializes a new AgentState for a user request."""
        req_id = f"req_{uuid.uuid4().hex[:12]}"
        return AgentState(
            request_id=req_id,
            user_request=user_request,
            status=AgentStatus.INITIALIZED,
        )

    async def decide(
        self,
        state: AgentState,
        mode: Optional[str] = None,
    ) -> AgentDecision:
        """
        Prompts the LLM with available tools and the decision protocol,
        and parses the response into an AgentDecision.

        Raises:
            DecisionParsingError: If model output is malformed or invalid.
        """
        state.status = AgentStatus.DECIDING
        state.mark_updated()

        tool_defs = self.tool_registry.get_definitions()
        system_prompt = build_agent_system_prompt(tool_defs)
        valid_tools = set(self.tool_registry.list_tool_names())

        # Pair decisions and execution records for multi-turn history
        history = list(zip(state.decisions, state.execution_records))
        messages = build_agent_messages(user_request=state.user_request, history=history)

        logger.info(
            f"Requesting agent decision for request '{state.request_id}' "
            f"(step {state.iteration_count}, history turns: {len(history)}, "
            f"available tools: {sorted(valid_tools)})"
        )

        raw_response = await self.ollama_service.generate_response(
            messages=messages,
            system_prompt=system_prompt,
            mode=mode,
        )

        decision = parse_agent_decision(raw_response, valid_tools=valid_tools)
        state.current_decision = decision
        state.decisions.append(decision)
        state.mark_updated()
        return decision

    def _is_repeated_call(
        self,
        decision: AgentDecision,
        tool_calls: list[dict[str, Any]],
        threshold: int = DEFAULT_MAX_REPEATED_CALLS,
    ) -> bool:
        """
        Detects if the current decision is an identical consecutive tool call to
        the immediately preceding tool call(s).
        """
        if decision.type != AgentDecisionType.TOOL_CALL or not tool_calls or threshold < 1:
            return False

        consecutive = 0
        for prev_call in reversed(tool_calls):
            if (
                prev_call.get("tool_name") == decision.tool_name
                and prev_call.get("arguments") == decision.tool_arguments
            ):
                consecutive += 1
                if consecutive >= threshold:
                    return True
            else:
                break

        return False

    async def execute_tool(
        self,
        state: AgentState,
        decision: AgentDecision,
    ) -> ToolExecutionRecord:
        """
        Validates and executes the tool requested in the decision strictly through
        the ToolExecutionService. Captures audit record and result in state.
        """
        if decision.type != AgentDecisionType.TOOL_CALL:
            raise ValueError(f"Cannot execute tool on decision type '{decision.type}'.")

        tool_name = decision.tool_name
        tool_args = decision.tool_arguments or {}

        # Record call attempt in state
        state.tool_calls.append({
            "tool_name": tool_name,
            "arguments": tool_args,
        })

        logger.info(
            f"Agent dispatching tool '{tool_name}' through ToolExecutionService for request '{state.request_id}'"
        )

        # Execute through single execution boundary
        exec_id = f"exec_{state.request_id}_{len(state.execution_records)+1}"
        record: ToolExecutionRecord = await self.execution_service.execute_tool(
            tool_name=tool_name,
            arguments=tool_args,
            execution_id=exec_id,
        )

        # Append to audit history
        state.execution_records.append(record)
        if record.result is not None:
            state.tool_results.append(record.result)

        state.mark_updated()
        return record

    async def run_step(
        self,
        user_request: str,
        state: Optional[AgentState] = None,
        mode: Optional[str] = None,
    ) -> AgentState:
        """
        Executes a single orchestration step:
        1. Initializes state if needed.
        2. Prompts model for decision.
        3. If FINAL_ANSWER: sets final_answer, marks COMPLETED.
        4. If TOOL_CALL: executes tool via ToolExecutionService, marks STEP_COMPLETED.

        Returns:
            Updated AgentState.
        """
        current_state = state if state is not None else self.create_state(user_request)
        current_state.iteration_count += 1
        current_state.mark_updated()

        try:
            decision = await self.decide(current_state, mode=mode)

            if decision.type == AgentDecisionType.FINAL_ANSWER:
                current_state.final_answer = decision.answer
                current_state.status = AgentStatus.COMPLETED
                current_state.termination_reason = "completed"
                logger.info(f"Agent resolved direct FINAL_ANSWER for request '{current_state.request_id}'")

            elif decision.type == AgentDecisionType.TOOL_CALL:
                record = await self.execute_tool(current_state, decision)
                obs_str = format_tool_observation(decision.tool_name or "tool", record)
                current_state.observations.append({
                    "step": current_state.iteration_count,
                    "tool_name": decision.tool_name,
                    "success": record.success,
                    "observation": obs_str,
                })
                if record.success:
                    current_state.status = AgentStatus.STEP_COMPLETED
                    logger.info(
                        f"Agent successfully executed tool '{decision.tool_name}' "
                        f"for request '{current_state.request_id}'"
                    )
                else:
                    current_state.status = AgentStatus.ERROR
                    current_state.error = record.error or f"Tool '{decision.tool_name}' failed."
                    current_state.termination_reason = "error"
                    logger.warning(
                        f"Agent tool execution '{decision.tool_name}' failed: {record.error}"
                    )

        except DecisionParsingError as dpe:
            logger.warning(f"Agent decision parsing error: {dpe}")
            current_state.status = AgentStatus.ERROR
            current_state.error = str(dpe)
            current_state.termination_reason = "error"
        except Exception as e:
            logger.error(f"Unexpected error in agent orchestration step: {e}")
            current_state.status = AgentStatus.ERROR
            current_state.error = f"Orchestration failure: {e}"
            current_state.termination_reason = "error"

        current_state.mark_updated()
        return current_state

    async def run(
        self,
        user_request: str,
        max_iterations: Optional[int] = None,
        mode: Optional[str] = None,
    ) -> AgentState:
        """
        Runs a controlled multi-step orchestration loop for a user request.

        Loop steps per iteration:
        1. Prompts LLM with request, history, and available tools.
        2. Parses structured decision (FINAL_ANSWER vs TOOL_CALL).
        3. If FINAL_ANSWER: sets final_answer, status COMPLETED, terminates.
        4. If TOOL_CALL:
           a. Checks repeated-call loop detector -> if loop, flags LOOP_DETECTED and terminates.
           b. Executes tool strictly via ToolExecutionService.
           c. Formats observation (success or error) and appends to history.
           d. If iteration_count >= max_iterations: flags MAX_ITERATIONS_REACHED and terminates.

        Safeguards:
        - Hard iteration limit (default: 5)
        - Repeated-call loop detection
        - Single execution boundary via ToolExecutionService
        - Full audit record preserved in returned AgentState
        """
        start_time = time.perf_counter()
        limit = max(1, max_iterations if max_iterations is not None else DEFAULT_MAX_ITERATIONS)
        state = self.create_state(user_request)
        state.max_iterations = limit

        valid_tools = set(self.tool_registry.list_tool_names())

        logger.info(
            f"Starting multi-step agent loop for request '{state.request_id}' "
            f"(max_iterations={limit}, available_tools={sorted(valid_tools)})"
        )

        while state.iteration_count < limit:
            state.iteration_count += 1
            logger.info(
                f"Agent step {state.iteration_count}/{limit} for request '{state.request_id}'"
            )

            try:
                decision = await self.decide(state, mode=mode)
            except DecisionParsingError as dpe:
                logger.warning(
                    f"Agent decision parsing error on step {state.iteration_count}: {dpe}"
                )
                state.status = AgentStatus.ERROR
                state.error = str(dpe)
                state.termination_reason = "error"
                break
            except Exception as e:
                logger.error(f"Unexpected error deciding next step: {e}")
                state.status = AgentStatus.ERROR
                state.error = f"Orchestration failure during decision: {e}"
                state.termination_reason = "error"
                break

            if decision.type == AgentDecisionType.FINAL_ANSWER:
                state.final_answer = decision.answer
                state.status = AgentStatus.COMPLETED
                state.termination_reason = "completed"
                logger.info(
                    f"Agent reached FINAL_ANSWER on step {state.iteration_count} "
                    f"for request '{state.request_id}'"
                )
                break

            elif decision.type == AgentDecisionType.TOOL_CALL:
                # Check repeated call protection before executing
                if self._is_repeated_call(decision, state.tool_calls):
                    state.status = AgentStatus.LOOP_DETECTED
                    state.termination_reason = "loop_detected"
                    state.error = (
                        f"Loop detected: tool '{decision.tool_name}' called with identical "
                        f"arguments in consecutive iterations."
                    )
                    logger.warning(
                        f"Agent loop detected on step {state.iteration_count} for request '{state.request_id}': "
                        f"Tool '{decision.tool_name}' with args {decision.tool_arguments}"
                    )
                    break

                try:
                    record = await self.execute_tool(state, decision)
                    obs_str = format_tool_observation(decision.tool_name or "tool", record)
                    state.observations.append({
                        "step": state.iteration_count,
                        "tool_name": decision.tool_name,
                        "success": record.success,
                        "observation": obs_str,
                    })
                    state.status = AgentStatus.STEP_COMPLETED
                except Exception as e:
                    logger.error(f"Unexpected tool execution error: {e}")
                    state.status = AgentStatus.ERROR
                    state.error = f"Tool execution failed: {e}"
                    state.termination_reason = "error"
                    break

                # Check if hard iteration limit has been reached after tool execution
                if state.iteration_count >= limit:
                    state.status = AgentStatus.MAX_ITERATIONS_REACHED
                    state.termination_reason = "max_iterations_reached"
                    logger.warning(
                        f"Agent reached max iterations limit ({limit}) without final answer "
                        f"for request '{state.request_id}'"
                    )
                    break

        # Ensure terminal status if loop exited without explicit completion
        if state.status not in (
            AgentStatus.COMPLETED,
            AgentStatus.MAX_ITERATIONS_REACHED,
            AgentStatus.LOOP_DETECTED,
            AgentStatus.ERROR,
        ):
            if state.iteration_count >= limit:
                state.status = AgentStatus.MAX_ITERATIONS_REACHED
                state.termination_reason = "max_iterations_reached"

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        state.total_duration_ms = round(duration_ms, 2)
        state.mark_updated()
        return state


# Global agent instance
agent = Agent()
