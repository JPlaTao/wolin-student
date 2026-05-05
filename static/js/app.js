/**
 * 沃林学生管理系统 - 主入口（纯编排层）
 *
 * 职责：导入模块工厂 → setup() 中实例化 → 返回模板所需状态和方法
 * 不包含业务逻辑，所有功能在各 modules/*.js 中实现
 */
import { createAuthModule } from './modules/auth.js';
import { createDashboardModule } from './modules/dashboard.js';
import { createChatModule } from './modules/chat.js';
import { createDaiyuModule } from './modules/daiyu.js';
import { createStatisticsModule } from './modules/statistics.js';
import { createImageGenModule } from './modules/imageGen.js';
import { createEmailModule } from './modules/email.js';
import { createManagementModule } from './modules/management.js';

const { createApp, ref, onMounted, watch, nextTick } = Vue;
const { ElMessage } = ElementPlus;

const app = createApp({
    setup() {
        // ===================================
        // 导航状态
        // ===================================
        const activeTab = ref('dashboard');
        const mgmtTab = ref('student');
        const sidebarOpen = ref(true);
        const sidebarCollapsed = ref(false);
        const isMobile = ref(window.innerWidth < 768);

        const toggleSidebar = () => { sidebarOpen.value = !sidebarOpen.value; };
        const toggleSidebarCollapsed = () => { sidebarCollapsed.value = !sidebarCollapsed.value; };

        const handleResize = () => {
            isMobile.value = window.innerWidth < 768;
            sidebarOpen.value = !isMobile.value;
        };
        if (isMobile.value) sidebarOpen.value = false;

        // ===================================
        // 工具函数
        // ===================================
        const renderMarkdown = (text) => {
            if (typeof marked !== 'undefined') return marked.parse(text);
            return text;
        };

        const scrollToBottom = async (container) => {
            await nextTick();
            if (container) container.scrollTop = container.scrollHeight;
        };

        // ===================================
        // 模块实例化
        // ===================================
        const auth = createAuthModule();
        const dashboard = createDashboardModule();
        const chat = createChatModule({
            renderMarkdown,
            scrollToBottom: async () => {
                await nextTick();
                chat.chatContainer?.value?.scrollTo?.(0, chat.chatContainer.value.scrollHeight);
            }
        });
        const daiyu = createDaiyuModule();
        const statistics = createStatisticsModule();
        const imageGen = createImageGenModule();
        const email = createEmailModule();
        const mgmt = createManagementModule();

        // ===================================
        // 帮助函数（模板需要，不在模块中）
        // ===================================
        const isLoading = ref(false);

        // ===================================
        // 生命周期编排
        // ===================================
        watch(activeTab, async (newVal) => {
            if (newVal === 'dashboard') await dashboard.refreshDashboard();
            else if (newVal === 'statistics') await statistics.renderAdvancedCharts();
            else if (newVal === 'management') {
                await mgmt.loadManagementData();
                if (mgmtTab.value === 'student') await mgmt.loadStudents();
                else if (mgmtTab.value === 'exam') await mgmt.loadExamRecords();
                else if (mgmtTab.value === 'employment') await mgmt.loadEmploymentData();
            } else if (newVal === 'userManagement') await mgmt.loadUsers();
        });

        watch(mgmtTab, async (newTab) => {
            if (activeTab.value === 'management') {
                if (newTab === 'student') await mgmt.loadStudents();
                else if (newTab === 'exam') await mgmt.loadExamRecords();
                else if (newTab === 'employment') await mgmt.loadEmploymentData();
            }
        });

        onMounted(async () => {
            const loggedIn = await auth.checkLogin();
            if (loggedIn) {
                await dashboard.refreshDashboard();
                await mgmt.loadManagementData();
                await mgmt.loadStudents();
                await email.fetchEmailProviders();
                await email.fetchEmailConfig();
            }
            window.addEventListener('resize', handleResize);
            handleResize();
        });

        // ===================================
        // 登录成功后的初始化编排
        // ===================================
        const originalSubmitAuth = auth.submitAuth;
        auth.submitAuth = async () => {
            const result = await originalSubmitAuth();
            if (result.success && result.action === 'login') {
                await dashboard.refreshDashboard();
                await mgmt.loadManagementData();
                await mgmt.loadStudents();
                await email.fetchEmailProviders();
                await email.fetchEmailConfig();
            }
            return result;
        };

        return {
            // 导航
            activeTab, mgmtTab, sidebarOpen, sidebarCollapsed, isMobile,
            toggleSidebar, toggleSidebarCollapsed,

            // 工具
            renderMarkdown,

            // 认证
            ...auth,

            // 仪表板
            ...dashboard,

            // 智能问答
            ...chat, isLoading,

            // 黛玉智能
            ...daiyu,

            // 文生图
            ...imageGen,

            // 高级统计
            ...statistics,

            // 邮件
            ...email,

            // 数据管理
            ...mgmt
        };
    }
});

app.use(ElementPlus);
app.mount('#app');
