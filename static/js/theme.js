/**
 * 主题切换功能
 * 支持：亮色(light)、暗色(dark)、跟随系统(system)
 * 以常规 script 加载（非 module），供内联 onclick 调用
 */

function setTheme(theme) {
    if (theme === 'system') {
        var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        document.documentElement.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
    } else {
        document.documentElement.setAttribute('data-theme', theme);
    }
    localStorage.setItem('theme', theme);
    updateThemeButtons(theme);
    if (theme === 'dark') {
        document.body.classList.remove('light-theme');
        document.body.classList.add('dark-theme');
    } else {
        document.body.classList.remove('dark-theme');
        document.body.classList.add('light-theme');
    }
}

function updateThemeButtons(currentTheme) {
    var buttons = document.querySelectorAll('.theme-btn');
    buttons.forEach(function(btn) {
        btn.classList.remove('active');
        if (btn.classList.contains(currentTheme === 'system' ? 'system' : currentTheme === 'light' ? 'light' : 'dark')) {
            btn.classList.add('active');
        }
    });
}

window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function(e) {
    var savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'system' || !savedTheme) {
        document.documentElement.setAttribute('data-theme', e.matches ? 'dark' : 'light');
    }
});

// 页面加载时初始化按钮状态（脚本在 body 底部，DOM 已就绪）
(function() {
    var savedTheme = localStorage.getItem('theme') || 'system';
    updateThemeButtons(savedTheme);
    var container = document.getElementById('themeSwitcher');
    if (container) container.style.display = 'flex';
})();
