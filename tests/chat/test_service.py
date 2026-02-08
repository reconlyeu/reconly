"""Tests for ChatService."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from reconly_core.chat.service import (
    ChatService,
    ConversationNotFoundError,
)
from reconly_core.chat.tools import ToolRegistry, ToolDefinition
from reconly_core.database.models import ChatConversation, ChatMessage


class TestChatServiceConversationCRUD:
    """Test conversation CRUD operations."""

    @pytest.fixture
    def service(self, db_session):
        """Create a ChatService instance."""
        return ChatService(db=db_session)

    @pytest.mark.asyncio
    async def test_create_conversation(self, service, db_session):
        """Test creating a new conversation."""
        conv = await service.create_conversation(
            title="Test Chat",
            model_provider="ollama",
            model_name="llama3.2",
        )

        assert conv.id is not None
        assert conv.title == "Test Chat"
        assert conv.model_provider == "ollama"
        assert conv.model_name == "llama3.2"
        assert conv.created_at is not None
        assert conv.updated_at is not None

        # Verify it's in the database
        db_conv = db_session.query(ChatConversation).filter_by(id=conv.id).first()
        assert db_conv is not None
        assert db_conv.title == "Test Chat"

    @pytest.mark.asyncio
    async def test_create_conversation_defaults(self, service):
        """Test creating conversation with default values."""
        conv = await service.create_conversation()

        assert conv.title == "New Conversation"
        assert conv.model_provider is None
        assert conv.model_name is None

    @pytest.mark.asyncio
    async def test_get_conversation(self, service, db_session):
        """Test retrieving an existing conversation."""
        # Create a conversation
        created = await service.create_conversation(title="My Chat")

        # Retrieve it
        conv = await service.get_conversation(created.id)

        assert conv.id == created.id
        assert conv.title == "My Chat"

    @pytest.mark.asyncio
    async def test_get_nonexistent_conversation_raises(self, service):
        """Test that getting nonexistent conversation raises error."""
        with pytest.raises(ConversationNotFoundError):
            await service.get_conversation(99999)

    @pytest.mark.asyncio
    async def test_list_conversations(self, service):
        """Test listing conversations with pagination."""
        # Create multiple conversations
        await service.create_conversation(title="Chat 1")
        await service.create_conversation(title="Chat 2")
        await service.create_conversation(title="Chat 3")

        # List all
        convs, total = await service.list_conversations(limit=10)

        assert total == 3
        assert len(convs) == 3

    @pytest.mark.asyncio
    async def test_list_conversations_pagination(self, service):
        """Test conversation pagination."""
        # Create 5 conversations
        for i in range(5):
            await service.create_conversation(title=f"Chat {i}")

        # Get first 2
        convs, total = await service.list_conversations(limit=2, offset=0)
        assert total == 5
        assert len(convs) == 2

        # Get next 2
        convs, total = await service.list_conversations(limit=2, offset=2)
        assert total == 5
        assert len(convs) == 2

    @pytest.mark.asyncio
    async def test_delete_conversation(self, service, db_session):
        """Test deleting a conversation."""
        conv = await service.create_conversation(title="To Delete")
        conv_id = conv.id

        deleted = await service.delete_conversation(conv_id)
        assert deleted is True

        # Verify it's gone
        db_conv = db_session.query(ChatConversation).filter_by(id=conv_id).first()
        assert db_conv is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_conversation(self, service):
        """Test deleting nonexistent conversation returns False."""
        deleted = await service.delete_conversation(99999)
        assert deleted is False

    @pytest.mark.asyncio
    async def test_update_conversation_title(self, service):
        """Test updating conversation title."""
        conv = await service.create_conversation(title="Old Title")
        original_updated_at = conv.updated_at

        updated = await service.update_conversation_title(conv.id, "New Title")

        assert updated.title == "New Title"
        # Use >= because the update can happen in the same millisecond
        assert updated.updated_at >= original_updated_at


class TestChatServiceMessageManagement:
    """Test message persistence and retrieval."""

    @pytest.fixture
    def service(self, db_session):
        return ChatService(db=db_session)

    @pytest.fixture
    def conversation(self, db_session):
        """Create a test conversation."""
        conv = ChatConversation(
            title="Test",
            model_provider=None,
            model_name=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(conv)
        db_session.commit()
        db_session.refresh(conv)
        return conv

    def test_save_user_message(self, service, conversation, db_session):
        """Test saving a user message."""
        message = service._save_message(
            conversation_id=conversation.id,
            role="user",
            content="Hello, how are you?",
        )

        assert message.id is not None
        assert message.role == "user"
        assert message.content == "Hello, how are you?"
        assert message.conversation_id == conversation.id

        # Verify in database
        db_msg = db_session.query(ChatMessage).filter_by(id=message.id).first()
        assert db_msg is not None

    def test_save_assistant_message(self, service, conversation):
        """Test saving an assistant message."""
        message = service._save_message(
            conversation_id=conversation.id,
            role="assistant",
            content="I'm doing well, thank you!",
            tokens_in=10,
            tokens_out=8,
        )

        assert message.role == "assistant"
        assert message.tokens_in == 10
        assert message.tokens_out == 8

    def test_save_message_with_tool_calls(self, service, conversation):
        """Test saving message with tool calls."""
        tool_calls = [
            {
                "id": "call_123",
                "name": "create_feed",
                "parameters": {"name": "News"},
            }
        ]

        message = service._save_message(
            conversation_id=conversation.id,
            role="assistant",
            content="I'll create that feed.",
            tool_calls=tool_calls,
        )

        assert message.tool_calls is not None
        assert len(message.tool_calls) == 1
        assert message.tool_calls[0]["name"] == "create_feed"

    def test_save_tool_result_message(self, service, conversation):
        """Test saving a tool result message."""
        message = service._save_message(
            conversation_id=conversation.id,
            role="tool_result",
            content='{"id": 5, "name": "News Feed"}',
            tool_call_id="call_123",
        )

        assert message.role == "tool_result"
        assert message.tool_call_id == "call_123"

    def test_load_messages(self, service, conversation):
        """Test loading messages from conversation."""
        # Save some messages
        service._save_message(conversation.id, "user", "Message 1")
        service._save_message(conversation.id, "assistant", "Message 2")
        service._save_message(conversation.id, "user", "Message 3")

        # Load them
        messages = service._load_messages(conversation.id)

        assert len(messages) == 3
        assert messages[0].content == "Message 1"
        assert messages[1].content == "Message 2"
        assert messages[2].content == "Message 3"

    def test_load_messages_with_limit(self, service, conversation):
        """Test loading messages with limit."""
        # Save 5 messages
        for i in range(5):
            service._save_message(conversation.id, "user", f"Message {i}")

        # Load last 2
        messages = service._load_messages(conversation.id, limit=2)

        assert len(messages) == 2
        assert messages[0].content == "Message 3"
        assert messages[1].content == "Message 4"


class TestChatServiceContextManagement:
    """Test context window management."""

    @pytest.fixture
    def service(self, db_session):
        return ChatService(db=db_session)

    @pytest.fixture
    def conversation(self, db_session):
        """Create a test conversation."""
        conv = ChatConversation(
            title="New Conversation",
            model_provider=None,
            model_name=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(conv)
        db_session.commit()
        db_session.refresh(conv)
        return conv

    def test_count_tokens(self, service):
        """Test token counting."""
        text = "This is a test message."
        count = service._count_tokens(text)

        assert count > 0
        assert isinstance(count, int)

    def test_messages_to_tokens(self, service):
        """Test counting tokens in message list."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "user", "content": "How are you?"},
        ]

        total = service._messages_to_tokens(messages)

        assert total > 0
        assert isinstance(total, int)

    @pytest.mark.asyncio
    async def test_prepare_context(self, service, conversation):
        """Test preparing message context."""
        # Add some messages
        service._save_message(conversation.id, "user", "Hello")
        service._save_message(conversation.id, "assistant", "Hi")

        # Prepare context with new message
        context = await service._prepare_context(conversation.id, "New message")

        assert len(context) >= 3  # Previous messages + new one
        assert context[-1]["role"] == "user"
        assert context[-1]["content"] == "New message"

    @pytest.mark.asyncio
    async def test_summarize_context(self, service):
        """Test context summarization."""
        # Create a long message history
        messages = []
        for i in range(20):
            messages.append({"role": "user", "content": f"Message {i}"})
            messages.append({"role": "assistant", "content": f"Response {i}"})

        # Summarize
        summarized = await service._summarize_context(messages)

        # Should have summary + recent messages
        assert len(summarized) < len(messages)
        assert any(msg.get("role") == "system" for msg in summarized)


