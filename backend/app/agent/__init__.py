"""
Agent Orchestration Foundation package for Goal 10.7.

Coordinates user requests, model decisions, and tool execution boundaries.
"""

from app.agent.models import (
    AgentDecisionType,
    AgentStatus,
    AgentDecision,
    AgentState,
)
from app.agent.parser import (
    DecisionParsingError,
    extract_json_payload,
    parse_agent_decision,
)
from app.agent.prompts import (
    AGENT_SYSTEM_PROMPT_TEMPLATE,
    build_agent_system_prompt,
)
from app.agent.orchestrator import (
    Agent,
    agent,
)

__all__ = [
    "AgentDecisionType",
    "AgentStatus",
    "AgentDecision",
    "AgentState",
    "DecisionParsingError",
    "extract_json_payload",
    "parse_agent_decision",
    "AGENT_SYSTEM_PROMPT_TEMPLATE",
    "build_agent_system_prompt",
    "Agent",
    "agent",
]
