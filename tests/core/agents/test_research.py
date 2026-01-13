"""Tests for research agent.

Tests cover:
- AgentResult schema
- ResearchAgent initialization
- ReAct loop execution with mocked LLM
- Tool call parsing and execution
- Final answer detection and parsing
- Token tracking
- Timeout handling
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from reconly_core.agents.schema import AgentResult
from reconly_core.agents.settings import AgentSettings
from reconly_core.agents.research import (
    ResearchAgent,
    AGENT_SYSTEM_PROMPT,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_summarizer():
    """Create a mock summarizer for testing."""
    summarizer = MagicMock()
    summarizer.summarize.return_value = {
        "summary": "Test response",
        "model_info": {
            "input_tokens": 100,
            "output_tokens": 50,
        },
    }
    return summarizer


@pytest.fixture
def agent_settings():
    """Create agent settings for testing."""
    return AgentSettings(
        search_provider="brave",
        brave_api_key="test-api-key",
        max_search_results=5,
        default_max_iterations=5,
    )


@pytest.fixture
def research_agent(mock_summarizer, agent_settings):
    """Create a research agent for testing."""
    return ResearchAgent(
        summarizer=mock_summarizer,
        settings=agent_settings,
        max_iterations=5,
    )


# =============================================================================
# AgentResult Schema Tests
# =============================================================================


class TestAgentResult:
    """Tests for AgentResult dataclass."""

    def test_default_values(self):
        """AgentResult has sensible defaults."""
        result = AgentResult(title="Test", content="Content")

        assert result.title == "Test"
        assert result.content == "Content"
        assert result.sources == []
        assert result.iterations == 0
        assert result.tool_calls == []

    def test_full_initialization(self):
        """AgentResult accepts all fields."""
        result = AgentResult(
            title="Research Title",
            content="Research findings here",
            sources=["https://example.com/1", "https://example.com/2"],
            iterations=3,
            tool_calls=[
                {"tool": "web_search", "input": {"query": "test"}, "output": "results"},
            ],
        )

        assert result.title == "Research Title"
        assert result.content == "Research findings here"
        assert len(result.sources) == 2
        assert result.iterations == 3
        assert len(result.tool_calls) == 1

    def test_to_dict(self):
        """to_dict converts result to dictionary."""
        result = AgentResult(
            title="Test",
            content="Content",
            sources=["url1"],
            iterations=2,
            tool_calls=[{"tool": "web_search"}],
        )

        data = result.to_dict()

        assert data["title"] == "Test"
        assert data["content"] == "Content"
        assert data["sources"] == ["url1"]
        assert data["iterations"] == 2
        assert data["tool_calls"] == [{"tool": "web_search"}]

    def test_from_dict(self):
        """from_dict creates AgentResult from dictionary."""
        data = {
            "title": "Dict Title",
            "content": "Dict Content",
            "sources": ["url1", "url2"],
            "iterations": 4,
            "tool_calls": [],
        }

        result = AgentResult.from_dict(data)

        assert result.title == "Dict Title"
        assert result.content == "Dict Content"
        assert result.sources == ["url1", "url2"]
        assert result.iterations == 4
        assert result.tool_calls == []

    def test_from_dict_with_defaults(self):
        """from_dict uses defaults for missing fields."""
        data = {"title": "Minimal"}

        result = AgentResult.from_dict(data)

        assert result.title == "Minimal"
        assert result.content == ""
        assert result.sources == []
        assert result.iterations == 0
        assert result.tool_calls == []


# =============================================================================
# ResearchAgent Initialization Tests
# =============================================================================


class TestResearchAgentInit:
    """Tests for ResearchAgent initialization."""

    def test_init_with_defaults(self, mock_summarizer, agent_settings):
        """Agent initializes with default max_iterations."""
        agent = ResearchAgent(
            summarizer=mock_summarizer,
            settings=agent_settings,
        )

        assert agent.summarizer is mock_summarizer
        assert agent.settings is agent_settings
        assert agent.max_iterations == 5
        assert agent.total_tokens_in == 0
        assert agent.total_tokens_out == 0

    def test_init_with_custom_max_iterations(self, mock_summarizer, agent_settings):
        """Agent accepts custom max_iterations."""
        agent = ResearchAgent(
            summarizer=mock_summarizer,
            settings=agent_settings,
            max_iterations=10,
        )

        assert agent.max_iterations == 10


# =============================================================================
# Tool Call Parsing Tests
# =============================================================================


class TestToolCallParsing:
    """Tests for _parse_tool_call and _extract_json methods."""

    def test_parse_search_tool_in_code_block(self, research_agent):
        """Parses web_search tool call in code block."""
        response = '''Let me search for that.

```json
{"tool": "web_search", "query": "python async patterns"}
```
'''
        result = research_agent._parse_tool_call(response)

        assert result is not None
        assert result["tool"] == "web_search"
        assert result["query"] == "python async patterns"

    def test_parse_fetch_tool_in_code_block(self, research_agent):
        """Parses web_fetch tool call in code block."""
        response = '''I'll fetch that article.

```json
{"tool": "web_fetch", "url": "https://example.com/article"}
```
'''
        result = research_agent._parse_tool_call(response)

        assert result is not None
        assert result["tool"] == "web_fetch"
        assert result["url"] == "https://example.com/article"

    def test_parse_tool_raw_json(self, research_agent):
        """Parses raw JSON tool call without code block."""
        response = 'I need to search: {"tool": "web_search", "query": "test"}'

        result = research_agent._parse_tool_call(response)

        assert result is not None
        assert result["tool"] == "web_search"
        assert result["query"] == "test"

    def test_parse_no_tool_call(self, research_agent):
        """Returns None when no tool call found."""
        response = "Let me think about this problem..."

        result = research_agent._parse_tool_call(response)

        assert result is None

    def test_parse_invalid_json(self, research_agent):
        """Returns None for invalid JSON."""
        response = '{"tool": "web_search", "query": incomplete'

        result = research_agent._parse_tool_call(response)

        assert result is None

    def test_extract_json_code_block(self, research_agent):
        """Extracts JSON from code block."""
        text = '```json\n{"key": "value"}\n```'

        result = research_agent._extract_json(text)

        assert result == '{"key": "value"}'

    def test_extract_json_generic_code_block(self, research_agent):
        """Extracts JSON from generic code block."""
        text = '```\n{"key": "value"}\n```'

        result = research_agent._extract_json(text)

        assert result == '{"key": "value"}'

    def test_extract_json_nested_braces(self, research_agent):
        """Handles nested braces in JSON."""
        text = '{"outer": {"inner": {"deep": "value"}}}'

        result = research_agent._extract_json(text)

        assert result == '{"outer": {"inner": {"deep": "value"}}}'

    def test_extract_json_with_string_braces(self, research_agent):
        """Handles braces inside strings correctly."""
        text = '{"message": "Use { and } for objects"}'

        result = research_agent._extract_json(text)

        assert result == '{"message": "Use { and } for objects"}'


# =============================================================================
# Final Answer Detection Tests
# =============================================================================


class TestFinalAnswerDetection:
    """Tests for _is_final_answer and _parse_final_answer methods."""

    def test_is_final_answer_with_valid_answer(self, research_agent):
        """Detects valid final answer."""
        response = '''Here are my findings:

```json
{
  "title": "Research Summary",
  "content": "The findings show...",
  "sources": ["https://example.com"]
}
```
'''
        assert research_agent._is_final_answer(response) is True

    def test_is_final_answer_with_tool_call(self, research_agent):
        """Does not detect tool call as final answer."""
        response = '{"tool": "web_search", "query": "test"}'

        assert research_agent._is_final_answer(response) is False

    def test_is_final_answer_no_json(self, research_agent):
        """Does not detect plain text as final answer."""
        response = "Let me search for more information."

        assert research_agent._is_final_answer(response) is False

    def test_is_final_answer_title_only(self, research_agent):
        """Does not detect partial answer without content."""
        response = '{"title": "Test"}'

        assert research_agent._is_final_answer(response) is False

    def test_parse_final_answer_code_block(self, research_agent):
        """Parses final answer from code block."""
        response = '''```json
{
  "title": "Research Title",
  "content": "Research content here",
  "sources": ["url1", "url2"]
}
```'''
        result = research_agent._parse_final_answer(response)

        assert result.title == "Research Title"
        assert result.content == "Research content here"
        assert result.sources == ["url1", "url2"]

    def test_parse_final_answer_missing_sources(self, research_agent):
        """Parses final answer without sources."""
        response = '{"title": "Title", "content": "Content"}'

        result = research_agent._parse_final_answer(response)

        assert result.title == "Title"
        assert result.content == "Content"
        assert result.sources == []

    def test_parse_final_answer_raises_for_tool_call(self, research_agent):
        """Raises error if JSON is a tool call."""
        response = '{"tool": "web_search", "query": "test"}'

        with pytest.raises(ValueError, match="tool call"):
            research_agent._parse_final_answer(response)

    def test_parse_final_answer_raises_for_no_json(self, research_agent):
        """Raises error if no JSON found."""
        response = "No JSON here"

        with pytest.raises(ValueError, match="Could not find"):
            research_agent._parse_final_answer(response)


# =============================================================================
# Tool Execution Tests
# =============================================================================


class TestToolExecution:
    """Tests for _execute_tool method."""

    @pytest.mark.asyncio
    async def test_execute_web_search(self, research_agent):
        """Executes web_search tool."""
        with patch(
            "reconly_core.agents.research.web_search",
            new_callable=AsyncMock,
        ) as mock_search:
            mock_search.return_value = "Search Results:\n\n1. **Test**\n   URL: https://example.com"

            result = await research_agent._execute_tool({
                "tool": "web_search",
                "query": "python testing",
            })

            assert "Search Results" in result
            mock_search.assert_called_once_with("python testing", research_agent.settings)

    @pytest.mark.asyncio
    async def test_execute_web_fetch(self, research_agent):
        """Executes web_fetch tool."""
        from reconly_core.agents.fetch import FetchResult

        mock_fetch_result = FetchResult(
            url="https://example.com/article",
            title="Test Article",
            content="Article content here",
            truncated=False,
        )

        with patch(
            "reconly_core.agents.research.web_fetch",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = mock_fetch_result

            result = await research_agent._execute_tool({
                "tool": "web_fetch",
                "url": "https://example.com/article",
            })

            assert "Test Article" in result
            assert "Article content here" in result
            mock_fetch.assert_called_once_with("https://example.com/article")

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self, research_agent):
        """Returns error for unknown tool."""
        result = await research_agent._execute_tool({
            "tool": "unknown_tool",
        })

        assert "Unknown tool" in result
        assert "web_search" in result
        assert "web_fetch" in result

    @pytest.mark.asyncio
    async def test_execute_web_search_missing_query(self, research_agent):
        """Returns error when query is missing."""
        result = await research_agent._execute_tool({
            "tool": "web_search",
        })

        assert "Error" in result
        assert "query" in result.lower()

    @pytest.mark.asyncio
    async def test_execute_web_fetch_missing_url(self, research_agent):
        """Returns error when url is missing."""
        result = await research_agent._execute_tool({
            "tool": "web_fetch",
        })

        assert "Error" in result
        assert "url" in result.lower()

    @pytest.mark.asyncio
    async def test_execute_web_search_handles_error(self, research_agent):
        """Handles web_search errors gracefully."""
        with patch(
            "reconly_core.agents.research.web_search",
            new_callable=AsyncMock,
        ) as mock_search:
            mock_search.side_effect = Exception("Search failed")

            result = await research_agent._execute_tool({
                "tool": "web_search",
                "query": "test",
            })

            assert "error" in result.lower()

    @pytest.mark.asyncio
    async def test_execute_web_fetch_handles_error(self, research_agent):
        """Handles web_fetch errors gracefully."""
        with patch(
            "reconly_core.agents.research.web_fetch",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.side_effect = Exception("Fetch failed")

            result = await research_agent._execute_tool({
                "tool": "web_fetch",
                "url": "https://example.com",
            })

            assert "error" in result.lower()


# =============================================================================
# Run Loop Tests
# =============================================================================


class TestRunLoop:
    """Tests for the main run() method."""

    @pytest.mark.asyncio
    async def test_run_immediate_final_answer(self, mock_summarizer, agent_settings):
        """Agent returns immediately when LLM gives final answer."""
        # LLM returns final answer on first call
        mock_summarizer.summarize.return_value = {
            "summary": '''```json
{
  "title": "Test Research",
  "content": "Here are my findings.",
  "sources": ["https://example.com"]
}
```''',
            "model_info": {"input_tokens": 100, "output_tokens": 50},
        }

        agent = ResearchAgent(
            summarizer=mock_summarizer,
            settings=agent_settings,
            max_iterations=5,
        )

        result = await agent.run("Test topic")

        assert result.title == "Test Research"
        assert result.content == "Here are my findings."
        assert result.sources == ["https://example.com"]
        assert result.iterations == 1
        assert len(result.tool_calls) == 0

    @pytest.mark.asyncio
    async def test_run_with_tool_calls(self, mock_summarizer, agent_settings):
        """Agent executes tool calls before final answer."""
        responses = [
            # First call: search
            {
                "summary": '{"tool": "web_search", "query": "python testing"}',
                "model_info": {"input_tokens": 100, "output_tokens": 30},
            },
            # Second call: fetch
            {
                "summary": '{"tool": "web_fetch", "url": "https://example.com/article"}',
                "model_info": {"input_tokens": 200, "output_tokens": 30},
            },
            # Third call: final answer
            {
                "summary": '''```json
{
  "title": "Python Testing Guide",
  "content": "Testing in Python is important.",
  "sources": ["https://example.com/article"]
}
```''',
                "model_info": {"input_tokens": 300, "output_tokens": 100},
            },
        ]
        mock_summarizer.summarize.side_effect = responses

        agent = ResearchAgent(
            summarizer=mock_summarizer,
            settings=agent_settings,
            max_iterations=5,
        )

        from reconly_core.agents.fetch import FetchResult

        with patch(
            "reconly_core.agents.research.web_search",
            new_callable=AsyncMock,
        ) as mock_search, patch(
            "reconly_core.agents.research.web_fetch",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_search.return_value = "Search Results:\n\n1. **Article**\n   URL: https://example.com/article"
            mock_fetch.return_value = FetchResult(
                url="https://example.com/article",
                title="Article",
                content="Article content",
                truncated=False,
            )

            result = await agent.run("How to test Python code?")

        assert result.title == "Python Testing Guide"
        assert result.iterations == 3
        assert len(result.tool_calls) == 2
        assert result.tool_calls[0]["tool"] == "web_search"
        assert result.tool_calls[1]["tool"] == "web_fetch"
        # Sources from fetch should be tracked
        assert "https://example.com/article" in result.sources

    @pytest.mark.asyncio
    async def test_run_tracks_tokens(self, mock_summarizer, agent_settings):
        """Agent tracks tokens across iterations."""
        responses = [
            {
                "summary": '{"tool": "web_search", "query": "test"}',
                "model_info": {"input_tokens": 100, "output_tokens": 20},
            },
            {
                "summary": '{"title": "Result", "content": "Done", "sources": []}',
                "model_info": {"input_tokens": 200, "output_tokens": 50},
            },
        ]
        mock_summarizer.summarize.side_effect = responses

        agent = ResearchAgent(
            summarizer=mock_summarizer,
            settings=agent_settings,
        )

        with patch(
            "reconly_core.agents.research.web_search",
            new_callable=AsyncMock,
        ) as mock_search:
            mock_search.return_value = "Results"

            await agent.run("Test")

        assert agent.total_tokens_in == 300  # 100 + 200
        assert agent.total_tokens_out == 70  # 20 + 50

    @pytest.mark.asyncio
    async def test_run_max_iterations_timeout(self, mock_summarizer, agent_settings):
        """Agent returns timeout result when max iterations reached."""
        # LLM always returns search (never final answer)
        mock_summarizer.summarize.return_value = {
            "summary": '{"tool": "web_search", "query": "more info"}',
            "model_info": {"input_tokens": 100, "output_tokens": 20},
        }

        agent = ResearchAgent(
            summarizer=mock_summarizer,
            settings=agent_settings,
            max_iterations=3,
        )

        with patch(
            "reconly_core.agents.research.web_search",
            new_callable=AsyncMock,
        ) as mock_search:
            mock_search.return_value = "Results"

            result = await agent.run("Test topic")

        assert result.iterations == 3
        assert "Max Iterations Reached" in result.title
        assert len(result.tool_calls) == 3  # 3 search calls

    @pytest.mark.asyncio
    async def test_run_handles_malformed_response(self, mock_summarizer, agent_settings):
        """Agent handles LLM responses without valid tool or answer."""
        responses = [
            # First call: invalid response (no tool or answer)
            {
                "summary": "I'm thinking about this...",
                "model_info": {"input_tokens": 100, "output_tokens": 20},
            },
            # Second call: final answer
            {
                "summary": '{"title": "Answer", "content": "Here it is", "sources": []}',
                "model_info": {"input_tokens": 200, "output_tokens": 50},
            },
        ]
        mock_summarizer.summarize.side_effect = responses

        agent = ResearchAgent(
            summarizer=mock_summarizer,
            settings=agent_settings,
        )

        result = await agent.run("Test")

        assert result.title == "Answer"
        assert result.iterations == 2

    @pytest.mark.asyncio
    async def test_run_sources_from_fetches(self, mock_summarizer, agent_settings):
        """Agent collects sources from web_fetch calls."""
        responses = [
            {"summary": '{"tool": "web_fetch", "url": "https://site1.com"}', "model_info": {}},
            {"summary": '{"tool": "web_fetch", "url": "https://site2.com"}', "model_info": {}},
            {"summary": '{"title": "Done", "content": "Result", "sources": ["https://site3.com"]}', "model_info": {}},
        ]
        mock_summarizer.summarize.side_effect = responses

        agent = ResearchAgent(
            summarizer=mock_summarizer,
            settings=agent_settings,
        )

        from reconly_core.agents.fetch import FetchResult

        with patch(
            "reconly_core.agents.research.web_fetch",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = FetchResult(
                url="test",
                title="Test",
                content="Content",
                truncated=False,
            )

            result = await agent.run("Research topic")

        # Should have all three sources (2 from fetch + 1 from final answer)
        assert "https://site1.com" in result.sources
        assert "https://site2.com" in result.sources
        assert "https://site3.com" in result.sources


# =============================================================================
# Build Prompt Tests
# =============================================================================


class TestBuildPrompt:
    """Tests for _build_initial_prompt method."""

    def test_build_initial_prompt_structure(self, research_agent):
        """Initial prompt has correct structure."""
        messages = research_agent._build_initial_prompt("Research AI trends")

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_build_initial_prompt_system_content(self, research_agent):
        """System message contains agent prompt."""
        messages = research_agent._build_initial_prompt("Test")

        assert AGENT_SYSTEM_PROMPT in messages[0]["content"]

    def test_build_initial_prompt_user_content(self, research_agent):
        """User message contains research topic."""
        messages = research_agent._build_initial_prompt("Python best practices")

        assert "Python best practices" in messages[1]["content"]
        assert "Research" in messages[1]["content"]


# =============================================================================
# LLM Call Tests
# =============================================================================


class TestCallLLM:
    """Tests for _call_llm method."""

    def test_call_llm_formats_messages(self, research_agent):
        """LLM call formats messages correctly."""
        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "User message"},
            {"role": "assistant", "content": "Assistant response"},
        ]

        research_agent._call_llm(messages)

        call_args = research_agent.summarizer.summarize.call_args
        user_prompt = call_args.kwargs["user_prompt"]

        assert "System prompt" in user_prompt
        assert "User: User message" in user_prompt
        assert "Assistant: Assistant response" in user_prompt

    def test_call_llm_returns_summary(self, research_agent):
        """LLM call returns summary from response."""
        research_agent.summarizer.summarize.return_value = {
            "summary": "Expected response",
            "model_info": {},
        }

        result = research_agent._call_llm([{"role": "user", "content": "test"}])

        assert result == "Expected response"


# =============================================================================
# Timeout Result Tests
# =============================================================================


class TestTimeoutResult:
    """Tests for _timeout_result method."""

    def test_timeout_result_structure(self, research_agent):
        """Timeout result has correct structure."""
        messages = [
            {"role": "user", "content": "Question"},
            {"role": "assistant", "content": "Response 1"},
            {"role": "user", "content": "Tool result"},
            {"role": "assistant", "content": "Response 2"},
        ]
        tool_calls = [{"tool": "web_search", "query": "test"}]
        sources = ["https://example.com"]

        result = research_agent._timeout_result(messages, tool_calls, sources)

        assert "Max Iterations" in result.title
        assert result.iterations == research_agent.max_iterations
        assert result.tool_calls == tool_calls
        assert result.sources == sources

    def test_timeout_result_includes_responses(self, research_agent):
        """Timeout result includes assistant responses."""
        messages = [
            {"role": "assistant", "content": "First finding"},
            {"role": "assistant", "content": "Second finding"},
            {"role": "assistant", "content": "Third finding"},
        ]

        result = research_agent._timeout_result(messages, [], [])

        assert "First finding" in result.content
        assert "Second finding" in result.content
        assert "Third finding" in result.content

    def test_timeout_result_empty_messages(self, research_agent):
        """Timeout result handles empty messages."""
        result = research_agent._timeout_result([], [], [])

        assert "incomplete" in result.content.lower()


# =============================================================================
# System Prompt Tests
# =============================================================================


class TestSystemPrompt:
    """Tests for AGENT_SYSTEM_PROMPT constant."""

    def test_system_prompt_contains_tools(self):
        """System prompt describes available tools."""
        assert "web_search" in AGENT_SYSTEM_PROMPT
        assert "web_fetch" in AGENT_SYSTEM_PROMPT

    def test_system_prompt_contains_output_format(self):
        """System prompt describes output format."""
        assert "title" in AGENT_SYSTEM_PROMPT
        assert "content" in AGENT_SYSTEM_PROMPT
        assert "sources" in AGENT_SYSTEM_PROMPT

    def test_system_prompt_contains_tool_format(self):
        """System prompt describes tool call format."""
        assert '"tool"' in AGENT_SYSTEM_PROMPT
        assert '"query"' in AGENT_SYSTEM_PROMPT
        assert '"url"' in AGENT_SYSTEM_PROMPT
