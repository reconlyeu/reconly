"""Chat service for LLM conversations with tool calling.

This module provides the ChatService class that orchestrates complete chat
conversations with LLM providers, including:
- Conversation management (create, load, persist)
- Tool calling loop (message -> LLM -> tools -> results -> LLM -> response)
- Context window management with automatic summarization
- Support for streaming and non-streaming responses

Example:
    >>> from reconly_core.chat.service import ChatService
    >>> from reconly_core.chat import tool_registry, ToolExecutor
    >>>
    >>> service = ChatService(db=session)
    >>> conversation = await service.create_conversation("My Chat")
    >>>
    >>> # Non-streaming
    >>> response = await service.chat(conversation.id, "List all my feeds")
    >>>
    >>> # Streaming
    >>> async for chunk in service.chat_stream(conversation.id, "Create a feed"):
    ...     print(chunk, end="", flush=True)
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator, Callable

from sqlalchemy.orm import Session

from reconly_core.database.models import ChatConversation, ChatMessage
from reconly_core.chat.tools import ToolRegistry, tool_registry
from reconly_core.chat.tools import ToolDefinition  # Used in type hints
from reconly_core.chat.executor import ToolExecutor, ToolResult
from reconly_core.chat.adapters.base import (
    BaseToolAdapter,
    ToolCallRequest,
    ToolCallResult,
)
from reconly_core.chat.adapters import get_adapter, list_adapters

logger = logging.getLogger(__name__)


# Default system prompt for the chat assistant
DEFAULT_SYSTEM_PROMPT = """You are a helpful assistant for Reconly, an RSS aggregator with AI summarization.
You can help users manage their feeds, sources, digests, and knowledge base.

Available capabilities:
- Create and manage feeds and sources
- Search and export digests
- Query the knowledge base (RAG)
- View analytics and statistics

When users ask to perform actions, use the available tools. For information queries,
try to answer from your knowledge or use the search/query tools.

Be concise and helpful. When executing tools:
- Briefly explain what you're doing
- Summarize results in natural language - NEVER output raw JSON or technical data
- For search results, present them in a readable format with titles, summaries, and key details
- If a tool returns many results, highlight the most relevant ones"""


# Maximum tokens for context window (configurable per model)
DEFAULT_MAX_CONTEXT_TOKENS = 8000

# Maximum iterations for tool calling loop (safety limit)
MAX_TOOL_ITERATIONS = 10

# Context management constants
CONTEXT_RECENT_MESSAGES_TO_KEEP = 5  # Messages to keep when summarizing
CONTEXT_MESSAGE_OVERHEAD_TOKENS = 10  # Approximate token overhead per message
CONTEXT_SUMMARY_TRUNCATE_LENGTH = 200  # Max chars per message in summary

# Provider defaults
DEFAULT_ANTHROPIC_MAX_TOKENS = 4096
DEFAULT_OLLAMA_TIMEOUT = 120.0  # seconds


@dataclass
class ChatResponse:
    """Response from a chat request.

    Attributes:
        content: The text response from the assistant.
        tool_calls: List of tool calls made during processing.
        tool_results: List of results from executed tools.
        tokens_in: Total input tokens used.
        tokens_out: Total output tokens generated.
        conversation_id: ID of the conversation.
        message_id: ID of the assistant message.
    """

    content: str
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    conversation_id: int | None = None
    message_id: int | None = None


@dataclass
class StreamChunk:
    """A chunk of streaming response.

    Attributes:
        type: Type of chunk ('text', 'tool_call', 'tool_result', 'done', 'error').
        content: The content of this chunk.
        tool_call: Tool call info if type is 'tool_call'.
        tool_result: Tool result if type is 'tool_result'.
        tokens_in: Input token count (in 'done' chunk).
        tokens_out: Output token count (in 'done' chunk).
    """

    type: str
    content: str = ""
    tool_call: dict[str, Any] | None = None
    tool_result: dict[str, Any] | None = None
    tokens_in: int = 0
    tokens_out: int = 0


class ChatServiceError(Exception):
    """Base exception for chat service errors."""


class ConversationNotFoundError(ChatServiceError):
    """Raised when a conversation is not found."""


class ProviderError(ChatServiceError):
    """Raised when there's an error with the LLM provider."""


