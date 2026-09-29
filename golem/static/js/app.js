// Golem - Main JavaScript
//
// Core UI module for the Golem chat interface. It owns:
// - Global state (conversation history, cumulative token usage)
// - DOM initialisation and event listeners
// - The health check shown at startup
// - Rendering helpers: user, assistant, system, tool-call and
//   tool-result messages, loading indicator, token counter
// - Conversation export and import
//
// Changes from the parent project (which could write to /config):
// - Removed the entire approval UI: addApprovalCard, viewChanges,
//   showDiffModal, generateDiffHtml, approvePendingChanges,
//   rejectPendingChanges, closeDiffModal, handleApproval and the
//   pendingChangeset / currentChangesetData state. There are no
//   changesets to display, because the backend can no longer propose
//   or apply changes.
// - Removed extractOriginalContents and processMessages: both existed
//   solely to build diff views for the approval modal.
// - Removed the SSE-based sendMessage implementation: it was dead code
//   (websocket-chat.js always overrides sendMessage) and its event
//   handler contained the changeset/approval logic. Only a minimal
//   stub remains, so the override contract with websocket-chat.js is
//   preserved.
// - Removed all references to the diffModal / diffContent DOM elements
//   and to the propose_config_changes tool.
//
// Message sending itself lives in websocket-chat.js, which overrides
// sendMessage() at page load to use the /ws/chat WebSocket (avoiding
// the Home Assistant Ingress SSE buffering problem).

console.log('Golem initializing...');

// ---------------------------------------------------------------------------
// Global state
// ---------------------------------------------------------------------------
// Conversation history is sent with each request so the model has context.
// Tool roles ('tool' messages and assistant 'tool_calls') are stored in the
// same shape the backend produces, keeping the round-trip lossless.
let conversationHistory = [];

// Track cumulative token usage across the entire conversation, shown in
// the footer counter.
let cumulativeInputTokens = 0;
let cumulativeOutputTokens = 0;
let cumulativeCachedTokens = 0;

// ---------------------------------------------------------------------------
// DOM elements
// ---------------------------------------------------------------------------
// Resolved once at page load and shared with websocket-chat.js, which relies
// on the same globals (messageInput, sendBtn, chatMessages...).
let chatMessages, messageInput, sendBtn, exportBtn, importBtn, importFileInput;
let tokenCounter, tokenCounterInput, tokenCounterOutput, tokenCounterCached;

// ---------------------------------------------------------------------------
// Initialisation
// ---------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
    console.log('Page loaded, initializing chat interface...');

    // Resolve all DOM elements used by this module and websocket-chat.js.
    chatMessages = document.getElementById('chatMessages');
    messageInput = document.getElementById('messageInput');
    sendBtn = document.getElementById('sendBtn');
    exportBtn = document.getElementById('exportBtn');
    importBtn = document.getElementById('importBtn');
    importFileInput = document.getElementById('importFileInput');
    tokenCounter = document.getElementById('tokenCounter');
    tokenCounterInput = document.getElementById('tokenCounterInput');
    tokenCounterOutput = document.getElementById('tokenCounterOutput');
    tokenCounterCached = document.getElementById('tokenCounterCached');

    // Send on button click, or on Enter (Shift+Enter inserts a newline).
    sendBtn.addEventListener('click', sendMessage);
    messageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Export the visible conversation as a JSON file; import restores one.
    exportBtn.addEventListener('click', exportConversation);
    importBtn.addEventListener('click', () => importFileInput.click());
    importFileInput.addEventListener('change', importConversation);

    // Report backend readiness (API key configured, agent initialised).
    checkHealth();
});

// ---------------------------------------------------------------------------
// Health check
// ---------------------------------------------------------------------------
// Queries the /health endpoint and shows a readiness banner. This warns the
// user immediately if OPENAI_API_KEY is missing rather than failing on the
// first message.
async function checkHealth() {
    try {
        const response = await fetch('health');
        const data = await response.json();
        console.log('Health check:', data);

        if (!data.agent_system_ready) {
            addSystemMessage('⚠️ AI system not ready. Please configure OPENAI_API_KEY.');
        } else {
            addSystemMessage('✅ Golem ready. Ask me anything about your Home Assistant configuration.');
        }
    } catch (error) {
        console.error('Health check failed:', error);
        addSystemMessage('❌ Failed to connect to agent system.');
    }
}

// ---------------------------------------------------------------------------
// Message sending (stub)
// ---------------------------------------------------------------------------
// The real implementation is in websocket-chat.js, which replaces this
// function at page load (see the inline script in index.html). This stub
// exists so the override contract is explicit and the page never breaks if
// websocket-chat.js fails to load.
async function sendMessage() {
    console.warn('sendMessage not overridden; WebSocket chat module missing.');
    addSystemMessage('❌ Chat module failed to load.');
}

// ---------------------------------------------------------------------------
// Message rendering helpers
// ---------------------------------------------------------------------------

