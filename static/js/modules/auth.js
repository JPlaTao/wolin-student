/**
 * 认证模块
 * 负责登录、注册、登出、用户状态管理
 */

const { ref } = Vue;
const { ElMessage, ElMessageBox } = ElementPlus;

export function createAuthModule() {
    // ===================================
    // 状态定义
    // ===================================
    const authMode = ref('login');
    const authUsername = ref('');
    const authPassword = ref('');
    const authRole = ref('user');
    const currentUser = ref(null);
    const isLoggedIn = ref(false);
    const isAdmin = ref(false);

    // ===================================
    // 内部方法
    // ===================================

    const initUserSession = (userId) => {
        const sessionId = `user_${userId}`;
        localStorage.setItem('user_session_id', sessionId);
    };

    const setAuthToken = (token) => {
        if (token) {
            axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
        } else {
            delete axios.defaults.headers.common['Authorization'];
        }
    };

    // ===================================
    // 公开方法
    // ===================================

    const submitAuth = async () => {
        try {
            if (authMode.value === 'login') {
                delete axios.defaults.headers.common['Authorization'];
                const res = await axios.post('/auth/login', {
                    username: authUsername.value,
                    password: authPassword.value
                });
                localStorage.setItem('access_token', res.data.access_token);
                setAuthToken(res.data.access_token);
                currentUser.value = {
                    username: res.data.username,
                    role: res.data.role,
                    userId: res.data.user_id
                };
                isLoggedIn.value = true;
                isAdmin.value = res.data.role === 'admin';
                initUserSession(res.data.user_id);
                ElMessage.success('登录成功');
                return { success: true, action: 'login' };
            } else {
                await axios.post('/auth/register', {
                    username: authUsername.value,
                    password: authPassword.value,
                    role: authRole.value
                });
                ElMessage.success('注册成功，请登录');
                authMode.value = 'login';
                return { success: true, action: 'register' };
            }
        } catch (err) {
            ElMessage.error(err.response?.data?.detail || '操作失败');
            return { success: false };
        }
    };

    const logout = async () => {
        try {
            await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
                confirmButtonText: '确定',
                cancelButtonText: '取消',
                type: 'warning'
            });
            localStorage.removeItem('access_token');
            localStorage.removeItem('user_session_id');
            setAuthToken(null);
            currentUser.value = null;
            isLoggedIn.value = false;
            isAdmin.value = false;
            ElMessage.success('已退出登录');
        } catch (err) { }
    };

    const checkLogin = async () => {
        const token = localStorage.getItem('access_token');
        if (token) {
            try {
                setAuthToken(token);
                const res = await axios.get('/auth/me');
                currentUser.value = res.data;
                isLoggedIn.value = true;
                isAdmin.value = res.data.role === 'admin';
                return true;
            } catch (err) {
                localStorage.removeItem('access_token');
                setAuthToken(null);
                currentUser.value = null;
                isLoggedIn.value = false;
                isAdmin.value = false;
                return false;
            }
        }
        return false;
    };

    return {
        authMode, authUsername, authPassword, authRole,
        currentUser, isLoggedIn, isAdmin,
        submitAuth, logout, checkLogin
    };
}
