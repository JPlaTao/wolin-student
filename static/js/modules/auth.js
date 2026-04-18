/**
 * 认证模块
 * 负责登录、注册、登出、用户状态管理
 */

/**
 * 创建认证模块
 * @param {Object} options - 配置项
 * @param {Function} options.setAuthToken - 设置认证令牌
 * @param {Function} options.initUserSession - 初始化用户会话
 * @param {Function} options.resetSessionId - 重置会话ID
 * @returns {Object} - 认证模块的响应式状态和方法
 */
export function createAuthModule({ setAuthToken, initUserSession, resetSessionId }) {
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
    const currentSessionId = ref(null);

    // ===================================
    // 生命周期 - 从 localStorage 恢复会话
    // ===================================
    const savedSessionId = localStorage.getItem('user_session_id');
    if (savedSessionId) {
        currentSessionId.value = savedSessionId;
        console.log('[Session] 从 localStorage 恢复 session_id:', savedSessionId);
    } else {
        console.log('[Session] localStorage 中无 session_id，等待登录后初始化');
    }

    // ===================================
    // 内部方法
    // ===================================
    const { ElMessage, ElMessageBox } = ElementPlus;

    /**
     * 获取用户会话ID
     */
    const getUserSessionId = () => {
        return currentSessionId.value;
    };

    /**
     * 内部：设置当前用户
     */
    const setCurrentUser = (userData) => {
        currentUser.value = userData;
        isLoggedIn.value = !!userData;
        isAdmin.value = userData?.role === 'admin';
    };

    /**
     * 内部：设置会话ID
     */
    const setCurrentSessionId = (sessionId) => {
        currentSessionId.value = sessionId;
        if (sessionId) {
            localStorage.setItem('user_session_id', sessionId);
        }
    };

    /**
     * 内部：清除会话
     */
    const clearSession = () => {
        setCurrentUser(null);
        resetSessionId?.();
    };

    // ===================================
    // 公开方法
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
                setCurrentUser({
                    username: res.data.username,
                    role: res.data.role,
                    userId: res.data.user_id
                });
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
            return { success: false, error: err };
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
            clearSession();
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
                setCurrentUser(res.data);
                resetSessionId?.();
                return true;
            } catch (err) {
                localStorage.removeItem('access_token');
                setAuthToken(null);
                clearSession();
                return false;
            }
        }
        return false;
    };

    /**
     * 重置认证表单
     */
    const resetAuthForm = () => {
        authUsername.value = '';
        authPassword.value = '';
        authRole.value = 'user';
    };

    /**
     * 切换认证模式
     */
    const switchAuthMode = (mode) => {
        authMode.value = mode;
        resetAuthForm();
    };

    // ===================================
    // 返回导出
    // ===================================
    return {
        // 状态
        authMode,
        authUsername,
        authPassword,
        authRole,
        currentUser,
        isLoggedIn,
        isAdmin,
        currentSessionId,

        // 方法
        submitAuth,
        logout,
        checkLogin,
        getUserSessionId,
        setCurrentSessionId,
        resetAuthForm,
        switchAuthMode
    };
}

// Vue 响应式引用
import { ref } from 'vue';
