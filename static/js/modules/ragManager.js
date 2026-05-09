/**
 * RAG 知识库模块
 * 负责文档上传、切片预览、确认入库、语义检索
 *
 * Mock 驱动开发，useMock 开关切换真实 API
 */

const { ref } = Vue;
const { ElMessage } = ElementPlus;

// ===================================
// Mock 数据
// ===================================

const MOCK_UPLOAD = {
    code: 200, message: "success",
    data: {
        filename: "test_novel.txt",
        total_chars: 296,
        total_chunks: 1,
        preview: [
            { index: 0, content: "话说林黛玉自从来到荣国府，步步留心，时时在意，不肯轻易多说一句话，多行一步路，怕被人耻笑了去。\n贾母一见黛玉，便搂在怀里痛哭，说：我这些儿女，所疼者独有你母亲，今日一旦先舍我而去，连面也不能一见，今见了你，我怎不伤心！" }
        ]
    }
};

const MOCK_CONFIRM = {
    code: 200, message: "success",
    data: { filename: "test_novel.txt", total_chunks: 2, model: "text-embedding-v3", status: "ingested" }
};

const MOCK_SEARCH = {
    code: 200, message: "success",
    data: {
        results: [
            { chunk_id: "mock-001", source: "test_novel.txt", content: "话说林黛玉自从来到荣国府，步步留心，时时在意，不肯轻易多说一句话...", score: 0.85, metadata: { chunk_index: 0, total_chunks: 2 } },
            { chunk_id: "mock-002", source: "test_novel.txt", content: "宝玉笑道：我送妹妹一妙字，莫若颦颦二字极妙...", score: 0.72, metadata: { chunk_index: 1, total_chunks: 2 } }
        ],
        total: 2
    }
};

const MOCK_SEARCH_EMPTY = {
    code: 200, message: "success",
    data: { results: [], total: 0 }
};

/** 模拟延迟 */
const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

/**
 * 创建知识库模块
 * @returns {Object} - 知识库模块的状态和方法
 */
export function createRagModule() {
    // ===================================
    // 状态定义
    // ===================================

    // 上传流程
    const selectedFile = ref(null);
    const uploadResult = ref(null);
    const previewChunks = ref([]);
    const confirmResult = ref(null);

    // 入库设置
    const vectorModels = ref(['text-embedding-v3', 'text-embedding-v4']);
    const selectedModel = ref('text-embedding-v3');
    const chunkSize = ref(500);
    const chunkOverlap = ref(100);

    // 搜索
    const searchQuery = ref('');
    const searchResults = ref([]);
    const searchTotal = ref(0);

    // 通用
    const ragLoading = ref(false);
    const useMock = ref(false);

    const hasSearched = ref(false);

    // ===================================
    // 方法定义
    // ===================================

    /**
     * 选择文件后校验并存储
     */
    function onFileSelected(file) {
        if (!file) return;
        if (!file.name.endsWith('.txt')) {
            ElMessage.warning('仅支持 .txt 文件');
            return;
        }
        if (file.size > 10 * 1024 * 1024) {
            ElMessage.warning('文件大小超过 10MB 限制');
            return;
        }
        selectedFile.value = file;
    }

    /**
     * 上传预览（mock 版）
     */
    async function doUpload() {
        if (!selectedFile.value) {
            ElMessage.warning('请先选择文件');
            return;
        }
        ragLoading.value = true;
        try {
            if (useMock.value) {
                await delay(800);
                const res = MOCK_UPLOAD;
                uploadResult.value = res.data;
                previewChunks.value = res.data.preview || [];
            } else {
                const formData = new FormData();
                formData.append('file', selectedFile.value);
                const res = await axios.post('/rag/upload', formData);
                uploadResult.value = res.data.data;
                previewChunks.value = res.data.data.preview || [];
            }
        } catch (err) {
            ElMessage.error(err.response?.data?.detail || '上传预览失败，请稍后重试');
        } finally {
            ragLoading.value = false;
        }
    }

    /**
     * 确认入库（mock 版）
     */
    async function doConfirm() {
        if (!uploadResult.value) {
            ElMessage.warning('请先上传预览');
            return;
        }
        ragLoading.value = true;
        try {
            if (useMock.value) {
                await delay(800);
                confirmResult.value = MOCK_CONFIRM.data;
            } else {
                const res = await axios.post('/rag/confirm', {
                    filename: uploadResult.value.filename,
                    chunk_size: chunkSize.value,
                    chunk_overlap: chunkOverlap.value,
                    model: selectedModel.value
                });
                confirmResult.value = res.data.data;
            }
        } catch (err) {
            ElMessage.error(err.response?.data?.detail || '入库失败，请稍后重试');
        } finally {
            ragLoading.value = false;
        }
    }

    /**
     * 搜索知识库（mock 版）
     */
    async function doSearch() {
        const query = searchQuery.value.trim();
        hasSearched.value = true;
        ragLoading.value = true;
        try {
            if (useMock.value) {
                await delay(800);
                const res = query ? MOCK_SEARCH : MOCK_SEARCH_EMPTY;
                searchResults.value = res.data.results;
                searchTotal.value = res.data.total;
            } else if (!query) {
                // 后端搜索要求 query 至少 1 字符，空 query 直接返回空
                searchResults.value = [];
                searchTotal.value = 0;
            } else {
                const res = await axios.post('/rag/search', {
                    query: query,
                    top_k: 5
                });
                searchResults.value = res.data.data.results;
                searchTotal.value = res.data.data.total;
            }
        } catch (err) {
            ElMessage.error(err.response?.data?.detail || '搜索失败，请稍后重试');
        } finally {
            ragLoading.value = false;
        }
    }

    /**
     * 重置上传相关状态
     */
    function resetUpload() {
        selectedFile.value = null;
        uploadResult.value = null;
        previewChunks.value = [];
        confirmResult.value = null;
    }

    /**
     * 匹配度分数转百分比显示（模板中无法使用 Math）
     */
    function formatScore(score) {
        return Math.round(score * 100);
    }

    // ===================================
    // 返回导出
    // ===================================
    return {
        // 上传
        selectedFile, uploadResult, previewChunks, confirmResult,
        // 入库设置
        vectorModels, selectedModel, chunkSize, chunkOverlap,
        // 搜索
        searchQuery, searchResults, searchTotal, hasSearched,
        // 通用
        ragLoading, useMock,
        // 方法
        onFileSelected, doUpload, doConfirm, doSearch, resetUpload, formatScore,
    };
}
