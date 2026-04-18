/**
 * 成绩管理模块
 * 负责成绩数据的增删改查
 */

/**
 * 创建成绩管理模块
 * @param {Function} options.getClasses - 获取班级列表
 * @param {Function} options.getStudents - 获取学生列表
 * @returns {Object} - 成绩管理模块的响应式状态和方法
 */
export function createExamModule({ getClasses, getStudents }) {
    // ===================================
    // 状态定义
    // ===================================
    const examRecords = ref([]);
    const examLoading = ref(false);
    const examDialogVisible = ref(false);
    const examForm = ref({
        stu_id: '',
        seq_no: '',
        grade: '',
        exam_date: ''
    });
    let editingExamKey = null;
    const selectedExam = ref(null);

    // 成绩维护相关
    const examMaintenanceDialogVisible = ref(false);
    const examQueryForm = ref({ stu_id: '', seq_no: '' });
    const queriedExamData = ref({
        found: false,
        grade: null,
        exam_date: null,
        notFoundMsg: ''
    });
    const examQueryLoading = ref(false);
    const maintenanceEditDialogVisible = ref(false);
    const maintenanceEditForm = ref({ grade: '', exam_date: '' });
    let currentQueryKey = null;

    // ===================================
    // 内部方法
    // ===================================
    const { ElMessage, ElMessageBox } = ElementPlus;

    // ===================================
    // 公开方法
    // ===================================

    /**
     * 加载成绩记录
     */
    const loadExamRecords = async () => {
        examLoading.value = true;
        try {
            const res = await axios.get('/exam/records');
            examRecords.value = res.data.data || [];
        } catch (err) {
            examRecords.value = [];
        } finally {
            examLoading.value = false;
        }
    };

    /**
     * 处理成绩选中
     */
    const handleExamSelection = (row) => {
        selectedExam.value = row;
    };

    /**
     * 打开成绩对话框
     */
    const openExamDialog = (row) => {
        if (row) {
            editingExamKey = { stu_id: row.stu_id, seq_no: row.seq_no };
            examForm.value = {
                stu_id: row.stu_id,
                seq_no: row.seq_no,
                grade: row.grade,
                exam_date: row.exam_date
            };
        } else {
            editingExamKey = null;
            examForm.value = {
                stu_id: '',
                seq_no: '',
                grade: '',
                exam_date: ''
            };
        }
        examDialogVisible.value = true;
    };

    /**
     * 保存成绩
     */
    const saveExam = async () => {
        try {
            if (editingExamKey) {
                await axios.put('/exam/', examForm.value, {
                    params: { stu_id: editingExamKey.stu_id, seq_no: editingExamKey.seq_no }
                });
                ElMessage.success('成绩更新成功！');
            } else {
                await axios.post('/exam/', examForm.value);
                ElMessage.success('成绩新增成功！');
            }
            await loadExamRecords();
            examDialogVisible.value = false;
        } catch (err) {
            ElMessage.error('操作失败');
        }
    };

    /**
     * 删除成绩
     */
    const deleteExam = async (row) => {
        try {
            await ElMessageBox.confirm(
                `确定删除学生 ${row.stu_name} 第 ${row.seq_no} 次考试成绩吗？`,
                '确认删除',
                { type: 'warning' }
            );
            await axios.delete(`/exam/${row.stu_id}`, { params: { seq_no: row.seq_no } });
            ElMessage.success('成绩删除成功！');
            await loadExamRecords();
            if (selectedExam.value === row) selectedExam.value = null;
        } catch (err) {
            if (err !== 'cancel') {
                ElMessage.error('删除失败');
            }
        }
    };

    /**
     * 打开成绩维护对话框
     */
    const openExamMaintenanceDialog = () => {
        examQueryForm.value = {
            stu_id: selectedExam.value?.stu_id || '',
            seq_no: selectedExam.value?.seq_no || ''
        };
        queriedExamData.value = { found: false, grade: null, exam_date: null, notFoundMsg: '' };
        examMaintenanceDialogVisible.value = true;
    };

    /**
     * 查询成绩记录
     */
    const queryExamRecord = async () => {
        if (!examQueryForm.value.stu_id || !examQueryForm.value.seq_no) {
            ElMessage.warning('请填写学号和考试序号');
            return;
        }
        examQueryLoading.value = true;
        try {
            const res = await axios.get('/exam/records');
            const records = res.data.data || [];
            const target = records.find(r =>
                r.stu_id === examQueryForm.value.stu_id &&
                r.seq_no === examQueryForm.value.seq_no
            );
            if (target) {
                queriedExamData.value = {
                    found: true,
                    grade: target.grade,
                    exam_date: target.exam_date,
                    notFoundMsg: ''
                };
                currentQueryKey = { stu_id: target.stu_id, seq_no: target.seq_no };
            } else {
                queriedExamData.value = {
                    found: false,
                    grade: null,
                    exam_date: null,
                    notFoundMsg: '未找到该学生的考试记录，请检查学号和序号'
                };
            }
        } catch (err) {
            ElMessage.error('查询失败');
        } finally {
            examQueryLoading.value = false;
        }
    };

    /**
     * 打开维护编辑表单
     */
    const openMaintenanceEditForm = () => {
        if (!queriedExamData.value.found) return;
        maintenanceEditForm.value = {
            grade: queriedExamData.value.grade,
            exam_date: queriedExamData.value.exam_date
        };
        maintenanceEditDialogVisible.value = true;
    };

    /**
     * 提交维护更新
     */
    const submitMaintenanceUpdate = async () => {
        try {
            await axios.put('/exam/', {
                grade: maintenanceEditForm.value.grade,
                exam_date: maintenanceEditForm.value.exam_date
            }, {
                params: { stu_id: currentQueryKey.stu_id, seq_no: currentQueryKey.seq_no }
            });
            ElMessage.success('修改成功');
            await loadExamRecords();
            examMaintenanceDialogVisible.value = false;
            maintenanceEditDialogVisible.value = false;
        } catch (err) {
            ElMessage.error('修改失败');
        }
    };

    /**
     * 删除查询到的成绩
     */
    const deleteQueriedExam = async () => {
        if (!queriedExamData.value.found) return;
        try {
            await ElMessageBox.confirm(
                `确定删除学号 ${currentQueryKey.stu_id} 第 ${currentQueryKey.seq_no} 次成绩吗？`,
                '确认删除',
                { type: 'warning' }
            );
            await axios.delete(`/exam/${currentQueryKey.stu_id}`, {
                params: { seq_no: currentQueryKey.seq_no }
            });
            ElMessage.success('删除成功');
            await loadExamRecords();
            examMaintenanceDialogVisible.value = false;
        } catch (err) {
            if (err !== 'cancel') {
                ElMessage.error('删除失败');
            }
        }
    };

    /**
     * 重置成绩维护
     */
    const resetExamMaintenance = () => {
        queriedExamData.value = { found: false, grade: null, exam_date: null, notFoundMsg: '' };
        currentQueryKey = null;
    };

    // ===================================
    // 返回导出
    // ===================================
    return {
        // 状态
        examRecords,
        examLoading,
        examDialogVisible,
        examForm,
        selectedExam,
        examMaintenanceDialogVisible,
        examQueryForm,
        queriedExamData,
        examQueryLoading,
        maintenanceEditDialogVisible,
        maintenanceEditForm,

        // 方法
        loadExamRecords,
        handleExamSelection,
        openExamDialog,
        saveExam,
        deleteExam,
        openExamMaintenanceDialog,
        queryExamRecord,
        openMaintenanceEditForm,
        submitMaintenanceUpdate,
        deleteQueriedExam,
        resetExamMaintenance
    };
}
