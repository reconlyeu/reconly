"""Chat module for LLM conversation with tool calling.

This module provides the tool calling infrastructure for LLM chat conversations.
It includes:
- ChatService: Main service for managing conversations and chat flow
- ToolDefinition: Defines a tool's schema and handler
- ToolRegistry: Stores and retrieves tool definitions
- ToolExecutor: Safely executes tool calls with validation
- Built-in tools: Imported from tools_impl when the module loads

Example:
    >>> from reconly_core.chat import ChatService, tool_registry
    >>> from sqlalchemy.orm import Session
    >>>
    >>> service = ChatService(db=session)
    >>> conv = await service.create_conversation("My Chat")
    >>> response = await service.chat(conv.id, "List my feeds")
    >>> print(response.content)
"""

from reconly_core.chat.tools import (
    ToolDefinition,
    ToolRegistry,
    tool_registry,
)
from reconly_core.chat.executor import (
    ToolExecutor,
    ToolResult,
    ToolExecutionError,
)
from reconly_core.chat.service import (
    ChatService,
    ChatResponse,
    StreamChunk,
    ChatServiceError,
    ConversationNotFoundError,
    ProviderError,
)

# Import tools_impl to register all built-in tools with the registry
# This happens at module load time via the @tool_registry.register decorators
import reconly_core.chat.tools_impl  # noqa: F401

__all__ = [
    # Service
    "ChatService",
    "ChatResponse",
    "StreamChunk",
    "ChatServiceError",
    "ConversationNotFoundError",
    "ProviderError",
    # Tools
    "ToolDefinition",
    "ToolRegistry",
    "tool_registry",
    "ToolExecutor",
    "ToolResult",
    "ToolExecutionError",
]