class TestChatServiceToolExecution:
    """Test tool calling integration."""

    @pytest.fixture
    def mock_registry(self):
        """Create a mock tool registry."""
        registry = ToolRegistry()

        # Register a simple test tool
        registry.register_tool(
            ToolDefinition(
                name="test_tool",
                description="A test tool",
                parameters={
                    "type": "object",
                    "properties": {
                        "input": {"type": "string", "description": "Input text"}
                    },
                    "required": ["input"],
                },
                handler=lambda input, **kwargs: {"result": f"Processed: {input}"},
            )
        )

        return registry

    @pytest.fixture
    def service_with_mock_tools(self, db_session, mock_registry):
        """Create service with mock tools and provider."""
        def mock_provider_factory(provider, model):
            # Return a mock client
            return Mock()

        return ChatService(
            db=db_session,
            registry=mock_registry,
            provider_factory=mock_provider_factory,
        )

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="Requires a running LLM provider — mock doesn't fully intercept provider resolution")
    async def test_chat_saves_messages(self, service_with_mock_tools, db_session):
        """Test that chat method saves messages."""
        conv = await service_with_mock_tools.create_conversation()

        # Mock LLM call to return simple response (no tools)
        async def mock_call_llm(*args, **kwargs):
            return {
                "content": "Hello!",
                "tool_calls": [],
                "usage": {"input_tokens": 10, "output_tokens": 5},
            }

        with patch.object(
            service_with_mock_tools, "_call_llm", new=mock_call_llm
        ):
            response = await service_with_mock_tools.chat(
                conversation_id=conv.id,
                user_message="Hi there",
            )

            assert response.content == "Hello!"

            # Check messages were saved
            messages = db_session.query(ChatMessage).filter_by(
                conversation_id=conv.id
            ).all()

            # Should have user + assistant
            assert len(messages) >= 2


