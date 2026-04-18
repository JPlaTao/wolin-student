/**
 * API 工具函数
 */

/**
 * 滚动到聊天底部
 */
export async function scrollToBottom(chatContainer, nextTick) {
    await nextTick();
    if (chatContainer && chatContainer.value) {
        chatContainer.value.scrollTop = chatContainer.value.scrollHeight;
    }
}

/**
 * 构建带认证头的 headers
 */
export function buildAuthHeaders() {
    return {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('access_token')}`
    };
}

/**
 * 解析 SSE 事件
 */
export function parseSSEEvent(text) {
    const lines = text.split('\n');
    let eventType = null;
    let eventData = null;

    for (const line of lines) {
        if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim();
        } else if (line.startsWith('data: ')) {
            const dataStr = line.slice(6).trim();
            if (dataStr) {
                try {
                    eventData = JSON.parse(dataStr);
                } catch {
                    eventData = dataStr;
                }
            }
        } else if (line === '') {
            if (eventType && eventData !== null) {
                return { type: eventType, data: eventData };
            }
            eventType = null;
            eventData = null;
        }
    }
    return null;
}

/**
 * 格式化时间
 */
export function formatTime(date) {
    const d = date instanceof Date ? date : new Date();
    return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
}

/**
 * 防抖函数
 */
export function debounce(fn, delay) {
    let timer = null;
    return function(...args) {
        if (timer) clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}

/**
 * 深拷贝
 */
export function deepClone(obj) {
    return JSON.parse(JSON.stringify(obj));
}
