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
    // Mock 数据（与真实 API 格式一致）
    // ===================================
    const MOCK_POLISH = {
        code: 200,
        data: {
            polished: "关于教室大扫除的通知\n\n各位同学：\n\n为营造整洁舒适的学习环境，定于明日放学后开展教室大扫除。请各位同学自备抹布等清洁工具，准时参加。\n\n特此通知。\n\nXX班 班主任\n2026年5月8日"
        }
    };

    const MOCK_DIAGNOSE = {
        code: 200,
        data: {
            stu_name: "张三",
            class_name: "高三(1)班",
            exam_records: [
                { seq_no: 1, grade: 85.0, exam_date: "2026-03-01" },
                { seq_no: 2, grade: 92.0, exam_date: "2026-04-01" },
                { seq_no: 3, grade: 78.0, exam_date: "2026-05-01" }
            ],
            analysis: "该生成绩呈现先升后降的趋势。第2次考试进步明显（+7分），但第3次退步较大（-14分），需关注近期学习状态。从数据看，该生有一定潜力，但成绩稳定性不足。建议：1. 分析退步原因；2. 巩固优势科目；3. 制定阶段性目标。"
        }
    };

    const MOCK_COMMENT = {
        code: 200,
        data: {
            comment: "你是个头脑灵活的孩子，数学课上总能快速找到解题思路，这一点非常难得。不过，有时候你的精力用错了地方，和同学发生争执不仅会影响友谊，也会让老师为你担心。老师相信，如果你能把数学上的聪明劲用在处理人际关系上，一定会成为一个更受欢迎的人。期待看到你温和待人、自律自强的那一天！"
        }
    };

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
            // TODO: 切换为真实 API 调用
            // const res = await axios.post('/tools/polish-notice', {
            //     text: polishText.value,
            //     style: polishStyle.value
            // });
            // polishResult.value = res.data.data.polished;
            await new Promise(r => setTimeout(r, 500));
            polishResult.value = MOCK_POLISH.data.polished;
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
            // TODO: 切换为真实 API 调用
            // const res = await axios.post('/tools/diagnose-score', {
            //     stu_id: diagnoseStuId.value
            // });
            // diagnoseResult.value = res.data.data;
            await new Promise(r => setTimeout(r, 600));
            diagnoseResult.value = MOCK_DIAGNOSE.data;
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
            // TODO: 切换为真实 API 调用
            // const res = await axios.post('/tools/generate-comment', {
            //     keywords: commentKeywords.value
            // });
            // commentResult.value = res.data.data.comment;
            await new Promise(r => setTimeout(r, 500));
            commentResult.value = MOCK_COMMENT.data.comment;
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
