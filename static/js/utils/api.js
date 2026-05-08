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
 * 遍历 SSE 文本块中的每个事件，回调处理
 * chat.js / daiyu.js 共用，消除重复的 SSE 解析代码
 *
 * 关键：使用持久缓冲区处理 chunk 边界切分。
 * stream reader 可能在任何字节处切断，单个 SSE 事件可能被 TCP 分片拆散。
 */
let _sseBuf = '';

export function forEachSSEEvent(text, callback) {
    _sseBuf += text;

    // 切行，保留末尾不完整行到下次
    const parts = _sseBuf.split('\n');
    _sseBuf = parts.pop() || '';

    let eventType = null;
    let dataAcc = [];

    for (const line of parts) {
        if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim();
            dataAcc = [];
        } else if (line.startsWith('data: ')) {
            dataAcc.push(line.slice(6).trim());
        } else if (line === '') {
            if (eventType) {
                const raw = dataAcc.join('\n');
                let data = raw;
                if (raw && raw.startsWith('{')) {
                    try { data = JSON.parse(raw); } catch { /* keep raw */ }
                }
                callback({ type: eventType, data });
            }
            eventType = null;
            dataAcc = [];
        }
    }
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
