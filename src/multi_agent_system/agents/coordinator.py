"""Supervisor 协调 Agent：全局协调 + 异常兜底。"""

import json
from typing import TYPE_CHECKING

from openai import APIConnectionError, APIError, AsyncOpenAI, AuthenticationError, RateLimitError

from src.multi_agent_system.config import Settings
from src.multi_agent_system.core import fallback_registry, with_retry
from src.multi_agent_system.core.exceptions import NonRetryableError, RetryableError

if TYPE_CHECKING:
    from src.multi_agent_system.tools.knowledge_search import KnowledgeSearchTool
    from src.multi_agent_system.tools.notification import NotificationTool

__all__ = ["CoordinatorAgent"]

# 升级提示词
_ESCALATE_PROMPT = """\
工单 {ticket_id} 需要升级到人工处理。
升级原因：{reason}
请生成一份简洁的升级说明，包含问题摘要和建议处理方向。

严格按以下 JSON 格式输出：
{{"escalation_summary": "问题摘要", "suggested_action": "建议处理方向", "assigned_team": "建议分配团队"}}\
"""

# 失败处理提示词
_FAILURE_PROMPT = """\
工单 {ticket_id} 处理失败。
错误信息：{error}
请生成一份失败分析报告。

严格按以下 JSON 格式输出：
{{"failure_analysis": "失败原因分析", "recovery_suggestion": "恢复建议", "requires_manual_review": true/false}}\
"""

# 报告生成提示词
_REPORT_PROMPT = """\
你是工单处理系统的协调员。请根据以下工单数据生成一份处理报告摘要。

工单数据：
{tickets_data}

报告要求：
1. 工单总数和分类统计
2. 平均处理评分
3. 失败工单占比
4. 改进建议

请用简洁的中文输出报告。\
"""


