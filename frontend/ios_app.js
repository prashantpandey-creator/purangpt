const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-button');
const messagesContainer = document.querySelector('main');
let currentSessionId = crypto.randomUUID();
let historyCount = 0;

function createMessageDiv(role, text, status = null, idx = null) {
    const wrapper = document.createElement('div');
    if (role === 'user') {
        wrapper.className = 'flex justify-end mb-2 user-msg group relative';
        if (idx !== null) wrapper.dataset.index = idx;
        wrapper.innerHTML = `
            <button class="absolute top-1/2 -left-10 -translate-y-1/2 opacity-80 p-2 bg-white/50 backdrop-blur-md border border-gray-200 rounded-full shadow-sm text-gray-700 hover:opacity-100 active:scale-95 transition-all flex items-center justify-center z-10" onclick="editUserMessage(this, ${idx})" title="Edit and Resend">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"></path></svg>
            </button>
            <div class="user-bubble-container bg-primary-container text-on-primary font-body text-body py-2 px-4 rounded-[20px] rounded-br-sm max-w-[80%] shadow-[0_2px_8px_rgba(0,0,0,0.04)]">
                <div class="user-text whitespace-pre-wrap">${escapeHtml(text)}</div>
            </div>
        `;
    } else {
        wrapper.className = 'flex flex-col items-start mb-2';
        let badgeHtml = '';
        if (status === 'grounded') {
            badgeHtml = `<div class="flex items-center gap-1 bg-[#E8F5E9] text-[#1B5E20] font-caption text-caption px-2.5 py-0.5 rounded-full mb-1 ml-2 border border-[#C8E6C9]/50">
                            <span class="material-symbols-outlined text-[12px]">check_circle</span>
                            <span>Grounded</span>
                        </div>`;
        } else if (status === 'partial') {
            badgeHtml = `<div class="flex items-center gap-1 bg-[#FFF8E1] text-[#F57F17] font-caption text-caption px-2.5 py-0.5 rounded-full mb-1 ml-2 border border-[#FFECB3]/50">
                            <span class="material-symbols-outlined text-[12px]">lightbulb</span>
                            <span>Partial</span>
                        </div>`;
        } else if (status === 'ungrounded') {
            badgeHtml = `<div class="flex items-center gap-1 bg-[#F5F5F5] text-[#757575] font-caption text-caption px-2.5 py-0.5 rounded-full mb-1 ml-2 border border-[#E0E0E0]/50">
                            <span class="material-symbols-outlined text-[12px]">info</span>
                            <span>Ungrounded</span>
                        </div>`;
        }
        
        wrapper.innerHTML = `
            ${badgeHtml}
            <div class="bg-bubble-gray text-on-background font-body text-body py-3 px-4 rounded-[20px] rounded-bl-sm max-w-[85%] shadow-[0_2px_8px_rgba(0,0,0,0.04)] leading-relaxed prose prose-sm max-w-none ai-content">
                ${marked.parse(text)}
            </div>
        `;
    }
    return wrapper;
}

function escapeHtml(unsafe) {
    return unsafe
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
}

function createTypingIndicator() {
    const indicator = document.createElement('div');
    indicator.className = 'flex flex-col items-start mb-2 transition-opacity duration-300';
    indicator.id = 'typing-indicator';
    indicator.innerHTML = `
        <div class="bg-bubble-gray text-on-background py-3 px-4 rounded-[20px] rounded-bl-sm w-[60px] h-[40px] flex items-center justify-center gap-1 shadow-[0_2px_8px_rgba(0,0,0,0.04)]">
            <div class="w-1.5 h-1.5 bg-text-secondary rounded-full animate-bounce" style="animation-delay: 0ms"></div>
            <div class="w-1.5 h-1.5 bg-text-secondary rounded-full animate-bounce" style="animation-delay: 150ms"></div>
            <div class="w-1.5 h-1.5 bg-text-secondary rounded-full animate-bounce" style="animation-delay: 300ms"></div>
        </div>
    `;
    return indicator;
}

