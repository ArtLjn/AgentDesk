"""工单审核 Agent：检查处理结果质量，返回 0-1 评分。"""

import json
import os

from loguru import logger
from openai import AsyncOpenAI

from src.multi_agent_system.config import Settings

__all__ = ["ReviewerAgent"]

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
        self._client: AsyncOpenAI | None = None

    @property
    def client(self) -> AsyncOpenAI:
        """延迟初始化 OpenAI 异步客户端。"""
        if self._client is None:
            settings = Settings()
            self._client = AsyncOpenAI(
                api_key=self._api_key or os.getenv("OPENAI_API_KEY", "ollama"),
                base_url=self._base_url or f"{settings.ollama_base_url}/v1",
            )
        return self._client

    async def review(
        self,
        content: str,
        processing_result: str,
        category: str,
    ) -> dict:
        """审核处理结果，返回评分和反馈。

        Args:
            content: 原始工单内容
            processing_result: 处理结果文本
            category: 工单分类

        Returns:
            包含 score（0-1）和 feedback 的字典
        """
        try:
            return await self._review_by_llm(content, processing_result, category)
        except Exception as e:
            logger.warning(f"LLM 审核失败，使用降级评分: {e}")
            return self._fallback_review()

    async def _review_by_llm(
        self,
        content: str,
        processing_result: str,
        category: str,
    ) -> dict:
        """通过 LLM 进行质量审核。

        Args:
            content: 原始工单内容
            processing_result: 处理结果文本
            category: 工单分类

        Returns:
            审核结果字典

        Raises:
            ValueError: LLM 返回的 JSON 格式无效时抛出
        """
        system_prompt = _REVIEWER_SYSTEM_PROMPT.format(
            content=content,
            category=category,
            processing_result=processing_result,
        )

        response = await self.client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "请对以上处理结果进行评分"},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content or "{}"
        result = json.loads(raw)

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
            base_url=f"{settings.ollama_base_url}/v1",
        )
