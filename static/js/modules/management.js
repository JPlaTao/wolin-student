/**
 * 数据管理模块
 * 学生/班级/教师/成绩/就业/用户 的增删改查
 */

const { ref, computed } = Vue;
const { ElMessage, ElMessageBox } = ElementPlus;

export function createManagementModule() {
    // ===================================
    // 数据管理 — 通用
    // ===================================
    const mgmtLoading = ref(false);
    const students = ref([]);
    const classes = ref([]);
    const teachers = ref([]);

    const studentPagination = ref({ currentPage: 1, pageSize: 10, total: 0 });
    const classPagination = ref({ currentPage: 1, pageSize: 10, total: 0 });
    const teacherPagination = ref({ currentPage: 1, pageSize: 10, total: 0 });

    const loadManagementData = async () => {
        mgmtLoading.value = true;
        try {
            const [studentRes, classRes, teacherRes] = await Promise.all([
                axios.get('/students', { params: { page: studentPagination.value.currentPage, page_size: studentPagination.value.pageSize } }),
                axios.get('/class/', { params: { page: classPagination.value.currentPage, page_size: classPagination.value.pageSize } }),
                axios.get('/teacher/all', { params: { page: teacherPagination.value.currentPage, page_size: teacherPagination.value.pageSize } })
            ]);
            const rawStudents = studentRes.data.data || [];
            studentPagination.value.total = studentRes.data.total || rawStudents.length;
            const classDict = classRes.data.data || {};
            classPagination.value.total = Object.keys(classDict).length;
            classes.value = Object.values(classDict).map(c => ({ ...c, head_teacher_name: c.head_teacher_name || '未知' }));
            const classMap = new Map(classes.value.map(c => [c.class_id, c.class_name]));
            students.value = rawStudents.map(s => ({ ...s, class_name: classMap.get(s.class_id) || `班级${s.class_id}` }));
            teachers.value = teacherRes.data.data || [];
            teacherPagination.value.total = teacherRes.data.total || teachers.value.length;
        } catch (err) {
            ElMessage.error('加载管理数据失败');
        } finally {
            mgmtLoading.value = false;
        }
    };

    // ===================================
    // 学生管理
    // ===================================
    const studentSearch = ref({ name: '', class_id: '' });
    const studentDialogVisible = ref(false);
    const studentForm = ref({
        stu_name: '', native_place: '', graduated_school: '', major: '',
        admission_date: '', graduation_date: '', education: '本科',
        age: '', gender: '男', class_id: '', advisor_id: null
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
    const headTeacherOptions = ref([]);

    const loadStudents = async () => {
        mgmtLoading.value = true;
        try {
            const params = {};
            if (studentSearch.value.name) params.stu_name = studentSearch.value.name;
            if (studentSearch.value.class_id) params.class_id = studentSearch.value.class_id;
            params.page = studentPagination.value.currentPage;
            params.page_size = studentPagination.value.pageSize;
            const res = await axios.get('/students', { params });
            const rawStudents = res.data.data || [];
            studentPagination.value.total = res.data.total || rawStudents.length;
            const classMap = new Map(classes.value.map(c => [c.class_id, c.class_name]));
            students.value = rawStudents.map(s => ({ ...s, class_name: classMap.get(s.class_id) || `班级${s.class_id}` }));
        } catch (err) {
            ElMessage.error('查询学生失败');
        } finally {
            mgmtLoading.value = false;
        }
    };

    const loadCounselors = async () => {
        try {
            const res = await axios.get('/teacher/counselors');
            teacherOptions.value = res.data.data || [];
        } catch (err) { console.error('加载顾问列表失败:', err); }
    };

    const handleStudentPageChange = (page) => { studentPagination.value.currentPage = page; loadStudents(); };
    const handleStudentSizeChange = (size) => { studentPagination.value.pageSize = size; studentPagination.value.currentPage = 1; loadStudents(); };
    const handleStudentSearch = () => { studentPagination.value.currentPage = 1; loadStudents(); };

    const openStudentDialog = async (row) => {
        await loadCounselors();
        if (row) {
            editingStudentId = row.stu_id;
            studentForm.value = { ...row, advisor_id: row.advisor_id || null };
        } else {
            editingStudentId = null;
            studentForm.value = {
                stu_name: '', native_place: '', graduated_school: '', major: '',
                admission_date: '', graduation_date: '', education: '本科',
                age: '', gender: '男', class_id: '', advisor_id: null
            };
        }
        studentDialogVisible.value = true;
    };

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
        } catch (err) { ElMessage.error('保存失败'); }
    };

    const deleteStudent = async (id) => {
        try {
            await ElMessageBox.confirm('确定删除该学生？', '确认删除', { type: 'warning' });
            await axios.delete(`/students/${id}`);
            await loadStudents();
            ElMessage.success('学生删除成功！');
        } catch (err) { if (err !== 'cancel') ElMessage.error('删除失败'); }
    };

    // ===================================
    // 班级管理
    // ===================================
    const classDialogVisible = ref(false);
    const classForm = ref({ class_name: '', head_teacher_id: '', start_time: '' });
    let editingClassId = null;

    const openClassDialog = (row) => {
        if (row) {
            editingClassId = row.class_id;
            classForm.value = { class_name: row.class_name, head_teacher_id: row.head_teacher_id, start_time: row.start_time };
        } else {
            editingClassId = null;
            classForm.value = { class_name: '', head_teacher_id: '', start_time: '' };
        }
        classDialogVisible.value = true;
    };

    const saveClass = async () => {
        try {
            if (editingClassId) {
                await axios.put(`/class/${editingClassId}`, classForm.value);
                ElMessage.success('班级信息更新成功！');
            } else {
                await axios.post('/class/', classForm.value);
                ElMessage.success('班级新增成功！');
            }
            await loadManagementData();
            classDialogVisible.value = false;
        } catch (err) { ElMessage.error('保存失败'); }
    };

    const deleteClass = async (id) => {
        try {
            await ElMessageBox.confirm('确定删除该班级？', '确认删除', { type: 'warning' });
            await axios.delete(`/class/${id}`);
            await loadManagementData();
            ElMessage.success('班级删除成功！');
        } catch (err) { if (err !== 'cancel') ElMessage.error('删除失败'); }
    };

    const handleClassPageChange = (page) => { classPagination.value.currentPage = page; loadManagementData(); };
    const handleClassSizeChange = (size) => { classPagination.value.pageSize = size; classPagination.value.currentPage = 1; loadManagementData(); };

    // ===================================
    // 教师管理
    // ===================================
    const teacherDialogVisible = ref(false);
    const teacherForm = ref({ teacher_name: '', gender: '男', role: 'lecturer', phone: '' });
    let editingTeacherId = null;

    const openTeacherDialog = (row) => {
        if (row) {
            editingTeacherId = row.teacher_id;
            teacherForm.value = { ...row };
        } else {
            editingTeacherId = null;
            teacherForm.value = { teacher_name: '', gender: '男', role: 'lecturer', phone: '' };
        }
        teacherDialogVisible.value = true;
    };

    const saveTeacher = async () => {
        try {
            if (editingTeacherId) {
                await axios.put(`/teacher/${editingTeacherId}`, teacherForm.value);
                ElMessage.success('教师信息更新成功！');
            } else {
                await axios.post('/teacher/', teacherForm.value);
                ElMessage.success('教师新增成功！');
            }
            await loadManagementData();
            teacherDialogVisible.value = false;
        } catch (err) { ElMessage.error('保存失败'); }
    };

    const deleteTeacher = async (id) => {
        try {
            await ElMessageBox.confirm('确定删除该教师？', '确认删除', { type: 'warning' });
            await axios.delete(`/teacher/${id}`);
            await loadManagementData();
            ElMessage.success('教师删除成功！');
        } catch (err) { if (err !== 'cancel') ElMessage.error('删除失败'); }
    };

    const handleTeacherPageChange = (page) => { teacherPagination.value.currentPage = page; loadManagementData(); };
    const handleTeacherSizeChange = (size) => { teacherPagination.value.pageSize = size; teacherPagination.value.currentPage = 1; loadManagementData(); };

    // ===================================
    // 成绩管理
    // ===================================
    const examRecords = ref([]);
    const examLoading = ref(false);
    const examCurrentPage = ref(1);
    const examPageSize = ref(15);
    const pagedExamRecords = computed(() => {
        const start = (examCurrentPage.value - 1) * examPageSize.value;
        return examRecords.value.slice(start, start + examPageSize.value);
    });
    const handleExamPageChange = (page) => { examCurrentPage.value = page; };
    const handleExamSizeChange = (size) => { examPageSize.value = size; examCurrentPage.value = 1; };
    const myExamRecords = ref([]);
    const myExamLoading = ref(false);
    const examDialogVisible = ref(false);
    const examForm = ref({ stu_id: '', seq_no: '', grade: '', exam_date: '' });
    let editingExamKey = null;
    const selectedExam = ref(null);
    const examMaintenanceDialogVisible = ref(false);
    const examQueryForm = ref({ stu_id: '', seq_no: '' });
    const queriedExamData = ref({ found: false, grade: null, exam_date: null, notFoundMsg: '' });
    const examQueryLoading = ref(false);
    const maintenanceEditDialogVisible = ref(false);
    const maintenanceEditForm = ref({ grade: '', exam_date: '' });
    let currentQueryKey = null;

    const loadExamRecords = async () => {
        examLoading.value = true;
        try {
            const res = await axios.get('/exam/records');
            examRecords.value = res.data.data || [];
        } catch (err) {
            examRecords.value = [];
            ElMessage.error('加载成绩记录失败');
        } finally { examLoading.value = false; }
    };

    const handleExamSelection = (row) => { selectedExam.value = row; };

    const openExamDialog = (row) => {
        if (row) {
            editingExamKey = { stu_id: row.stu_id, seq_no: row.seq_no };
            examForm.value = { stu_id: row.stu_id, seq_no: row.seq_no, grade: row.grade, exam_date: row.exam_date };
        } else {
            editingExamKey = null;
            examForm.value = { stu_id: '', seq_no: '', grade: '', exam_date: '' };
        }
        examDialogVisible.value = true;
    };

    const saveExam = async () => {
        try {
            if (editingExamKey) {
                await axios.put('/exam/', examForm.value, { params: { stu_id: editingExamKey.stu_id, seq_no: editingExamKey.seq_no } });
                ElMessage.success('成绩更新成功！');
            } else {
                await axios.post('/exam/', examForm.value);
                ElMessage.success('成绩新增成功！');
            }
            await loadExamRecords();
            examDialogVisible.value = false;
        } catch (err) { ElMessage.error('操作失败'); }
    };

    const deleteExam = async (row) => {
        try {
            await ElMessageBox.confirm(`确定删除学生 ${row.stu_name} 第 ${row.seq_no} 次考试成绩吗？`, '确认删除', { type: 'warning' });
            await axios.delete(`/exam/${row.stu_id}`, { params: { seq_no: row.seq_no } });
            ElMessage.success('成绩删除成功！');
            await loadExamRecords();
            if (selectedExam.value === row) selectedExam.value = null;
        } catch (err) { if (err !== 'cancel') ElMessage.error('删除失败'); }
    };

    const openExamMaintenanceDialog = () => {
        examQueryForm.value = { stu_id: selectedExam.value?.stu_id || '', seq_no: selectedExam.value?.seq_no || '' };
        queriedExamData.value = { found: false, grade: null, exam_date: null, notFoundMsg: '' };
        examMaintenanceDialogVisible.value = true;
    };

    const queryExamRecord = async () => {
        if (!examQueryForm.value.stu_id || !examQueryForm.value.seq_no) { ElMessage.warning('请填写学号和考试序号'); return; }
        examQueryLoading.value = true;
        try {
            const res = await axios.get('/exam/records');
            const records = res.data.data || [];
            const target = records.find(r => r.stu_id === examQueryForm.value.stu_id && r.seq_no === examQueryForm.value.seq_no);
            if (target) {
                queriedExamData.value = { found: true, grade: target.grade, exam_date: target.exam_date, notFoundMsg: '' };
                currentQueryKey = { stu_id: target.stu_id, seq_no: target.seq_no };
            } else {
                queriedExamData.value = { found: false, grade: null, exam_date: null, notFoundMsg: '未找到该学生的考试记录' };
            }
        } catch (err) { ElMessage.error('查询失败'); } finally { examQueryLoading.value = false; }
    };

    const openMaintenanceEditForm = () => {
        if (!queriedExamData.value.found) return;
        maintenanceEditForm.value = { grade: queriedExamData.value.grade, exam_date: queriedExamData.value.exam_date };
        maintenanceEditDialogVisible.value = true;
    };

    const submitMaintenanceUpdate = async () => {
        try {
            await axios.put('/exam/', { grade: maintenanceEditForm.value.grade, exam_date: maintenanceEditForm.value.exam_date },
                { params: { stu_id: currentQueryKey.stu_id, seq_no: currentQueryKey.seq_no } });
            ElMessage.success('修改成功');
            await loadExamRecords();
            examMaintenanceDialogVisible.value = false;
            maintenanceEditDialogVisible.value = false;
        } catch (err) { ElMessage.error('修改失败'); }
    };

    const deleteQueriedExam = async () => {
        if (!queriedExamData.value.found) return;
        try {
            await ElMessageBox.confirm(`确定删除学号 ${currentQueryKey.stu_id} 第 ${currentQueryKey.seq_no} 次成绩吗？`, '确认删除', { type: 'warning' });
            await axios.delete(`/exam/${currentQueryKey.stu_id}`, { params: { seq_no: currentQueryKey.seq_no } });
            ElMessage.success('删除成功');
            await loadExamRecords();
            examMaintenanceDialogVisible.value = false;
        } catch (err) { if (err !== 'cancel') ElMessage.error('删除失败'); }
    };

    const resetExamMaintenance = () => {
        queriedExamData.value = { found: false, grade: null, exam_date: null, notFoundMsg: '' };
        currentQueryKey = null;
    };

    const loadMyExamScores = async () => {
        myExamLoading.value = true;
        try {
            const res = await axios.get('/exam/my-scores');
            myExamRecords.value = res.data.data || [];
        } catch (err) {
            myExamRecords.value = [];
            ElMessage.error('加载成绩失败');
        } finally {
            myExamLoading.value = false;
        }
    };

    // ===================================
    // 就业管理
    // ===================================
    const empSearch = ref({ stu_name: '', class_id: '' });
    const employmentRecords = ref([]);
    const empLoading = ref(false);
    const employmentDialogVisible = ref(false);
    const employmentForm = ref({ emp_id: null, stu_id: '', company: '', salary: '', offer_time: '' });
    let editingEmploymentId = null;
    const selectedEmployment = ref(null);

    const loadEmploymentData = async () => {
        empLoading.value = true;
        try {
            const res = await axios.get('/employment/query');
            let rawData = res.data.data || [];
            if (empSearch.value.class_id) rawData = rawData.filter(emp => emp.class_id === Number(empSearch.value.class_id));
            if (empSearch.value.stu_name) rawData = rawData.filter(emp => emp.stu_name && emp.stu_name.includes(empSearch.value.stu_name.trim()));
            const classMap = new Map(classes.value.map(c => [c.class_id, c.class_name]));
            employmentRecords.value = rawData.map(emp => ({ ...emp, class_name: classMap.get(emp.class_id) || `班级${emp.class_id}` }));
        } catch (err) { ElMessage.error('加载就业数据失败'); } finally { empLoading.value = false; }
    };

    const handleEmploymentSelection = (row) => { selectedEmployment.value = row; };

    const openEmploymentDialog = (row) => {
        if (row) {
            editingEmploymentId = row.emp_id;
            employmentForm.value = { emp_id: row.emp_id, stu_id: row.stu_id, company: row.company, salary: row.salary, offer_time: row.offer_time };
        } else {
            editingEmploymentId = null;
            employmentForm.value = { emp_id: null, stu_id: '', company: '', salary: '', offer_time: '' };
        }
        employmentDialogVisible.value = true;
    };

    const saveEmployment = async () => {
        try {
            if (editingEmploymentId) {
                await axios.put(`/employment/students/${employmentForm.value.stu_id}`, {
                    company: employmentForm.value.company, salary: employmentForm.value.salary, offer_time: employmentForm.value.offer_time
                });
                ElMessage.success('更新成功');
            } else {
                await axios.post('/employment/', {
                    stu_id: employmentForm.value.stu_id, company: employmentForm.value.company, salary: employmentForm.value.salary, offer_time: employmentForm.value.offer_time
                });
                ElMessage.success('新增成功');
            }
            await loadEmploymentData();
            employmentDialogVisible.value = false;
        } catch (err) { ElMessage.error('操作失败'); }
    };

    const deleteEmployment = async (row) => {
        try {
            await ElMessageBox.confirm(`确定删除学生 ${row.stu_name} 的就业记录吗？`, '确认删除', { type: 'warning' });
            await axios.delete(`/employment/delete/${row.emp_id}`);
            ElMessage.success('删除成功');
            await loadEmploymentData();
            if (selectedEmployment.value === row) selectedEmployment.value = null;
        } catch (err) { if (err !== 'cancel') ElMessage.error('删除失败'); }
    };

    // ===================================
    // 用户管理
    // ===================================
    const users = ref([]);
    const userLoading = ref(false);
    const userDialogVisible = ref(false);
    const userForm = ref({ id: null, username: '', role: 'user', is_active: true, stu_id: null });
    let editingUserId = null;

    const loadUsers = async () => {
        userLoading.value = true;
        try {
            const res = await axios.get('/auth/users');
            users.value = res.data.data || [];
        } catch (err) { ElMessage.error('加载用户列表失败'); } finally { userLoading.value = false; }
    };

    const openUserDialog = (row) => {
        if (row) {
            editingUserId = row.id;
            userForm.value = { id: row.id, username: row.username, role: row.role, is_active: row.is_active, stu_id: row.stu_id || null };
        } else {
            editingUserId = null;
            userForm.value = { id: null, username: '', role: 'user', is_active: true, stu_id: null };
        }
        userDialogVisible.value = true;
    };

    const saveUser = async () => {
        if (!userForm.value.username || !userForm.value.role) { ElMessage.warning('请填写完整信息'); return; }
        try {
            if (editingUserId) {
                const payload = { role: userForm.value.role, is_active: userForm.value.is_active };
                if (userForm.value.stu_id !== undefined) {
                    payload.stu_id = userForm.value.stu_id || null;
                }
                await axios.put(`/auth/users/${editingUserId}`, payload);
                ElMessage.success('用户更新成功');
            } else {
                const regPayload = { username: userForm.value.username, password: userForm.value.password || '123456', role: userForm.value.role };
                if (userForm.value.stu_id) regPayload.stu_id = userForm.value.stu_id;
                await axios.post('/auth/register', regPayload);
                ElMessage.success('用户创建成功');
            }
            userDialogVisible.value = false;
            await loadUsers();
        } catch (err) { ElMessage.error(err.response?.data?.detail || '操作失败'); }
    };

    const deleteUser = async (userId, username) => {
        try {
            await ElMessageBox.confirm(`确定要删除用户 "${username}" 吗？此操作不可恢复。`, '确认删除', { type: 'warning' });
            await axios.delete(`/auth/users/${userId}`);
            ElMessage.success('用户删除成功');
            await loadUsers();
        } catch (err) { if (err !== 'cancel') ElMessage.error(err.response?.data?.detail || '删除失败'); }
    };

    const getRoleText = (role) => {
        const roleMap = { 'admin': '管理员', 'teacher': '教师', 'student': '学生', 'user': '普通用户' };
        return roleMap[role] || role;
    };

    const getRoleClass = (role) => `role-${role}`;

    return {
        // 通用
        students, classes, teachers, mgmtLoading,
        loadManagementData, loadStudents,
        // 搜索
        studentSearch, handleStudentSearch,
        // 分页
        studentPagination, classPagination, teacherPagination,
        handleStudentPageChange, handleStudentSizeChange,
        handleClassPageChange, handleClassSizeChange,
        handleTeacherPageChange, handleTeacherSizeChange,
        // 学生表单
        studentDialogVisible, studentForm, studentFormRef, studentRules,
        teacherOptions, headTeacherOptions,
        openStudentDialog, saveStudent, deleteStudent,
        // 班级表单
        classDialogVisible, classForm,
        openClassDialog, saveClass, deleteClass,
        // 教师表单
        teacherDialogVisible, teacherForm,
        openTeacherDialog, saveTeacher, deleteTeacher,
        // 成绩
        examRecords, examLoading, examDialogVisible, examForm, loadExamRecords,
        openExamDialog, saveExam, deleteExam, selectedExam, handleExamSelection,
        examMaintenanceDialogVisible, examQueryForm, queriedExamData, examQueryLoading,
        queryExamRecord, openExamMaintenanceDialog, maintenanceEditDialogVisible,
        maintenanceEditForm, openMaintenanceEditForm, submitMaintenanceUpdate,
        deleteQueriedExam, resetExamMaintenance,
        myExamRecords, myExamLoading, loadMyExamScores,
        examCurrentPage, examPageSize, pagedExamRecords, handleExamPageChange, handleExamSizeChange,
        // 就业
        empSearch, employmentRecords, empLoading, loadEmploymentData,
        selectedEmployment, handleEmploymentSelection, employmentDialogVisible, employmentForm,
        openEmploymentDialog, saveEmployment, deleteEmployment,
        // 用户管理
        users, userLoading, userDialogVisible, userForm,
        openUserDialog, saveUser, deleteUser, getRoleText, getRoleClass,
        loadUsers,
    };
}
