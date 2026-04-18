/**
 * 仪表板模块
 * 负责数据看板的加载和图表渲染
 */

import { nextTick } from 'vue';

/**
 * 创建仪表板模块
 * @param {Object} options - 配置项
 * @returns {Object} - 仪表板模块的响应式状态和方法
 */
export function createDashboardModule() {
    // ===================================
    // 状态定义
    // ===================================
    const dashboard = ref({
        studentCount: 0,
        classCount: 0,
        avgAge: 0,
        employmentRate: 0,
        topSalary: []
    });

    // 图表实例
    let genderChart = null;
    let scoreChart = null;

    // ===================================
    // 内部方法
    // ===================================

    /**
     * 加载仪表板数据
     */
    const loadDashboardData = async () => {
        try {
            const res = await axios.get('/statistics/dashboard');
            const data = res.data.data;
            dashboard.value = {
                studentCount: data.total_students,
                classCount: data.total_classes,
                avgAge: data.avg_age,
                employmentRate: data.employment_rate,
                topSalary: data.top_salary
            };
        } catch (err) {
            console.error('加载仪表板数据失败:', err);
        }
    };

    /**
     * 渲染仪表板图表
     */
    const renderDashboardCharts = async () => {
        try {
            const [genderRes, scoreRes] = await Promise.all([
                axios.get('/statistics/classes/gender-stat'),
                axios.get('/statistics/advanced/class-avg-score-rank')
            ]);
            await nextTick();

            if (genderChart) genderChart.dispose();
            if (scoreChart) scoreChart.dispose();

            genderChart = echarts.init(document.getElementById('genderChart'));
            scoreChart = echarts.init(document.getElementById('scoreChart'));

            // 性别分布图
            genderChart.setOption({
                tooltip: { trigger: 'axis' },
                legend: {
                    data: ['男生', '女生'],
                    textStyle: { color: '#ccc' }
                },
                xAxis: {
                    type: 'category',
                    data: genderRes.data.data.map(c => c.class_name),
                    axisLabel: { rotate: 30, color: '#aaa' }
                },
                yAxis: { type: 'value', name: '人数' },
                series: [
                    {
                        name: '男生',
                        type: 'bar',
                        data: genderRes.data.data.map(c => c.male),
                        color: '#3b82f6'
                    },
                    {
                        name: '女生',
                        type: 'bar',
                        data: genderRes.data.data.map(c => c.female),
                        color: '#ec489a'
                    }
                ]
            });

            // 平均成绩排名图
            scoreChart.setOption({
                tooltip: { trigger: 'axis' },
                xAxis: {
                    type: 'category',
                    data: scoreRes.data.data.map(d => d.class_name),
                    axisLabel: { rotate: 30, color: '#aaa' }
                },
                yAxis: { type: 'value', name: '平均分' },
                series: [{
                    type: 'bar',
                    data: scoreRes.data.data.map(d => d.avg_score),
                    color: '#10b981'
                }]
            });
        } catch (err) {
            console.error('渲染仪表板图表失败:', err);
        }
    };

    /**
     * 销毁图表实例
     */
    const disposeCharts = () => {
        if (genderChart) {
            genderChart.dispose();
            genderChart = null;
        }
        if (scoreChart) {
            scoreChart.dispose();
            scoreChart = null;
        }
    };

    // ===================================
    // 公开方法
    // ===================================

    /**
     * 刷新仪表板（完整刷新）
     */
    const refreshDashboard = async () => {
        await loadDashboardData();
        await renderDashboardCharts();
    };

    // ===================================
    // 返回导出
    // ===================================
    return {
        // 状态
        dashboard,

        // 方法
        loadDashboardData,
        renderDashboardCharts,
        refreshDashboard,
        disposeCharts
    };
}
