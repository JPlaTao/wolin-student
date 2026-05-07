# 会话隔离 + 心理状态追踪 + 预警邮件

> 状态: 待实现 | 优先级: P2 | 预估工时: ~5-7 h

---

## 一、目标

1. **会话隔离** — 每条对话会话（session）的记忆完全独立
2. **状态摘要** — 每次会话结束时，自动抽取 1-2 条用户状态/偏好摘要
3. **心理预警** — 监测学生在黛玉聊天中的情绪状态，发现风险迹象时自动给班主任发邮件

## 二、当前状态分析

### 2.1 已有会话机制

黛玉 Agent 已通过 `services/lin_daiyu_service.py` 使用 `ConversationMemory` 表做多轮对话记忆：

- `session_id = f"ldy_{user_id}"` — 每个用户只有一个会话
- 取最近 10 轮历史拼接成 context
- 无会话分离、无摘要、无风险检测

### 2.2 现有基础设施可复用

| 能力 | 位置 | 状态 |
|------|------|------|
| 会话存储 | `model/conversation.py` → `ConversationMemory` | 已有 |
| 邮件发送 | `services/email_service.py` | 已有 |
| 班主任查询 | `dao/teacher_dao.py` + `class_model.py` | 已有 |
| JWT 用户信息 | `core/auth.py` → `get_current_user` | 已有 |

## 三、设计方案

### 3.1 会话隔离

将现有的 `ldy_{user_id}` 单会话改为 `ldy_{user_id}_{session_uid}` 多会话：

```
ConversationMemory 表结构（无需改动）:
  session_id: "ldy_42_a1b2c3d4"   ← 用户42的第1个会话
  session_id: "ldy_42_e5f6g7h8"   ← 用户42的第2个会话
```

**前端行为：**
- 黛玉聊天面板顶部增加"新建会话"按钮
- 左侧增加会话列表（按时间倒序，标题取首条用户消息前20字）
- 切换会话 → 加载对应历史
- 删除会话 → 软删除（`is_deleted = True`）

### 3.2 会话摘要提取

每次会话结束（用户主动点"结束"或超过 30 分钟无新消息）时触发：

```
输入: 该会话的完整对话历史 (~10-20 轮)
LLM: 使用低温度(0.3) + 结构化输出 prompt
输出:
  {
    "mood": "积极 / 中性 / 低落 — 一句话描述",
    "topics": ["诗词", "考试焦虑", "同学关系"],
    "risk_flags": [],
    "preferences": "该生偏好文学类话题"
  }
```

摘要存储在 `ConversationMemory` 表的一个新字段 `summary`（JSON TEXT）或单独的 `session_summaries` 表中。

**触发时机（非实时）：**
- 用户点击"结束会话"
- 会话闲置超过 30 分钟后，下次打开时后台异步生成

### 3.3 心理风险检测

**两层机制：**

**第1层 — 关键词/规则（快速，无 LLM 成本）：**
```python
RISK_KEYWORDS = [
    "不想活", "自杀", "死了算了", "活着没意思",
    "自残", "割腕", "跳楼", "安眠药",
    "没人关心", "被孤立", "被欺负", "天天哭",
]
```

命中任一词 → 该会话标记 `risk_level = "high"`，触发邮件。

**第2层 — LLM 分类（定期批量分析，更准确）：**
- 每小时/每天跑一次 cron 风格的批处理
- 输入：该用户所有未评估过的新会话摘要
- LLM prompt：判断是否有抑郁/焦虑/自伤倾向
- 输出：风险等级 `none / low / medium / high`

**风险追踪表（新建）：**

```sql
CREATE TABLE student_risk_tracking (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    session_id VARCHAR(128),
    risk_level ENUM('none', 'low', 'medium', 'high') DEFAULT 'none',
    summary TEXT,                -- LLM 分析摘要
    keywords_matched TEXT,       -- 命中的关键词
    alert_sent BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_time (user_id, created_at)
);
```

