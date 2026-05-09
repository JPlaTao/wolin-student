/**
 * Markdown 渲染共享模块
 *
 * 使用 ES module 动态 import 加载 marked（无时序问题），
 * 内置轻量 fallback 兜底，不依赖任何外部 CDN 或 script 标签。
 */

// ===================================
// 异步加载 marked（ESM 方式）
// ===================================
let _marked = null;
let _markedReady = false;

const markedLoading = import('../../lib/marked.esm.js')
    .then(mod => {
        _marked = mod.marked || mod;
        _markedReady = true;
    })
    .catch(e => {
        console.warn('[markdown] marked 加载失败，将使用内置渲染器:', e);
        _markedReady = true;
    });

/**
 * 等待 marked 加载完成的 Promise。
 * 供外部在首次渲染前调用，避免 fallback 和 marked 结果不一致。
 */
export const ensureMarkedLoaded = () => markedLoading;

// ===================================
// 内置轻量 fallback 渲染器
// ===================================
function fallbackRender(text) {
    if (!text) return '';

    // 转义 HTML（先做，防止 XSS）
    let html = text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');

    // 代码块（必须优先于行内 code）
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
        const cls = lang ? ` class="lang-${lang}"` : '';
        return `<pre><code${cls}>${code.trim()}</code></pre>`;
    });
    // 行内代码
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    // 分隔线
    html = html.replace(/^---$/gm, '<hr>');
    // 标题
    html = html.replace(/^######\s+(.+)$/gm, '<h6>$1</h6>');
    html = html.replace(/^#####\s+(.+)$/gm, '<h5>$1</h5>');
    html = html.replace(/^####\s+(.+)$/gm, '<h4>$1</h4>');
    html = html.replace(/^###\s+(.+)$/gm, '<h3>$1</h3>');
    html = html.replace(/^##\s+(.+)$/gm, '<h2>$1</h2>');
    html = html.replace(/^#\s+(.+)$/gm, '<h1>$1</h1>');
    // 引用
    html = html.replace(/^>\s+(.+)$/gm, '<blockquote>$1</blockquote>');
    // 无序列表
    html = html.replace(/^[\s]*[-*]\s+(.+)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>)\n(<li>)/g, '$1$2');
    html = html.replace(/((?:<li>.*<\/li>)+)/g, '<ul>$1</ul>');
    // 有序列表
    html = html.replace(/^[\s]*\d+\.\s+(.+)$/gm, '<li>$1</li>');
    html = html.replace(/(?:^<ul>.*<\/ul>\n)?((?:<li>.*<\/li>)+)/g, (m, lis) => {
        if (m.startsWith('<ul>')) return m;
        return `<ol>${lis}</ol>`;
    });
    // 加粗+斜体
    html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
    // 链接
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

    // 段落包装：连续两个换行为段落
    const blocks = html.split(/\n\n+/);
    if (blocks.length > 1) {
        html = blocks
            .map(b => {
                const t = b.trim();
                if (!t) return '';
                if (/^<(h[1-6]|ul|ol|li|blockquote|pre|hr|table|div|p)\b/.test(t)) return t;
                return `<p>${t.replace(/\n/g, '<br>')}</p>`;
            })
            .join('\n');
    }
    return html;
}

/**
 * 渲染 Markdown 文本为 HTML
 * @param {string} text 原始 Markdown
 * @returns {string} 渲染后的 HTML
 *
 * - 优先使用 marked（通过 ESM import 异步加载）
 * - marked 加载完成前使用内置 fallback（无空白期）
 * - 两种渲染器任一失败时自动降级
 */
export function renderMarkdown(text) {
    if (!text) return '';
    if (_marked) {
        try { return _marked.parse(text); }
        catch (e) { console.warn('[markdown] marked.parse 失败，降级到 fallback:', e); }
    }
    return fallbackRender(text);
}

/**
 * 转义 HTML 特殊字符
 */
export function escapeHtml(text) {
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}