class CoordinatorAgent:
    """Supervisor 协调 Agent：全局协调 + 异常兜底。

    负责工单升级、失败处理和报告生成等全局协调工作。

    Args:
        model: 模型名称
        notification_tool: 通知发送工具
        knowledge_tool: 知识库检索工具
        api_key: API 密钥
        base_url: API 基础地址
    """

    def __init__(
        self,
        model: str,
        notification_tool: "NotificationTool",
        knowledge_tool: "KnowledgeSearchTool",
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._model = model
        self._notification_tool = notification_tool
        self._knowledge_tool = knowledge_tool
        self._api_key = api_key
        self._base_url = base_url
        self._client: AsyncOpenAI | None = None

    @property
    def client(self) -> AsyncOpenAI:
        """延迟初始化 OpenAI 异步客户端。"""
        if self._client is None:
            settings = Settings()
            self._client = AsyncOpenAI(
                api_key=self._api_key or settings.llm_api_key,
                base_url=self._base_url or settings.llm_base_url,
            )
        return self._client

    async def escalate(self, ticket_id: str, reason: str) -> dict:
        """升级工单到人工处理。

        重试和降级由 @with_retry 装饰器统一处理。

        Args:
            ticket_id: 工单 ID
            reason: 升级原因

        Returns:
            升级信息字典，包含摘要、建议和分配团队
        """
        result = await self._escalate_by_llm(ticket_id, reason)

        # 发送升级通知
        self._notification_tool.send(
            ticket_id=ticket_id,
            message=f"工单升级：{result.get('escalation_summary', reason)}",
            channel="email",
        )

        return result

    @with_retry(
        max_retries=3,
        backoff_base=2.0,
        retryable_exceptions=(APIError, APIConnectionError, RateLimitError, RetryableError),
        fallback=lambda self, ticket_id, reason: fallback_registry.execute(
            "coordinator.escalate", ticket_id, reason
        ),
    )
    async def _escalate_by_llm(self, ticket_id: str, reason: str) -> dict:
        """通过 LLM 生成升级分析。

        由 @with_retry 装饰器统一处理重试和降级逻辑。

        Args:
            ticket_id: 工单 ID
            reason: 升级原因

        Returns:
            升级分析结果字典

        Raises:
            RetryableError: OpenAI API 可重试错误
            NonRetryableError: 认证失败或 JSON 解析失败
        """
        prompt = _ESCALATE_PROMPT.format(ticket_id=ticket_id, reason=reason)

        try:
            response = await self.client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"请分析工单 {ticket_id} 的升级需求"},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
        except AuthenticationError as e:
            raise NonRetryableError(f"API 认证失败: {e}", cause=e)
        except (APIError, APIConnectionError, RateLimitError) as e:
            raise RetryableError(f"API 调用失败: {e}", cause=e)

        raw = response.choices[0].message.content or "{}"

        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise NonRetryableError(f"LLM 返回非法 JSON: {e}", cause=e)

    @staticmethod
    def _fallback_escalate(ticket_id: str, reason: str) -> dict:
        """升级分析降级方案。

        Args:
            ticket_id: 工单 ID
            reason: 升级原因

        Returns:
            降级升级信息字典
        """
        return {
            "escalation_summary": f"工单 {ticket_id} 升级处理：{reason}",
            "suggested_action": "人工介入审核处理",
            "assigned_team": "客服团队",
        }

    async def handle_failure(self, ticket_id: str, error: str) -> dict:
        """处理失败的工单。

        重试和降级由 @with_retry 装饰器统一处理。

        Args:
            ticket_id: 工单 ID
            error: 错误信息

        Returns:
            失败分析字典，包含原因分析、恢复建议等
        """
        result = await self._analyze_failure_by_llm(ticket_id, error)

        # 发送失败通知
        self._notification_tool.send(
            ticket_id=ticket_id,
            message=f"工单处理失败：{result.get('failure_analysis', error)}",
            channel="email",
        )

        return result

    @with_retry(
        max_retries=3,
        backoff_base=2.0,
        retryable_exceptions=(APIError, APIConnectionError, RateLimitError, RetryableError),
        fallback=lambda self, ticket_id, error: fallback_registry.execute(
            "coordinator.handle_failure", ticket_id, error
        ),
    )
    async def _analyze_failure_by_llm(self, ticket_id: str, error: str) -> dict:
        """通过 LLM 分析失败原因。

        由 @with_retry 装饰器统一处理重试和降级逻辑。

        Args:
            ticket_id: 工单 ID
            error: 错误信息

        Returns:
            失败分析结果字典

        Raises:
            RetryableError: OpenAI API 可重试错误
            NonRetryableError: 认证失败或 JSON 解析失败
        """
        prompt = _FAILURE_PROMPT.format(ticket_id=ticket_id, error=error)

        try:
            response = await self.client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"请分析工单 {ticket_id} 的失败原因"},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
        except AuthenticationError as e:
            raise NonRetryableError(f"API 认证失败: {e}", cause=e)
        except (APIError, APIConnectionError, RateLimitError) as e:
            raise RetryableError(f"API 调用失败: {e}", cause=e)

        raw = response.choices[0].message.content or "{}"

        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise NonRetryableError(f"LLM 返回非法 JSON: {e}", cause=e)

    @staticmethod
    def _fallback_failure(ticket_id: str, error: str) -> dict:
        """失败分析降级方案。

        Args:
            ticket_id: 工单 ID
            error: 错误信息

        Returns:
            降级失败分析字典
        """
        return {
            "failure_analysis": f"工单 {ticket_id} 处理失败：{error}",
            "recovery_suggestion": "建议人工介入检查",
            "requires_manual_review": True,
        }

    async def generate_report(self, tickets: list[dict]) -> str:
        """生成工单处理报告。

        重试和降级由 @with_retry 装饰器统一处理。

        Args:
            tickets: 工单列表，每个工单为字典格式

        Returns:
            报告文本
        """
        if not tickets:
            return "无工单数据，无法生成报告。"

        return await self._generate_report_by_llm(tickets)

    @with_retry(
        max_retries=3,
        backoff_base=2.0,
        retryable_exceptions=(APIError, APIConnectionError, RateLimitError, RetryableError),
        fallback=lambda self, tickets: fallback_registry.execute(
            "coordinator.generate_report", tickets
        ),
    )
    async def _generate_report_by_llm(self, tickets: list[dict]) -> str:
        """通过 LLM 生成处理报告。

        由 @with_retry 装饰器统一处理重试和降级逻辑。

        Args:
            tickets: 工单列表

        Returns:
            报告文本

        Raises:
            RetryableError: OpenAI API 可重试错误
            NonRetryableError: 认证失败
        """
        tickets_data = json.dumps(tickets, ensure_ascii=False, indent=2)
        prompt = _REPORT_PROMPT.format(tickets_data=tickets_data)

        try:
            response = await self.client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": "请生成工单处理报告"},
                ],
                temperature=0.3,
            )
        except AuthenticationError as e:
            raise NonRetryableError(f"API 认证失败: {e}", cause=e)
        except (APIError, APIConnectionError, RateLimitError) as e:
            raise RetryableError(f"API 调用失败: {e}", cause=e)

        return response.choices[0].message.content or "报告生成失败"

    @staticmethod
    def _fallback_report(tickets: list[dict]) -> str:
        """报告生成降级方案。

        Args:
            tickets: 工单列表

        Returns:
            基础统计报告文本
        """
        total = len(tickets)
        categories: dict[str, int] = {}
        scores: list[float] = []
        failed = 0

        for ticket in tickets:
            cat = ticket.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1

            score = ticket.get("review_score")
            if score is not None:
                scores.append(float(score))

            status = ticket.get("status", "")
            if status == "failed":
                failed += 1

        cat_stats = ", ".join(f"{k}: {v}" for k, v in categories.items())
        avg_score = sum(scores) / len(scores) if scores else 0.0
        fail_rate = (failed / total * 100) if total > 0 else 0.0

        return (
            f"工单处理报告\n"
            f"总计: {total} 条\n"
            f"分类统计: {cat_stats}\n"
            f"平均评分: {avg_score:.2f}\n"
            f"失败率: {fail_rate:.1f}%\n"
        )

    @staticmethod
    def create_from_settings(
        notification_tool: "NotificationTool | None" = None,
        knowledge_tool: "KnowledgeSearchTool | None" = None,
    ) -> "CoordinatorAgent":
        """从 Settings 创建 CoordinatorAgent 实例。

        Args:
            notification_tool: 通知工具，不传时自动创建
            knowledge_tool: 知识库工具，不传时自动创建

        Returns:
            配置好的 CoordinatorAgent 实例
        """
        from src.multi_agent_system.tools.knowledge_search import KnowledgeSearchTool
        from src.multi_agent_system.tools.notification import NotificationTool

        settings = Settings()
        if notification_tool is None:
            notification_tool = NotificationTool()
        if knowledge_tool is None:
            knowledge_tool = KnowledgeSearchTool.create_from_settings()

        return CoordinatorAgent(
            model=settings.llm_model,
            notification_tool=notification_tool,
            knowledge_tool=knowledge_tool,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )


# 模块级降级注册
fallback_registry.register("coordinator.escalate", CoordinatorAgent._fallback_escalate)
fallback_registry.register("coordinator.handle_failure", CoordinatorAgent._fallback_failure)
fallback_registry.register("coordinator.generate_report", CoordinatorAgent._fallback_report)
