/**
 * 用户管理模块
 * 负责用户数据的增删改查（管理员功能）
 */

/**
 * 创建用户管理模块
 * @param {Function} options.getCurrentUser - 获取当前用户
 * @returns {Object} - 用户管理模块的响应式状态和方法
 */
export function createUserManagementModule({ getCurrentUser }) {
    // ===================================
    // 状态定义
    // ===================================
    const users = ref([]);
    const userLoading = ref(false);
    const userDialogVisible = ref(false);
    const userForm = ref({
        id: null,
        username: '',
        role: 'user',
        is_active: true
    });
    let editingUserId = null;

    // ===================================
    // 内部方法
    // ===================================
    const { ElMessage, ElMessageBox } = ElementPlus;

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

    // ===================================
    // 公开方法
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
     * 打开用户对话框
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
        const currentUser = getCurrentUser?.();
        if (currentUser?.username === username) {
            ElMessage.warning('不能删除当前登录用户');
            return;
        }

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
    // 返回导出
    // ===================================
    return {
        // 状态
        users,
        userLoading,
        userDialogVisible,
        userForm,

        // 方法
        loadUsers,
        openUserDialog,
        saveUser,
        deleteUser,
        getRoleText,
        getRoleClass
    };
}
