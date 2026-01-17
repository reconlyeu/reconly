/**
 * Chat API functions for conversation management and chat completions.
 *
 * This module provides:
 * - Conversation CRUD operations
 * - Non-streaming chat completions
 * - SSE streaming for real-time responses
 */

import type {
  ChatConversation,
  ChatConversationCreate,
  ChatConversationDetail,
  ChatConversationList,
  ChatConversationUpdate,
  ChatCompletionRequest,
  ChatCompletionResponse,
  ChatStreamContentEvent,
  ChatStreamToolCallEvent,
  ChatStreamToolResultEvent,
  ChatStreamDoneEvent,
  ChatStreamErrorEvent,
} from '@/types/entities';

const API_BASE = '/api/v1/chat';

// ═══════════════════════════════════════════════════════════════════════════════
// CONVERSATION CRUD
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * List all conversations with pagination.
 */
export async function listConversations(
  limit = 50,
  offset = 0
): Promise<ChatConversationList> {
  const params = new URLSearchParams({
    limit: limit.toString(),
    offset: offset.toString(),
  });

  const response = await fetch(`${API_BASE}/conversations?${params}`);
  if (!response.ok) {
    throw new Error(`Failed to list conversations: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Create a new conversation.
 */
export async function createConversation(
  data: ChatConversationCreate = {}
): Promise<ChatConversation> {
  const response = await fetch(`${API_BASE}/conversations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    throw new Error(`Failed to create conversation: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Get a specific conversation with all messages.
 */
export async function getConversation(
  conversationId: number
): Promise<ChatConversationDetail> {
  const response = await fetch(`${API_BASE}/conversations/${conversationId}`);
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error('Conversation not found');
    }
    throw new Error(`Failed to get conversation: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Update a conversation's title or model settings.
 */
export async function updateConversation(
  conversationId: number,
  data: ChatConversationUpdate
): Promise<ChatConversation> {
  const response = await fetch(`${API_BASE}/conversations/${conversationId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error('Conversation not found');
    }
    throw new Error(`Failed to update conversation: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Delete a conversation and all its messages.
 */
export async function deleteConversation(conversationId: number): Promise<void> {
  const response = await fetch(`${API_BASE}/conversations/${conversationId}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error('Conversation not found');
    }
    throw new Error(`Failed to delete conversation: ${response.statusText}`);
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// CHAT COMPLETION (Non-Streaming)
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Send a message and get a complete response (non-streaming).
 */
export async function sendMessage(
  conversationId: number,
  request: ChatCompletionRequest
): Promise<ChatCompletionResponse> {
  const params = new URLSearchParams({
    conversation_id: conversationId.toString(),
  });

  const response = await fetch(`${API_BASE}?${params}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error('Conversation not found');
    }
    if (response.status === 502) {
      throw new Error('LLM provider error');
    }
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `Failed to send message: ${response.statusText}`);
  }
  return response.json();
}

// ═══════════════════════════════════════════════════════════════════════════════
// CHAT COMPLETION (SSE Streaming)
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Event handlers for SSE stream events.
 */
export interface ChatStreamHandlers {
  /** Called when text content is received */
  onContent?: (event: ChatStreamContentEvent) => void;
  /** Called when a tool is being called */
  onToolCall?: (event: ChatStreamToolCallEvent) => void;
  /** Called when a tool call completes */
  onToolResult?: (event: ChatStreamToolResultEvent) => void;
  /** Called when the stream completes */
  onDone?: (event: ChatStreamDoneEvent) => void;
  /** Called when an error occurs */
  onError?: (event: ChatStreamErrorEvent) => void;
  /** Called when the connection closes (cleanly or due to error) */
  onClose?: () => void;
}

/**
 * Send a message and stream the response via SSE.
 *
 * Returns an object with a close() method to abort the stream.
 *
 * @example
 * ```typescript
 * const stream = sendMessageStream(conversationId, { message: 'Hello' }, {
 *   onContent: (e) => appendText(e.content),
 *   onToolCall: (e) => showToolStatus(e.name),
 *   onDone: (e) => console.log('Tokens:', e.tokens_in, e.tokens_out),
 *   onError: (e) => showError(e.error),
 * });
 *
 * // Later, to cancel:
 * stream.close();
 * ```
 */
export function sendMessageStream(
  conversationId: number,
  request: ChatCompletionRequest,
  handlers: ChatStreamHandlers
): { close: () => void } {
  const abortController = new AbortController();

  // Use fetch instead of EventSource for POST requests
  const streamFetch = async () => {
    const params = new URLSearchParams({
      conversation_id: conversationId.toString(),
    });

    try {
      const response = await fetch(`${API_BASE}/stream?${params}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
        },
        body: JSON.stringify(request),
        signal: abortController.signal,
      });

      if (!response.ok) {
        const errorText = await response.text().catch(() => response.statusText);
        handlers.onError?.({ error: `HTTP ${response.status}: ${errorText}` });
        handlers.onClose?.();
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        handlers.onError?.({ error: 'No response body' });
        handlers.onClose?.();
        return;
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Process complete events in the buffer
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // Keep incomplete line in buffer

        let eventType = '';
        let eventData = '';

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            eventData = line.slice(6);
          } else if (line === '' && eventType && eventData) {
            // End of event, process it
            try {
              const data = JSON.parse(eventData);

              switch (eventType) {
                case 'content':
                  handlers.onContent?.(data as ChatStreamContentEvent);
                  break;
                case 'tool_call':
                  handlers.onToolCall?.(data as ChatStreamToolCallEvent);
                  break;
                case 'tool_result':
                  handlers.onToolResult?.(data as ChatStreamToolResultEvent);
                  break;
                case 'done':
                  handlers.onDone?.(data as ChatStreamDoneEvent);
                  break;
                case 'error':
                  handlers.onError?.(data as ChatStreamErrorEvent);
                  break;
              }
            } catch {
              console.warn('Failed to parse SSE event data:', eventData);
            }

            // Reset for next event
            eventType = '';
            eventData = '';
          }
        }
      }

      handlers.onClose?.();
    } catch (error) {
      if ((error as Error).name === 'AbortError') {
        // Stream was intentionally closed
        handlers.onClose?.();
        return;
      }

      handlers.onError?.({ error: (error as Error).message || 'Stream error' });
      handlers.onClose?.();
    }
  };

  // Start the stream
  streamFetch();

  return {
    close: () => abortController.abort(),
  };
}
