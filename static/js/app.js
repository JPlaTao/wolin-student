/**
 * 沃林学生管理系统 - 前端应用
 * Vue 3 + Element Plus + Axios
 */

const { createApp, ref, onMounted, watch, nextTick } = Vue;
const { ElMessage, ElMessageBox } = ElementPlus;

const app = createApp({
    setup() {
        // ===================================
        // 状态管理
        // ===================================

        // 认证状态
        const isLoggedIn = ref(false);
        const authMode = ref('login');
        const authUsername = ref('');
        const authPassword = ref('');
        const authRole = ref('user');  // 注册时选择的角色
        const currentUser = ref(null);
        const isAdmin = ref(false);  // 当前用户是否为管理员

        // 导航状态
        const activeTab = ref('dashboard');
        const mgmtTab = ref('student');
        const sidebarOpen = ref(true);
        const isMobile = ref(window.innerWidth < 768);

        // 侧边栏切换
        const toggleSidebar = () => {
            sidebarOpen.value = !sidebarOpen.value;
        };

        // 监听窗口大小变化
        const handleResize = () => {
            isMobile.value = window.innerWidth < 768;
            if (!isMobile.value) {
                sidebarOpen.value = true;
            } else {
                sidebarOpen.value = false;
            }
        };

        // 初始化时检测移动设备
        if (isMobile.value) {
            sidebarOpen.value = false;
        }

        // 仪表板数据
        const dashboard = ref({
            studentCount: 0,
            classCount: 0,
            avgAge: 0,
            employmentRate: 0,
            topSalary: []
        });

        // 智能问答
        const chatMessages = ref([{
            id: 1,
            role: 'ai',
            type: 'text',
            content: '✨ 你好！我是智能助手，可以问数据问题（如"学生有多少人？"或"李芳老师有多少个学生？"）或业务问题。我也支持多轮对话记忆，可以基于上下文连续提问。'
        }]);
        const currentQuestion = ref('');
        const isLoading = ref(false);
        const chatContainer = ref(null);
        const currentSessionId = ref(null);

        /**
         * 获取用户会话ID（用户级别固定会话）
         * 格式: user_{user_id}
         * 未来扩展: 改为 list 存储多个会话
         */
        const getUserSessionId = () => {
            const stored = localStorage.getItem('user_session_id');
            if (stored) return stored;
            // 如果有登录用户，使用用户ID生成固定session
            const token = localStorage.getItem('access_token');
            if (token) {
                // 暂时用时间戳作为session（登录时后端会返回真正的user_id）
                // 实际session_id由后端基于user_id生成
                return null;
            }
            return null;
        };

        /**
         * 初始化用户会话（登录成功后调用）
         */
        const initUserSession = (userId) => {
            const sessionId = `user_${userId}`;
            currentSessionId.value = sessionId;
            localStorage.setItem('user_session_id', sessionId);
            console.log('[Session] 初始化用户会话:', sessionId);
        };

        // 从 localStorage 恢复 session_id
        const savedSessionId = localStorage.getItem('user_session_id');
        if (savedSessionId) {
            currentSessionId.value = savedSessionId;
            console.log('[Session] 从 localStorage 恢复 session_id:', savedSessionId);
        } else {
            console.log('[Session] localStorage 中无 session_id，等待登录后初始化');
        }

        // 数据管理
        const mgmtLoading = ref(false);
        const students = ref([]);
        const classes = ref([]);
        const teachers = ref([]);
        const users = ref([]);
        const userLoading = ref(false);
        const studentSearch = ref({ name: '', class_id: '' });

        // 成绩
        const examRecords = ref([]);
        const examLoading = ref(false);
        const examDialogVisible = ref(false);
        const examForm = ref({ stu_id: '', seq_no: '', grade: '', exam_date: '' });
        let editingExamKey = null;
        const selectedExam = ref(null);
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

        // 就业
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

        // 用户管理
        const userDialogVisible = ref(false);
        const userForm = ref({
            id: null,
            username: '',
            role: 'user',
            is_active: true
        });
        let editingUserId = null;

        // 表单状态
        const studentDialogVisible = ref(false);
        const classDialogVisible = ref(false);
        const teacherDialogVisible = ref(false);
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
        const classForm = ref({
            class_name: '',
            head_teacher_id: '',
            start_time: ''
        });
        const teacherForm = ref({
            teacher_name: '',
            gender: '男',
            role: 'lecturer',
            phone: ''
        });
        let editingStudentId = null,
            editingClassId = null,
            editingTeacherId = null;
        const studentFormRef = ref(null);
        const studentRules = {
            stu_name: [{ required: true, message: '请输入姓名' }],
            native_place: [{ required: true, message: '请输入籍贯' }],
            class_id: [{ required: true, message: '请选择班级' }],
            age: [{ type: 'number', min: 0, max: 120, message: '年龄需0-120' }]
        };
        const teacherOptions = ref([]);
        const headTeacherOptions = ref([]);

        // 图表实例
        let genderChart, scoreChart, salaryChart, durationChart, examSeqChart;

        // ===================================
        // 文生图
        // ===================================

        const imageForm = ref({
            prompt: '',
            negative_prompt: '',
            size: '1280*1280',
            n: 1,
            prompt_extend: true,
            watermark: false
        });
        const isGenerating = ref(false);
        const generatedImages = ref([]);
        const imageHistory = ref([]);
        const showImagePreview = ref(false);
        const previewImageUrl = ref('');

        // ===================================
        // 辅助函数
        // ===================================

        /**
         * 设置认证令牌
         */
        const setAuthToken = (token) => {
            if (token) {
                axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
            } else {
                delete axios.defaults.headers.common['Authorization'];
            }
        };

        /**
         * 重置会话ID（仅清除内存，用于刷新场景）
         * 注意：user_session_id 是用户级别固定值，不应轻易清除
         */
        const resetSessionId = () => {
            // 只清除内存，不清除 localStorage
            // session_id 是用户级别固定的，与用户绑定
            currentSessionId.value = localStorage.getItem('user_session_id');
        };

        /**
         * 获取角色显示文本
         */
        const getRoleText = (role) => {
            const roleMap = {
                'admin': '管理员',
                'teacher': '教师',
                'student': '学生',
                'user': '普通用户'
            };
            return roleMap[role] || role;
        };

        /**
         * 获取角色标签类
         */
        const getRoleClass = (role) => {
            return `role-${role}`;
        };

        /**
         * 渲染 Markdown 文本
         */
        const renderMarkdown = (text) => {
            if (typeof marked !== 'undefined') {
                return marked.parse(text);
            }
            return text;
        };

        // ===================================
        // 认证相关
        // ===================================

        /**
         * 提交认证（登录/注册）
         */
        const submitAuth = async () => {
            try {
                if (authMode.value === 'login') {
                    // 登录前先清除旧的 token
                    delete axios.defaults.headers.common['Authorization'];
                    const res = await axios.post('/auth/login', {
                        username: authUsername.value,
                        password: authPassword.value
                    });
                    localStorage.setItem('access_token', res.data.access_token);
                    setAuthToken(res.data.access_token);
                    isLoggedIn.value = true;
                    currentUser.value = {
                        username: res.data.username,
                        role: res.data.role,
                        userId: res.data.user_id
                    };
                    isAdmin.value = res.data.role === 'admin';
                    // 初始化用户会话（基于 user_id 的固定会话）
                    initUserSession(res.data.user_id);
                    await refreshDashboard();
                    await loadManagementData();
                    ElMessage.success('登录成功');
                } else {
                    await axios.post('/auth/register', {
                        username: authUsername.value,
                        password: authPassword.value,
                        role: authRole.value
                    });
                    ElMessage.success('注册成功，请登录');
                    authMode.value = 'login';
                }
            } catch (err) {
                ElMessage.error(err.response?.data?.detail || '操作失败');
            }
        };

        /**
         * 退出登录
         */
        const logout = async () => {
            try {
                await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
                    confirmButtonText: '确定',
                    cancelButtonText: '取消',
                    type: 'warning'
                });
                localStorage.removeItem('access_token');
                setAuthToken(null);
                delete axios.defaults.headers.common['Authorization'];
                isLoggedIn.value = false;
                currentUser.value = null;
                isAdmin.value = false;
                resetSessionId();
                ElMessage.success('已退出登录');
            } catch (err) {
                // 用户取消操作
            }
        };

        /**
         * 检查登录状态
         */
        const checkLogin = async () => {
            const token = localStorage.getItem('access_token');
            if (token) {
                try {
                    setAuthToken(token);
                    const res = await axios.get('/auth/me');
                    isLoggedIn.value = true;
                    currentUser.value = res.data;
                    isAdmin.value = res.data.role === 'admin';
                    resetSessionId();
                } catch (err) {
                    // Token 无效，清除本地存储
                    localStorage.removeItem('access_token');
                    setAuthToken(null);
                    isLoggedIn.value = false;
                    currentUser.value = null;
                    isAdmin.value = false;
                }
            }
        };

        // ===================================
        // 用户管理
        // ===================================

        /**
         * 加载用户列表
         */
        const loadUsers = async () => {
            userLoading.value = true;
            try {
                const res = await axios.get('/auth/users');
                users.value = res.data.data || [];
            } catch (err) {
                ElMessage.error('加载用户列表失败');
            } finally {
                userLoading.value = false;
            }
        };

        /**
         * 打开用户编辑对话框
         */
        const openUserDialog = (row) => {
            if (row) {
                editingUserId = row.id;
                userForm.value = {
                    id: row.id,
                    username: row.username,
                    role: row.role,
                    is_active: row.is_active
                };
            } else {
                editingUserId = null;
                userForm.value = {
                    id: null,
                    username: '',
                    role: 'user',
                    is_active: true
                };
            }
            userDialogVisible.value = true;
        };

        /**
         * 保存用户
         */
        const saveUser = async () => {
            if (!userForm.value.username || !userForm.value.role) {
                ElMessage.warning('请填写完整信息');
                return;
            }

            try {
                if (editingUserId) {
                    await axios.put(`/auth/users/${editingUserId}`, {
                        role: userForm.value.role,
                        is_active: userForm.value.is_active
                    });
                    ElMessage.success('用户更新成功');
                } else {
                    // 注册新用户
                    await axios.post('/auth/register', {
                        username: userForm.value.username,
                        password: userForm.value.password || '123456',
                        role: userForm.value.role
                    });
                    ElMessage.success('用户创建成功');
                }
                userDialogVisible.value = false;
                await loadUsers();
            } catch (err) {
                ElMessage.error(err.response?.data?.detail || '操作失败');
            }
        };

        /**
         * 删除用户
         */
        const deleteUser = async (userId, username) => {
            try {
                await ElMessageBox.confirm(
                    `确定要删除用户 "${username}" 吗？此操作不可恢复。`,
                    '确认删除',
                    {
                        confirmButtonText: '确定',
                        cancelButtonText: '取消',
                        type: 'warning'
                    }
                );
                await axios.delete(`/auth/users/${userId}`);
                ElMessage.success('用户删除成功');
                await loadUsers();
            } catch (err) {
                if (err !== 'cancel') {
                    ElMessage.error(err.response?.data?.detail || '删除失败');
                }
            }
        };

        // ===================================
        // 数据看板
        // ===================================

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

        const refreshDashboard = async () => {
            await loadDashboardData();
            await renderDashboardCharts();
        };

        // ===================================
        // 高级统计
        // ===================================

        const renderAdvancedCharts = async () => {
            try {
                const [salaryRes, durationRes, examSeqRes] = await Promise.all([
                    axios.get('/statistics/advanced/salary-distribution'),
                    axios.get('/statistics/employment/avg-duration-per-class'),
                    axios.get('/statistics/score/class-avg-per-exam')
                ]);
                await nextTick();

                if (salaryChart) salaryChart.dispose();
                if (durationChart) durationChart.dispose();
                if (examSeqChart) examSeqChart.dispose();

                salaryChart = echarts.init(document.getElementById('salaryDistChart'));
                durationChart = echarts.init(document.getElementById('durationChart'));
                examSeqChart = echarts.init(document.getElementById('examSeqChart'));

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

        // ===================================
        // 数据管理
        // ===================================

        const loadManagementData = async () => {
            mgmtLoading.value = true;
            try {
                const [studentRes, classRes, teacherRes] = await Promise.all([
                    axios.get('/students'),
                    axios.get('/class/'),
                    axios.get('/teacher/all')
                ]);

                const rawStudents = studentRes.data.data || [];
                const classDict = classRes.data.data || {};

                classes.value = Object.values(classDict).map(c => ({
                    ...c,
                    head_teacher_name: c.head_teacher_name || '未知'
                }));

                const classMap = new Map(classes.value.map(c => [c.class_id, c.class_name]));
                students.value = rawStudents.map(s => ({
                    ...s,
                    class_name: classMap.get(s.class_id) || `班级${s.class_id}`
                }));

                teachers.value = teacherRes.data.data || [];
                teacherOptions.value = teachers.value;
                headTeacherOptions.value = teachers.value.filter(t => t.role === 'headteacher');
            } catch (err) {
                ElMessage.error('加载管理数据失败');
            } finally {
                mgmtLoading.value = false;
            }
        };

        const loadStudents = async () => {
            mgmtLoading.value = true;
            try {
                const params = {};
                if (studentSearch.value.name) params.stu_name = studentSearch.value.name;
                if (studentSearch.value.class_id) params.class_id = studentSearch.value.class_id;

                const res = await axios.get('/students', { params });
                const rawStudents = res.data.data || [];
                const classMap = new Map(classes.value.map(c => [c.class_id, c.class_name]));
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
            } catch (err) {
                ElMessage.error('保存失败');
            }
        };

        const deleteClass = async (id) => {
            try {
                await ElMessageBox.confirm('确定删除该班级？', '确认删除', {
                    type: 'warning'
                });
                await axios.delete(`/class/${id}`);
                await loadManagementData();
                ElMessage.success('班级删除成功！');
            } catch (err) {
                if (err !== 'cancel') {
                    ElMessage.error('删除失败');
                }
            }
        };

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
            } catch (err) {
                ElMessage.error('保存失败');
            }
        };

        const deleteTeacher = async (id) => {
            try {
                await ElMessageBox.confirm('确定删除该教师？', '确认删除', {
                    type: 'warning'
                });
                await axios.delete(`/teacher/${id}`);
                await loadManagementData();
                ElMessage.success('教师删除成功！');
            } catch (err) {
                if (err !== 'cancel') {
                    ElMessage.error('删除失败');
                }
            }
        };

        // ===================================
        // 成绩管理
        // ===================================

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

        const handleExamSelection = (row) => {
            selectedExam.value = row;
        };

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

        const openExamMaintenanceDialog = () => {
            examQueryForm.value = {
                stu_id: selectedExam.value?.stu_id || '',
                seq_no: selectedExam.value?.seq_no || ''
            };
            queriedExamData.value = { found: false, grade: null, exam_date: null, notFoundMsg: '' };
            examMaintenanceDialogVisible.value = true;
        };

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

        const openMaintenanceEditForm = () => {
            if (!queriedExamData.value.found) return;
            maintenanceEditForm.value = {
                grade: queriedExamData.value.grade,
                exam_date: queriedExamData.value.exam_date
            };
            maintenanceEditDialogVisible.value = true;
        };

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

        const resetExamMaintenance = () => {
            queriedExamData.value = { found: false, grade: null, exam_date: null, notFoundMsg: '' };
            currentQueryKey = null;
        };

        // ===================================
        // 就业管理
        // ===================================

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

                const classMap = new Map(classes.value.map(c => [c.class_id, c.class_name]));
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

        const handleEmploymentSelection = (row) => {
            selectedEmployment.value = row;
        };

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
        // 文生图
        // ===================================

        /**
         * 生成图片
         */
        const generateImage = async () => {
            if (!imageForm.value.prompt.trim()) {
                ElMessage.warning('请输入提示词');
                return;
            }

            isGenerating.value = true;
            generatedImages.value = [];

            try {
                const res = await axios.post('/image/generate', {
                    prompt: imageForm.value.prompt,
                    negative_prompt: imageForm.value.negative_prompt,
                    size: imageForm.value.size,
                    n: imageForm.value.n,
                    prompt_extend: imageForm.value.prompt_extend,
                    watermark: imageForm.value.watermark
                });

                const data = res.data;
                generatedImages.value = data.images;

                // 添加到历史记录
                const now = new Date();
                const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
                imageHistory.value.unshift({
                    prompt: imageForm.value.prompt,
                    size: data.size,
                    image_count: data.image_count,
                    images: data.images,
                    time: timeStr
                });

                // 限制历史记录数量
                if (imageHistory.value.length > 10) {
                    imageHistory.value = imageHistory.value.slice(0, 10);
                }

                ElMessage.success(`成功生成 ${data.image_count} 张图片`);
            } catch (err) {
                ElMessage.error(err.response?.data?.detail || '图片生成失败');
            } finally {
                isGenerating.value = false;
            }
        };

        /**
         * 重置表单
         */
        const resetImageForm = () => {
            imageForm.value = {
                prompt: '',
                negative_prompt: '',
                size: '1280*1280',
                n: 1,
                prompt_extend: true,
                watermark: false
            };
            generatedImages.value = [];
        };

        /**
         * 处理图片加载错误
         */
        const handleImageError = (index) => {
            ElMessage.warning(`图片 ${index + 1} 加载失败，请点击"预览"尝试打开`);
        };

        /**
         * 预览图片
         */
        const previewImage = (url) => {
            previewImageUrl.value = url;
            showImagePreview.value = true;
        };

        /**
         * 下载图片
         */
        const downloadImage = async (url, index) => {
            try {
                ElMessage.info('正在下载...');
                const link = document.createElement('a');
                link.href = url;
                link.download = `generated_image_${Date.now()}_${index + 1}.png`;
                link.target = '_blank';
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            } catch (err) {
                ElMessage.error('下载失败，请右键点击"查看原图"手动保存');
            }
        };

        // ===================================
        // 智能问答
        // ===================================

        const sendQuestion = async () => {
            if (!currentQuestion.value.trim()) return;

            const question = currentQuestion.value;
            chatMessages.value.push({
                id: Date.now(),
                role: 'user',
                type: 'text',
                content: question
            });
            currentQuestion.value = '';
            isLoading.value = true;

            await nextTick();
            if (chatContainer.value) {
                chatContainer.value.scrollTop = chatContainer.value.scrollHeight;
            }

            try {
                const payload = { question };
                if (currentSessionId.value) {
                    payload.session_id = currentSessionId.value;
                }
                console.log('[Session] 发送请求，携带 session_id:', currentSessionId.value);

                const res = await axios.post('/query/natural', payload);

                // 处理返回的 session_id（持久化到 localStorage）
                if (res.data && res.data.session_id) {
                    currentSessionId.value = res.data.session_id;
                    localStorage.setItem('current_session_id', res.data.session_id);
                    console.log('[Session] 保存 session_id 到 localStorage:', res.data.session_id);
                } else if (res.data && res.data.data && res.data.data.session_id) {
                    currentSessionId.value = res.data.data.session_id;
                    localStorage.setItem('current_session_id', res.data.data.session_id);
                    console.log('[Session] 保存 session_id 到 localStorage:', res.data.data.session_id);
                }

                const result = res.data;
                if (result.type === 'sql') {
                    const data = result.data;
                    const count = result.count;
                    let formattedContent = '';
                    let isSingleValue = false;

                    if (count === 0) {
                        formattedContent = '未查询到相关数据。';
                    } else if (count === 1 && Object.keys(data[0]).length === 1) {
                        const key = Object.keys(data[0])[0];
                        let value = data[0][key];
                        isSingleValue = true;
                        formattedContent = `${key}：${value}`;
                    } else {
                        let tableHtml = '<table class="result-table"><thead><tr>';
                        const headers = Object.keys(data[0]);
                        headers.forEach(h => { tableHtml += `<th>${h}</th>`; });
                        tableHtml += '</tr></thead><tbody>';
                        data.slice(0, 10).forEach(row => {
                            tableHtml += '<tr>';
                            headers.forEach(h => { tableHtml += `<td>${row[h]}</td>`; });
                            tableHtml += '</tr>';
                        });
                        tableHtml += '</tbody></table>';
                        if (count > 10) {
                            tableHtml += `<p class="text-xs text-slate-400 mt-2">共 ${count} 条记录，仅显示前 10 条。</p>`;
                        }
                        formattedContent = tableHtml;
                    }
                    chatMessages.value.push({
                        id: Date.now(),
                        role: 'ai',
                        type: 'sql',
                        content: formattedContent,
                        sql: result.sql,
                        isSingleValue
                    });
                } else {
                    chatMessages.value.push({
                        id: Date.now(),
                        role: 'ai',
                        type: 'text',
                        content: result.answer
                    });
                }
            } catch (err) {
                chatMessages.value.push({
                    id: Date.now(),
                    role: 'ai',
                    type: 'text',
                    content: `错误：${err.response?.data?.detail || err.message}`
                });
            } finally {
                isLoading.value = false;
                await nextTick();
                if (chatContainer.value) {
                    chatContainer.value.scrollTop = chatContainer.value.scrollHeight;
                }
            }
        };

        // ===================================
        // 生命周期钩子
        // ===================================

        watch(activeTab, async (newVal) => {
            if (newVal === 'dashboard') {
                await refreshDashboard();
            } else if (newVal === 'statistics') {
                await renderAdvancedCharts();
            } else if (newVal === 'management') {
                await loadManagementData();
                if (mgmtTab.value === 'student') await loadStudents();
                else if (mgmtTab.value === 'exam') await loadExamRecords();
                else if (mgmtTab.value === 'employment') await loadEmploymentData();
            } else if (newVal === 'userManagement') {
                await loadUsers();
            } else if (newVal === 'imageGen') {
                // 文生图页面无需额外加载
            }
        });

        watch(mgmtTab, async (newTab) => {
            if (activeTab.value === 'management') {
                if (newTab === 'student') await loadStudents();
                else if (newTab === 'exam') await loadExamRecords();
                else if (newTab === 'employment') await loadEmploymentData();
            }
        });

        onMounted(async () => {
            await checkLogin();
            if (isLoggedIn.value) {
                await refreshDashboard();
                await loadManagementData();
                await loadStudents();
            }

            // 添加窗口大小变化监听
            window.addEventListener('resize', handleResize);
            handleResize();
        });

        // ===================================
        // 返回值
        // ===================================

        return {
            // 认证
            isLoggedIn,
            authMode,
            authUsername,
            authPassword,
            authRole,
            currentUser,
            isAdmin,
            submitAuth,
            logout,
            checkLogin,

            // 导航
            activeTab,
            mgmtTab,
            sidebarOpen,
            isMobile,
            toggleSidebar,

            // 仪表板
            dashboard,
            refreshDashboard,

            // 智能问答
            chatMessages,
            currentQuestion,
            isLoading,
            sendQuestion,
            chatContainer,
            renderMarkdown,

            // 文生图
            imageForm,
            isGenerating,
            generatedImages,
            imageHistory,
            showImagePreview,
            previewImageUrl,
            generateImage,
            resetImageForm,
            handleImageError,
            previewImage,
            downloadImage,

            // 数据管理
            students,
            classes,
            teachers,
            mgmtLoading,
            studentSearch,
            loadStudents,
            studentDialogVisible,
            classDialogVisible,
            teacherDialogVisible,
            studentForm,
            classForm,
            teacherForm,
            studentFormRef,
            studentRules,
            openStudentDialog,
            saveStudent,
            deleteStudent,
            openClassDialog,
            saveClass,
            deleteClass,
            openTeacherDialog,
            saveTeacher,
            deleteTeacher,
            teacherOptions,
            headTeacherOptions,

            // 成绩
            examRecords,
            examLoading,
            examDialogVisible,
            examForm,
            openExamDialog,
            saveExam,
            deleteExam,
            selectedExam,
            handleExamSelection,
            examMaintenanceDialogVisible,
            examQueryForm,
            queriedExamData,
            examQueryLoading,
            queryExamRecord,
            openExamMaintenanceDialog,
            maintenanceEditDialogVisible,
            maintenanceEditForm,
            openMaintenanceEditForm,
            submitMaintenanceUpdate,
            deleteQueriedExam,
            resetExamMaintenance,

            // 就业
            empSearch,
            employmentRecords,
            empLoading,
            loadEmploymentData,
            selectedEmployment,
            handleEmploymentSelection,
            employmentDialogVisible,
            employmentForm,
            openEmploymentDialog,
            saveEmployment,
            deleteEmployment,

            // 用户管理
            users,
            userLoading,
            userDialogVisible,
            userForm,
            openUserDialog,
            saveUser,
            deleteUser,
            getRoleText,
            getRoleClass
        };
    }
});

app.use(ElementPlus);
app.mount('#app');