// Add a user message as plain text (user input is never rendered as HTML,
// which prevents any markup injection from the input box).
function addUserMessage(content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message user-message';
    messageDiv.textContent = content;
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

// Add a fully-formed assistant message with markdown rendering.
function addAssistantMessage(content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant-message';

    if (typeof marked !== 'undefined') {
        messageDiv.innerHTML = marked.parse(content);
    } else {
        messageDiv.textContent = content;
    }

    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

// Create a streaming assistant message element (plain text while streaming).
function addAssistantMessageStreaming(content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant-message streaming';
    messageDiv.textContent = content;
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
    return messageDiv;
}

// Update a streaming assistant message as tokens arrive.
function updateAssistantMessageStreaming(messageDiv, content) {
    messageDiv.textContent = content;
    scrollToBottom();
}

// Finalise a streaming message: apply markdown rendering once complete, so
// the user sees progressive plain text and the formatted result at the end.
function finalizeAssistantMessageStreaming(messageDiv) {
    const content = messageDiv.textContent;
    messageDiv.classList.remove('streaming');

    if (typeof marked !== 'undefined') {
        messageDiv.innerHTML = marked.parse(content);
    }
    scrollToBottom();
}

// Add a system/informational message.
function addSystemMessage(content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message system-message';
    messageDiv.textContent = content;
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

// ---------------------------------------------------------------------------
// Tool activity rendering
// ---------------------------------------------------------------------------

// Add a collapsible summary card showing which tools the model called and
// their arguments. All tool activity in Golem is read-only (searches and
// file reads), so this is purely informational.
function addToolCallMessage(toolCalls) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message tool-call-message';

    const toolCallId = 'toolcall-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
    const toolNames = toolCalls.map(tc => tc.function.name).join(', ');

    let html = '<div class="tool-call-content">';
    html += `<div class="tool-call-header">`;
    html += `<span class="tool-call-icon">🔧</span>`;
    html += `<span class="tool-call-summary">Calling ${toolCalls.length} tool(s): ${escapeHtml(toolNames)}</span>`;
    html += `<button class="tool-call-toggle" onclick="toggleToolCall('${toolCallId}')">▼ Arguments</button>`;
    html += `</div>`;
    html += `<div class="tool-call-details" id="${toolCallId}" style="display: none;">`;

    for (let i = 0; i < toolCalls.length; i++) {
        const tc = toolCalls[i];
        html += '<div class="tool-call-item">';
        html += `<div class="tool-call-item-header"><strong>${i + 1}. ${escapeHtml(tc.function.name)}</strong></div>`;

        // Arguments arrive as a JSON string from the API; pretty-print them.
        let args;
        try {
            args = typeof tc.function.arguments === 'string'
                ? JSON.parse(tc.function.arguments)
                : tc.function.arguments;
            html += `<pre><code>${escapeHtml(JSON.stringify(args, null, 2))}</code></pre>`;
        } catch (e) {
            html += `<pre><code>${escapeHtml(tc.function.arguments)}</code></pre>`;
        }

        html += '</div>';
    }

    html += `</div>`;
    html += '</div>';

    messageDiv.innerHTML = html;
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

// Toggle the arguments section of a tool-call card.
window.toggleToolCall = function(toolCallId) {
    const detailsDiv = document.getElementById(toolCallId);
    const button = detailsDiv.previousElementSibling.querySelector('.tool-call-toggle');

    if (detailsDiv.style.display === 'none') {
        detailsDiv.style.display = 'block';
        button.textContent = '▲ Arguments';
    } else {
        detailsDiv.style.display = 'none';
        button.textContent = '▼ Arguments';
    }
};

// Add a collapsible result card for one completed tool call. Summaries are
// generated per read-only tool; designed rejections (result.rejected) are
// shown as notices, and unknown tools fall through to a generic line.
function addToolResultMessage(functionName, result) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message tool-result-message';

    let summary = '';
    let icon = '';

    // Designed rejections (e.g. a search pattern too broad for the tool)
    // are not errors: show them as informational notices. The 'rejected'
    // flag is set by the backend so genuine failures remain distinct.
    if (result.rejected === true) {
        icon = '🔎';
        const patternMatch = result.error ? result.error.match(/'([^']+)'/) : null;
        const pattern = patternMatch ? patternMatch[1] : '';
        summary = pattern
            ? `Search pattern "${pattern}" was too broad — a more specific identifier is needed`
            : 'Search pattern rejected — a more specific identifier is needed';
    } else if (result.success === false) {
        icon = '❌';
        summary = `Error in ${functionName}: ${result.error || 'Unknown error'}`;
    } else if (functionName === 'search_config_files') {
        icon = '🔍';
        const fileCount = result.count || result.files?.length || 0;
        summary = `Found ${fileCount} file(s)`;
    } else if (functionName === 'read_config_file') {
        icon = '📄';
        summary = `Read ${result.path}${result.truncated ? ' (truncated)' : ''}`;
    } else {
        icon = '✓';
        summary = `${functionName} completed`;
    }

    const resultId = 'result-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);

    let html = '<div class="tool-result-content">';
    html += `<div class="tool-result-header">`;
    html += `<span class="tool-result-icon">${icon}</span>`;
    html += `<span class="tool-result-summary">${escapeHtml(summary)}</span>`;
    html += `<button class="tool-result-toggle" onclick="toggleToolResult('${resultId}')">▼ Details</button>`;
    html += `</div>`;
    html += `<div class="tool-result-details" id="${resultId}" style="display: none;">`;
    html += `<pre><code>${escapeHtml(JSON.stringify(result, null, 2))}</code></pre>`;
    html += `</div>`;
    html += '</div>';

    messageDiv.innerHTML = html;
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

// Toggle the details section of a tool-result card.
window.toggleToolResult = function(resultId) {
    const detailsDiv = document.getElementById(resultId);
    const button = detailsDiv.previousElementSibling.querySelector('.tool-result-toggle');

    if (detailsDiv.style.display === 'none') {
        detailsDiv.style.display = 'block';
        button.textContent = '▲ Details';
    } else {
        detailsDiv.style.display = 'none';
        button.textContent = '▼ Details';
    }
};

// ---------------------------------------------------------------------------
// Loading indicator
// ---------------------------------------------------------------------------

// Three-dot "thinking" indicator shown while waiting for the first event.
function addLoadingIndicator() {
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'message assistant-message loading-message';
    loadingDiv.innerHTML = `
        <div class="loading-indicator">
            <div class="loading-dots">
                <span class="dot"></span>
                <span class="dot"></span>
                <span class="dot"></span>
            </div>
            <span class="loading-text">Golem is thinking...</span>
        </div>
    `;
    chatMessages.appendChild(loadingDiv);
    scrollToBottom();
    return loadingDiv;
}

// Remove the loading indicator (safe to call with a stale reference).
function removeLoadingIndicator(indicator) {
    if (indicator && indicator.parentNode) {
        indicator.parentNode.removeChild(indicator);
    }
}

// ---------------------------------------------------------------------------
// Token usage counter
// ---------------------------------------------------------------------------

// Accumulate and display token usage in the footer bubble. Called from
// websocket-chat.js on message_complete and complete events.
function updateTokenCounter(inputTokens, outputTokens, cachedTokens = 0) {
    cumulativeInputTokens += inputTokens;
    cumulativeOutputTokens += outputTokens;
    cumulativeCachedTokens += cachedTokens;

    tokenCounterInput.textContent = `↓${cumulativeInputTokens.toLocaleString()}`;
    tokenCounterOutput.textContent = `↑${cumulativeOutputTokens.toLocaleString()}`;

    // The cached-tokens span only appears once some cached tokens exist.
    if (cumulativeCachedTokens > 0) {
        tokenCounterCached.textContent = `💾${cumulativeCachedTokens.toLocaleString()}`;
        tokenCounterCached.style.display = 'inline';
    } else {
        tokenCounterCached.style.display = 'none';
    }

    if (tokenCounter.style.display === 'none') {
        tokenCounter.style.display = 'flex';
    }

    // Brief pulse animation on each update.
    tokenCounter.classList.add('updated');
    setTimeout(() => {
        tokenCounter.classList.remove('updated');
    }, 300);
}

// Reset the counter (used on import of a fresh conversation).
function resetTokenCounter() {
    cumulativeInputTokens = 0;
    cumulativeOutputTokens = 0;
    cumulativeCachedTokens = 0;
    tokenCounterInput.textContent = '↓0';
    tokenCounterOutput.textContent = '↑0';
    tokenCounterCached.textContent = '💾0';
    tokenCounterCached.style.display = 'none';
    tokenCounter.style.display = 'none';
}

// ---------------------------------------------------------------------------
// Conversation export / import
// ---------------------------------------------------------------------------

// Download the conversation history as a JSON file.
function exportConversation() {
    const exportData = {
        exported_at: new Date().toISOString(),
        conversation: conversationHistory
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `golem-conversation-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
}

// Load a previously exported conversation file and re-render it.
function importConversation(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
        try {
            const data = JSON.parse(e.target.result);
            const messages = data.conversation || data; // tolerate raw history too

            // Clear current state before re-rendering.
            conversationHistory = [];
            chatMessages.innerHTML = '';
            resetTokenCounter();

            for (const msg of messages) {
                conversationHistory.push(msg);

                // Re-render each history entry in the appropriate style.
                // Tool entries are skipped visually; their content is
                // preserved in the history sent to the backend.
                if (msg.role === 'user') {
                    addUserMessage(msg.content);
                } else if (msg.role === 'assistant' && msg.content) {
                    addAssistantMessage(msg.content);
                }
            }

            addSystemMessage(`📥 Imported conversation (${messages.length} message(s)).`);
        } catch (err) {
            console.error('Import failed:', err);
            addSystemMessage('❌ Failed to import conversation: invalid file.');
        }
    };
    reader.readAsText(file);

    // Allow re-selecting the same file later.
    event.target.value = '';
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

// Escape text for safe insertion into innerHTML. All dynamic content is
// escaped; markdown rendering is applied only to model-generated text.
function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

// Keep the newest message in view.
function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}