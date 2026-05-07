/**
 * 对话式 BI 模块
 * 负责 SSE 流式数据对话、SQL/表格/图表渲染、分页翻页
 *
 * 布局方案：文本优先 + 数据折叠
 *   - 自然语言回答（textContent）始终可见，最先展示
 *   - key_findings 始终可见
 *   - SQL / 表格 / 图表 折叠在 <details> 中
 */

const { ref, nextTick } = Vue;
import { buildAuthHeaders, forEachSSEEvent } from '../utils/api.js';

export function createBiChatModule({ scrollToBottom }) {
    // ===================================
    // 状态
    // ===================================
    const biMessages = ref([{
        id: 1,
        role: 'ai',
        textContent: '你好！我是数据分析助手。可以直接问我数据问题，比如"五班最近一次考试成绩怎么样？"或"分析一下各班级的就业率"。',
        thinking: '',
        sql: '',
        sqlHash: '',
        tableData: null,
        analysisData: null,
        chartId: null,
        isComplete: true,
    }]);
    const biQuestion = ref('');
    const biStreaming = ref(false);
    const biChatContainer = ref(null);

    // 当前正在流式写入的消息索引
    let streamingMsgIndex = -1;

    // ===================================
    // Markdown 表格生成
    // ===================================
    const buildMarkdownTable = (data) => {
        if (!data || !data.success) return '';
        if (!data.rows || data.rows.length === 0) return '（无数据）';

        const cols = data.columns;
        if (!cols || cols.length === 0) return '';

        let md = '| ' + cols.join(' | ') + ' |\n';
        md += '| ' + cols.map(() => '---').join(' | ') + ' |\n';
        data.rows.forEach(row => {
            md += '| ' + cols.map(c => {
                const v = row[c];
                if (v === null || v === undefined) return '-';
                return String(v).replace(/\|/g, '\\|');
            }).join(' | ') + ' |\n';
        });
        return md;
    };

    // ===================================
    // 图表构建
    // ===================================
    const buildEChartsOption = (chartType, title, statistics, columns, rows) => {
        const option = {
            title: { text: title, textStyle: { color: '#e2e8f0', fontSize: 14 } },
            tooltip: { trigger: 'axis' },
            legend: { textStyle: { color: '#94a3b8' } },
            grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
            backgroundColor: 'transparent'
        };

        if (chartType === 'pie') {
            option.tooltip = { trigger: 'item' };
            option.series = [{
                type: 'pie',
                radius: ['40%', '70%'],
                label: { color: '#94a3b8' },
                data: rows.map(row => ({ name: row[columns[0]], value: row[columns[1]] }))
            }];
        } else if (chartType === 'bar' || chartType === 'line') {
            const numericCols = columns.filter(c => rows.length > 0 && typeof rows[0][c] === 'number');
            const labelCol = columns.find(c => typeof rows[0]?.[c] === 'string') || columns[0];

            option.xAxis = {
                type: 'category',
                data: rows.map(r => r[labelCol]),
                axisLabel: { color: '#94a3b8', rotate: rows.length > 6 ? 30 : 0 }
            };
            option.yAxis = { type: 'value', axisLabel: { color: '#94a3b8' } };
            option.series = numericCols.map(col => ({
                name: col,
                type: chartType,
                data: rows.map(r => r[col]),
                smooth: chartType === 'line'
            }));
        } else if (chartType === 'scatter') {
            const numCols = columns.filter(c => typeof rows[0]?.[c] === 'number');
            option.xAxis = { type: 'value', name: numCols[0] || '', axisLabel: { color: '#94a3b8' } };
            option.yAxis = { type: 'value', name: numCols[1] || '', axisLabel: { color: '#94a3b8' } };
            option.series = [{
                type: 'scatter',
                data: rows.map(r => [r[numCols[0]], r[numCols[1]]])
            }];
        }

        return option;
    };

    const renderChart = async (container, chartType, title, statistics, columns, rows) => {
        await nextTick();
        if (!container || typeof echarts === 'undefined') return null;
        const option = buildEChartsOption(chartType, title, statistics, columns, rows);
        const chart = echarts.init(container);
        chart.setOption(option);
        const observer = new ResizeObserver(() => chart.resize());
        observer.observe(container);
        return chart;
    };

    // ===================================
    // 分页翻页
    // ===================================
    const goToPage = async (sqlHash, page, msgId) => {
        try {
            const resp = await fetch('/bi/data-page', {
                method: 'POST',
                headers: buildAuthHeaders(),
                body: JSON.stringify({ sql_hash: sqlHash, page, page_size: 50 })
            });
            const result = await resp.json();
            if (result.code === 200 && result.data) {
                const idx = biMessages.value.findIndex(m => m.id === msgId);
                if (idx !== -1 && biMessages.value[idx].tableData) {
                    biMessages.value[idx].tableData.rows = result.data.rows;
                    biMessages.value[idx].tableData.page = result.data.page;
                }
            }
        } catch (err) {
            console.error('翻页失败:', err);
        }
    };

    window._biGoToPage = (sqlHash, page) => {
        const msg = biMessages.value.find(m => m.tableData?.sql_hash === sqlHash);
        if (msg) goToPage(sqlHash, page, msg.id);
    };

    // ===================================
    // SSE 事件处理
    // ===================================
    const handleStreamEvent = (event) => {
        if (streamingMsgIndex < 0) return;
        const msg = biMessages.value[streamingMsgIndex];
        if (!msg) return;

        switch (event.type) {
            case 'thinking':
                msg.thinking = event.data;
                break;

            case 'sql':
                msg.sql = event.data.sql;
                msg.sqlHash = event.data.sql_hash;
                msg.thinking = '';
                break;

            case 'data':
                msg.tableData = event.data;
                msg.thinking = '';
                break;

            case 'analysis':
                msg.analysisData = event.data;
                msg.thinking = '';
                if (event.data?.chart_suggestion && msg.tableData?.rows?.length > 0) {
                    msg.chartId = 'chart-' + msg.id;
                }
                break;

            case 'chunk':
                msg.textContent += event.data;
                msg.thinking = '';
                break;

            case 'done':
                msg.thinking = '';
                msg.isComplete = true;
                // 渲染图表
                scheduleChartRender(msg);
                break;

            case 'error':
                console.error('BI SSE 错误:', event.data);
                msg.thinking = '';
                msg.isComplete = true;
                break;
        }
    };

    const scheduleChartRender = async (msg) => {
        if (!msg.chartId) return;
        const cs = msg.analysisData?.chart_suggestion;
        if (!cs) return;

        await nextTick();
        // 可能需要等待 DOM 渲染，延迟一点
        setTimeout(async () => {
            const container = document.getElementById(msg.chartId);
            if (container && container.clientHeight > 0) {
                await renderChart(container, cs.type, cs.title,
                    msg.analysisData?.statistics || {},
                    msg.tableData?.columns || [],
                    msg.tableData?.rows || []);
            }
        }, 100);
    };

    // ===================================
    // 发送问题
    // ===================================
    const sendBiQuestion = async () => {
        if (!biQuestion.value.trim() || biStreaming.value) return;

        const question = biQuestion.value;
        const userMsgId = Date.now();
        biMessages.value.push({
            id: userMsgId,
            role: 'user',
            textContent: question,
        });
        biQuestion.value = '';
        biStreaming.value = true;

        // 创建 AI 消息占位（所有字段有初始值）
        const aiMsgId = Date.now() + 1;
        const aiMsg = {
            id: aiMsgId,
            role: 'ai',
            textContent: '',
            thinking: '正在分析问题...',
            sql: '',
            sqlHash: '',
            tableData: null,
            analysisData: null,
            chartId: null,
            isComplete: false,
        };
        biMessages.value.push(aiMsg);
        streamingMsgIndex = biMessages.value.length - 1;
        await scrollToBottom();

        let sessionId = localStorage.getItem('bi_session_id');
        if (!sessionId) {
            sessionId = 'bi_' + crypto.randomUUID().slice(0, 12);
            localStorage.setItem('bi_session_id', sessionId);
        }

        try {
            const response = await fetch('/bi/stream', {
                method: 'POST',
                headers: buildAuthHeaders(),
                body: JSON.stringify({ question, session_id: sessionId })
            });

            if (!response.ok) {
                const errMsg = response.status === 404
                    ? '服务端点未找到，请检查服务器是否已重启。'
                    : `服务错误 (${response.status})，请稍后重试。`;
                aiMsg.textContent = errMsg;
                aiMsg.thinking = '';
                aiMsg.isComplete = true;
                biStreaming.value = false;
                return;
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                const text = decoder.decode(value, { stream: true });
                forEachSSEEvent(text, handleStreamEvent);
                await scrollToBottom();
            }
        } catch (err) {
            console.error('BI 请求错误:', err);
            const msg2 = err.message || '';
            if (msg2.includes('Failed to fetch') || msg2.includes('NetworkError')) {
                aiMsg.textContent = '网络连接失败，请检查网络后重试。';
            } else if (!aiMsg.textContent) {
                aiMsg.textContent = '服务暂时不可用，请稍后重试。';
            }
            aiMsg.thinking = '';
            aiMsg.isComplete = true;
        } finally {
            biStreaming.value = false;
            streamingMsgIndex = -1;
            await scrollToBottom();
        }
    };

    const clearBiChat = () => {
        biMessages.value = [{
            id: Date.now(),
            role: 'ai',
            textContent: '聊天记录已清空，有什么可以帮您分析的？',
            thinking: '',
            sql: '',
            sqlHash: '',
            tableData: null,
            analysisData: null,
            chartId: null,
            isComplete: true,
        }];
    };

    return {
        biMessages,
        biQuestion,
        biStreaming,
        biChatContainer,
        sendBiQuestion,
        clearBiChat,
        goToPage,
        buildMarkdownTable,
    };
}
