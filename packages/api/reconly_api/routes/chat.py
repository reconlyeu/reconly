"""Chat API endpoints for LLM conversations with tool calling.

This module provides REST endpoints for the chat interface:
- Non-streaming and streaming chat completions
- Conversation CRUD operations
- SSE streaming for real-time responses

Example usage:
    # Non-streaming chat
    POST /api/v1/chat
    {"message": "List my feeds", "conversation_id": 1}

    # Streaming chat (SSE)
    POST /api/v1/chat/stream
    Accept: text/event-stream
    {"message": "Create a feed for HN", "conversation_id": 1}

    # List conversations
    GET /api/v1/chat/conversations
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from reconly_api.dependencies import get_db, limiter
from reconly_api.schemas.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatConversationCreate,
    ChatConversationDetail,
    ChatConversationList,
    ChatConversationResponse,
    ChatConversationUpdate,
    ChatMessageResponse,
)
from reconly_core.chat.service import (
    ChatService,
    ConversationNotFoundError,
    ProviderError,
)

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Chat Completion Endpoints
# =============================================================================


@router.post("", response_model=ChatCompletionResponse)
@limiter.limit("30/minute")
async def chat_completion(
    request: Request,
    chat_request: ChatCompletionRequest,
    conversation_id: int = Query(..., description="Conversation ID to send message to"),
    db: Session = Depends(get_db),
):
    """
    Send a message and get a non-streaming response.

    This endpoint handles the complete chat workflow:
    1. Saves the user message to the conversation
    2. Calls the LLM with available tools
    3. Executes any requested tool calls
    4. Returns the assistant's response

    - **message**: The user's message (1-32000 characters)
    - **conversation_id**: ID of the conversation
    - **model_provider**: Override LLM provider (optional)
    - **model_name**: Override model name (optional)
    """
    try:
        service = ChatService(db)

        # Send message and get response
        response = await service.chat(
            conversation_id=conversation_id,
            user_message=chat_request.message,
            context={"db": db},
        )

        # Build tool calls executed list
        tool_calls_executed = None
        if response.tool_calls or response.tool_results:
            tool_calls_executed = []
            for i, call in enumerate(response.tool_calls):
                result = response.tool_results[i] if i < len(response.tool_results) else None
                tool_calls_executed.append({
                    "id": call.call_id,
                    "name": call.tool_name,
                    "parameters": call.parameters,
                    "success": result.success if result else None,
                    "result": result.result if result and result.success else None,
                    "error": result.error if result and not result.success else None,
                })

        # Load the assistant message for response
        conversation = await service.get_conversation(conversation_id)
        assistant_messages = [m for m in conversation.messages if m.role == "assistant"]
        latest_message = assistant_messages[-1] if assistant_messages else None

        if not latest_message:
            raise HTTPException(status_code=500, detail="Failed to get assistant response")

        return ChatCompletionResponse(
            message=ChatMessageResponse(
                id=latest_message.id,
                conversation_id=conversation_id,
                role=latest_message.role,
                content=response.content,
                tool_calls=latest_message.tool_calls,
                tool_call_id=latest_message.tool_call_id,
                tokens_in=response.tokens_in,
                tokens_out=response.tokens_out,
                created_at=latest_message.created_at,
            ),
            conversation_id=conversation_id,
            tool_calls_executed=tool_calls_executed,
        )

    except ConversationNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation {conversation_id} not found"
        )
    except ProviderError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Chat completion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
@limiter.limit("30/minute")
async def chat_stream(
    request: Request,
    chat_request: ChatCompletionRequest,
    conversation_id: int = Query(..., description="Conversation ID to send message to"),
    db: Session = Depends(get_db),
):
    """
    Send a message and stream the response via Server-Sent Events (SSE).

    The response is a stream of SSE events:
    - `content`: Text content chunks as they're generated
    - `tool_call`: Notification when a tool is being called
    - `tool_result`: Result of a tool call
    - `done`: Stream complete with token usage stats
    - `error`: An error occurred

    SSE Event Format:
    ```
    event: content
    data: {"content": "Sure, I'll create..."}

    event: tool_call
    data: {"id": "call_123", "name": "create_feed", "arguments": {...}}

    event: tool_result
    data: {"call_id": "call_123", "result": {...}}

    event: done
    data: {"tokens_in": 150, "tokens_out": 200}
    ```

    - **message**: The user's message (1-32000 characters)
    - **conversation_id**: ID of the conversation
    - **model_provider**: Override LLM provider (optional)
    - **model_name**: Override model name (optional)
    """
    # Validate conversation exists before starting stream
    try:
        service = ChatService(db)
        await service.get_conversation(conversation_id)
    except ConversationNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation {conversation_id} not found"
        )
    except Exception as e:
        logger.exception(f"Error validating conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    async def generate_sse():
        """Generate SSE events from chat stream."""
        service = ChatService(db)

        try:
            async for chunk in service.chat_stream(
                conversation_id=conversation_id,
                user_message=chat_request.message,
                context={"db": db},
            ):
                if chunk.type == "text":
                    yield f"event: content\ndata: {json.dumps({'content': chunk.content})}\n\n"

                elif chunk.type == "tool_call":
                    yield f"event: tool_call\ndata: {json.dumps(chunk.tool_call)}\n\n"

                elif chunk.type == "tool_result":
                    yield f"event: tool_result\ndata: {json.dumps(chunk.tool_result)}\n\n"

                elif chunk.type == "done":
                    yield f"event: done\ndata: {json.dumps({'tokens_in': chunk.tokens_in, 'tokens_out': chunk.tokens_out})}\n\n"

                elif chunk.type == "error":
                    yield f"event: error\ndata: {json.dumps({'error': chunk.content})}\n\n"

        except ConversationNotFoundError:
            yield f"event: error\ndata: {json.dumps({'error': 'Conversation not found'})}\n\n"
        except ProviderError as e:
            yield f"event: error\ndata: {json.dumps({'error': f'Provider error: {str(e)}'})}\n\n"
        except Exception as e:
            logger.exception(f"Stream error: {e}")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


# =============================================================================
# Conversation CRUD Endpoints
# =============================================================================


@router.get("/conversations", response_model=ChatConversationList)
async def list_conversations(
    limit: int = Query(50, ge=1, le=100, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db),
):
    """
    List chat conversations with pagination.

    Returns conversations ordered by most recently updated.

    - **limit**: Maximum number of conversations to return (1-100)
    - **offset**: Number of conversations to skip for pagination
    """
    try:
        service = ChatService(db)
        conversations, total = await service.list_conversations(
            limit=limit,
            offset=offset,
            user_id=None,  # Single-user OSS mode
        )

        # Convert to response format with message counts
        items = []
        for conv in conversations:
            items.append(ChatConversationResponse(
                id=conv.id,
                user_id=conv.user_id,
                title=conv.title,
                model_provider=conv.model_provider,
                model_name=conv.model_name,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                message_count=len(conv.messages) if conv.messages else 0,
            ))

        return ChatConversationList(total=total, items=items)

    except Exception as e:
        logger.exception(f"Error listing conversations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conversations", response_model=ChatConversationResponse, status_code=201)
async def create_conversation(
    conversation: ChatConversationCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new chat conversation.

    - **title**: Conversation title (default: "New Conversation")
    - **model_provider**: LLM provider (ollama, anthropic, openai)
    - **model_name**: Specific model name (llama3.2, claude-3-5-sonnet, etc.)
    """
    try:
        service = ChatService(db)
        conv = await service.create_conversation(
            title=conversation.title,
            model_provider=conversation.model_provider,
            model_name=conversation.model_name,
            user_id=None,  # Single-user OSS mode
        )

        return ChatConversationResponse(
            id=conv.id,
            user_id=conv.user_id,
            title=conv.title,
            model_provider=conv.model_provider,
            model_name=conv.model_name,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=0,
        )

    except Exception as e:
        logger.exception(f"Error creating conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations/{conversation_id}", response_model=ChatConversationDetail)
