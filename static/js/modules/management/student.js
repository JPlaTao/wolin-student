/**
 * 学生管理模块
 * 负责学生数据的增删改查
 */

/**
 * 创建学生管理模块
 * @param {Object} options - 配置项
 * @param {Function} options.getClasses - 获取班级列表
 * @returns {Object} - 学生管理模块的响应式状态和方法
 */
export function createStudentModule({ getClasses }) {
    // ===================================
    // 状态定义
    // ===================================
    const students = ref([]);
    const mgmtLoading = ref(false);
    const studentSearch = ref({ name: '', class_id: '' });
    const studentDialogVisible = ref(false);
    const studentForm = ref({
        stu_name: '',
        native_place: '',
        graduated_school: '',
        major: '',
        admission_date: '',
        graduation_date: '',
        education: '本科',
        age: '',
        gender: '男',
        class_id: '',
        advisor_id: null
    });
    let editingStudentId = null;
    const studentFormRef = ref(null);
    const studentRules = {
        stu_name: [{ required: true, message: '请输入姓名' }],
        native_place: [{ required: true, message: '请输入籍贯' }],
        class_id: [{ required: true, message: '请选择班级' }],
        age: [{ type: 'number', min: 0, max: 120, message: '年龄需0-120' }]
    };
    const teacherOptions = ref([]);

    // ===================================
    // 内部方法
    // ===================================
    const { ElMessage, ElMessageBox } = ElementPlus;

    /**
     * 加载学生列表
     */
    const loadStudents = async () => {
        mgmtLoading.value = true;
        try {
            const params = {};
            if (studentSearch.value.name) params.stu_name = studentSearch.value.name;
            if (studentSearch.value.class_id) params.class_id = studentSearch.value.class_id;

            const res = await axios.get('/students', { params });
            const rawStudents = res.data.data || [];
            const classes = getClasses();
            const classMap = new Map(classes.map(c => [c.class_id, c.class_name]));
            students.value = rawStudents.map(s => ({
                ...s,
                class_name: classMap.get(s.class_id) || `班级${s.class_id}`
            }));
        } catch (err) {
            ElMessage.error('查询学生失败');
        } finally {
            mgmtLoading.value = false;
        }
    };

    /**
     * 加载所有学生（不带筛选）
     */
    const loadAllStudents = async () => {
        try {
            const res = await axios.get('/students');
            const rawStudents = res.data.data || [];
            const classes = getClasses();
            const classMap = new Map(classes.map(c => [c.class_id, c.class_name]));
            students.value = rawStudents.map(s => ({
                ...s,
                class_name: classMap.get(s.class_id) || `班级${s.class_id}`
            }));
        } catch (err) {
            console.error('加载学生失败:', err);
        }
    };

    // ===================================
    // 公开方法
    // ===================================

    /**
     * 打开学生对话框
     */
    const openStudentDialog = (row) => {
        if (row) {
            editingStudentId = row.stu_id;
            studentForm.value = { ...row, advisor_id: row.advisor_id || null };
        } else {
            editingStudentId = null;
            studentForm.value = {
                stu_name: '',
                native_place: '',
                graduated_school: '',
                major: '',
                admission_date: '',
                graduation_date: '',
                education: '本科',
                age: '',
                gender: '男',
                class_id: '',
                advisor_id: null
            };
        }
        studentDialogVisible.value = true;
    };

    /**
     * 保存学生
     */
    const saveStudent = async () => {
        try {
            if (editingStudentId) {
                await axios.put(`/students/${editingStudentId}`, studentForm.value);
                ElMessage.success('学生信息更新成功！');
            } else {
                await axios.post('/students/', studentForm.value);
                ElMessage.success('学生新增成功！');
            }
            await loadStudents();
            studentDialogVisible.value = false;
        } catch (err) {
            ElMessage.error('保存失败');
        }
    };

    /**
     * 删除学生
     */
    const deleteStudent = async (id) => {
        try {
            await ElMessageBox.confirm('确定删除该学生？', '确认删除', {
                type: 'warning'
            });
            await axios.delete(`/students/${id}`);
            await loadStudents();
            ElMessage.success('学生删除成功！');
        } catch (err) {
            if (err !== 'cancel') {
                ElMessage.error('删除失败');
            }
        }
    };

    /**
     * 设置教师选项
     */
    const setTeacherOptions = (teachers) => {
        teacherOptions.value = teachers;
    };

    /**
     * 获取学生列表（供其他模块使用）
     */
    const getStudents = () => students.value;

    // ===================================
    // 返回导出
    // ===================================
    return {
        // 状态
        students,
        mgmtLoading,
        studentSearch,
        studentDialogVisible,
        studentForm,
        studentFormRef,
        studentRules,
        teacherOptions,

        // 方法
        loadStudents,
        loadAllStudents,
        openStudentDialog,
        saveStudent,
        deleteStudent,
        setTeacherOptions,
        getStudents
    };
}
