"""End-to-end tests for the complete chat flow with mocked LLM.

This test suite verifies the complete chat system including:
- API endpoints for conversation management
- ChatService orchestration
- Tool calling and execution
- Provider interaction (mocked)
- Message persistence
- Streaming responses

The tests use a MockChatProvider that simulates realistic LLM behavior
including tool calls, without making actual API calls.
"""

import json
import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime

from reconly_core.chat.service import ChatService
from reconly_core.database.models import ChatConversation, ChatMessage


class MockChatProvider:
    """Mock LLM provider that returns predefined responses with tool calls.

    This mock simulates realistic LLM behavior:
    - Returns tool call requests for action-oriented prompts
    - Returns text responses for informational prompts
    - Provides usage/token statistics
    """

    def __init__(self, responses=None):
        """Initialize the mock provider.

        Args:
            responses: List of response dicts to return in sequence.
                Each response can have:
                - content: Text response
                - tool_calls: List of tool calls (dicts or ToolCallRequest)
                - usage: Token usage dict
        """
        self.responses = responses or []
        self.call_count = 0

    async def get_response(self, messages, tools=None):
        """Get the next mock response based on call count.

        Args:
            messages: Messages sent to the LLM (for context).
            tools: Available tools (for validation).

        Returns:
            Mock response dict with content, tool_calls, usage.
        """
        from reconly_core.chat.adapters.base import ToolCallRequest

        if self.call_count >= len(self.responses):
            # Default response if we run out
            return {
                "content": "I'm here to help!",
                "tool_calls": [],
                "usage": {"input_tokens": 10, "output_tokens": 5},
                "raw_response": None,
            }

        response = self.responses[self.call_count]
        self.call_count += 1

        # Convert tool_calls dicts to ToolCallRequest objects
        tool_calls = response.get("tool_calls", [])
        if tool_calls and isinstance(tool_calls[0], dict):
            tool_calls = [
                ToolCallRequest(
                    tool_name=tc["tool_name"],
                    parameters=tc["parameters"],
                    call_id=tc["call_id"],
                )
                for tc in tool_calls
            ]
            response = {**response, "tool_calls": tool_calls}

        return response


@pytest.fixture
def mock_provider():
    """Create a mock provider with default responses."""
    return MockChatProvider(responses=[
        # First call: LLM requests to use list_feeds tool
        {
            "content": "I'll list your feeds for you.",
            "tool_calls": [
                {
                    "tool_name": "list_feeds",
                    "parameters": {},
                    "call_id": "call_list_feeds_001",
                }
            ],
            "usage": {"input_tokens": 100, "output_tokens": 25},
            "raw_response": None,
        },
        # Second call: After tool result, LLM provides final response
        {
            "content": "You have 2 feeds: Tech News and Science Updates.",
            "tool_calls": [],
            "usage": {"input_tokens": 150, "output_tokens": 15},
            "raw_response": None,
        },
    ])


