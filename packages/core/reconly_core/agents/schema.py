"""Agent result schema for research operations.

Defines the structured output format for agent-based research.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AgentResult:
    """Structured result from agent research operations.

    Attributes:
        title: A descriptive title for the research findings
        content: The research findings in markdown format
        sources: List of URLs that were consulted during research
        iterations: Number of iterations the agent loop ran
        tool_calls: List of tool calls made during research, each containing:
            - tool: The tool name (web_search or web_fetch)
            - input: The input parameters for the tool call
            - output: Truncated output from the tool (first 500 chars)
    """

    title: str
    content: str
    sources: list[str] = field(default_factory=list)
    iterations: int = 0
    tool_calls: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert result to dictionary format.

        Returns:
            Dictionary representation of the agent result
        """
        return {
            "title": self.title,
            "content": self.content,
            "sources": self.sources,
            "iterations": self.iterations,
            "tool_calls": self.tool_calls,
        }

    @classmethod
    def from_dict(cls, data: dict) -> AgentResult:
        """Create AgentResult from dictionary.

        Args:
            data: Dictionary with agent result fields

        Returns:
            AgentResult instance
        """
        return cls(
            title=data.get("title", ""),
            content=data.get("content", ""),
            sources=data.get("sources", []),
            iterations=data.get("iterations", 0),
            tool_calls=data.get("tool_calls", []),
        )
