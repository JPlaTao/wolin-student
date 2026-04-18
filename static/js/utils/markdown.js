/**
 * Markdown 渲染工具
 */

/**
 * 渲染 Markdown 文本
 */
export function renderMarkdown(text) {
    if (typeof marked !== 'undefined') {
        return marked.parse(text);
    }
    return text;
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

/**
 * 格式化 SQL 结果为 HTML
 */
export function formatSqlResult(data, count, isFullSave) {
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
}

/**
 * 获取角色显示文本
 */
export function getRoleText(role) {
    const roleMap = {
        'admin': '管理员',
        'teacher': '教师',
        'student': '学生',
        'user': '普通用户'
    };
    return roleMap[role] || role;
}

/**
 * 获取角色标签类
 */
export function getRoleClass(role) {
    return `role-${role}`;
}

/**
 * 设置认证令牌
 */
export function setAuthToken(token) {
    if (token) {
        axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    } else {
        delete axios.defaults.headers.common['Authorization'];
    }
}