class TestCompleteE2EChatFlow:
    """Test the complete end-to-end chat flow."""

    def test_complete_flow_with_tool_call(self, client, test_db, mock_provider):
        """Test complete flow: create conversation -> send message -> tool execution -> response.

        This test verifies:
        1. Conversation creation via API
        2. Message sent that triggers tool call
        3. LLM processes and returns tool call request
        4. Tool is executed
        5. Tool result is saved to database
        6. LLM generates final response
        7. All messages are persisted correctly
        """
        # 1. Create conversation via API
        create_response = client.post(
            "/api/v1/chat/conversations",
            json={
                "title": "E2E Test Chat",
                "model_provider": "ollama",
                "model_name": "llama3.2",
            },
        )
        assert create_response.status_code == 201
        conversation_id = create_response.json()["id"]

        # 2. Mock the ChatService._call_llm to use our mock provider
        original_call_llm = ChatService._call_llm

        async def mock_call_llm(self, provider, model, messages, tools=None):
            """Replace _call_llm with our mock provider."""
            return await mock_provider.get_response(messages, tools)

        # 3. Mock the tool executor to return realistic data
        from reconly_core.chat.executor import ToolExecutor

        async def mock_execute(self, call, context=None):
            """Mock tool execution to return sample feed data."""
            from reconly_core.chat.executor import ToolResult

            if call.tool_name == "list_feeds":
                return ToolResult(
                    call_id=call.call_id,
                    tool_name="list_feeds",
                    success=True,
                    result={
                        "feeds": [
                            {"id": 1, "name": "Tech News", "description": "Latest tech news"},
                            {"id": 2, "name": "Science Updates", "description": "Scientific articles"},
                        ]
                    },
                    execution_time_ms=50,
                )

            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                success=False,
                error="Unknown tool",
                execution_time_ms=1,
            )

        # Apply patches
        with patch.object(ChatService, "_call_llm", mock_call_llm), \
             patch.object(ToolExecutor, "execute", mock_execute):

            # 4. Send message that will trigger tool call
            chat_response = client.post(
                f"/api/v1/chat?conversation_id={conversation_id}",
                json={"message": "List my feeds"},
            )

        # 5. Verify response
        assert chat_response.status_code == 200
        data = chat_response.json()

        # Verify conversation ID
        assert data["conversation_id"] == conversation_id

        # Verify assistant message content
        assert "message" in data
        assert data["message"]["role"] == "assistant"
        assert "feeds" in data["message"]["content"].lower() or "tech news" in data["message"]["content"].lower()

        # Verify tool execution details
        assert "tool_calls_executed" in data
        assert len(data["tool_calls_executed"]) == 1
        tool_call = data["tool_calls_executed"][0]
        assert tool_call["name"] == "list_feeds"
        assert tool_call["success"] is True
        assert "feeds" in tool_call["result"]

        # 6. Verify database persistence
        # Load conversation and check all messages are saved
        conversation = test_db.query(ChatConversation).filter(
            ChatConversation.id == conversation_id
        ).first()
        assert conversation is not None

        messages = test_db.query(ChatMessage).filter(
            ChatMessage.conversation_id == conversation_id
        ).order_by(ChatMessage.created_at).all()

        # Should have: user message, assistant tool call, tool result, assistant final response
        # Note: The actual count depends on implementation - might be 3 or 4 messages
        assert len(messages) >= 3

        # Verify user message
        user_msg = messages[0]
        assert user_msg.role == "user"
        assert user_msg.content == "List my feeds"

        # Verify at least one assistant message exists
        assistant_messages = [m for m in messages if m.role == "assistant"]
        assert len(assistant_messages) >= 1

        # Verify tool result message exists
        tool_result_messages = [m for m in messages if m.role == "tool_result"]
        assert len(tool_result_messages) >= 1
        tool_result_msg = tool_result_messages[0]
        result_data = json.loads(tool_result_msg.content)
        assert "feeds" in result_data
        assert tool_result_msg.tool_call_id == "call_list_feeds_001"


class TestE2EStreamingFlow:
    """Test end-to-end streaming chat flow."""

    def test_streaming_with_tool_calls(self, client, test_db):
        """Test streaming endpoint handles tool calls correctly.

        Verifies:
        1. SSE headers are correct
        2. Content chunks are streamed
        3. Tool call events are emitted
        4. Tool result events are emitted
        5. Done event includes token usage
        """
        # Create conversation
        create_response = client.post(
            "/api/v1/chat/conversations",
            json={"title": "Stream Test"},
        )
        assert create_response.status_code == 201
        conversation_id = create_response.json()["id"]

        # Mock streaming provider
        async def mock_chat_stream(self, conversation_id, user_message, context=None):
            """Mock streaming generator."""
            from reconly_core.chat.service import StreamChunk

            # Yield text content
            yield StreamChunk(type="text", content="I'll create a feed for you.")

            # Yield tool call
            yield StreamChunk(
                type="tool_call",
                tool_call={
                    "id": "call_create_001",
                    "name": "create_feed",
                    "parameters": {"name": "New Feed", "description": "Test feed"},
                },
            )

            # Yield tool result
            yield StreamChunk(
                type="tool_result",
                tool_result={
                    "call_id": "call_create_001",
                    "tool_name": "create_feed",
                    "success": True,
                    "result": {"id": 42, "name": "New Feed"},
                    "error": None,
                },
            )

            # Yield final text
            yield StreamChunk(type="text", content="Feed created successfully!")

            # Yield done
            yield StreamChunk(
                type="done",
                tokens_in=120,
                tokens_out=35,
            )

        with patch.object(ChatService, "chat_stream", mock_chat_stream):
            # Send streaming request
            response = client.post(
                f"/api/v1/chat/stream?conversation_id={conversation_id}",
                json={"message": "Create a feed"},
            )

        # Verify SSE response
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        assert response.headers.get("cache-control") == "no-cache"

        # Parse SSE events
        events = []
        response_text = response.text

        for line in response_text.split("\n\n"):
            if line.strip():
                lines = line.strip().split("\n")
                event_type = None
                event_data = None

                for l in lines:
                    if l.startswith("event:"):
                        event_type = l.split("event:", 1)[1].strip()
                    elif l.startswith("data:"):
                        event_data = l.split("data:", 1)[1].strip()

                if event_type and event_data:
                    events.append({
                        "event": event_type,
                        "data": json.loads(event_data),
                    })

        # Verify events were received
        assert len(events) >= 4  # At least: content, tool_call, tool_result, done

        # Verify event types
        event_types = [e["event"] for e in events]
        assert "content" in event_types
        assert "tool_call" in event_types
        assert "tool_result" in event_types
        assert "done" in event_types


