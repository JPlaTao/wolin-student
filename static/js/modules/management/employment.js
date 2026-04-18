/**
 * 就业管理模块
 * 负责就业数据的增删改查
 */

/**
 * 创建就业管理模块
 * @param {Function} options.getClasses - 获取班级列表
 * @param {Function} options.getStudents - 获取学生列表
 * @returns {Object} - 就业管理模块的响应式状态和方法
 */
export function createEmploymentModule({ getClasses, getStudents }) {
    // ===================================
    // 状态定义
    // ===================================
    const empSearch = ref({ stu_name: '', class_id: '' });
    const employmentRecords = ref([]);
    const empLoading = ref(false);
    const employmentDialogVisible = ref(false);
    const employmentForm = ref({
        emp_id: null,
        stu_id: '',
        company: '',
        salary: '',
        offer_time: ''
    });
    let editingEmploymentId = null;
    const selectedEmployment = ref(null);

    // ===================================
    // 内部方法
    // ===================================
    const { ElMessage, ElMessageBox } = ElementPlus;

    // ===================================
    // 公开方法
    // ===================================

    /**
     * 加载就业数据
     */
    const loadEmploymentData = async () => {
        empLoading.value = true;
        try {
            const res = await axios.get('/employment/query');
            let rawData = res.data.data || [];
            let filteredData = rawData;

            if (empSearch.value.class_id) {
                filteredData = filteredData.filter(emp => emp.class_id === Number(empSearch.value.class_id));
            }
            if (empSearch.value.stu_name) {
                filteredData = filteredData.filter(emp =>
                    emp.stu_name && emp.stu_name.includes(empSearch.value.stu_name.trim())
                );
            }

            const classes = getClasses();
            const classMap = new Map(classes.map(c => [c.class_id, c.class_name]));
            employmentRecords.value = filteredData.map(emp => ({
                ...emp,
                class_name: classMap.get(emp.class_id) || `班级${emp.class_id}`
            }));
        } catch (err) {
            ElMessage.error('加载就业数据失败');
        } finally {
            empLoading.value = false;
        }
    };

    /**
     * 处理就业记录选中
     */
    const handleEmploymentSelection = (row) => {
        selectedEmployment.value = row;
    };

    /**
     * 打开就业对话框
     */
    const openEmploymentDialog = (row) => {
        if (row) {
            editingEmploymentId = row.emp_id;
            employmentForm.value = {
                emp_id: row.emp_id,
                stu_id: row.stu_id,
                company: row.company,
                salary: row.salary,
                offer_time: row.offer_time
            };
        } else {
            editingEmploymentId = null;
            employmentForm.value = {
                emp_id: null,
                stu_id: '',
                company: '',
                salary: '',
                offer_time: ''
            };
        }
        employmentDialogVisible.value = true;
    };

    /**
     * 保存就业记录
     */
    const saveEmployment = async () => {
        try {
            if (editingEmploymentId) {
                await axios.put(`/employment/students/${employmentForm.value.stu_id}`, {
                    company: employmentForm.value.company,
                    salary: employmentForm.value.salary,
                    offer_time: employmentForm.value.offer_time
                });
                ElMessage.success('更新成功');
            } else {
                await axios.post('/employment/', {
                    stu_id: employmentForm.value.stu_id,
                    company: employmentForm.value.company,
                    salary: employmentForm.value.salary,
                    offer_time: employmentForm.value.offer_time
                });
                ElMessage.success('新增成功');
            }
            await loadEmploymentData();
            employmentDialogVisible.value = false;
        } catch (err) {
            ElMessage.error('操作失败');
        }
    };

    /**
     * 删除就业记录
     */
    const deleteEmployment = async (row) => {
        try {
            await ElMessageBox.confirm(
                `确定删除学生 ${row.stu_name} 的就业记录吗？`,
                '确认删除',
                { type: 'warning' }
            );
            await axios.delete(`/employment/delete/${row.emp_id}`);
            ElMessage.success('删除成功');
            await loadEmploymentData();
            if (selectedEmployment.value === row) selectedEmployment.value = null;
        } catch (err) {
            if (err !== 'cancel') {
                ElMessage.error('删除失败');
            }
        }
    };

    // ===================================
    // 返回导出
    // ===================================
    return {
        // 状态
        empSearch,
        employmentRecords,
        empLoading,
        employmentDialogVisible,
        employmentForm,
        selectedEmployment,

        // 方法
        loadEmploymentData,
        handleEmploymentSelection,
        openEmploymentDialog,
        saveEmployment,
        deleteEmployment
    };
}
