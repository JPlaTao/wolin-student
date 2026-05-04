# TODO

## P1 — 开发环境整理

_梳理这台机器的 Python 依赖环境，搞清楚哪些东西装在哪里、怎么管理的。_

- [ ] 搞清楚 `.venv` vs Anaconda 全局环境的关系
  - 项目用的是 `.venv` 还是 Anaconda？
  - 之前的依赖安装是否分散在两个环境中？
  - 有没有重复/冲突的包？
- [ ] 检查 pip 和 `python -m pip` 的行为差异（`.venv/Scripts/pip` 有 shebang 问题）
- [ ] 明确后续开发的标准操作流程: 用 `.venv/Scripts/python -m pip` 还是 `pip`？
- [ ] 清理不必要的全局包，避免污染

## P1 — docs/ 目录整理

_docs/ 下文件越来越多，spec、handoff、技术文档混在一起。_

- [ ] 建立子目录结构（建议）:
  - `docs/specs/` — 方向 A/B 等开发规格文档
  - `docs/handoffs/` — 项目交接文档
  - `docs/arch/` — 架构/设计文档
- [ ] 将现有文件归类移入对应子目录
- [ ] 更新 CLAUDE.md 中涉及 docs/ 路径的引用（如果有）
- [ ] 保留 `docs/README.md` 简要说明各子目录用途

## P2 — 日志系统重构

_评估并重构项目日志，使其更可读、统一、实用。_

- [ ] 评估现有日志的问题:
  - 终端输出无颜色，难以区分等级（INFO/WARN/ERROR）
  - 多模块日志格式不一致（`query_agent`、`middleware`、`api_logger` 等各有各的格式）
  - 敏感信息审计日志混杂在普通日志中
- [ ] 设计新的日志格式规范（建议: 时间 | 级别 | 模块 | 消息）
- [ ] 引入 `rich` 或 `colorlog` 做彩色终端输出
- [ ] 统一所有 logger 初始化方式，消除重复配置
- [ ] 必要时分离审计日志文件

## 后续

- [ ] 前端模型切换功能：如何在前端/后端层面支持用户切换 LLM 模型（Kimi ↔ DeepSeek ↔ OpenAI），不依赖改配置文件
