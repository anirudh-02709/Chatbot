"""
Agent Orchestrator for Goal 10.7: Agent Orchestration Foundation.

Coordinates user requests, LLM decisions, and the single tool execution boundary.
Does NOT execute tools directly; all executions pass through ToolExecutionService.
"""

import logging
import uuid
from typing import Any, Optional

from app.agent.models import AgentDecision, AgentDecisionType, AgentState, AgentStatus
from app.agent.parser import parse_agent_decision, DecisionParsingError
from app.agent.prompts import build_agent_system_prompt
from app.models.chat import ChatMessage
from app.models.tool import ToolExecutionRecord
from app.services.ollama import OllamaService
from app.tools.registry import ToolRegistry, tool_registry as global_tool_registry
from app.tools.executor import ToolExecutionService, tool_execution_service as global_execution_service

logger = logging.getLogger("chatbot.agent.orchestrator")


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

        messages = [ChatMessage(role="user", content=state.user_request)]

        logger.info(
            f"Requesting agent decision for request '{state.request_id}' "
            f"(available tools: {sorted(valid_tools)})"
        )

        raw_response = await self.ollama_service.generate_response(
            messages=messages,
            system_prompt=system_prompt,
            mode=mode,
        )

        decision = parse_agent_decision(raw_response, valid_tools=valid_tools)
        state.current_decision = decision
        state.mark_updated()
        return decision

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
                logger.info(f"Agent resolved direct FINAL_ANSWER for request '{current_state.request_id}'")

            elif decision.type == AgentDecisionType.TOOL_CALL:
                record = await self.execute_tool(current_state, decision)
                if record.success:
                    current_state.status = AgentStatus.STEP_COMPLETED
                    logger.info(
                        f"Agent successfully executed tool '{decision.tool_name}' "
                        f"for request '{current_state.request_id}'"
                    )
                else:
                    current_state.status = AgentStatus.ERROR
                    current_state.error = record.error or f"Tool '{decision.tool_name}' failed."
                    logger.warning(
                        f"Agent tool execution '{decision.tool_name}' failed: {record.error}"
                    )

        except DecisionParsingError as dpe:
            logger.warning(f"Agent decision parsing error: {dpe}")
            current_state.status = AgentStatus.ERROR
            current_state.error = str(dpe)
        except Exception as e:
            logger.error(f"Unexpected error in agent orchestration step: {e}")
            current_state.status = AgentStatus.ERROR
            current_state.error = f"Orchestration failure: {e}"

        current_state.mark_updated()
        return current_state


# Global agent instance
agent = Agent()
