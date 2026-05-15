"""工单审核 Agent：检查处理结果质量，返回 0-1 评分。"""

import json
import re

from loguru import logger
from openai import APIConnectionError, APIError, AuthenticationError, RateLimitError

from src.multi_agent_system.config import Settings
from src.multi_agent_system.core import CachedLLMClient, fallback_registry, with_retry
from src.multi_agent_system.core.exceptions import NonRetryableError, RetryableError

__all__ = ["ReviewerAgent"]


def _parse_json_response(raw: str) -> dict:
    """从 LLM 响应中提取 JSON，兼容 markdown 代码块包裹。"""
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
    if match:
        return json.loads(match.group(1).strip())
    return json.loads(raw)

# 审核提示词
_REVIEWER_SYSTEM_PROMPT = """\
你是一个工单处理质量审核专家。请根据以下信息对处理结果进行评分。

原始工单内容：{content}
工单分类：{category}
处理结果：{processing_result}

评审标准：
1. 准确性（0-0.3）：处理结果是否准确回答了工单中的问题
2. 可行性（0-0.3）：解决方案是否切实可行、步骤清晰
3. 完整性（0-0.2）：是否覆盖了工单中提到的所有要点
4. 专业性（0-0.2）：语言是否清晰、专业、无歧义

请综合以上维度给出总分（0-1），并提供改进反馈。
严格按以下 JSON 格式输出，不要添加任何额外内容：
{{"score": 0.85, "feedback": "评分理由和改进建议"}}\
"""


class ReviewerAgent:
    """工单审核 Agent：检查处理结果质量，返回 0-1 评分。

    通过 LLM 从准确性、可行性、完整性和专业性四个维度
    评估工单处理结果的质量。

    Args:
        model: 模型名称
        api_key: API 密钥
        base_url: API 基础地址
    """

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._model = model
        self._api_key = api_key
        self._base_url = base_url
        self._client: CachedLLMClient | None = None

    @property
    def client(self) -> CachedLLMClient:
        """延迟初始化带缓存的 LLM 客户端。"""
        if self._client is None:
            settings = Settings()
            self._client = CachedLLMClient(
                api_key=self._api_key or settings.llm_api_key,
                base_url=self._base_url or settings.llm_base_url,
                model=self._model,
            )
        return self._client

    async def review(
        self,
        content: str,
        processing_result: str,
        category: str,
    ) -> dict:
        """审核处理结果，返回评分和反馈。

        重试和降级由 @with_retry 装饰器统一处理。

        Args:
            content: 原始工单内容
            processing_result: 处理结果文本
            category: 工单分类

        Returns:
            包含 score（0-1）和 feedback 的字典
        """
        return await self._review_by_llm(content, processing_result, category)

    @with_retry(
        max_retries=3,
        backoff_base=2.0,
        retryable_exceptions=(APIError, APIConnectionError, RateLimitError, RetryableError),
        fallback=lambda self, content, processing_result, category: fallback_registry.execute(
            "reviewer.review"
        ),
    )
    async def _review_by_llm(
        self,
        content: str,
        processing_result: str,
        category: str,
    ) -> dict:
        """通过 LLM 进行质量审核。

        由 @with_retry 装饰器统一处理重试和降级逻辑。

        Args:
            content: 原始工单内容
            processing_result: 处理结果文本
            category: 工单分类

        Returns:
            审核结果字典

        Raises:
            RetryableError: OpenAI API 可重试错误
            NonRetryableError: 认证失败或 JSON 解析失败
        """
        system_prompt = _REVIEWER_SYSTEM_PROMPT.format(
            content=content,
            category=category,
            processing_result=processing_result,
        )

        logger.info(f"[Reviewer] 调用 LLM 模型: {self._model}")
        logger.debug(f"[Reviewer] 审核内容:\n工单: {content}\n结果: {processing_result}")

        try:
            response = await self.client.chat_completions_create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "请对以上处理结果进行评分"},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
        except AuthenticationError as e:
            raise NonRetryableError(f"API 认证失败: {e}", cause=e)
        except (APIError, APIConnectionError, RateLimitError) as e:
            raise RetryableError(f"API 调用失败: {e}", cause=e)

        raw = response.choices[0].message.content or "{}"
        logger.info(f"[Reviewer] LLM 响应: {raw}")

        try:
            result = _parse_json_response(raw)
        except json.JSONDecodeError as e:
            raise NonRetryableError(f"LLM 返回非法 JSON: {e}", cause=e)

        score = float(result.get("score", 0.7))
        # 确保 score 在 0-1 范围内
        score = max(0.0, min(1.0, score))

        return {
            "score": score,
            "feedback": result.get("feedback", ""),
        }

    @staticmethod
    def _fallback_review() -> dict:
        """LLM 调用失败时的降级审核。

        Returns:
            默认审核结果字典
        """
        return {
            "score": 0.7,
            "feedback": "LLM 审核不可用，使用默认评分",
        }

    @staticmethod
    def create_from_settings() -> "ReviewerAgent":
        """从 Settings 创建 ReviewerAgent 实例。

        Returns:
            配置好的 ReviewerAgent 实例
        """
        settings = Settings()
        return ReviewerAgent(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )


# 模块级降级注册
fallback_registry.register("reviewer.review", ReviewerAgent._fallback_review)
