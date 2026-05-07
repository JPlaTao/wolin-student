/**
 * 智能问答模块
 * 负责流式问答、聊天消息管理
 */

const { ref } = Vue;
import { buildAuthHeaders, forEachSSEEvent } from '../utils/api.js';

/**
 * 创建智能问答模块
 * @param {Object} options - 配置项
 * @param {Function} options.renderMarkdown - Markdown 渲染函数
 * @param {Function} options.scrollToBottom - 滚动到底部
 * @returns {Object} - 智能问答模块的响应式状态和方法
 */
export function createChatModule({ renderMarkdown, scrollToBottom }) {
    // ===================================
    // 状态定义
    // ===================================
    const chatMessages = ref([{
        id: 1,
        role: 'ai',
        type: 'text',
        content: '✨ 你好！我是智能助手，可以问数据问题（如"学生有多少人？"或"李芳老师有多少个学生？"）或业务问题。我也支持多轮对话记忆，可以基于上下文连续提问。'
    }]);
    const currentQuestion = ref('');
    const isLoading = ref(false);
    const chatContainer = ref(null);

    // 流式消息状态
    const streamingState = ref({
        active: false,
        messageId: null,
        currentContent: '',
        currentSql: '',
        thinkingMessage: '',
        finalData: null,
        type: null,
        isSingleValue: false,
        isComplete: false
    });

    // ===================================
    // 内部方法
    // ===================================

    /**
     * 格式化 SQL 结果为 HTML
     */
    const formatSqlResult = (data, count, isFullSave) => {
        if (count === 0) {
            return '未查询到相关数据。';
        }

        if (count === 1 && Object.keys(data[0]).length === 1) {
            const key = Object.keys(data[0])[0];
            const value = data[0][key];
            return `${key}：${value}`;
        }

        let tableHtml = '<table class="result-table"><thead><tr>';
        const headers = Object.keys(data[0]);
        headers.forEach(h => { tableHtml += `<th>${h}</th>`; });
        tableHtml += '</tr></thead><tbody>';
        data.slice(0, 10).forEach(row => {
            tableHtml += '<tr>';
            headers.forEach(h => { tableHtml += `<td>${row[h]}</td>`; });
            tableHtml += '</tr>';
        });
        tableHtml += '</tbody></table>';
        if (count > 10) {
            tableHtml += `<p class="text-xs text-slate-400 mt-2">共 ${count} 条记录，仅显示前 10 条。</p>`;
        }
        if (!isFullSave) {
            tableHtml += `<p class="text-xs text-amber-400 mt-2"><i class="fas fa-info-circle"></i> 数据量较大，已存储完整结果供后续分析。</p>`;
        }
        return tableHtml;
    };

    /**
     * 更新流式消息内容
     */
    const updateStreamingMessage = () => {
        const msgIndex = chatMessages.value.findIndex(m => m.id === streamingState.value.messageId);
        if (msgIndex === -1) return;

        const state = streamingState.value;
        let content = '';

        // 显示 SQL
        if (state.currentSql) {
            content += `<div class="sql-display mb-3"><div class="text-slate-400 text-xs mb-1">生成的SQL：</div><code class="bg-slate-800 px-3 py-2 rounded block text-sm text-green-400 overflow-x-auto">${state.currentSql.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</code></div>`;
        }

        // 显示数据结果
        if (state.type === 'sql' && state.finalData) {
            const formatted = formatSqlResult(state.finalData.data, state.finalData.row_count, state.finalData.full_save);
            content += `<div class="sql-result">${formatted}</div>`;
        }

        // 显示流式内容
        if (state.currentContent) {
            if (state.isComplete) {
                if (state.type === 'sql') {
                    content += `<div class="answer-text">${renderMarkdown(state.currentContent)}</div>`;
                } else {
                    content += renderMarkdown(state.currentContent);
                }
            } else {
                const escapedContent = state.currentContent
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;');
                content += `<pre class="whitespace-pre-wrap break-words text-slate-200">${escapedContent}</pre>`;
            }
        }

        // 显示加载状态
        if (state.active && state.thinkingMessage) {
            content = `<div class="text-blue-400 text-sm mb-2"><i class="fas fa-spinner fa-spin mr-1"></i>${state.thinkingMessage}</div>` + content;
        }

        chatMessages.value[msgIndex].content = content;
    };

    /**
     * 处理流式事件
     */
    const handleStreamEvent = async (event) => {
        const state = streamingState.value;

        switch (event.type) {
            case 'intent':
                state.type = event.data === 'sql' ? 'sql' : 'text';
                break;

            case 'thinking':
                state.thinkingMessage = event.data;
                updateStreamingMessage();
                break;

            case 'sql':
                state.currentSql = event.data;
                state.thinkingMessage = '';
                updateStreamingMessage();
                break;

            case 'data':
                state.finalData = event.data;
                state.type = 'sql';
                state.thinkingMessage = '';
                updateStreamingMessage();
                break;

            case 'chunk':
                state.currentContent += event.data;
                updateStreamingMessage();
                break;

            case 'done':
                state.thinkingMessage = '';
                state.active = false;
                state.isComplete = true;
                updateStreamingMessage();
                break;

            case 'error':
                state.thinkingMessage = '';
                state.active = false;
                state.isComplete = true;
                const msgIndex = chatMessages.value.findIndex(m => m.id === state.messageId);
                if (msgIndex !== -1) {
                    chatMessages.value[msgIndex].content += `<div class="text-red-400 mt-2">错误: ${event.data}</div>`;
                }
                updateStreamingMessage();
                break;
        }
    };

    // ===================================
    // 公开方法
    // ===================================

    /**
     * 发送问题
     */
    const sendQuestion = async () => {
        if (!currentQuestion.value.trim()) return;

        const question = currentQuestion.value;
        const userMsgId = Date.now();

        // 添加用户消息
        chatMessages.value.push({
            id: userMsgId,
            role: 'user',
            type: 'text',
            content: question
        });

        currentQuestion.value = '';
        isLoading.value = true;

        // 初始化流式状态
        const aiMsgId = Date.now() + 1;
        streamingState.value = {
            active: true,
            messageId: aiMsgId,
            currentContent: '',
            currentSql: '',
            thinkingMessage: '正在分析问题...',
            finalData: null,
            type: null,
            isSingleValue: false,
            isComplete: false
        };

        // 添加 AI 消息占位
        chatMessages.value.push({
            id: aiMsgId,
            role: 'ai',
            type: 'text',
            content: ''
        });

        await scrollToBottom();

        try {
            const payload = { question };
            const sessionId = localStorage.getItem('user_session_id');
            if (sessionId) {
                payload.session_id = sessionId;
            }

            const response = await fetch('/query/stream', {
                method: 'POST',
                headers: buildAuthHeaders(),
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                throw new Error(`请求失败: ${response.status}`);
            }

            if (sessionId) {
                localStorage.setItem('current_session_id', sessionId);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const text = decoder.decode(value, { stream: true });
                forEachSSEEvent(text, async (event) => {
                    await handleStreamEvent(event);
                });

                await scrollToBottom();
            }

        } catch (err) {
            console.error('流式请求错误:', err);
            streamingState.value.thinkingMessage = '';
            streamingState.value.isComplete = true;
            updateStreamingMessage();
            const msgIndex = chatMessages.value.findIndex(m => m.id === streamingState.value.messageId);
            if (msgIndex !== -1) {
                chatMessages.value[msgIndex].content += `<div class="text-red-400 mt-2">请求失败: ${err.message}</div>`;
            }
        } finally {
            isLoading.value = false;
            streamingState.value.active = false;
            streamingState.value.thinkingMessage = '';
            if (!streamingState.value.isComplete) {
                streamingState.value.isComplete = true;
                updateStreamingMessage();
            }
            await scrollToBottom();
        }
    };

    /**
     * 清空聊天记录
     */
    const clearChat = () => {
        chatMessages.value = [{
            id: Date.now(),
            role: 'ai',
            type: 'text',
            content: '✨ 聊天记录已清空，有什么可以帮您的？'
        }];
    };

    /**
     * 获取聊天容器引用
     */
    const setChatContainer = (container) => {
        chatContainer.value = container;
    };

    // ===================================
    // 返回导出
    // ===================================
    return {
        // 状态
        chatMessages,
        currentQuestion,
        isLoading,
        chatContainer,
        streamingState,

        // 方法
        sendQuestion,
        clearChat,
        setChatContainer
    };
}
