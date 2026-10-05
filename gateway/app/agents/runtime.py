"""Reusable agent runtime — Part 12.

An "agent" here is deliberately small and auditable: given a question, pick
one tool from a fixed registry, run it, return the result. No framework
magic — every decision point is code we wrote and can read.

The MCP (Model Context Protocol) convention this follows: each tool is
described by a name, a plain-English description, and a JSON schema for its
arguments — the same shape MCP-compatible tools use, so these definitions
could plug into another MCP-aware agent later without rewriting them.
"""
import json
import time
from dataclasses import dataclass
from typing import Awaitable, Callable

MAX_STEPS = 3  # hard cap — a buggy or adversarial prompt cannot loop forever


@dataclass
class Tool:
    name: str
    description: str
    parameters_schema: dict  # JSON schema, MCP-style
    handler: Callable[..., Awaitable[dict]]
    requires_approval: bool = False  # Part 13 hook: some tools pause for a human


class ToolRegistry:
    """The only actions an agent may take — if it isn't registered here, the
    agent cannot do it, no matter what a prompt asks for.
    """

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def as_mcp_descriptions(self) -> list[dict]:
        """What gets shown to the LLM when it's deciding which tool to use."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters_schema,
            }
            for t in self._tools.values()
        ]


@dataclass
class AgentStep:
    tool_name: str
    tool_input: dict
    tool_output: dict
    latency_ms: int


@dataclass
class AgentRunResult:
    steps: list[AgentStep]
    final_answer: str
    stopped_reason: str  # "completed" | "step_limit" | "no_tool_matched" | "error"


async def run_agent(
    registry: ToolRegistry,
    tool_name: str,
    tool_input: dict,
) -> AgentRunResult:
    """Runs exactly one tool call (this project's agents are single-step by
    design — the step limit exists for future multi-step agents, e.g. Part 13's
    incident copilot, which may need to chain a few read-only tool calls).
    """
    steps: list[AgentStep] = []

    tool = registry.get(tool_name)
    if tool is None:
        return AgentRunResult(
            steps=steps,
            final_answer=f"No tool named '{tool_name}' is registered.",
            stopped_reason="no_tool_matched",
        )

    if len(steps) >= MAX_STEPS:
        return AgentRunResult(steps=steps, final_answer="Step limit reached.", stopped_reason="step_limit")

    start = time.perf_counter()
    try:
        output = await tool.handler(**tool_input)
    except Exception as exc:
        return AgentRunResult(
            steps=steps,
            final_answer=f"Tool '{tool_name}' failed: {exc}",
            stopped_reason="error",
        )
    latency_ms = int((time.perf_counter() - start) * 1000)

    steps.append(AgentStep(tool_name=tool_name, tool_input=tool_input, tool_output=output, latency_ms=latency_ms))

    return AgentRunResult(
        steps=steps,
        final_answer=output.get("answer", json.dumps(output)),
        stopped_reason="completed",
    )
