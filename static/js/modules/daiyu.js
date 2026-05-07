/**
 * 黛玉智能模块
 * 负责林黛玉人设聊天
 */

const { ref, nextTick } = Vue;
import { buildAuthHeaders, forEachSSEEvent } from '../utils/api.js';

export function createDaiyuModule() {
    const daiyuMessages = ref([{
        id: 'daiyu-init', role: 'ai', type: 'text',
        content: '这位小友好。我是颦儿，偶然间来到这方天地。不知你有什么心事要与我说说，或是有何诗文要我品评？'
    }]);
    const daiyuQuestion = ref('');
    const daiyuStreaming = ref(false);
    const daiyuChatContainer = ref(null);

    const scrollDaiyuToBottom = async () => {
        await nextTick();
        if (daiyuChatContainer.value) {
            daiyuChatContainer.value.scrollTop = daiyuChatContainer.value.scrollHeight;
        }
    };

    const sendDaiyuQuestion = async () => {
        if (!daiyuQuestion.value.trim() || daiyuStreaming.value) return;

        const question = daiyuQuestion.value;
        const userMsgId = 'daiyu-user-' + Date.now();
        daiyuMessages.value.push({ id: userMsgId, role: 'user', type: 'text', content: question });
        daiyuQuestion.value = '';
        daiyuStreaming.value = true;
        await scrollDaiyuToBottom();

        const aiMsgId = 'daiyu-ai-' + (Date.now() + 1);
        daiyuMessages.value.push({ id: aiMsgId, role: 'ai', type: 'text', content: '' });

        try {
            const payload = { question };
            const sessionId = localStorage.getItem('user_session_id');
            if (sessionId) payload.session_id = 'ldy_' + sessionId;

            const response = await fetch('/api/daiyu/stream', {
                method: 'POST',
                headers: buildAuthHeaders(),
                body: JSON.stringify(payload)
            });

            if (!response.ok) throw new Error(`请求失败: ${response.status}`);

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let currentContent = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                const text = decoder.decode(value, { stream: true });
                forEachSSEEvent(text, (event) => {
                    if (event.type === 'chunk' && event.data) {
                        currentContent += event.data;
                        const idx = daiyuMessages.value.findIndex(m => m.id === aiMsgId);
                        if (idx !== -1) daiyuMessages.value[idx].content = currentContent;
                    }
                    if (event.type === 'error' && event.data) {
                        const idx = daiyuMessages.value.findIndex(m => m.id === aiMsgId);
                        if (idx !== -1) daiyuMessages.value[idx].content += `\n\n（错误：${event.data}）`;
                    }
                });
                await scrollDaiyuToBottom();
            }
        } catch (err) {
            console.error('黛玉请求错误:', err);
            const idx = daiyuMessages.value.findIndex(m => m.id === aiMsgId);
            if (idx !== -1) daiyuMessages.value[idx].content += `\n\n请求失败: ${err.message}`;
        } finally {
            daiyuStreaming.value = false;
            await scrollDaiyuToBottom();
        }
    };

    return {
        daiyuMessages, daiyuQuestion, daiyuStreaming, daiyuChatContainer, sendDaiyuQuestion
    };
}