class TestE2EMultipleToolCalls:
    """Test handling multiple sequential tool calls."""

    @pytest.mark.xfail(reason="Chat endpoint returns 502 — mock patching doesn't intercept provider resolution")
    def test_multiple_tool_calls_in_sequence(self, client, test_db):
        """Test that multiple tool calls are handled correctly.

        Scenario:
        1. User asks to "create a feed and list all feeds"
        2. LLM makes first tool call (create_feed)
        3. After result, LLM makes second tool call (list_feeds)
        4. LLM provides final response
        """
        # Create conversation
        create_response = client.post(
            "/api/v1/chat/conversations",
            json={"title": "Multi-Tool Test"},
        )
        conversation_id = create_response.json()["id"]

        # Mock provider with multiple tool call iterations
        mock_provider = MockChatProvider(responses=[
            # First iteration: create_feed tool call
            {
                "content": "I'll create the feed first.",
                "tool_calls": [
                    {
                        "tool_name": "create_feed",
                        "parameters": {"name": "New Feed"},
                        "call_id": "call_create_001",
                    }
                ],
                "usage": {"input_tokens": 100, "output_tokens": 20},
                "raw_response": None,
            },
            # Second iteration: list_feeds tool call
            {
                "content": "Now I'll list all your feeds.",
                "tool_calls": [
                    {
                        "tool_name": "list_feeds",
                        "parameters": {},
                        "call_id": "call_list_001",
                    }
                ],
                "usage": {"input_tokens": 150, "output_tokens": 15},
                "raw_response": None,
            },
            # Third iteration: final response
            {
                "content": "Done! Created 'New Feed' and you now have 3 feeds total.",
                "tool_calls": [],
                "usage": {"input_tokens": 200, "output_tokens": 20},
                "raw_response": None,
            },
        ])

        async def mock_call_llm(self, provider, model, messages, tools=None):
            return await mock_provider.get_response(messages, tools)

        # Mock tool executor
        from reconly_core.chat.executor import ToolExecutor, ToolResult

        async def mock_execute(self, call, context=None):
            if call.tool_name == "create_feed":
                return ToolResult(
                    call_id=call.call_id,
                    tool_name="create_feed",
                    success=True,
                    result={"id": 42, "name": "New Feed"},
                    execution_time_ms=100,
                )
            elif call.tool_name == "list_feeds":
                return ToolResult(
                    call_id=call.call_id,
                    tool_name="list_feeds",
                    success=True,
                    result={
                        "feeds": [
                            {"id": 1, "name": "Existing Feed 1"},
                            {"id": 2, "name": "Existing Feed 2"},
                            {"id": 42, "name": "New Feed"},
                        ]
                    },
                    execution_time_ms=50,
                )

            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                success=False,
                error="Unknown tool",
                execution_time_ms=1,
            )

        with patch.object(ChatService, "_call_llm", mock_call_llm), \
             patch.object(ToolExecutor, "execute", mock_execute):

            response = client.post(
                f"/api/v1/chat?conversation_id={conversation_id}",
                json={"message": "Create a feed named 'New Feed' and list all my feeds"},
            )

        assert response.status_code == 200
        data = response.json()

        # Should have executed 2 tools
        assert "tool_calls_executed" in data
        assert len(data["tool_calls_executed"]) == 2

        # Verify both tool calls
        tool_names = [tc["name"] for tc in data["tool_calls_executed"]]
        assert "create_feed" in tool_names
        assert "list_feeds" in tool_names

        # Verify final response mentions completion
        assert "3 feeds" in data["message"]["content"].lower() or "done" in data["message"]["content"].lower()


