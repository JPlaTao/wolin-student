/**
 * 高级统计模块
 * 负责高级图表的渲染
 */

/**
 * 创建高级统计模块
 * @returns {Object} - 高级统计模块的响应式状态和方法
 */
export function createStatisticsModule() {
    // ===================================
    // 状态定义
    // ===================================

    // 图表实例
    let salaryChart = null;
    let durationChart = null;
    let examSeqChart = null;

    // ===================================
    // 内部方法
    // ===================================

    /**
     * 渲染高级图表
     */
    const renderAdvancedCharts = async () => {
        try {
            const { nextTick } = await import('vue');

            const [salaryRes, durationRes, examSeqRes] = await Promise.all([
                axios.get('/statistics/advanced/salary-distribution'),
                axios.get('/statistics/employment/avg-duration-per-class'),
                axios.get('/statistics/score/class-avg-per-exam')
            ]);
            await nextTick();

            // 销毁旧图表
            if (salaryChart) salaryChart.dispose();
            if (durationChart) durationChart.dispose();
            if (examSeqChart) examSeqChart.dispose();

            // 初始化新图表
            salaryChart = echarts.init(document.getElementById('salaryDistChart'));
            durationChart = echarts.init(document.getElementById('durationChart'));
            examSeqChart = echarts.init(document.getElementById('examSeqChart'));

            // 薪资分布饼图
            salaryChart.setOption({
                tooltip: { trigger: 'item' },
                legend: { textStyle: { color: '#ccc' } },
                series: [{
                    type: 'pie',
                    radius: '55%',
                    data: salaryRes.data.data.map(d => ({ name: d.range, value: d.count })),
                    label: { color: '#fff' }
                }]
            });

            // 就业时长折线图
            durationChart.setOption({
                tooltip: { trigger: 'axis' },
                xAxis: {
                    type: 'category',
                    data: durationRes.data.data.map(d => d.class_name),
                    axisLabel: { rotate: 30, color: '#aaa' }
                },
                yAxis: { type: 'value', name: '天数' },
                series: [{
                    type: 'line',
                    data: durationRes.data.data.map(d => d.avg_duration_days),
                    smooth: true,
                    lineStyle: { color: '#f59e0b', width: 3 }
                }]
            });

            // 考试序列折线图
            const data = examSeqRes.data.data;
            const exams = Object.keys(data);
            const classNames = [...new Set(exams.flatMap(e => data[e].map(c => c.class_name)))];
            const series = classNames.map(cn => ({
                name: cn,
                type: 'line',
                data: exams.map(e => {
                    const item = data[e].find(d => d.class_name === cn);
                    return item ? item.avg_grade : null;
                }),
                smooth: true
            }));

            examSeqChart.setOption({
                tooltip: { trigger: 'axis' },
                legend: { data: classNames, textStyle: { color: '#ccc' } },
                xAxis: {
                    type: 'category',
                    data: exams,
                    axisLabel: { rotate: 30, color: '#aaa' }
                },
                yAxis: { type: 'value', name: '平均分' },
                series
            });
        } catch (err) {
            console.error('渲染高级图表失败:', err);
        }
    };

    /**
     * 销毁图表实例
     */
    const disposeCharts = () => {
        if (salaryChart) {
            salaryChart.dispose();
            salaryChart = null;
        }
        if (durationChart) {
            durationChart.dispose();
            durationChart = null;
        }
        if (examSeqChart) {
            examSeqChart.dispose();
            examSeqChart = null;
        }
    };

    // ===================================
    // 返回导出
    // ===================================
    return {
        // 方法
        renderAdvancedCharts,
        disposeCharts
    };
}
