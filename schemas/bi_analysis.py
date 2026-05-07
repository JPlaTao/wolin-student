"""
BI 结构化分析输出 Schema
为对话式 BI 提供类型安全的结构化分析结果，前端可直接消费
"""

from pydantic import BaseModel, Field


class ChartSuggestion(BaseModel):
    """图表建议"""
    type: str = Field(description="图表类型: bar / line / pie / scatter / table")
    title: str = Field(description="图表标题，不超过15字", max_length=15)
    reason: str = Field(description="为什么推荐这个图表类型，给 Agent 内部分析用")


class AnalysisOutput(BaseModel):
    """结构化分析输出 — LLM 分析 Tool 的返回类型"""
    summary: str = Field(description="自然语言分析总结，2-4 句话，面向最终用户")
    chart_suggestion: ChartSuggestion | None = Field(
        default=None,
        description="如果数据适合可视化，给出图表建议；纯文本数据则留空"
    )
    key_findings: list[str] = Field(description="关键发现列表，每条一句话")
    statistics: dict = Field(
        default_factory=dict,
        description="关键统计数据，如 {avg: 78.5, max: 98, min: 42, trend: '下降'}"
    )
