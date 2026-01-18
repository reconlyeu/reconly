"""Research agent with ReAct loop for web research.

Implements a simple ReAct (Reasoning and Acting) loop that uses an LLM
to conduct web research using web_search and web_fetch tools.
"""
from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from reconly_core.providers.base import BaseProvider
    from reconly_core.agents.settings import AgentSettings

from reconly_core.agents.schema import AgentResult
from reconly_core.agents.search import web_search
from reconly_core.agents.fetch import web_fetch, format_fetch_result

logger = logging.getLogger(__name__)


# System prompt for the research agent
AGENT_SYSTEM_PROMPT = '''You are a research assistant. Your task is to investigate the given topic using web search and fetch tools.

Available tools:
- web_search(query): Search the web for information. Returns a list of results with titles, snippets, and URLs.
- web_fetch(url): Fetch the full content of a URL. Use this to read articles found via search.

Process:
1. Think about what information you need
2. Use web_search to find relevant sources
3. Use web_fetch to read promising articles
4. Synthesize your findings

When you have enough information, respond with your final answer in this format:
```json
{
  "title": "A descriptive title for your findings",
  "content": "Your research findings in markdown format",
  "sources": ["url1", "url2", ...]
}
```

To use a tool, respond with:
```json
{"tool": "web_search", "query": "your search query"}
```
or
```json
{"tool": "web_fetch", "url": "https://example.com/article"}
```
'''


