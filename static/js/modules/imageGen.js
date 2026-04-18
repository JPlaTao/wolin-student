/**
 * 文生图模块
 * 负责图片生成相关功能
 */

/**
 * 创建文生图模块
 * @returns {Object} - 文生图模块的响应式状态和方法
 */
export function createImageGenModule() {
    // ===================================
    // 状态定义
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
    // 内部方法
    // ===================================
    const { ElMessage } = ElementPlus;

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

    /**
     * 从历史记录恢复
     */
    const restoreFromHistory = (item) => {
        imageForm.value.prompt = item.prompt;
        generatedImages.value = item.images || [];
        showImagePreview.value = false;
    };

    // ===================================
    // 返回导出
    // ===================================
    return {
        // 状态
        imageForm,
        isGenerating,
        generatedImages,
        imageHistory,
        showImagePreview,
        previewImageUrl,

        // 方法
        generateImage,
        resetImageForm,
        handleImageError,
        previewImage,
        downloadImage,
        restoreFromHistory
    };
}
