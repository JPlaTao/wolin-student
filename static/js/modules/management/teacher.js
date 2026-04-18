/**
 * 教师管理模块
 * 负责教师数据的增删改查
 */

/**
 * 创建教师管理模块
 * @param {Function} options.notifyUpdate - 通知更新的回调
 * @returns {Object} - 教师管理模块的响应式状态和方法
 */
export function createTeacherModule({ notifyUpdate }) {
    // ===================================
    // 状态定义
    // ===================================
    const teachers = ref([]);
    const teacherDialogVisible = ref(false);
    const teacherForm = ref({
        teacher_name: '',
        gender: '男',
        role: 'lecturer',
        phone: ''
    });
    let editingTeacherId = null;

    // ===================================
    // 内部方法
    // ===================================
    const { ElMessage, ElMessageBox } = ElementPlus;

    // ===================================
    // 公开方法
    // ===================================

    /**
     * 加载教师列表
     */
    const loadTeachers = async () => {
        try {
            const res = await axios.get('/teacher/all');
            teachers.value = res.data.data || [];
        } catch (err) {
            console.error('加载教师失败:', err);
        }
    };

    /**
     * 获取教师列表
     */
    const getTeachers = () => teachers.value;

    /**
     * 打开教师对话框
     */
    const openTeacherDialog = (row) => {
        if (row) {
            editingTeacherId = row.teacher_id;
            teacherForm.value = { ...row };
        } else {
            editingTeacherId = null;
            teacherForm.value = {
                teacher_name: '',
                gender: '男',
                role: 'lecturer',
                phone: ''
            };
        }
        teacherDialogVisible.value = true;
    };

    /**
     * 保存教师
     */
    const saveTeacher = async () => {
        try {
            if (editingTeacherId) {
                await axios.put(`/teacher/${editingTeacherId}`, teacherForm.value);
                ElMessage.success('教师信息更新成功！');
            } else {
                await axios.post('/teacher/', teacherForm.value);
                ElMessage.success('教师新增成功！');
            }
            await loadTeachers();
            teacherDialogVisible.value = false;
            notifyUpdate?.('teacher');
        } catch (err) {
            ElMessage.error('保存失败');
        }
    };

    /**
     * 删除教师
     */
    const deleteTeacher = async (id) => {
        try {
            await ElMessageBox.confirm('确定删除该教师？', '确认删除', {
                type: 'warning'
            });
            await axios.delete(`/teacher/${id}`);
            await loadTeachers();
            ElMessage.success('教师删除成功！');
            notifyUpdate?.('teacher');
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
        teachers,
        teacherDialogVisible,
        teacherForm,

        // 方法
        loadTeachers,
        getTeachers,
        openTeacherDialog,
        saveTeacher,
        deleteTeacher
    };
}