class ResearchAgent:
    """Simple ReAct agent with hardcoded web_search and web_fetch tools.

    This agent runs a research loop where it:
    1. Gets an LLM response
    2. Checks if it's a final answer or a tool call
    3. Executes the tool if needed
    4. Appends results and continues until done or max iterations reached

    Attributes:
        summarizer: The LLM summarizer to use for generating responses
        settings: Agent settings with search configuration
        max_iterations: Maximum number of loop iterations
        total_tokens_in: Total input tokens used across all iterations
        total_tokens_out: Total output tokens used across all iterations
    """

    def __init__(
        self,
        summarizer: "BaseProvider",
        settings: "AgentSettings",
        max_iterations: int = 5,
    ):
        """Initialize the research agent.

        Args:
            summarizer: LLM summarizer for generating responses
            settings: Agent settings with search provider configuration
            max_iterations: Maximum number of research loop iterations
        """
        self.summarizer = summarizer
        self.settings = settings
        self.max_iterations = max_iterations
        self.total_tokens_in = 0
        self.total_tokens_out = 0

    async def run(self, prompt: str) -> AgentResult:
        """Execute research loop and return structured findings.

        Args:
            prompt: The research topic or question to investigate

        Returns:
            AgentResult with title, content, sources, and metadata
        """
        messages = self._build_initial_prompt(prompt)
        tool_calls: list[dict] = []
        sources: set[str] = set()

        for iteration in range(self.max_iterations):
            logger.info(
                "Agent iteration",
                extra={
                    "iteration": iteration + 1,
                    "max_iterations": self.max_iterations,
                },
            )

            # Get LLM response
            response = self._call_llm(messages)

            # Check for final answer
            if self._is_final_answer(response):
                try:
                    result = self._parse_final_answer(response)
                    result.iterations = iteration + 1
                    result.tool_calls = tool_calls
                    result.sources = list(sources.union(set(result.sources)))
                    logger.info(
                        "Agent completed with final answer",
                        extra={
                            "iterations": result.iterations,
                            "sources_count": len(result.sources),
                        },
                    )
                    return result
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(
                        "Failed to parse final answer, continuing",
                        extra={
                            "error": str(e),
                            "response_preview": response[:500] if response else None,
                        },
                    )

            # Parse and execute tool call
            tool_call = self._parse_tool_call(response)
            if tool_call:
                tool_result = await self._execute_tool(tool_call)

                # Truncate long results for the log
                truncated_output = (
                    tool_result[:500] + "..."
                    if len(tool_result) > 500
                    else tool_result
                )

                tool_calls.append({
                    "tool": tool_call["tool"],
                    "input": tool_call,
                    "output": truncated_output,
                })

                # Track sources from web_fetch
                if tool_call["tool"] == "web_fetch":
                    url = tool_call.get("url", "")
                    if url:
                        sources.add(url)

                logger.debug(
                    "Tool executed",
                    extra={
                        "tool": tool_call["tool"],
                        "output_length": len(tool_result),
                    },
                )

                # Append to conversation
                messages.append({"role": "assistant", "content": response})
                messages.append({
                    "role": "user",
                    "content": f"Tool result:\n{tool_result}",
                })
            else:
                # No tool call found, prompt to use tools or provide answer
                logger.debug(
                    "No tool call or final answer found in response",
                    extra={"response_preview": response[:500] if response else None},
                )
                messages.append({"role": "assistant", "content": response})
                messages.append({
                    "role": "user",
                    "content": (
                        "Please use a tool or provide your final answer "
                        "in the JSON format specified."
                    ),
                })

        # Max iterations reached - return partial result
        logger.warning(
            "Agent reached max iterations",
            extra={"max_iterations": self.max_iterations},
        )
        return self._timeout_result(messages, tool_calls, list(sources))

    def _build_initial_prompt(self, user_prompt: str) -> list[dict]:
        """Build initial messages with system prompt and user request.

        Args:
            user_prompt: The user's research topic or question

        Returns:
            List of message dicts with system and user roles
        """
        return [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": f"Research the following:\n\n{user_prompt}"},
        ]

    def _call_llm(self, messages: list[dict]) -> str:
        """Call the LLM with messages and return response text.

        Converts the message list to a single prompt for summarizer compatibility.

        Args:
            messages: List of conversation messages

        Returns:
            LLM response text
        """
        # Format messages into single prompt (for summarizer compatibility)
        prompt_parts = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "system":
                prompt_parts.append(content)
            elif role == "user":
                prompt_parts.append(f"User: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")

        full_prompt = "\n\n".join(prompt_parts)
        full_prompt += "\n\nAssistant:"

        # Use summarizer to call LLM
        result = self.summarizer.summarize(
            content_data={"content": full_prompt, "title": "Research Agent"},
            system_prompt="",  # System prompt already in messages
            user_prompt=full_prompt,
        )

        # Track tokens
        model_info = result.get("model_info")
        if isinstance(model_info, dict):
            self.total_tokens_in += model_info.get("input_tokens", 0)
            self.total_tokens_out += model_info.get("output_tokens", 0)

        return result.get("summary", "")

    def _is_final_answer(self, response: str) -> bool:
        """Check if response contains a final JSON answer.

        Actually tries to extract and validate JSON rather than just pattern matching,
        to avoid false positives from narrative text mentioning "title" or "content".

        Args:
            response: LLM response text

        Returns:
            True if response contains valid final answer JSON
        """
        # Try to extract JSON and validate it's a final answer
        json_str = self._extract_json(response)
        if not json_str:
            return False

        try:
            data = json.loads(json_str)
            # Must have title and content, but NOT be a tool call
            has_title = "title" in data
            has_content = "content" in data
            is_tool_call = "tool" in data
            return has_title and has_content and not is_tool_call
        except json.JSONDecodeError:
            return False

    def _parse_final_answer(self, response: str) -> AgentResult:
        """Extract AgentResult from JSON in response.

        Args:
            response: LLM response containing final answer JSON

        Returns:
            AgentResult parsed from the JSON

        Raises:
            ValueError: If JSON cannot be found or parsed
        """
        json_str = self._extract_json(response)
        if not json_str:
            raise ValueError("Could not find final answer JSON in response")

        data = json.loads(json_str)

        # Validate it's a final answer (has title/content, not a tool call)
        if "tool" in data:
            raise ValueError("JSON appears to be a tool call, not a final answer")

        return AgentResult(
            title=data.get("title", "Research Findings"),
            content=data.get("content", ""),
            sources=data.get("sources", []),
            iterations=0,  # Will be set by caller
            tool_calls=[],  # Will be set by caller
        )

    def _parse_tool_call(self, response: str) -> dict | None:
        """Extract tool call from response.

        Args:
            response: LLM response text

        Returns:
            Dict with tool call info or None if not found
        """
        json_str = self._extract_json(response)
        if not json_str:
            return None

        try:
            data = json.loads(json_str)
            if "tool" in data:
                return data
        except json.JSONDecodeError:
            pass

        return None

    def _extract_json(self, text: str) -> str | None:
        """Extract JSON from text, handling code blocks and raw JSON.

        Args:
            text: Text potentially containing JSON

        Returns:
            JSON string or None if not found
        """
        # Try to find JSON in code block first
        match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Try to find JSON in generic code block
        match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
        if match:
            potential_json = match.group(1).strip()
            if potential_json.startswith("{"):
                return potential_json

        # Try to find raw JSON object
        # Find the first { and match to its closing }
        start = text.find("{")
        if start == -1:
            return None

        depth = 0
        in_string = False
        escape_next = False

        for i, char in enumerate(text[start:], start):
            if escape_next:
                escape_next = False
                continue

            if char == "\\" and in_string:
                escape_next = True
                continue

            if char == '"':
                in_string = not in_string
                continue

            if in_string:
                continue

            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]

        return None

    async def _execute_tool(self, tool_call: dict) -> str:
        """Execute a tool and return result string.

        Args:
            tool_call: Dict with tool name and parameters

        Returns:
            Tool execution result as string
        """
        tool_name = tool_call.get("tool")

        if tool_name == "web_search":
            query = tool_call.get("query", "")
            if not query:
                return "Error: web_search requires a 'query' parameter"

            try:
                return await web_search(query, self.settings)
            except Exception as e:
                logger.error(
                    "web_search failed",
                    extra={"query": query, "error": str(e)},
                )
                return f"Search error: {e}"

        elif tool_name == "web_fetch":
            url = tool_call.get("url", "")
            if not url:
                return "Error: web_fetch requires a 'url' parameter"

            try:
                result = await web_fetch(url)
                return format_fetch_result(result)
            except Exception as e:
                logger.error(
                    "web_fetch failed",
                    extra={"url": url, "error": str(e)},
                )
                return f"Fetch error: {e}"

        else:
            return f"Unknown tool: {tool_name}. Available tools: web_search, web_fetch"

    def _timeout_result(
        self,
        messages: list[dict],
        tool_calls: list[dict],
        sources: list[str],
    ) -> AgentResult:
        """Create partial result when max iterations reached.

        Extracts useful content from the conversation history.

        Args:
            messages: Full conversation history
            tool_calls: List of tool calls made
            sources: List of URLs fetched

        Returns:
            AgentResult with partial findings
        """
        # Extract any useful content from the conversation
        content_parts = []
        for msg in messages:
            if msg["role"] == "assistant":
                content_parts.append(msg["content"])

        # Use last 3 assistant responses to build content
        relevant_content = content_parts[-3:] if content_parts else []

        return AgentResult(
            title="Research In Progress (Max Iterations Reached)",
            content="\n\n---\n\n".join(relevant_content) if relevant_content else "Research incomplete.",
            sources=sources,
            iterations=self.max_iterations,
            tool_calls=tool_calls,
        )