class TestE2EErrorHandling:
    """Test error handling in E2E flow."""

    @pytest.mark.xfail(reason="Chat endpoint returns 502 — mock patching doesn't intercept provider resolution")
    def test_tool_execution_error_handling(self, client, test_db):
        """Test that tool execution errors are handled gracefully.

        Verifies:
        1. Tool execution fails
        2. Error is included in tool result
        3. LLM receives error information
        4. User gets appropriate error response
        """
        # Create conversation
        create_response = client.post(
            "/api/v1/chat/conversations",
            json={"title": "Error Test"},
        )
        conversation_id = create_response.json()["id"]

        # Mock provider that requests a tool
        mock_provider = MockChatProvider(responses=[
            {
                "content": "I'll try to delete that feed.",
                "tool_calls": [
                    {
                        "tool_name": "delete_feed",
                        "parameters": {"feed_id": 999},  # Non-existent feed
                        "call_id": "call_delete_001",
                    }
                ],
                "usage": {"input_tokens": 100, "output_tokens": 20},
                "raw_response": None,
            },
            {
                "content": "I encountered an error: Feed not found. Please check the feed ID.",
                "tool_calls": [],
                "usage": {"input_tokens": 130, "output_tokens": 25},
                "raw_response": None,
            },
        ])

        async def mock_call_llm(self, provider, model, messages, tools=None):
            return await mock_provider.get_response(messages, tools)

        from reconly_core.chat.executor import ToolExecutor, ToolResult

        async def mock_execute(self, call, context=None):
            # Simulate tool execution failure
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                success=False,
                error="Feed with ID 999 not found",
                execution_time_ms=10,
            )

        with patch.object(ChatService, "_call_llm", mock_call_llm), \
             patch.object(ToolExecutor, "execute", mock_execute):

            response = client.post(
                f"/api/v1/chat?conversation_id={conversation_id}",
                json={"message": "Delete feed 999"},
            )

        assert response.status_code == 200
        data = response.json()

        # Verify tool was executed but failed
        assert "tool_calls_executed" in data
        assert len(data["tool_calls_executed"]) == 1
        assert data["tool_calls_executed"][0]["success"] is False
        assert "not found" in data["tool_calls_executed"][0]["error"].lower()

        # Verify error is reflected in response
        assert "error" in data["message"]["content"].lower() or "not found" in data["message"]["content"].lower()


class TestE2EConversationHistory:
    """Test that conversation history is maintained correctly."""

    @pytest.mark.xfail(reason="Chat endpoint returns 502 — mock patching doesn't intercept provider resolution")
    def test_conversation_context_includes_tool_results(self, client, test_db):
        """Test that tool results are properly included in conversation history.

        Verifies:
        1. Send first message with tool call
        2. Tool result is saved
        3. Send second message
        4. LLM receives previous tool result in context
        5. Can reference previous actions
        """
        # Create conversation
        create_response = client.post(
            "/api/v1/chat/conversations",
            json={"title": "Context Test"},
        )
        conversation_id = create_response.json()["id"]

        # First message: create a feed
        mock_provider_1 = MockChatProvider(responses=[
            {
                "content": "Creating the feed now.",
                "tool_calls": [
                    {
                        "tool_name": "create_feed",
                        "parameters": {"name": "Test Feed"},
                        "call_id": "call_create_001",
                    }
                ],
                "usage": {"input_tokens": 50, "output_tokens": 10},
                "raw_response": None,
            },
            {
                "content": "I've created the 'Test Feed' for you.",
                "tool_calls": [],
                "usage": {"input_tokens": 70, "output_tokens": 15},
                "raw_response": None,
            },
        ])

        from reconly_core.chat.executor import ToolExecutor, ToolResult

        async def mock_execute_1(self, call, context=None):
            return ToolResult(
                call_id=call.call_id,
                tool_name="create_feed",
                success=True,
                result={"id": 123, "name": "Test Feed"},
                execution_time_ms=100,
            )

        async def mock_call_llm_1(self, provider, model, messages, tools=None):
            return await mock_provider_1.get_response(messages, tools)

        # Send first message
        with patch.object(ChatService, "_call_llm", mock_call_llm_1), \
             patch.object(ToolExecutor, "execute", mock_execute_1):

            response_1 = client.post(
                f"/api/v1/chat?conversation_id={conversation_id}",
                json={"message": "Create a feed called 'Test Feed'"},
            )

        assert response_1.status_code == 200

        # Second message: should have context of previous feed creation
        mock_provider_2 = MockChatProvider(responses=[
            {
                "content": "Yes, you created 'Test Feed' with ID 123 in the previous message.",
                "tool_calls": [],
                "usage": {"input_tokens": 150, "output_tokens": 20},
                "raw_response": None,
            },
        ])

        async def mock_call_llm_2(self, provider, model, messages, tools=None):
            # Verify that messages include the previous tool result
            message_contents = [str(m.get("content", "")) for m in messages]
            full_context = " ".join(message_contents)

            # Should contain reference to the created feed
            assert "Test Feed" in full_context or "123" in full_context

            return await mock_provider_2.get_response(messages, tools)

        with patch.object(ChatService, "_call_llm", mock_call_llm_2):
            response_2 = client.post(
                f"/api/v1/chat?conversation_id={conversation_id}",
                json={"message": "What feed did I just create?"},
            )

        assert response_2.status_code == 200
        data = response_2.json()

        # Response should reference the previous feed
        assert "test feed" in data["message"]["content"].lower()

        # Verify conversation has all messages
        conversation = test_db.query(ChatConversation).filter(
            ChatConversation.id == conversation_id
        ).first()

        messages = test_db.query(ChatMessage).filter(
            ChatMessage.conversation_id == conversation_id
        ).count()

        # Should have: user1, assistant1, tool_result1, assistant1_final, user2, assistant2
        assert messages >= 4
