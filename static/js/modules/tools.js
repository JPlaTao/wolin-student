/**
 * 教师实用工具模块
 * 负责公告润色、成绩诊断、期末评语三个 AI 辅助工具
 */

const { ref } = Vue;
const { ElMessage } = ElementPlus;

/**
 * 创建教师工具模块
 * @returns {Object} - 教师工具模块的状态和方法
 */
export function createToolsModule() {
    // ===================================
    // 状态定义
    // ===================================
    const teacherToolsLoading = ref(false);

    // 公告润色
    const polishText = ref('');
    const polishStyle = ref('formal');
    const polishResult = ref('');

    // 成绩诊断
    const diagnoseStuId = ref(null);
    const diagnoseResult = ref(null);

    // 期末评语
    const commentKeywords = ref('');
    const commentResult = ref('');

    // ===================================
    // 方法定义
    // ===================================

    /**
     * 公告润色
     */
    async function doPolishNotice() {
        if (!polishText.value.trim()) {
            ElMessage.warning('请输入通知草稿');
            return;
        }
        teacherToolsLoading.value = true;
        try {
            const res = await axios.post('/tools/polish-notice', {
                text: polishText.value,
                style: polishStyle.value
            });
            polishResult.value = res.data.data.polished;
        } catch (err) {
            ElMessage.error(err.response?.data?.detail || '润色失败，请稍后重试');
        } finally {
            teacherToolsLoading.value = false;
        }
    }

    /**
     * 成绩诊断
     */
    async function doDiagnoseScore() {
        if (!diagnoseStuId.value) {
            ElMessage.warning('请输入学号');
            return;
        }
        teacherToolsLoading.value = true;
        try {
            const res = await axios.post('/tools/diagnose-score', {
                stu_id: diagnoseStuId.value
            });
            diagnoseResult.value = res.data.data;
        } catch (err) {
            if (err.response?.status === 404) {
                ElMessage.warning('未找到该学生的成绩记录');
            } else {
                ElMessage.error(err.response?.data?.detail || '诊断失败，请稍后重试');
            }
        } finally {
            teacherToolsLoading.value = false;
        }
    }

    /**
     * 期末评语生成
     */
    async function doGenerateComment() {
        if (!commentKeywords.value.trim()) {
            ElMessage.warning('请输入学生特点关键词');
            return;
        }
        teacherToolsLoading.value = true;
        try {
            const res = await axios.post('/tools/generate-comment', {
                keywords: commentKeywords.value
            });
            commentResult.value = res.data.data.comment;
        } catch (err) {
            ElMessage.error(err.response?.data?.detail || '评语生成失败，请稍后重试');
        } finally {
            teacherToolsLoading.value = false;
        }
    }

    // ===================================
    // 返回导出
    // ===================================
    return {
        // 状态
        teacherToolsLoading,
        polishText, polishStyle, polishResult,
        diagnoseStuId, diagnoseResult,
        commentKeywords, commentResult,

        // 方法
        doPolishNotice, doDiagnoseScore, doGenerateComment,
    };
}