async def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
):
    """
    Get a specific conversation with all its messages.

    - **conversation_id**: ID of the conversation to retrieve
    """
    try:
        service = ChatService(db)
        conv = await service.get_conversation(conversation_id)

        # Build message responses
        messages = []
        for msg in conv.messages:
            messages.append(ChatMessageResponse(
                id=msg.id,
                conversation_id=msg.conversation_id,
                role=msg.role,
                content=msg.content,
                tool_calls=msg.tool_calls,
                tool_call_id=msg.tool_call_id,
                tokens_in=msg.tokens_in,
                tokens_out=msg.tokens_out,
                created_at=msg.created_at,
            ))

        return ChatConversationDetail(
            id=conv.id,
            user_id=conv.user_id,
            title=conv.title,
            model_provider=conv.model_provider,
            model_name=conv.model_name,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=len(messages),
            messages=messages,
        )

    except ConversationNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation {conversation_id} not found"
        )
    except Exception as e:
        logger.exception(f"Error getting conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/conversations/{conversation_id}", response_model=ChatConversationResponse)
async def update_conversation(
    conversation_id: int,
    update: ChatConversationUpdate,
    db: Session = Depends(get_db),
):
    """
    Update a conversation's title or model settings.

    - **conversation_id**: ID of the conversation to update
    - **title**: New title (optional)
    - **model_provider**: New LLM provider (optional)
    - **model_name**: New model name (optional)
    """
    try:
        service = ChatService(db)

        # Get existing conversation
        conv = await service.get_conversation(conversation_id)

        # Update fields if provided
        if update.title is not None:
            conv = await service.update_conversation_title(conversation_id, update.title)

        # For model updates, we need to update directly since the service
        # only has update_conversation_title method
        if update.model_provider is not None or update.model_name is not None:
            from datetime import datetime
            if update.model_provider is not None:
                conv.model_provider = update.model_provider
            if update.model_name is not None:
                conv.model_name = update.model_name
            conv.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(conv)

        return ChatConversationResponse(
            id=conv.id,
            user_id=conv.user_id,
            title=conv.title,
            model_provider=conv.model_provider,
            model_name=conv.model_name,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=len(conv.messages) if conv.messages else 0,
        )

    except ConversationNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation {conversation_id} not found"
        )
    except Exception as e:
        logger.exception(f"Error updating conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
):
    """
    Delete a conversation and all its messages.

    - **conversation_id**: ID of the conversation to delete
    """
    try:
        service = ChatService(db)
        deleted = await service.delete_conversation(conversation_id)

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=f"Conversation {conversation_id} not found"
            )

        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error deleting conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))