class ChatService:
    """Service for managing LLM chat conversations with tool calling.

    This service handles the complete chat workflow:
    1. Conversation management (create, load, list, delete)
    2. Message persistence in the database
    3. Context window management with summarization
    4. Tool calling loop execution
    5. Provider-agnostic LLM interaction

    Example:
        >>> service = ChatService(db=session)
        >>> conv = await service.create_conversation("Tech Discussion")
        >>> response = await service.chat(conv.id, "What feeds do I have?")
        >>> print(response.content)

        >>> # With streaming
        >>> async for chunk in service.chat_stream(conv.id, "Create a news feed"):
        ...     if chunk.type == 'text':
        ...         print(chunk.content, end='')
        ...     elif chunk.type == 'tool_call':
        ...         print(f"\\n[Calling: {chunk.tool_call['name']}]")
    """

    def __init__(
        self,
        db: Session,
        registry: ToolRegistry | None = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        max_context_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
        provider_factory: Callable[[str, str], Any] | None = None,
    ):
        """Initialize the chat service.

        Args:
            db: SQLAlchemy database session.
            registry: Tool registry (defaults to global tool_registry).
            system_prompt: System prompt for the assistant.
            max_context_tokens: Maximum tokens for context window.
            provider_factory: Optional factory for creating LLM providers.
                If not provided, uses default provider initialization.
        """
        self.db = db
        self.registry = registry or tool_registry
        self.executor = ToolExecutor(self.registry)
        self.system_prompt = system_prompt
        self.max_context_tokens = max_context_tokens
        self.provider_factory = provider_factory

        # Initialize chunking service for token counting
        self._chunking_service = None

    @property
    def chunking_service(self):
        """Lazy-load the chunking service for token counting."""
        if self._chunking_service is None:
            from reconly_core.rag.chunking import ChunkingService

            self._chunking_service = ChunkingService()
        return self._chunking_service

    def _get_adapter(self, provider: str) -> BaseToolAdapter:
        """Get the appropriate adapter for a provider.

        Uses the adapter registry which supports aliases (e.g., lmstudio -> openai).

        Args:
            provider: Provider name or alias (openai, anthropic, ollama, lmstudio).

        Returns:
            The adapter for the provider.

        Raises:
            ValueError: If provider is not supported.
        """
        try:
            return get_adapter(provider.lower())
        except ValueError:
            available = list_adapters()
            raise ValueError(
                f"Unsupported provider: {provider}. "
                f"Available adapters: {available}"
            )

    def _get_adapter_format(self, provider: str) -> str:
        """Get the chat adapter format for a provider.

        Looks up the provider in the registry and returns its chat_adapter_format
        from metadata, or the provider name if not specified.

        Args:
            provider: Provider name.

        Returns:
            Adapter format string (e.g., 'openai', 'anthropic', 'ollama').
        """
        provider_lower = provider.lower()

        from reconly_core.providers.registry import is_provider_registered, get_provider_entry
        import reconly_core.providers.factory  # noqa: F401 - ensure providers are loaded

        if is_provider_registered(provider_lower):
            entry = get_provider_entry(provider_lower)
            if hasattr(entry.cls, 'metadata'):
                return getattr(entry.cls.metadata, 'chat_adapter_format', None) or provider_lower

        return provider_lower

    def _get_default_provider(self) -> str:
        """Get the default provider from app settings or environment.

        Priority:
        1. First provider in llm.fallback_chain that supports chat
        2. Environment variable DEFAULT_CHAT_PROVIDER (if chat-supported)
        3. First available chat provider with API key/URL configured
        4. Fallback to 'ollama'

        Note: Chat supports providers with registered adapters (ollama, openai,
        anthropic) and aliases (lmstudio). HuggingFace is only supported for
        summarization, not chat.

        Returns:
            Provider name (e.g., 'ollama', 'anthropic', 'openai', 'lmstudio').
        """
        import logging
        from reconly_core.services.settings_service import SettingsService
        from reconly_core.chat.adapters.registry import is_adapter_registered

        logger = logging.getLogger(__name__)

        # Get list of chat-supported providers (adapters + aliases)
        chat_providers = set(list_adapters())
        # Also include known aliases for the check
        chat_providers.add("lmstudio")

        # Check fallback chain from settings (position 0 = default provider)
        try:
            settings_service = SettingsService(self.db)
            chain = settings_service.get("llm.fallback_chain")
            if chain and isinstance(chain, list):
                # Find first provider in chain that supports chat
                for provider in chain:
                    if is_adapter_registered(provider):
                        return provider
                    else:
                        logger.debug(
                            f"Provider '{provider}' from fallback chain is not supported for chat. "
                            f"Chat supports: {sorted(chat_providers)}. Trying next."
                        )
        except Exception:
            pass  # Fall through to env var

        # Check environment variable
        env_provider = os.getenv("DEFAULT_CHAT_PROVIDER", "").lower()
        if env_provider and is_adapter_registered(env_provider):
            return env_provider

        # Auto-detect: prefer providers with API keys/URLs configured
        if os.getenv("ANTHROPIC_API_KEY"):
            return "anthropic"
        if os.getenv("OPENAI_API_KEY"):
            return "openai"
        if os.getenv("LMSTUDIO_BASE_URL"):
            return "lmstudio"

        # Default fallback
        return "ollama"

    def _resolve_provider(self) -> dict:
        """Resolve the default provider using the central resolve_default_provider().

        Returns:
            Dict with provider, model, available, fallback_used, unavailable_providers
        """
        from reconly_core.providers.factory import resolve_default_provider
        return resolve_default_provider(db=self.db)

    def _get_default_model(self, provider: str) -> str:
        """Get the default model from app settings for the given provider.

        Uses SettingsService which provides fallback chain: DB -> env -> default.
        Looks up provider-specific model setting: provider.{name}.model

        Args:
            provider: Provider name to get default model for.

        Returns:
            Model name from settings (with fallback to registry default).
        """
        from reconly_core.services.settings_service import SettingsService

        try:
            settings_service = SettingsService(self.db)
            # Use provider-specific model key
            model_key = f"provider.{provider}.model"
            model = settings_service.get(model_key)
            if model:
                return model
        except KeyError:
            # Provider model setting not registered (possibly for extensions)
            pass
        except Exception:
            pass

        # Fallback to empty string if SettingsService fails
        return ""

    def _get_provider_client(self, provider: str, model: str | None = None) -> Any:
        """Get or create an LLM provider client.

        Uses the provider registry to dynamically create clients based on
        provider metadata. Supports any provider with chat_adapter_format set.

        Args:
            provider: Provider name.
            model: Optional model name.

        Returns:
            Provider client instance.
        """
        if self.provider_factory:
            return self.provider_factory(provider, model or "")

        provider_lower = provider.lower()

        # Import provider registry to get metadata
        from reconly_core.providers.registry import is_provider_registered, get_provider_entry
        import reconly_core.providers.factory  # noqa: F401 - ensure providers are loaded

        if not is_provider_registered(provider_lower):
            raise ProviderError(f"Unknown provider: {provider}")

        entry = get_provider_entry(provider_lower)
        provider_cls = entry.cls

        if not hasattr(provider_cls, 'metadata'):
            raise ProviderError(f"Provider '{provider}' has no metadata configured")

        metadata = provider_cls.metadata

        # Determine the adapter format (what API format this provider uses)
        adapter_format = getattr(metadata, 'chat_adapter_format', None) or provider_lower

        # Create client based on adapter format
        if adapter_format == "anthropic":
            from anthropic import Anthropic

            api_key = metadata.get_api_key()
            if not api_key:
                env_var = metadata.api_key_env_var or "ANTHROPIC_API_KEY"
                raise ProviderError(
                    f"{env_var} not set. Please configure your API key."
                )
            return Anthropic(api_key=api_key)

        elif adapter_format == "openai":
            from openai import OpenAI

            api_key = metadata.get_api_key()
            # Some providers (like LMStudio) don't require API keys
            if metadata.requires_api_key and not api_key:
                env_var = metadata.api_key_env_var or "API key"
                raise ProviderError(
                    f"{env_var} not set. Please configure your API key."
                )

            # Determine base URL: chat_api_base_url > base_url > None (use OpenAI default)
            base_url = getattr(metadata, 'chat_api_base_url', None) or metadata.get_base_url()

            # Build client kwargs
            client_kwargs = {}
            if base_url:
                client_kwargs["base_url"] = base_url
            if api_key:
                client_kwargs["api_key"] = api_key
            elif not metadata.requires_api_key:
                # Providers like LMStudio need a dummy key for OpenAI client
                client_kwargs["api_key"] = "not-required"

            return OpenAI(**client_kwargs)

        elif adapter_format == "ollama":
            import httpx

            base_url = metadata.get_base_url() or "http://localhost:11434"
            return {"base_url": base_url, "client": httpx.Client(base_url=base_url, timeout=DEFAULT_OLLAMA_TIMEOUT)}

        else:
            raise ProviderError(
                f"Unsupported chat adapter format '{adapter_format}' for provider '{provider}'. "
                f"Supported formats: anthropic, openai, ollama"
            )

    # =========================================================================
    # Conversation CRUD
    # =========================================================================

    async def create_conversation(
        self,
        title: str = "New Conversation",
        model_provider: str | None = None,
        model_name: str | None = None,
        user_id: int | None = None,
    ) -> ChatConversation:
        """Create a new chat conversation.

        Args:
            title: Title for the conversation.
            model_provider: LLM provider (ollama, anthropic, openai).
            model_name: Specific model name.
            user_id: Optional user ID (for multi-user mode).

        Returns:
            The created ChatConversation.

        Example:
            >>> conv = await service.create_conversation(
            ...     title="Feed Management",
            ...     model_provider="anthropic",
            ...     model_name="claude-sonnet-4-20250514"
            ... )
        """
        conversation = ChatConversation(
            title=title,
            model_provider=model_provider,
            model_name=model_name,
            user_id=user_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)

        logger.info(f"Created conversation {conversation.id}: {title}")
        return conversation

    async def get_conversation(
        self, conversation_id: int
    ) -> ChatConversation:
        """Load a conversation with its messages.

        Args:
            conversation_id: ID of the conversation to load.

        Returns:
            The ChatConversation with messages loaded.

        Raises:
            ConversationNotFoundError: If conversation doesn't exist.

        Example:
            >>> conv = await service.get_conversation(123)
            >>> print(f"Has {len(conv.messages)} messages")
        """
        conversation = (
            self.db.query(ChatConversation)
            .filter(ChatConversation.id == conversation_id)
            .first()
        )

        if conversation is None:
            raise ConversationNotFoundError(
                f"Conversation {conversation_id} not found"
            )

        return conversation

    async def list_conversations(
        self,
        limit: int = 50,
        offset: int = 0,
        user_id: int | None = None,
    ) -> tuple[list[ChatConversation], int]:
        """List conversations with pagination.

        Args:
            limit: Maximum number to return.
            offset: Number to skip.
            user_id: Filter by user ID (optional).

        Returns:
            Tuple of (conversations list, total count).

        Example:
            >>> convs, total = await service.list_conversations(limit=10)
            >>> print(f"Showing {len(convs)} of {total}")
        """
        query = self.db.query(ChatConversation)

        if user_id is not None:
            query = query.filter(ChatConversation.user_id == user_id)

        total = query.count()

        conversations = (
            query.order_by(ChatConversation.updated_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return conversations, total

    async def delete_conversation(self, conversation_id: int) -> bool:
        """Delete a conversation and all its messages.

        Args:
            conversation_id: ID of the conversation to delete.

        Returns:
            True if deleted, False if not found.

        Example:
            >>> deleted = await service.delete_conversation(123)
        """
        conversation = (
            self.db.query(ChatConversation)
            .filter(ChatConversation.id == conversation_id)
            .first()
        )

        if conversation is None:
            return False

        self.db.delete(conversation)
        self.db.commit()

        logger.info(f"Deleted conversation {conversation_id}")
        return True

    async def update_conversation_title(
        self, conversation_id: int, title: str
    ) -> ChatConversation:
        """Update the title of a conversation.

        Args:
            conversation_id: ID of the conversation.
            title: New title.

        Returns:
            Updated conversation.

        Raises:
            ConversationNotFoundError: If conversation doesn't exist.
        """
        conversation = await self.get_conversation(conversation_id)
        conversation.title = title
        conversation.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    # =========================================================================
    # Message Management
    # =========================================================================

    def _save_message(
        self,
        conversation_id: int,
        role: str,
        content: str | None,
        tool_calls: list[dict[str, Any]] | None = None,
        tool_call_id: str | None = None,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
    ) -> ChatMessage:
        """Save a message to the database.

        Args:
            conversation_id: ID of the conversation.
            role: Message role (user, assistant, tool_result).
            content: Message content.
            tool_calls: Tool calls from assistant.
            tool_call_id: ID of tool call this result is for.
            tokens_in: Input tokens for this message.
            tokens_out: Output tokens for this message.

        Returns:
            The saved ChatMessage.
        """
        message = ChatMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
            tool_call_id=tool_call_id,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            created_at=datetime.utcnow(),
        )
        self.db.add(message)

        # Update conversation timestamp in same transaction
        self.db.query(ChatConversation).filter(
            ChatConversation.id == conversation_id
        ).update({"updated_at": datetime.utcnow()})

        self.db.commit()
        self.db.refresh(message)

        return message

    def _load_messages(
        self, conversation_id: int, limit: int | None = None
    ) -> list[ChatMessage]:
        """Load messages from the database.

        Args:
            conversation_id: ID of the conversation.
            limit: Maximum messages to load (most recent).

        Returns:
            List of ChatMessage objects.
        """
        query = (
            self.db.query(ChatMessage)
            .filter(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at.asc())
        )

        if limit:
            # Get total count and offset to get last N
            total = query.count()
            if total > limit:
                query = query.offset(total - limit)

        return query.all()

    # =========================================================================
    # Context Management
    # =========================================================================

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text.

        Args:
            text: Text to count tokens in.

        Returns:
            Estimated token count.
        """
        return self.chunking_service.count_tokens(text)

    def _messages_to_tokens(self, messages: list[dict[str, Any]]) -> int:
        """Count total tokens in a list of messages.

        Args:
            messages: List of message dicts.

        Returns:
            Total token count.
        """
        total = 0
        for msg in messages:
            content = msg.get("content", "") or ""
            if isinstance(content, str):
                total += self._count_tokens(content)
            elif isinstance(content, list):
                # Anthropic-style content blocks
                for block in content:
                    if isinstance(block, dict):
                        text = block.get("text", "") or block.get("content", "")
                        total += self._count_tokens(str(text))
            # Add overhead for message structure
            total += CONTEXT_MESSAGE_OVERHEAD_TOKENS

        return total

    async def _prepare_context(
        self,
        conversation_id: int,
        new_message: str,
    ) -> list[dict[str, Any]]:
        """Prepare message context for LLM, managing context window.

        Loads recent messages and summarizes older ones if needed to fit
        within the context window.

        Args:
            conversation_id: ID of the conversation.
            new_message: The new user message being added.

        Returns:
            List of message dicts ready for the LLM.
        """
        # Load all messages
        db_messages = self._load_messages(conversation_id)

        # Convert to provider-agnostic format
        messages = []
        for msg in db_messages:
            message_dict: dict[str, Any] = {"role": msg.role, "content": msg.content}

            if msg.tool_calls:
                message_dict["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                message_dict["tool_call_id"] = msg.tool_call_id

            messages.append(message_dict)

        # Add new message
        messages.append({"role": "user", "content": new_message})

        # Check if we need to summarize
        token_count = self._messages_to_tokens(messages)

        if token_count > self.max_context_tokens and len(messages) > CONTEXT_RECENT_MESSAGES_TO_KEEP:
            # Summarize older messages
            messages = await self._summarize_context(messages)

        return messages

    async def _summarize_context(
        self, messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Summarize older messages to fit context window.

        Keeps the last 5 messages and summarizes everything before them.

        Args:
            messages: Full list of messages.

        Returns:
            Compressed message list with summary.
        """
        # Keep most recent messages
        recent_messages = messages[-CONTEXT_RECENT_MESSAGES_TO_KEEP:]
        older_messages = messages[:-CONTEXT_RECENT_MESSAGES_TO_KEEP]

        if not older_messages:
            return messages

        # Build summary of older messages
        summary_parts = []
        for msg in older_messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            if content and isinstance(content, str):
                # Truncate very long messages
                if len(content) > CONTEXT_SUMMARY_TRUNCATE_LENGTH:
                    content = content[:CONTEXT_SUMMARY_TRUNCATE_LENGTH] + "..."
                summary_parts.append(f"{role}: {content}")

        summary_text = "\n".join(summary_parts)

        # Create a context message with the summary
        context_message = {
            "role": "system",
            "content": f"Previous conversation context:\n{summary_text}\n\n---\n",
        }

        return [context_message] + recent_messages

    # =========================================================================
    # LLM Interaction
    # =========================================================================

    def _format_messages_for_provider(
        self,
        provider: str,
        messages: list[dict[str, Any]],
        adapter: BaseToolAdapter,
        tools: list[ToolDefinition],
    ) -> list[dict[str, Any]]:
        """Format messages for a specific provider.

        Args:
            provider: Provider name.
            messages: Generic message format.
            adapter: Provider adapter.
            tools: Available tools.

        Returns:
            Provider-formatted messages.
        """
        adapter_format = self._get_adapter_format(provider)

        # Add tool instructions for Ollama-format providers
        if adapter_format == "ollama" and tools:
            tool_prompt = adapter.get_system_prompt_prefix(tools)
            if tool_prompt:
                # Prepend to system prompt or create one
                system_content = tool_prompt + "\n\n" + self.system_prompt
                messages = [{"role": "system", "content": system_content}] + [
                    m for m in messages if m.get("role") != "system"
                ]

        return messages

    def _append_tool_result_to_messages(
        self,
        messages: list[dict[str, Any]],
        provider: str,
        adapter: BaseToolAdapter,
        call: ToolCallRequest,
        result: ToolResult,
        raw_response: Any | None = None,
    ) -> None:
        """Append tool result to messages list in provider-specific format.

        This helper handles the provider-specific formatting of tool results
        for the next LLM iteration.

        Args:
            messages: Messages list to append to (modified in place).
            provider: Provider name.
            adapter: Provider adapter.
            call: The tool call request.
            result: The tool execution result.
            raw_response: Raw LLM response (needed for Anthropic).
        """
        adapter_format = self._get_adapter_format(provider)
        tool_call_result = ToolCallResult(
            call_id=call.call_id or "",
            tool_name=call.tool_name,
            result=result.result if result.success else {"error": result.error},
            is_error=not result.success,
        )

        if adapter_format == "anthropic":
            # Add assistant message with tool use
            if raw_response:
                messages.append(adapter.format_assistant_tool_use(raw_response))
            messages.append(adapter.format_tool_results_message([tool_call_result]))

        elif adapter_format == "openai":
            # OpenAI-compatible format
            openai_adapter = get_adapter("openai")
            messages.append(openai_adapter.format_assistant_tool_call([call]))
            messages.append(adapter.format_tool_result(tool_call_result))

        else:
            # Ollama - add as text
            ollama_adapter = get_adapter("ollama")
            result_text = ollama_adapter.format_tool_result_as_message(tool_call_result)
            messages.append({"role": "user", "content": result_text})

    async def _call_llm(
        self,
        provider: str,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Call the LLM provider.

        Uses the provider's chat_adapter_format to determine which API to call.

        Args:
            provider: Provider name.
            model: Model name.
            messages: Messages to send.
            tools: Formatted tools for the provider.

        Returns:
            Provider response dict with 'content', 'tool_calls', 'usage' keys.
        """
        client = self._get_provider_client(provider, model)
        adapter_format = self._get_adapter_format(provider)

        if adapter_format == "anthropic":
            return await self._call_anthropic(client, model, messages, tools)
        elif adapter_format == "openai":
            return await self._call_openai(client, model, messages, tools)
        elif adapter_format == "ollama":
            return await self._call_ollama(client, model, messages)
        else:
            raise ProviderError(f"Unsupported provider: {provider}")

    async def _call_anthropic(
        self,
        client: Any,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        """Call Anthropic Claude API.

        Args:
            client: Anthropic client.
            model: Model name.
            messages: Messages to send.
            tools: Formatted tools.

        Returns:
            Normalized response dict.
        """
        # Extract system prompt
        system_prompt = self.system_prompt
        api_messages = []

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")

            if role == "system":
                system_prompt = content or system_prompt
                continue

            # Handle tool results for Anthropic
            if role == "tool_result" or msg.get("tool_call_id"):
                api_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.get("tool_call_id"),
                        "content": content or "",
                    }],
                })
            else:
                api_messages.append({"role": role, "content": content})

        if not model:
            raise ProviderError(
                "No Anthropic model configured. Please set a model in Settings > Providers "
                "(e.g., claude-sonnet-4-20250514, claude-3-5-haiku-20241022)."
            )

        # Make API call
        kwargs = {
            "model": model,
            "max_tokens": DEFAULT_ANTHROPIC_MAX_TOKENS,
            "system": system_prompt,
            "messages": api_messages,
        }

        if tools:
            kwargs["tools"] = tools

        try:
            response = client.messages.create(**kwargs)
        except Exception as e:
            raise ProviderError(f"Anthropic API error: {e}")

        # Parse response
        adapter = get_adapter("anthropic")
        content = adapter.get_text_content(response)
        tool_calls = adapter.parse_tool_calls(response)

        return {
            "content": content,
            "tool_calls": tool_calls,
            "usage": {
                "input_tokens": response.usage.input_tokens if response.usage else 0,
                "output_tokens": response.usage.output_tokens if response.usage else 0,
            },
            "raw_response": response,
        }

    async def _call_openai(
        self,
        client: Any,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        """Call OpenAI API.

        Args:
            client: OpenAI client.
            model: Model name.
            messages: Messages to send.
            tools: Formatted tools.

        Returns:
            Normalized response dict.
        """
        # Prepend system prompt
        api_messages = [{"role": "system", "content": self.system_prompt}]

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")

            if role == "system":
                continue  # Already handled

            # Handle tool results for OpenAI
            if role == "tool_result" or msg.get("tool_call_id"):
                api_messages.append({
                    "role": "tool",
                    "tool_call_id": msg.get("tool_call_id"),
                    "content": content or "",
                })
            elif msg.get("tool_calls"):
                # Assistant message with tool calls
                api_messages.append({
                    "role": "assistant",
                    "content": content,
                    "tool_calls": msg.get("tool_calls"),
                })
            else:
                api_messages.append({"role": role, "content": content})

        if not model:
            raise ProviderError(
                "No OpenAI model configured. Please set a model in Settings > Providers "
                "(e.g., gpt-4o, gpt-4-turbo, gpt-3.5-turbo)."
            )

        # Make API call
        kwargs = {
            "model": model,
            "messages": api_messages,
        }

        if tools:
            kwargs["tools"] = tools

        try:
            response = client.chat.completions.create(**kwargs)
        except Exception as e:
            raise ProviderError(f"OpenAI API error: {e}")

        # Parse response
        adapter = get_adapter("openai")
        message = response.choices[0].message
        content = message.content or ""
        tool_calls = adapter.parse_tool_calls(response)

        return {
            "content": content,
            "tool_calls": tool_calls,
            "usage": {
                "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                "output_tokens": response.usage.completion_tokens if response.usage else 0,
            },
            "raw_response": response,
        }

    async def _call_ollama(
        self,
        client: dict[str, Any],
        model: str,
        messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Call Ollama API.

        Args:
            client: Ollama client dict with base_url and client.
            model: Model name.
            messages: Messages to send.

        Returns:
            Normalized response dict.
        """
        import httpx

        base_url = client["base_url"]
        http_client = client.get("client")

        if http_client is None:
            http_client = httpx.Client(base_url=base_url, timeout=DEFAULT_OLLAMA_TIMEOUT)

        # Build request
        api_messages = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")

            if role in ("user", "assistant", "system"):
                api_messages.append({"role": role, "content": content})

        if not model:
            raise ProviderError(
                "No Ollama model configured. Please set a model in Settings > Providers, "
                "or run 'ollama list' to see available models."
            )

        try:
            response = http_client.post(
                f"{base_url}/api/chat",
                json={
                    "model": model,
                    "messages": api_messages,
                    "stream": False,
                },
            )
            response.raise_for_status()
            data = response.json()
        except httpx.ConnectError:
            raise ProviderError(
                f"Cannot connect to Ollama at {base_url}. "
                "Make sure Ollama is running (run 'ollama serve' in a terminal)."
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Could be wrong endpoint or model not found
                raise ProviderError(
                    f"Ollama returned 404. This could mean:\n"
                    f"1. Model '{model}' is not installed (run 'ollama pull {model}')\n"
                    f"2. Ollama version is too old (need 0.1.14+ for /api/chat)\n"
                    f"3. Try updating Ollama: https://ollama.ai/download"
                )
            raise ProviderError(f"Ollama API error (HTTP {e.response.status_code}): {e}")
        except httpx.TimeoutException:
            raise ProviderError(
                "Ollama request timed out. The model may be loading or the request is too large. "
                "Try again or use a smaller model."
            )
        except Exception as e:
            raise ProviderError(f"Ollama API error: {e}")

        # Parse response
        adapter = get_adapter("ollama")
        content = data.get("message", {}).get("content", "")
        tool_calls = adapter.parse_tool_calls(content)

        # If there are tool calls, extract the non-tool text
        if tool_calls:
            content = adapter.extract_text_without_tool_calls(content)

        return {
            "content": content,
            "tool_calls": tool_calls,
            "usage": {
                "input_tokens": data.get("prompt_eval_count", 0),
                "output_tokens": data.get("eval_count", 0),
            },
            "raw_response": data,
        }

    # =========================================================================
    # Tool Calling Loop
    # =========================================================================

    async def _process_with_tools(
        self,
        conversation_id: int,
        messages: list[dict[str, Any]],
        provider: str,
        model: str,
        adapter: BaseToolAdapter,
        tools: list[ToolDefinition],
        context: dict[str, Any] | None = None,
    ) -> ChatResponse:
        """Process messages with tool calling loop.

        This implements the core tool calling loop:
        1. Send messages to LLM
        2. If LLM wants to call tools, execute them
        3. Add tool results to messages
        4. Repeat until LLM provides final response

        Args:
            conversation_id: ID of the conversation.
            messages: Current message history.
            provider: LLM provider name.
            model: Model name.
            adapter: Provider adapter.
            tools: Available tools.
            context: Context dict for tool execution (db session, etc.).

        Returns:
            ChatResponse with final response and tool history.
        """
        formatted_tools = adapter.format_tools(tools) if tools else None

        all_tool_calls: list[ToolCallRequest] = []
        all_tool_results: list[ToolResult] = []
        total_tokens_in = 0
        total_tokens_out = 0

        iteration = 0

        while iteration < MAX_TOOL_ITERATIONS:
            iteration += 1

            # Call LLM
            response = await self._call_llm(
                provider, model, messages, formatted_tools
            )

            total_tokens_in += response["usage"].get("input_tokens", 0)
            total_tokens_out += response["usage"].get("output_tokens", 0)

            tool_calls = response.get("tool_calls", [])

            # If no tool calls, we're done
            if not tool_calls:
                return ChatResponse(
                    content=response["content"],
                    tool_calls=all_tool_calls,
                    tool_results=all_tool_results,
                    tokens_in=total_tokens_in,
                    tokens_out=total_tokens_out,
                    conversation_id=conversation_id,
                )

            # Execute tool calls
            for call in tool_calls:
                all_tool_calls.append(call)

                # Execute tool
                result = await self.executor.execute(
                    call,
                    context=context or {"db": self.db},
                )
                all_tool_results.append(result)

                # Save tool call and result to database
                self._save_message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=response.get("content"),
                    tool_calls=[{
                        "id": call.call_id,
                        "name": call.tool_name,
                        "parameters": call.parameters,
                    }],
                )

                # Save tool result
                result_content = (
                    json.dumps(result.result, ensure_ascii=False)
                    if result.success
                    else f"Error: {result.error}"
                )
                self._save_message(
                    conversation_id=conversation_id,
                    role="tool_result",
                    content=result_content,
                    tool_call_id=call.call_id,
                )

                # Add to messages for next iteration
                self._append_tool_result_to_messages(
                    messages=messages,
                    provider=provider,
                    adapter=adapter,
                    call=call,
                    result=result,
                    raw_response=response.get("raw_response"),
                )

        # If we hit max iterations, return what we have
        logger.warning(
            f"Hit max tool iterations ({MAX_TOOL_ITERATIONS}) for conversation {conversation_id}"
        )
        return ChatResponse(
            content="I've completed multiple operations. Is there anything else you need?",
            tool_calls=all_tool_calls,
            tool_results=all_tool_results,
            tokens_in=total_tokens_in,
            tokens_out=total_tokens_out,
            conversation_id=conversation_id,
        )

    # =========================================================================
    # Public Chat Methods
    # =========================================================================

    async def chat(
        self,
        conversation_id: int,
        user_message: str,
        stream: bool = False,
        context: dict[str, Any] | None = None,
    ) -> ChatResponse:
        """Send a message and get a response (non-streaming).

        This is the main chat method that:
        1. Loads conversation and prepares context
        2. Saves user message
        3. Calls LLM with tool calling loop
        4. Saves assistant response
        5. Returns complete response

        Args:
            conversation_id: ID of the conversation.
            user_message: The user's message.
            stream: If True, raises error (use chat_stream instead).
            context: Optional context for tool execution.

        Returns:
            ChatResponse with assistant's response.

        Raises:
            ConversationNotFoundError: If conversation doesn't exist.
            ProviderError: If LLM call fails.

        Example:
            >>> response = await service.chat(123, "List my feeds")
            >>> print(response.content)
            >>> print(f"Used {len(response.tool_calls)} tools")
        """
        if stream:
            raise ValueError("Use chat_stream() for streaming responses")

        # Load conversation
        conversation = await self.get_conversation(conversation_id)

        # Determine provider and model
        # Priority: conversation setting > resolved default from fallback chain
        if conversation.model_provider:
            provider = conversation.model_provider
            model = conversation.model_name or self._get_default_model(provider)
        else:
            # Use central resolve_default_provider() to get first available
            resolved = self._resolve_provider()
            if not resolved["available"]:
                unavailable = ", ".join(resolved["unavailable_providers"]) or "none configured"
                raise ProviderError(
                    f"No providers available. Checked: {unavailable}\n\n"
                    "Please ensure at least one provider is available:\n"
                    "  - For local providers (Ollama, LMStudio), check the server is running\n"
                    "  - For cloud providers, check your API key is configured"
                )
            provider = resolved["provider"]
            model = conversation.model_name or resolved["model"] or self._get_default_model(provider)

            if resolved["fallback_used"]:
                logger.info(
                    f"Using fallback provider '{provider}' "
                    f"(primary was unavailable: {resolved['unavailable_providers']})"
                )

        # Get adapter and tools
        adapter = self._get_adapter(provider)
        tools = self.registry.list_tools()

        # Save user message
        self._save_message(
            conversation_id=conversation_id,
            role="user",
            content=user_message,
        )

        # Prepare context
        messages = await self._prepare_context(conversation_id, user_message)
        messages = self._format_messages_for_provider(provider, messages, adapter, tools)

        # Process with tools
        response = await self._process_with_tools(
            conversation_id=conversation_id,
            messages=messages,
            provider=provider,
            model=model,
            adapter=adapter,
            tools=tools,
            context=context,
        )

        # Save assistant response
        message = self._save_message(
            conversation_id=conversation_id,
            role="assistant",
            content=response.content,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
        )

        response.message_id = message.id
        return response

    async def chat_stream(
        self,
        conversation_id: int,
        user_message: str,
        context: dict[str, Any] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Send a message and stream the response.

        Yields chunks as the response is generated. Tool calls are
        executed inline and their status is yielded.

        Args:
            conversation_id: ID of the conversation.
            user_message: The user's message.
            context: Optional context for tool execution.

        Yields:
            StreamChunk objects with response pieces.

        Example:
            >>> async for chunk in service.chat_stream(123, "Create a feed"):
            ...     if chunk.type == 'text':
            ...         print(chunk.content, end='')
            ...     elif chunk.type == 'tool_call':
            ...         print(f"[Calling {chunk.tool_call['name']}]")
            ...     elif chunk.type == 'tool_result':
            ...         print(f"[Result: {chunk.tool_result['success']}]")
        """
        # Load conversation
        conversation = await self.get_conversation(conversation_id)

        # Determine provider and model
        # Priority: conversation setting > resolved default from fallback chain
        if conversation.model_provider:
            provider = conversation.model_provider
            model = conversation.model_name or self._get_default_model(provider)
        else:
            # Use central resolve_default_provider() to get first available
            resolved = self._resolve_provider()
            if not resolved["available"]:
                unavailable = ", ".join(resolved["unavailable_providers"]) or "none configured"
                yield StreamChunk(
                    type="error",
                    content=f"No providers available. Checked: {unavailable}"
                )
                return
            provider = resolved["provider"]
            model = conversation.model_name or resolved["model"] or self._get_default_model(provider)

            if resolved["fallback_used"]:
                logger.info(
                    f"Using fallback provider '{provider}' "
                    f"(primary was unavailable: {resolved['unavailable_providers']})"
                )

        # Get adapter and tools
        adapter = self._get_adapter(provider)
        tools = self.registry.list_tools()

        # Save user message
        self._save_message(
            conversation_id=conversation_id,
            role="user",
            content=user_message,
        )

        # Prepare context
        messages = await self._prepare_context(conversation_id, user_message)
        messages = self._format_messages_for_provider(provider, messages, adapter, tools)
        formatted_tools = adapter.format_tools(tools) if tools else None

        # Process with streaming
        # Note: Currently implements pseudo-streaming by yielding after each step
        # True streaming would require provider-specific streaming implementations

        total_tokens_in = 0
        total_tokens_out = 0
        iteration = 0
        full_content = ""

        while iteration < MAX_TOOL_ITERATIONS:
            iteration += 1

            # Call LLM
            try:
                response = await self._call_llm(provider, model, messages, formatted_tools)
            except Exception as e:
                yield StreamChunk(type="error", content=str(e))
                return

            total_tokens_in += response["usage"].get("input_tokens", 0)
            total_tokens_out += response["usage"].get("output_tokens", 0)

            tool_calls = response.get("tool_calls", [])
            content = response.get("content", "")

            # Yield text content
            if content:
                yield StreamChunk(type="text", content=content)
                full_content += content

            # If no tool calls, we're done
            if not tool_calls:
                break

            # Execute tool calls
            for call in tool_calls:
                # Yield tool call notification
                yield StreamChunk(
                    type="tool_call",
                    tool_call={
                        "id": call.call_id,
                        "name": call.tool_name,
                        "parameters": call.parameters,
                    },
                )

                # Execute tool
                result = await self.executor.execute(
                    call,
                    context=context or {"db": self.db},
                )

                # Yield tool result
                yield StreamChunk(
                    type="tool_result",
                    tool_result={
                        "call_id": call.call_id,
                        "tool_name": call.tool_name,
                        "success": result.success,
                        "result": result.result if result.success else None,
                        "error": result.error if not result.success else None,
                    },
                )

                # Save to database
                self._save_message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=content,
                    tool_calls=[{
                        "id": call.call_id,
                        "name": call.tool_name,
                        "parameters": call.parameters,
                }],
            )

            result_content = (
                json.dumps(result.result, ensure_ascii=False)
                if result.success
                else f"Error: {result.error}"
            )
            self._save_message(
                conversation_id=conversation_id,
                role="tool_result",
                content=result_content,
                tool_call_id=call.call_id,
            )

            self._append_tool_result_to_messages(
                messages=messages,
                provider=provider,
                adapter=adapter,
                call=call,
                result=result,
                raw_response=response.get("raw_response"),
            )

        # Continue with remaining iterations
        while iteration < MAX_TOOL_ITERATIONS:
            iteration += 1

            # Call LLM
            try:
                response = await self._call_llm(
                    provider, model, messages, formatted_tools
                )
            except Exception as e:
                yield StreamChunk(type="error", content=str(e))
                return

            total_tokens_in += response["usage"].get("input_tokens", 0)
            total_tokens_out += response["usage"].get("output_tokens", 0)

            tool_calls = response.get("tool_calls", [])
            content = response.get("content", "")

            # Yield text content
            if content:
                yield StreamChunk(type="text", content=content)
                full_content += content

            # If no tool calls, we're done
            if not tool_calls:
                break

            # Execute tool calls
            for call in tool_calls:
                # Yield tool call notification
                yield StreamChunk(
                    type="tool_call",
                    tool_call={
                        "id": call.call_id,
                        "name": call.tool_name,
                        "parameters": call.parameters,
                    },
                )

                # Execute tool
                result = await self.executor.execute(
                    call,
                    context=context or {"db": self.db},
                )

                # Yield tool result
                yield StreamChunk(
                    type="tool_result",
                    tool_result={
                        "call_id": call.call_id,
                        "tool_name": call.tool_name,
                        "success": result.success,
                        "result": result.result if result.success else None,
                        "error": result.error if not result.success else None,
                    },
                )

                # Save to database
                self._save_message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=content,
                    tool_calls=[{
                        "id": call.call_id,
                        "name": call.tool_name,
                        "parameters": call.parameters,
                    }],
                )

                result_content = (
                    json.dumps(result.result, ensure_ascii=False)
                    if result.success
                    else f"Error: {result.error}"
                )
                self._save_message(
                    conversation_id=conversation_id,
                    role="tool_result",
                    content=result_content,
                    tool_call_id=call.call_id,
                )

                # Update messages for next iteration
                self._append_tool_result_to_messages(
                    messages=messages,
                    provider=provider,
                    adapter=adapter,
                    call=call,
                    result=result,
                    raw_response=response.get("raw_response"),
                )

        # Save final response
        self._save_message(
            conversation_id=conversation_id,
            role="assistant",
            content=full_content,
            tokens_in=total_tokens_in,
            tokens_out=total_tokens_out,
        )

        # Signal completion with token counts
        yield StreamChunk(
            type="done",
            tokens_in=total_tokens_in,
            tokens_out=total_tokens_out,
        )
