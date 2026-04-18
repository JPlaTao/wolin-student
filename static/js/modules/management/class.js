/**
 * 班级管理模块
 * 负责班级数据的增删改查
 */

/**
 * 创建班级管理模块
 * @param {Function} options.notifyUpdate - 通知更新的回调
 * @returns {Object} - 班级管理模块的响应式状态和方法
 */
export function createClassModule({ notifyUpdate }) {
    // ===================================
    // 状态定义
    // ===================================
    const classes = ref([]);
    const classDialogVisible = ref(false);
    const classForm = ref({
        class_name: '',
        head_teacher_id: '',
        start_time: ''
    });
    let editingClassId = null;
    const headTeacherOptions = ref([]);

    // ===================================
    // 内部方法
    // ===================================
    const { ElMessage, ElMessageBox } = ElementPlus;

    // ===================================
    // 公开方法
    // ===================================

    /**
     * 加载班级列表
     */
    const loadClasses = async () => {
        try {
            const res = await axios.get('/class/');
            const classDict = res.data.data || {};
            classes.value = Object.values(classDict).map(c => ({
                ...c,
                head_teacher_name: c.head_teacher_name || '未知'
            }));
        } catch (err) {
            console.error('加载班级失败:', err);
        }
    };

    /**
     * 获取班级列表
     */
    const getClasses = () => classes.value;

    /**
     * 打开班级对话框
     */
    const openClassDialog = (row) => {
        if (row) {
            editingClassId = row.class_id;
            classForm.value = {
                class_name: row.class_name,
                head_teacher_id: row.head_teacher_id,
                start_time: row.start_time
            };
        } else {
            editingClassId = null;
            classForm.value = {
                class_name: '',
                head_teacher_id: '',
                start_time: ''
            };
        }
        classDialogVisible.value = true;
    };

    /**
     * 保存班级
     */
    const saveClass = async () => {
        try {
            if (editingClassId) {
                await axios.put(`/class/${editingClassId}`, classForm.value);
                ElMessage.success('班级信息更新成功！');
            } else {
                await axios.post('/class/', classForm.value);
                ElMessage.success('班级新增成功！');
            }
            await loadClasses();
            classDialogVisible.value = false;
            notifyUpdate?.('class');
        } catch (err) {
            ElMessage.error('保存失败');
        }
    };

    /**
     * 删除班级
     */
    const deleteClass = async (id) => {
        try {
            await ElMessageBox.confirm('确定删除该班级？', '确认删除', {
                type: 'warning'
            });
            await axios.delete(`/class/${id}`);
            await loadClasses();
            ElMessage.success('班级删除成功！');
            notifyUpdate?.('class');
        } catch (err) {
            if (err !== 'cancel') {
                ElMessage.error('删除失败');
            }
        }
    };

    /**
     * 设置班主任选项
     */
    const setHeadTeacherOptions = (teachers) => {
        headTeacherOptions.value = teachers.filter(t => t.role === 'headteacher');
    };

    // ===================================
    // 返回导出
    // ===================================
    return {
        // 状态
        classes,
        classDialogVisible,
        classForm,
        headTeacherOptions,

        // 方法
        loadClasses,
        getClasses,
        openClassDialog,
        saveClass,
        deleteClass,
        setHeadTeacherOptions
    };
}