### 3.4 预警邮件

**触发条件：**
- 单次会话命中高风险关键词
- 或累计 3 次 `medium` 风险等级

**收件人：** 该学生的班主任（`headteacher`）

**查询链路：**
```
student_user.stu_id → StuBasicInfo.class_id → Class.class_teacher[role=headteacher] → Teacher.email
```

**邮件内容：**

```
主题：[沃林系统] 学生心理健康关注提醒

尊敬的 {班主任姓名} 老师：

系统检测到您班级的学生 {学生姓名} 近期在平台交流中表现出一些值得关注的情绪迹象。

【风险等级】{高/中}
【涉及方面】{情绪低落 / 社交困扰 / 学业焦虑 / ...}
【建议】建议您近期主动与{学生姓名}进行一次非正式交流，了解其近况。

*此邮件由系统自动生成，仅作为辅助提醒，不代表确定结论。*

沃林学生管理系统
```

**防骚扰机制：**
- 同一学生 7 天内最多发 1 封预警邮件
- 同一班主任 24 小时内最多收 3 封预警邮件

### 3.5 数据流架构

```
用户聊天消息
  ├─ 存入 ConversationMemory (session_id 隔离)
  │
  ├─ [实时] 关键词扫描 ──→ 命中 high → 立即触发邮件
  │
  └─ [异步] 会话结束后
       ├─ LLM 摘要生成 → 存 summary
       └─ LLM 风险分类 → 存 student_risk_tracking
            └─ 累计阈值触发 → 发送预警邮件
```

## 四、改动文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `model/student_risk_tracking.py` | 新建 | 风险追踪 ORM 模型 |
| `services/session_service.py` | 新建 | 会话管理：创建/切换/删除/摘要生成 |
| `services/psych_monitor.py` | 新建 | 关键词扫描 + LLM 风险评估 + 阈值判断 |
| `services/lin_daiyu_service.py` | 修改 | 发送消息后调用 psych_monitor 关键词扫描 |
| `api/chat_session_api.py` | 新建 | 会话 CRUD API（列表/切换/删除） |
| `api/lin_daiyu_agent.py` | 修改 | 可选：会话结束端点 |
| `dao/conversation_dao.py` | 修改 | 新增按 session_id 查询/删除方法 |
| `dao/teacher_dao.py` | 修改 | 新增"根据学生查班主任邮箱"方法 |
| `main.py` | 修改 | 注册新路由 + 创建新表 |
| `static/js/modules/daiyu.js` | 修改 | 加"新建会话"按钮 + 会话列表 |
| `static/index.html` | 修改 | 黛玉面板加会话管理 UI |
| `static/css/style.css` | 修改 | 会话列表样式 |

## 五、约束

1. **不能拖慢聊天响应** — 关键词扫描在内存在做（~1ms），LLM 分析全异步
2. **隐私边界** — 摘要和风险分析只对管理员/班主任可见，学生端无感知
3. **不误报** — 关键词匹配要精确（避免"我想死你了"触发"想死"）
4. **不依赖外部定时任务框架** — 用 FastAPI BackgroundTasks 或简单的 asyncio.create_task

## 六、暂不处理

- 班主任在系统内直接查看心理报告（需要新的 UI 页面）
- 学生自我情绪记录/心情打卡（需要新的产品设计）
- 危机干预自动化流程（需要人工介入兜底）
- 会话导出功能
- 跨角色的心理监测（目前只看黛玉聊天）

## 七、验证方法

1. 学生 A 登录 → 黛玉智能 → 创建 2 个会话 → 各自对话 → 切换会话确认历史独立
2. 学生 A 在会话中说"活不下去了" → 检查 `student_risk_tracking` 表有 high 记录
3. 确认班主任邮箱收到预警邮件
4. 同一学生 10 分钟内再发高危消息 → 确认不发重复邮件（7 天冷却）
5. 学生 B 发送"我想死你了我的好朋友" → 确认不触发预警（精确匹配）
