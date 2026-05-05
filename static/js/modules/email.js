/**
 * 邮件模块
 * 负责邮件发送与邮箱配置管理
 */

const { ref } = Vue;
const { ElMessage } = ElementPlus;

export function createEmailModule() {
    const emailForm = ref({ to: '', subject: '', content: '' });
    const emailSending = ref(false);
    const emailConfig = ref(null);
    const emailProviders = ref([]);
    const emailConfigDialogVisible = ref(false);
    const emailConfigSaving = ref(false);
    const emailConfigForm = ref({
        provider: '', email_address: '', auth_code: '', from_name: ''
    });

    const fetchEmailProviders = async () => {
        try {
            const res = await axios.get('/api/email/providers');
            emailProviders.value = res.data.providers;
        } catch (err) {
            console.error('获取服务商列表失败', err);
        }
    };

    const fetchEmailConfig = async () => {
        try {
            const res = await axios.get('/api/email/config');
            emailConfig.value = {
                ...res.data,
                provider_name: emailProviders.value.find(p => p.value === res.data.provider)?.label || res.data.provider
            };
        } catch (err) {
            if (err.response?.status !== 404) {
                console.error('获取邮箱配置失败', err);
            }
            emailConfig.value = null;
        }
    };

    const showEmailConfigDialog = () => {
        if (emailConfig.value) {
            emailConfigForm.value = {
                provider: emailConfig.value.provider,
                email_address: emailConfig.value.email_address,
                auth_code: '',
                from_name: emailConfig.value.from_name || ''
            };
        } else {
            emailConfigForm.value = {
                provider: '', email_address: '', auth_code: '', from_name: ''
            };
        }
        emailConfigDialogVisible.value = true;
    };

    const saveEmailConfig = async () => {
        if (!emailConfigForm.value.provider) { ElMessage.warning('请选择邮箱服务商'); return; }
        if (!emailConfigForm.value.email_address) { ElMessage.warning('请填写邮箱地址'); return; }
        if (!emailConfigForm.value.auth_code) { ElMessage.warning('请填写授权码'); return; }

        emailConfigSaving.value = true;
        try {
            const res = await axios.post('/api/email/config', emailConfigForm.value);
            emailConfig.value = {
                ...res.data,
                provider_name: emailProviders.value.find(p => p.value === res.data.provider)?.label || res.data.provider
            };
            emailConfigDialogVisible.value = false;
            ElMessage.success('邮箱配置保存成功');
        } catch (err) {
            ElMessage.error(err.response?.data?.detail || '保存失败');
        } finally {
            emailConfigSaving.value = false;
        }
    };

    const sendEmail = async () => {
        if (!emailForm.value.to.trim()) { ElMessage.warning('请填写收件人邮箱'); return; }
        if (!emailForm.value.subject.trim()) { ElMessage.warning('请填写邮件主题'); return; }
        if (!emailForm.value.content.trim()) { ElMessage.warning('请填写邮件内容'); return; }

        const toList = emailForm.value.to.split(',').map(email => email.trim()).filter(email => email);
        emailSending.value = true;
        try {
            const res = await axios.post('/api/email/send', {
                to: toList, subject: emailForm.value.subject, content: emailForm.value.content
            });
            if (res.data.success) {
                ElMessage.success(`邮件发送成功！已发送给 ${toList.length} 个收件人`);
                resetEmailForm();
            }
        } catch (err) {
            if (err.response?.status === 400 && err.response?.data?.detail?.includes('配置')) {
                emailConfig.value = null;
                showEmailConfigDialog();
            }
            ElMessage.error(err.response?.data?.detail || '邮件发送失败');
        } finally {
            emailSending.value = false;
        }
    };

    const resetEmailForm = () => {
        emailForm.value = { to: '', subject: '', content: '' };
    };

    return {
        emailForm, emailSending, emailConfig, emailProviders,
        emailConfigDialogVisible, emailConfigForm, emailConfigSaving,
        sendEmail, resetEmailForm,
        fetchEmailProviders, fetchEmailConfig, showEmailConfigDialog, saveEmailConfig
    };
}