async function sendMessage(truncateIndex = null) {
    let text = chatInput.value.trim();
    if (!text) return;
    
    let currentIdx = truncateIndex !== null ? truncateIndex : historyCount;
    // Set historyCount to currentIdx in case the backend hasn't responded yet, to prevent out-of-order edits from overlapping.
    // It will be accurately synced when the backend streams the 'done' event.
    historyCount = currentIdx;
    
    // Add user message
    messagesContainer.appendChild(createMessageDiv('user', text, null, currentIdx));
    chatInput.value = '';
    chatInput.style.height = '44px'; // Reset height
    toggleSendButton();
    window.scrollTo(0, document.body.scrollHeight);
    
    // Add typing indicator
    const typingIndicator = createTypingIndicator();
    messagesContainer.appendChild(typingIndicator);
    window.scrollTo(0, document.body.scrollHeight);
    
    // Create assistant message placeholder
    const assistantWrapper = document.createElement('div');
    assistantWrapper.className = 'flex flex-col items-start mb-2';
    
    const badgeContainer = document.createElement('div');
    const bubble = document.createElement('div');
    bubble.className = 'bg-bubble-gray text-on-background font-body text-body py-3 px-4 rounded-[20px] rounded-bl-sm max-w-[85%] shadow-[0_2px_8px_rgba(0,0,0,0.04)] leading-relaxed prose prose-sm max-w-none ai-content';
    
    assistantWrapper.appendChild(badgeContainer);
    assistantWrapper.appendChild(bubble);
    
    let currentHtml = '';
    
    let payload = {
        query: text,
        mode: 'scholar',
        session_id: currentSessionId
    };
    if (truncateIndex !== null) {
        payload.truncate_history_from_index = truncateIndex;
    }
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        typingIndicator.remove();
        messagesContainer.appendChild(assistantWrapper);
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\\n');
            buffer = lines.pop(); // keep last incomplete line
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const dataStr = line.substring(6).trim();
                    if (!dataStr) continue;
                    if (dataStr === '[DONE]') continue;
                    
                    try {
                        const data = JSON.parse(dataStr);
                        if (data.type === 'token') {
                            currentHtml += data.content;
                            bubble.innerHTML = marked.parse(currentHtml);
                            window.scrollTo(0, document.body.scrollHeight);
                        } else if (data.type === 'done') {
                            if (data.history_len !== undefined) {
                                historyCount = data.history_len;
                            }
                            const status = data.grounding_quality || 'ungrounded';
                            if (status === 'grounded') {
                                badgeContainer.innerHTML = `<div class="flex items-center gap-1 bg-[#E8F5E9] text-[#1B5E20] font-caption text-caption px-2.5 py-0.5 rounded-full mb-1 ml-2 border border-[#C8E6C9]/50"><span class="material-symbols-outlined text-[12px]">check_circle</span><span>Grounded (${data.total_sources_found} sources)</span></div>`;
                            } else if (status === 'partial') {
                                badgeContainer.innerHTML = `<div class="flex items-center gap-1 bg-[#FFF8E1] text-[#F57F17] font-caption text-caption px-2.5 py-0.5 rounded-full mb-1 ml-2 border border-[#FFECB3]/50"><span class="material-symbols-outlined text-[12px]">lightbulb</span><span>Partial</span></div>`;
                            } else {
                                badgeContainer.innerHTML = `<div class="flex items-center gap-1 bg-[#F5F5F5] text-[#757575] font-caption text-caption px-2.5 py-0.5 rounded-full mb-1 ml-2 border border-[#E0E0E0]/50"><span class="material-symbols-outlined text-[12px]">info</span><span>Ungrounded</span></div>`;
                            }
                        }
                    } catch (e) {
                        console.error("Error parsing JSON", e, dataStr);
                    }
                }
            }
        }
    } catch (e) {
        typingIndicator.remove();
        bubble.innerText = 'Error connecting to the Vedic Scholar.';
        messagesContainer.appendChild(assistantWrapper);
    }
}

sendBtn.addEventListener('click', () => sendMessage());
chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// Edit & Resend Logic
window.editUserMessage = function(btn, idx) {
    const wrapper = btn.closest('.user-msg');
    const container = wrapper.querySelector('.user-bubble-container');
    const textEl = container.querySelector('.user-text');
    const currentText = textEl.innerText;
    
    container.innerHTML = `
        <textarea class="edit-textarea w-full bg-white/20 text-on-primary border-b border-white/50 focus:border-white outline-none resize-none overflow-hidden" rows="2" style="min-width: 200px;">${escapeHtml(currentText)}</textarea>
        <div class="flex justify-end gap-2 mt-2">
            <button class="text-xs bg-white text-primary-container px-2 py-1 rounded-md" onclick="saveEditedMessage(this, ${idx})">Save & Resend</button>
            <button class="text-xs bg-transparent border border-white/50 px-2 py-1 rounded-md" onclick="cancelEditMessage(this, \`${escapeHtml(currentText).replace(/`/g, '\\`')}\`, ${idx})">Cancel</button>
        </div>
    `;
    const textarea = container.querySelector('textarea');
    textarea.focus();
    textarea.selectionStart = textarea.value.length;
};

window.cancelEditMessage = function(btn, origText, idx) {
    const container = btn.closest('.user-bubble-container');
    container.innerHTML = `<div class="user-text whitespace-pre-wrap">${origText}</div>`;
};

window.saveEditedMessage = function(btn, idx) {
    const wrapper = btn.closest('.user-msg');
    const container = wrapper.querySelector('.user-bubble-container');
    const newText = container.querySelector('.edit-textarea').value.trim();
    if (!newText) return;
    
    let nextEl = wrapper.nextElementSibling;
    while(nextEl) {
        const toRemove = nextEl;
        nextEl = nextEl.nextElementSibling;
        toRemove.remove();
    }
    
    wrapper.remove();
    historyCount = idx;
    chatInput.value = newText;
    sendMessage(idx);
};
