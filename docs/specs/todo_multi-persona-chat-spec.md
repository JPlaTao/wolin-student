# P3 — 趣味聊天多角色扩展

> 状态: 待实现 | 优先级: P3 | 预估工时: ~2-3 h

---

## 一、目标

在现有"林黛玉 Agent"的基础上，扩展为多角色聊天平台。学生可以选择不同角色模板进行对话。

## 二、核心设计

### 2.1 角色模板机制

林黛玉 Agent 的架构（`api/lin_daiyu_agent.py` → `services/lin_daiyu_service.py`）已经是一个可复用的模板。唯一变化的是 **System Prompt**。

**扩展方案**：一个通用 Agent 路由 + 角色配置字典。

```python
# services/persona_service.py
PERSONAS = {
    "daiyu": {  # 已有
        "name": "林黛玉",
        "system_prompt": "<林黛玉人设提示词>",
        "temperature": 0.85,
        "greeting": "这位小友好。我是颦儿...",
        "icon": "fa-feather-alt",
        "theme": "purple",
    },
    "wukong": {  # 新增
        "name": "孙悟空",
        "system_prompt": "你是齐天大圣孙悟空...",
        "temperature": 0.9,
        "greeting": "俺老孙来也！...",
        "icon": "fa-cloud",
        "theme": "gold",
    },
    "interviewer": {  # 新增
        "name": "面试官",
        "system_prompt": "你是一家知名企业的面试官...",
        "temperature": 0.6,
        "greeting": "你好，请先做个自我介绍。",
        "icon": "fa-briefcase",
        "theme": "blue",
    },
}
```

### 2.2 API 改动

```
api/persona_api.py                  ← 通用角色 API (替代 daiyu 独有路由)
       │
       ├─ GET /persona/list         ← 返回可用角色列表
       ├─ POST /persona/{id}/chat   ← 非流式对话
       └─ POST /persona/{id}/stream ← SSE 流式对话
```

### 2.3 前端

- 保留林黛玉 Tab（不破坏现有体验）
- 黛玉 Tab 顶部加角色选择器（下拉/横向卡片）
- 切换角色后：对话历史清空（不同角色独立会话）
- 每个角色有自己的主题色/聊天气泡颜色

## 三、动文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `services/persona_service.py` | 新建 | 角色配置 + 通用 LLM 对话 |
| `api/persona_api.py` | 新建 | 通用角色 API |
| `api/lin_daiyu_agent.py` | 标记废弃 | 重定向到 persona_api 或直接迁移 |
| `main.py` | 修改 | 注册 persona 路由 |
| `static/index.html` | 修改 | 黛玉 Tab 加角色选择器 |
| `static/js/modules/daiyu.js` | 修改 | 改为通用角色对话逻辑 |
| `static/css/style.css` | 修改 | 多角色主题样式 |

## 四、约束

1. **不复用 query_agent 的 conversation 表** — 角色对话用 `ldy_` 前缀的 session_id
2. **不改 config.json**
3. **向后兼容** — 现有黛玉 Tab 不能 break
4. **角色 System Prompt 写在代码里** — 暂时不抽成外部文件（与黛玉 agent 一致）

## 五、暂不处理

- 英语陪练角色（需专门的语音/纠错 prompt，设计复杂）
- 角色自定义（用户自己写 prompt）
- 角色对话历史管理（当前无删除历史功能）

## 六、验证方法

1. 启动服务，登录任意角色
2. 点击"黛玉智能"Tab → 看到林黛玉角色已选中（默认）
3. 切换到"孙悟空" → 确认问候语和对话风格变化
4. 切换到"面试官" → 确认面试类对话
5. 切换角色后 → 确认对话历史清空（独立会话）
