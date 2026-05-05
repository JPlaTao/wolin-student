# 前端代码重构方案

## Context

当前前端三大文件：
| 文件 | 行数 | 问题 |
|------|------|------|
| `static/index.html` | 1,319 | HTML 模板 + Vue 模板 + 主题脚本全部混在一个文件 |
| `static/js/app.js` | 1,455 | 所有功能写在一个 `setup()` 函数里，状态/方法/生命周期全部平铺 |
| `static/js/modules/*.js` | 多个 | 已定义 `export function createXxxModule()` 工厂函数，但**从未被加载或使用**（死代码） |
| `static/js/utils/*.js` | 多个 | 同样使用 `export` 但未被引用 |

核心矛盾：模块文件已存在但未被使用，app.js 在内部重复定义了同样的函数（如 `setAuthToken`, `scrollToBottom`, `renderMarkdown`, `getRoleText` 等）。

## 重构目标

1. **真正使用模块文件** — 用 `<script type="module">` 加载，通过 `import`/`export` 连接
2. **大幅缩减 app.js** — 将业务逻辑拆分到各模块，app.js 只保留状态编排和生命周期
3. **保持零构建** — 不引入 Vite/Webpack，纯浏览器原生 ES Modules，现有后端服务无需改动

## 方案

### 技术选型：ES Modules（原生）

- 用 `<script type="module">` 替代 `<script src="app.js">`
- 导出模块用 `export`，导入用 `import`
- 所有现代浏览器均支持，无需构建工具
- 与现有 CDN 依赖兼容（Vue/Element Plus/Axios/ECharts 仍通过全局变量调用）

### 文件结构

```
static/
├── index.html              ← 大幅精简：只剩 Vue 模板和 script type="module" 入口
├── css/
│   ├── style.css           ← 不变
│   └── themes.css          ← 不变
├── js/
│   ├── app.js              ← 精简至 ~200 行：只保留 setup() 编排 + import
│   ├── utils/
│   │   ├── api.js          ← 不变（ES module，已有 export）
│   │   └── markdown.js     ← 不变（ES module，已有 export）
│   └── modules/
│       ├── auth.js         ← 新增：登录/注册/登出逻辑（现有文件是死代码，需要重写）
│       ├── dashboard.js    ← 可用：已有 createDashboardModule，需接入
│       ├── chat.js         ← 可用：已有 createChatModule，需接入
│       ├── daiyu.js        ← 新增：黛玉智能逻辑（从 app.js 提取）
│       ├── statistics.js   ← 可用：已有 createStatisticsModule，需接入
│       ├── email.js        ← 新增：邮件模块（从 app.js 提取）
│       ├── imageGen.js     ← 可用：已有 createImageGenModule，需接入
│       └── management.js   ← 新增：数据管理编排（从 app.js 提取）
```

### 各模块拆分内容

| 模块 | 从 app.js 提取的内容 |
|------|---------------------|
| `app.js` | 导航状态 (activeTab/mgmtTab/sidebar)，认证令牌管理，生命周期编排，watch 监听 |
| `auth.js` | 登录/注册表单状态，submitAuth，logout，checkLogin，currentUser |
| `dashboard.js` | dashboard 状态，refreshDashboard（复用已有 createDashboardModule） |
| `chat.js` | chatMessages, sendQuestion, streamingState（复用已有 createChatModule） |
| `daiyu.js` | daiyuMessages, sendDaiyuQuestion, daiyuStreaming（从 app.js 提取） |
| `statistics.js` | 图表状态，renderAdvancedCharts（复用已有 createStatisticsModule） |
| `email.js` | emailForm, sendEmail, emailConfig（从 app.js 提取） |
| `imageGen.js` | imageForm, generateImage（复用已有 createImageGenModule） |
| `management.js` | 学生/班级/教师/成绩/就业的 CRUD 状态和方法（从 app.js 提取） |

### 实现步骤

**Step 1:** 改写 `index.html` — 移除底部 `<script src="app.js">`，改为 `<script type="module" src="js/app.js"></script>`，删除内联主题切换脚本（移到独立文件）

**Step 2:** 清洗模块文件 — 重新实现 `modules/auth.js`、`daiyu.js`、`email.js`、`management.js`，将 app.js 中的函数移入对应模块并用 `export` 导出

**Step 3:** 重写 `app.js` — 只保留：
- 共享状态（activeTab, sidebarCollapsed 等导航相关）
- `setup()` 函数：导入各模块的工厂函数 → 调用获取状态和方法 → return 所有绑定
- `onMounted` 生命周期编排
- `watch` 监听

**Step 4:** 清理重复代码 — 验证 utils 是否被正确 import，删除 app.js 内重复的工具函数（直接 import from utils）

**Step 5:** 验证功能完整性 — 逐个 Tab 测试

### 关键设计决策

1. **每个模块输出一个工厂函数**（延续已有模式）：`createXxxModule()` 返回 `{ ref1, ref2, method1, method2 }`
2. **app.js 做纯编排**：调用工厂函数 → 解构返回值 → 统一 return 给模板
3. **不改变后端 API 结构**：纯前端重构，接口不变
4. **Vue 模板保留在 index.html**：因为使用包含模板编译器的 Vue CDN 版本，在 DOM 中编译模板

### 涉及文件

| 文件 | 改动类型 |
|------|----------|
| `static/index.html` | 修改 — 替换 script 加载方式，移除内联脚本 |
| `static/js/app.js` | 重写 — 大幅精简 |
| `static/js/modules/auth.js` | 重写 — 接入真实逻辑 |
| `static/js/modules/daiyu.js` | 新增 — 从 app.js 提取 |
| `static/js/modules/email.js` | 新增 — 从 app.js 提取 |
| `static/js/modules/management.js` | 新增 — 从 app.js 提取 |
| `static/js/modules/dashboard.js` | 无需改动（已有实现） |
| `static/js/modules/chat.js` | 无需改动（已有实现） |
| `static/js/modules/statistics.js` | 无需改动（已有实现） |
| `static/js/modules/imageGen.js` | 无需改动（已有实现） |
| `static/js/utils/api.js` | 无需改动 |
| `static/js/utils/markdown.js` | 无需改动 |

### 验证方法

1. 启动服务，访问页面，确认所有功能 Tab 可正常切换
2. 测试登录/注册/登出
3. 逐个测试每个 Tab：
   - 数据看板（图表渲染）
   - 智能问答（消息发送与显示）
   - 黛玉智能（流式对话）
   - 高级统计（图表）
   - 文生图（图片生成与展示）
   - 发送邮件（表单与发送）
   - 数据管理（CRUD 操作）
   - 用户管理（管理员）
4. 检查浏览器控制台无 `import`/`export` 相关错误
5. 确认主题切换功能正常
