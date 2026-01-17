"""Chat conversation and message schemas for LLM chat interface."""
from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class ChatMessageRole(str, Enum):
    """Supported message roles in chat conversations."""
    user = "user"
    assistant = "assistant"
    tool_call = "tool_call"
    tool_result = "tool_result"


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL CALL SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════


class ToolCall(BaseModel):
    """A tool call requested by the assistant.

    Uses a simplified format for internal storage:
    - id: Tool call identifier
    - name: Name of the tool/function
    - parameters: Dict of parameters passed to the tool
    """
    id: str | None = Field(None, description="Unique identifier for this tool call")
    name: str = Field(..., description="Name of the tool to call")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Parameters for the tool")

    model_config = ConfigDict(from_attributes=True)


# ═══════════════════════════════════════════════════════════════════════════════
# MESSAGE SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════


class ChatMessageCreate(BaseModel):
    """Schema for creating a new chat message."""
    role: ChatMessageRole = Field(..., description="Message role: user, assistant, tool_call, tool_result")
    content: str | None = Field(None, description="Message content (nullable for tool_call messages)")
    tool_calls: list[ToolCall] | None = Field(
        None,
        description="Tool calls for assistant messages requesting tools"
    )
    tool_call_id: str | None = Field(
        None,
        description="Tool call ID for tool_result messages"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "role": "user",
                "content": "What news articles are available about AI?"
            }
        }
    )


class ChatMessageResponse(BaseModel):
    """Schema for chat message response."""
    id: int = Field(..., description="Message ID")
    conversation_id: int = Field(..., description="Parent conversation ID")
    role: ChatMessageRole = Field(..., description="Message role")
    content: str | None = Field(None, description="Message content")
    tool_calls: list[ToolCall] | None = Field(None, description="Tool calls if any")
    tool_call_id: str | None = Field(None, description="Tool call ID for tool results")
    tokens_in: int | None = Field(None, description="Input tokens used")
    tokens_out: int | None = Field(None, description="Output tokens used")
    created_at: datetime = Field(..., description="Message creation timestamp")

    model_config = ConfigDict(from_attributes=True)


# ═══════════════════════════════════════════════════════════════════════════════
# CONVERSATION SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════


class ChatConversationCreate(BaseModel):
    """Schema for creating a new chat conversation."""
    title: str = Field(
        default="New Conversation",
        max_length=255,
        description="Conversation title"
    )
    model_provider: str | None = Field(
        None,
        max_length=50,
        description="LLM provider (ollama, anthropic, openai)"
    )
    model_name: str | None = Field(
        None,
        max_length=100,
        description="Model name (llama3.2, claude-3-5-sonnet)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Research on AI trends",
                "model_provider": "ollama",
                "model_name": "llama3.2"
            }
        }
    )


class ChatConversationUpdate(BaseModel):
    """Schema for updating a chat conversation."""
    title: str | None = Field(None, max_length=255, description="New conversation title")
    model_provider: str | None = Field(None, max_length=50, description="New LLM provider")
    model_name: str | None = Field(None, max_length=100, description="New model name")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Updated conversation title"
            }
        }
    )


class ChatConversationResponse(BaseModel):
    """Schema for chat conversation response (without messages)."""
    id: int = Field(..., description="Conversation ID")
    user_id: int | None = Field(None, description="User ID (nullable for single-user mode)")
    title: str = Field(..., description="Conversation title")
    model_provider: str | None = Field(None, description="LLM provider")
    model_name: str | None = Field(None, description="Model name")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    message_count: int = Field(default=0, description="Number of messages in conversation")

    model_config = ConfigDict(from_attributes=True)


class ChatConversationDetail(ChatConversationResponse):
    """Schema for chat conversation with messages."""
    messages: list[ChatMessageResponse] = Field(
        default_factory=list,
        description="Messages in chronological order"
    )

    model_config = ConfigDict(from_attributes=True)


# ═══════════════════════════════════════════════════════════════════════════════
# LIST SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════


class ChatConversationList(BaseModel):
    """Schema for paginated list of conversations."""
    total: int = Field(..., description="Total number of conversations")
    items: list[ChatConversationResponse] = Field(
        default_factory=list,
        description="List of conversations"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CHAT REQUEST/RESPONSE SCHEMAS (for chat completion API)
# ═══════════════════════════════════════════════════════════════════════════════


class ChatCompletionRequest(BaseModel):
    """Schema for sending a chat completion request."""
    message: str = Field(
        ...,
        min_length=1,
        max_length=32000,
        description="User message to send"
    )
    model_provider: str | None = Field(
        None,
        description="Override LLM provider for this request"
    )
    model_name: str | None = Field(
        None,
        description="Override model name for this request"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "What are the latest news articles about machine learning?"
            }
        }
    )


class ChatCompletionResponse(BaseModel):
    """Schema for chat completion response."""
    message: ChatMessageResponse = Field(
        ...,
        description="The assistant's response message"
    )
    conversation_id: int = Field(
        ...,
        description="ID of the conversation"
    )
    tool_calls_executed: list[dict[str, Any]] | None = Field(
        None,
        description="Details of any tool calls that were executed"
    )

    model_config = ConfigDict(from_attributes=True)
