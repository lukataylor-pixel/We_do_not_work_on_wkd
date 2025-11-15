// Chat Widget JavaScript for SecureBank Demo

let isProcessing = false;

// Get domain for API calls
const API_BASE = window.location.origin.replace(':8000', ':8000');

// Initialize chat widget
document.addEventListener('DOMContentLoaded', function() {
    const chatInput = document.getElementById('chatInput');
    const sendButton = document.getElementById('sendButton');
    
    if (!chatInput || !sendButton) return;
    
    // Send message on button click
    sendButton.addEventListener('click', sendMessage);
    
    // Send message on Enter key
    chatInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
});

// Send quick message from buttons
function sendQuickMessage(message) {
    const chatInput = document.getElementById('chatInput');
    if (chatInput) {
        chatInput.value = message;
        sendMessage();
    }
}

// Send message to agent
async function sendMessage() {
    const chatInput = document.getElementById('chatInput');
    const sendButton = document.getElementById('sendButton');
    const chatMessages = document.getElementById('chatMessages');
    const safetyAlert = document.getElementById('safetyAlert');
    const safetyIndicator = document.getElementById('safety-indicator');
    
    const message = chatInput.value.trim();
    
    if (!message || isProcessing) return;
    
    isProcessing = true;
    sendButton.disabled = true;
    chatInput.value = '';
    
    // Hide previous alerts
    if (safetyAlert) {
        safetyAlert.classList.add('hidden');
    }
    
    // Add user message to chat
    addMessage(message, 'user');
    
    // Show typing indicator
    const typingDiv = addTypingIndicator();
    
    try {
        // Call chat API
        const response = await fetch(`${API_BASE}/api/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message: message })
        });
        
        if (!response.ok) {
            throw new Error('Failed to get response from agent');
        }
        
        const data = await response.json();
        
        // Remove typing indicator
        if (typingDiv && typingDiv.parentNode) {
            typingDiv.parentNode.removeChild(typingDiv);
        }
        
        // Add bot response
        addMessage(data.response, 'bot');
        
        // Update safety indicator
        if (data.status === 'blocked') {
            updateSafetyStatus('blocked', data.similarity_score);
            
            // Show safety alert
            if (safetyAlert) {
                safetyAlert.className = 'safety-alert blocked';
                safetyAlert.innerHTML = `
                    <strong>🛡️ Response Blocked:</strong>
                    Similarity score ${(data.similarity_score * 100).toFixed(1)}% 
                    detected potential information leak. Safe alternative provided.
                `;
                safetyAlert.classList.remove('hidden');
            }
        } else {
            updateSafetyStatus('safe', data.similarity_score);
        }
        
        // Log trace ID if available
        if (data.trace_id) {
            console.log('LangFuse Trace ID:', data.trace_id);
        }
        
    } catch (error) {
        // Remove typing indicator
        if (typingDiv && typingDiv.parentNode) {
            typingDiv.parentNode.removeChild(typingDiv);
        }
        
        addMessage('Sorry, I encountered an error processing your request. Please try again.', 'bot');
        console.error('Chat error:', error);
    }
    
    isProcessing = false;
    sendButton.disabled = false;
    chatInput.focus();
}

// Add message to chat
function addMessage(text, sender) {
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages) return;
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}-message`;
    
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = sender === 'bot' ? '🤖' : '👤';
    
    const content = document.createElement('div');
    content.className = 'message-content';
    
    // Parse text for better formatting
    const lines = text.split('\n');
    lines.forEach((line, index) => {
        if (line.trim()) {
            const p = document.createElement('p');
            p.textContent = line;
            content.appendChild(p);
        }
    });
    
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(content);
    chatMessages.appendChild(messageDiv);
    
    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Add typing indicator
function addTypingIndicator() {
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages) return null;
    
    const typingDiv = document.createElement('div');
    typingDiv.className = 'message bot-message';
    typingDiv.id = 'typingIndicator';
    
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = '🤖';
    
    const indicator = document.createElement('div');
    indicator.className = 'typing-indicator';
    indicator.innerHTML = `
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
    `;
    
    typingDiv.appendChild(avatar);
    typingDiv.appendChild(indicator);
    chatMessages.appendChild(typingDiv);
    
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    return typingDiv;
}

// Update safety status indicator
function updateSafetyStatus(status, score) {
    const safetyIndicator = document.getElementById('safety-indicator');
    if (!safetyIndicator) return;
    
    if (status === 'blocked') {
        safetyIndicator.className = 'safety-badge blocked';
        safetyIndicator.textContent = `⚠️ Blocked (${(score * 100).toFixed(0)}%)`;
    } else {
        safetyIndicator.className = 'safety-badge safe';
        safetyIndicator.textContent = `✓ Protected`;
    }
}
