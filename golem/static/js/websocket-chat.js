// Golem - WebSocket-based chat implementation
//
// Owns the WebSocket connection to /ws/chat and the event handlers for the
// agent's streaming protocol (token, tool_call, tool_start, tool_result,
// message_complete, complete, error). Rendering helpers are defined in
// app.js and called from here.
//
// WebSocket streaming is used instead of SSE because the Home Assistant
// Ingress proxy buffers SSE responses, which broke progressive output.
//
// Changes from the parent project (which could write to /config):
// - Removed the propose_config_changes branch in the tool_result handler:
//   with write access removed the backend never emits that tool, so the
//   changeset assembly, the toolCallArguments store and the addApprovalCard
//   call were dead code referencing a function that no longer exists.
// - Removed the toolCallArguments global and its reset per request: it
//   existed solely to reconstruct propose_config_changes arguments for
//   the approval modal.
// - Removed the argument-capture logic in the tool_start handler for the
//   same reason; tool_start now only displays the execution notice.
//
// The send path, connection management and all retained event handlers
// are unchanged in behaviour.

let ws = null;
let currentAssistantMessage = null;
let currentMessageContent = '';
let loadingIndicator = null;

// ---------------------------------------------------------------------------
// Connection management
// ---------------------------------------------------------------------------

function connectWebSocket() {
    // Reuse an existing open connection rather than opening a new one.
    if (ws && ws.readyState === WebSocket.OPEN) {
        return ws;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // Relative path so the URL works behind the Home Assistant Ingress proxy.
    const wsUrl = `${protocol}//${window.location.host}${window.location.pathname}ws/chat`;

    console.log('Connecting to WebSocket:', wsUrl);
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log('WebSocket connected');
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        addSystemMessage('❌ WebSocket connection error');
    };

    ws.onclose = () => {
        console.log('WebSocket closed');
        ws = null;
    };

    return ws;
}

// ---------------------------------------------------------------------------
// Send path
// ---------------------------------------------------------------------------

// This function replaces the stub sendMessage in app.js at page load (see
// the override block in index.html).
async function sendMessageWebSocket() {
    const message = messageInput.value.trim();
    if (!message) return;

    console.log('Sending message via WebSocket:', message);

    // Render the user message and add it to the conversation history.
    addUserMessage(message);
    conversationHistory.push({
        role: 'user',
        content: message
    });

    // Clear the input.
    messageInput.value = '';
    messageInput.style.height = 'auto';

    // Disable the send button while the response streams; show the
    // "thinking" indicator until the first token arrives.
    sendBtn.disabled = true;
    currentAssistantMessage = null;
    currentMessageContent = '';
    loadingIndicator = addLoadingIndicator();

    try {
        const ws = connectWebSocket();

        // Wait for the connection if it is still opening, with a timeout.
        if (ws.readyState !== WebSocket.OPEN) {
            await new Promise((resolve, reject) => {
                ws.onopen = resolve;
                ws.onerror = reject;
                setTimeout(() => reject(new Error('Connection timeout')), 5000);
            });
        }

        // Install the handler for this session; every server event is a
        // single JSON frame dispatched to handleWebSocketMessage.
        ws.onmessage = (event) => {
            const message = JSON.parse(event.data);
            handleWebSocketMessage(message);
        };

        // Send the chat request; history excludes the message just added.
        ws.send(JSON.stringify({
            type: 'chat',
            message: message,
            conversation_history: conversationHistory.slice(0, -1)
        }));

    } catch (error) {
        console.error('WebSocket send error:', error);
        removeLoadingIndicator(loadingIndicator);
        addSystemMessage(`❌ Error: ${error.message}`);
        sendBtn.disabled = false;
        messageInput.focus();
    }
}

// ---------------------------------------------------------------------------
// Event handling
// ---------------------------------------------------------------------------

// Dispatch one server event. Every branch cleans up the loading indicator
// and send button state as appropriate, so the UI never sticks mid-stream.
function handleWebSocketMessage(message) {
    const eventType = message.event;
    const data = message.data;

    console.log('WebSocket event:', eventType);

    try {
        if (eventType === 'token') {
            // First token: remove the thinking indicator and create the
            // streaming message element.
            if (loadingIndicator && loadingIndicator.parentNode) {
                removeLoadingIndicator(loadingIndicator);
                loadingIndicator = null;
            }

            // Accumulate content and update the streaming element.
            currentMessageContent += data.content;

            if (!currentAssistantMessage) {
                currentAssistantMessage = addAssistantMessageStreaming('');
            }
            updateAssistantMessageStreaming(currentAssistantMessage, currentMessageContent);

        } else if (eventType === 'message_complete') {
            // Add the final assistant message to the history.
            conversationHistory.push(data.message);

            // Apply markdown rendering to the completed message.
            if (currentAssistantMessage) {
                finalizeAssistantMessageStreaming(currentAssistantMessage);
            }
            currentMessageContent = '';
            currentAssistantMessage = null;

            // Update the cumulative token counter if usage was reported.
            if (data.usage) {
                updateTokenCounter(
                    data.usage.input_tokens || 0,
                    data.usage.output_tokens || 0,
                    data.usage.cached_tokens || 0
                );
            }

        } else if (eventType === 'tool_call') {
            // The model requested tools: finalise any partial message,
            // record the assistant turn in the history, then show a
            // summary card and re-show the indicator while the tools run.
            if (currentAssistantMessage) {
                finalizeAssistantMessageStreaming(currentAssistantMessage);
                currentAssistantMessage = null;
            }

            conversationHistory.push({
                role: 'assistant',
                content: currentMessageContent,
                tool_calls: data.tool_calls
            });
            currentMessageContent = '';

            addToolCallMessage(data.tool_calls);

            if (!loadingIndicator) {
                loadingIndicator = addLoadingIndicator();
            }

        } else if (eventType === 'tool_start') {
            // Individual tool execution notice; both remaining tools are
            // read-only, so this is purely informational.
            addSystemMessage(`▶️ Executing: ${data.function}...`);

        } else if (eventType === 'tool_result') {
            console.log('Tool result received:', data.function, 'success:', data.result?.success);

            // Record the result in the history exactly as the backend
            // produced it, preserving the round-trip for later turns.
            conversationHistory.push({
                role: 'tool',
                tool_call_id: data.tool_call_id,
                content: JSON.stringify(data.result)
            });

            // Render the collapsible result card.
            addToolResultMessage(data.function, data.result);

        } else if (eventType === 'complete') {
            console.log('Stream complete:', data);

            // Final cumulative usage update.
            if (data.usage) {
                updateTokenCounter(
                    data.usage.input_tokens || 0,
                    data.usage.output_tokens || 0,
                    data.usage.cached_tokens || 0
                );
            }

            // Final cleanup: restore the send button.
            if (loadingIndicator && loadingIndicator.parentNode) {
                removeLoadingIndicator(loadingIndicator);
                loadingIndicator = null;
            }
            sendBtn.disabled = false;
            messageInput.focus();

        } else if (eventType === 'error') {
            // Surface the error and restore the input state.
            addSystemMessage(`❌ Error: ${data.error}`);

            if (loadingIndicator && loadingIndicator.parentNode) {
                removeLoadingIndicator(loadingIndicator);
                loadingIndicator = null;
            }
            sendBtn.disabled = false;
            messageInput.focus();
        }

    } catch (e) {
        console.error('Error handling WebSocket message:', e);
    }
}

// Export for the override in index.html.
window.sendMessageWebSocket = sendMessageWebSocket;