class TestChatServiceProviderSelection:
    """Test provider client initialization."""

    @pytest.fixture
    def service(self, db_session):
        return ChatService(db=db_session)

    def test_get_adapter_openai(self, service):
        """Test getting OpenAI adapter."""
        adapter = service._get_adapter("openai")
        assert adapter.provider_name == "openai"

    def test_get_adapter_anthropic(self, service):
        """Test getting Anthropic adapter."""
        adapter = service._get_adapter("anthropic")
        assert adapter.provider_name == "anthropic"

    def test_get_adapter_ollama(self, service):
        """Test getting Ollama adapter."""
        adapter = service._get_adapter("ollama")
        assert adapter.provider_name == "ollama"

    def test_get_adapter_unsupported_raises(self, service):
        """Test that unsupported provider raises error."""
        with pytest.raises(ValueError, match="Unsupported provider"):
            service._get_adapter("unknown_provider")

    def test_get_adapter_lmstudio(self, service):
        """Test getting LMStudio adapter (alias to OpenAI)."""
        adapter = service._get_adapter("lmstudio")
        # LMStudio uses OpenAI's adapter
        assert adapter.provider_name == "openai"

    def test_get_adapter_case_insensitive(self, service):
        """Test that ChatService handles case-insensitive provider names."""
        # ChatService lowercases provider names before lookup
        adapter_lower = service._get_adapter("openai")
        adapter_upper = service._get_adapter("OPENAI")
        adapter_mixed = service._get_adapter("OpenAI")

        # All should return the same type
        assert type(adapter_lower) == type(adapter_upper) == type(adapter_mixed)
        assert adapter_lower.provider_name == "openai"
        assert adapter_upper.provider_name == "openai"
        assert adapter_mixed.provider_name == "openai"

    def test_get_provider_client_with_factory(self, db_session):
        """Test using custom provider factory."""
        mock_client = Mock()

        def factory(provider, model):
            return mock_client

        service = ChatService(db=db_session, provider_factory=factory)
        client = service._get_provider_client("test_provider", "test_model")

        assert client is mock_client


class TestChatServiceErrors:
    """Test error handling."""

    @pytest.fixture
    def service(self, db_session):
        return ChatService(db=db_session)

    @pytest.mark.asyncio
    async def test_chat_nonexistent_conversation_raises(self, service):
        """Test that chatting with nonexistent conversation raises error."""
        with pytest.raises(ConversationNotFoundError):
            await service.chat(99999, "Hello")

    @pytest.mark.asyncio
    async def test_provider_error_propagates(self, service, monkeypatch):
        """Test that provider errors are caught and wrapped."""
        # This test would require mocking the provider to fail
        # Implementation depends on how you want to test provider failures
        pass  # Placeholder for provider error test
