"""Tests for chat API endpoints."""

import pytest
import json
from unittest.mock import patch

from reconly_core.chat.service import ChatService
from reconly_core.database.models import ChatConversation


class TestChatCompletionEndpoint:
    """Test POST /api/v1/chat endpoint."""

    @pytest.fixture
    def conversation(self, test_db):
        """Create a test conversation."""
        from datetime import datetime

        conv = ChatConversation(
            title="Test Chat",
            model_provider="ollama",
            model_name="llama3.2",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        test_db.add(conv)
        test_db.commit()
        test_db.refresh(conv)
        return conv

    def test_chat_completion_success(self, client, conversation, test_db):
        """Test successful chat completion."""
        from datetime import datetime
        from reconly_core.database.models import ChatMessage

        # Mock the ChatService.chat method
        async def mock_chat(self, conversation_id, user_message, **kwargs):
            from reconly_core.chat.service import ChatResponse
            # The API expects an assistant message to exist after chat() completes
            # So we need to create one in the mock
            assistant_msg = ChatMessage(
                conversation_id=conversation_id,
                role="assistant",
                content="Here are your feeds: Feed 1, Feed 2",
                tokens_in=15,
                tokens_out=10,
                created_at=datetime.utcnow(),
            )
            self.db.add(assistant_msg)
            self.db.commit()

            return ChatResponse(
                content="Here are your feeds: Feed 1, Feed 2",
                tool_calls=[],
                tool_results=[],
                tokens_in=15,
                tokens_out=10,
                conversation_id=conversation_id,
            )

        with patch.object(ChatService, "chat", mock_chat):
            response = client.post(
                f"/api/v1/chat?conversation_id={conversation.id}",
                json={"message": "List my feeds"},
            )

        assert response.status_code == 200
        data = response.json()

        assert data["conversation_id"] == conversation.id
        assert "message" in data
        assert data["message"]["role"] == "assistant"
        assert "feeds" in data["message"]["content"].lower()

    def test_chat_completion_nonexistent_conversation(self, client):
        """Test chat with nonexistent conversation returns 404."""
        response = client.post(
            "/api/v1/chat?conversation_id=99999",
            json={"message": "Hello"},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_chat_completion_missing_message(self, client, conversation):
        """Test that missing message field is rejected."""
        response = client.post(
            f"/api/v1/chat?conversation_id={conversation.id}",
            json={},
        )

        assert response.status_code == 422  # Validation error

    def test_chat_completion_with_tool_calls(self, client, conversation, test_db):
        """Test chat completion with tool execution."""
        from datetime import datetime
        from reconly_core.chat.adapters.base import ToolCallRequest
        from reconly_core.chat.executor import ToolResult
        from reconly_core.database.models import ChatMessage

        tool_calls_data = [
            {
                "id": "call_123",
                "name": "create_feed",
                "parameters": {"name": "News"},
            }
        ]

        async def mock_chat(self, conversation_id, user_message, **kwargs):
            from reconly_core.chat.service import ChatResponse
            # Create assistant message that the API will look up
            assistant_msg = ChatMessage(
                conversation_id=conversation_id,
                role="assistant",
                content="I've created the feed for you.",
                tool_calls=tool_calls_data,
                tokens_in=20,
                tokens_out=15,
                created_at=datetime.utcnow(),
            )
            self.db.add(assistant_msg)
            self.db.commit()

            return ChatResponse(
                content="I've created the feed for you.",
                tool_calls=[
                    ToolCallRequest(
                        tool_name="create_feed",
                        parameters={"name": "News"},
                        call_id="call_123",
                    )
                ],
                tool_results=[
                    ToolResult(
                        call_id="call_123",
                        tool_name="create_feed",
                        success=True,
                        result={"id": 5, "name": "News"},
                        execution_time_ms=100,
                    )
                ],
                tokens_in=20,
                tokens_out=15,
                conversation_id=conversation_id,
            )

        with patch.object(ChatService, "chat", mock_chat):
            response = client.post(
                f"/api/v1/chat?conversation_id={conversation.id}",
                json={"message": "Create a news feed"},
            )

        assert response.status_code == 200
        data = response.json()

        assert "tool_calls_executed" in data
        assert len(data["tool_calls_executed"]) == 1
        assert data["tool_calls_executed"][0]["name"] == "create_feed"
        assert data["tool_calls_executed"][0]["success"] is True


class TestChatStreamEndpoint:
    """Test POST /api/v1/chat/stream endpoint (SSE)."""

    @pytest.fixture
    def conversation(self, test_db):
        """Create a test conversation."""
        from datetime import datetime

        conv = ChatConversation(
            title="Stream Test",
            model_provider=None,
            model_name=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        test_db.add(conv)
        test_db.commit()
        test_db.refresh(conv)
        return conv

    def test_chat_stream_headers(self, client, conversation):
        """Test that streaming response has correct headers."""
        # Mock the chat_stream generator
        async def mock_stream(*args, **kwargs):
            from reconly_core.chat.service import StreamChunk
            yield StreamChunk(type="text", content="Hello")
            yield StreamChunk(type="done", tokens_in=10, tokens_out=5)

        with patch.object(ChatService, "chat_stream", new=mock_stream):
            response = client.post(
                f"/api/v1/chat/stream?conversation_id={conversation.id}",
                json={"message": "Hi"},
            )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        assert response.headers.get("cache-control") == "no-cache"

    def test_chat_stream_nonexistent_conversation(self, client):
        """Test streaming with nonexistent conversation returns 404."""
        response = client.post(
            "/api/v1/chat/stream?conversation_id=99999",
            json={"message": "Hello"},
        )

        assert response.status_code == 404


class TestConversationCRUD:
    """Test conversation management endpoints."""

    def test_create_conversation(self, client):
        """Test POST /api/v1/chat/conversations."""
        response = client.post(
            "/api/v1/chat/conversations",
            json={
                "title": "New Chat",
                "model_provider": "anthropic",
                "model_name": "claude-sonnet-4-20250514",
            },
        )

        assert response.status_code == 201
        data = response.json()

        assert data["title"] == "New Chat"
        assert data["model_provider"] == "anthropic"
        assert data["model_name"] == "claude-sonnet-4-20250514"
        assert "id" in data
        assert data["message_count"] == 0

    def test_create_conversation_defaults(self, client):
        """Test creating conversation with default values."""
        response = client.post(
            "/api/v1/chat/conversations",
            json={},
        )

        assert response.status_code == 201
        data = response.json()

        assert data["title"] == "New Conversation"
        assert data["model_provider"] is None

    def test_list_conversations(self, client, test_db):
        """Test GET /api/v1/chat/conversations."""
        # Create some conversations
        service = ChatService(db=test_db)
        import asyncio
        asyncio.run(service.create_conversation(title="Chat 1"))
        asyncio.run(service.create_conversation(title="Chat 2"))

        response = client.get("/api/v1/chat/conversations")

        assert response.status_code == 200
        data = response.json()

        assert data["total"] >= 2
        assert len(data["items"]) >= 2

    def test_list_conversations_pagination(self, client, test_db):
        """Test conversation list pagination."""
        # Create conversations
        service = ChatService(db=test_db)
        import asyncio
        for i in range(5):
            asyncio.run(service.create_conversation(title=f"Chat {i}"))

        # Get first page
        response = client.get("/api/v1/chat/conversations?limit=2&offset=0")

        assert response.status_code == 200
        data = response.json()

        assert data["total"] >= 5
        assert len(data["items"]) == 2

    def test_get_conversation(self, client, test_db):
        """Test GET /api/v1/chat/conversations/{id}."""
        # Create a conversation with messages
        service = ChatService(db=test_db)
        import asyncio
        conv = asyncio.run(service.create_conversation(title="Detail Test"))
        service._save_message(conv.id, "user", "Hello")
        service._save_message(conv.id, "assistant", "Hi there")

        response = client.get(f"/api/v1/chat/conversations/{conv.id}")

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == conv.id
        assert data["title"] == "Detail Test"
        assert data["message_count"] == 2
        assert len(data["messages"]) == 2

    def test_get_nonexistent_conversation(self, client):
        """Test getting nonexistent conversation returns 404."""
        response = client.get("/api/v1/chat/conversations/99999")

        assert response.status_code == 404

    def test_update_conversation(self, client, test_db):
        """Test PATCH /api/v1/chat/conversations/{id}."""
        # Create a conversation
        service = ChatService(db=test_db)
        import asyncio
        conv = asyncio.run(service.create_conversation(title="Old Title"))

        # Update it
        response = client.patch(
            f"/api/v1/chat/conversations/{conv.id}",
            json={"title": "New Title"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["title"] == "New Title"

    def test_update_conversation_model(self, client, test_db):
        """Test updating conversation model settings."""
        service = ChatService(db=test_db)
        import asyncio
        conv = asyncio.run(service.create_conversation())

        response = client.patch(
            f"/api/v1/chat/conversations/{conv.id}",
            json={
                "model_provider": "openai",
                "model_name": "gpt-4",
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["model_provider"] == "openai"
        assert data["model_name"] == "gpt-4"

    def test_delete_conversation(self, client, test_db):
        """Test DELETE /api/v1/chat/conversations/{id}."""
        # Create a conversation
        service = ChatService(db=test_db)
        import asyncio
        conv = asyncio.run(service.create_conversation(title="To Delete"))

        # Delete it
        response = client.delete(f"/api/v1/chat/conversations/{conv.id}")

        assert response.status_code == 204

        # Verify it's gone
        response = client.get(f"/api/v1/chat/conversations/{conv.id}")
        assert response.status_code == 404

    def test_delete_nonexistent_conversation(self, client):
        """Test deleting nonexistent conversation returns 404."""
        response = client.delete("/api/v1/chat/conversations/99999")

        assert response.status_code == 404


class TestChatAPIRateLimiting:
    """Test rate limiting on chat endpoints."""

    def test_chat_rate_limit(self, client, test_db):
        """Test that chat endpoint is rate limited."""
        # Create conversation
        service = ChatService(db=test_db)
        import asyncio
        conv = asyncio.run(service.create_conversation())

        # Mock chat to return quickly
        async def mock_chat(*args, **kwargs):
            from reconly_core.chat.service import ChatResponse
            return ChatResponse(
                content="Response",
                conversation_id=conv.id,
            )

        with patch.object(ChatService, "chat", new=mock_chat):
            # Make many requests (rate limit is 30/min)
            # This test is tricky in practice, might need adjustment
            # based on how rate limiting is implemented
            pass  # Placeholder for rate limit test


class TestChatAPIErrorHandling:
    """Test error handling in chat API."""

    @pytest.fixture
    def conversation(self, test_db):
        """Create a test conversation."""
        from datetime import datetime

        conv = ChatConversation(
            title="New Conversation",
            model_provider=None,
            model_name=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        test_db.add(conv)
        test_db.commit()
        test_db.refresh(conv)
        return conv

    def test_provider_error_returns_502(self, client, conversation):
        """Test that provider errors return 502."""
        from reconly_core.chat.service import ProviderError

        async def mock_chat_error(*args, **kwargs):
            raise ProviderError("LLM API is down")

        with patch.object(ChatService, "chat", new=mock_chat_error):
            response = client.post(
                f"/api/v1/chat?conversation_id={conversation.id}",
                json={"message": "Hello"},
            )

        assert response.status_code == 502
        assert "LLM API is down" in response.json()["detail"]

    def test_generic_error_returns_500(self, client, conversation):
        """Test that unexpected errors return 500."""
        async def mock_chat_error(*args, **kwargs):
            raise Exception("Unexpected error")

        with patch.object(ChatService, "chat", new=mock_chat_error):
            response = client.post(
                f"/api/v1/chat?conversation_id={conversation.id}",
                json={"message": "Hello"},
            )

        assert response.status_code == 500
