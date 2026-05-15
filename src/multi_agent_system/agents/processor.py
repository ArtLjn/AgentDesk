"""工单处理 Agent：检索知识库并生成解决方案。"""

import json
import re
from typing import TYPE_CHECKING

from loguru import logger
from openai import APIConnectionError, APIError, AuthenticationError, RateLimitError

from src.multi_agent_system.config import Settings
from src.multi_agent_system.core import CachedLLMClient, fallback_registry, with_retry
from src.multi_agent_system.core.exceptions import NonRetryableError, RetryableError
from src.multi_agent_system.models.ticket import TicketCategory

if TYPE_CHECKING:
    from src.multi_agent_system.tools.knowledge_search import KnowledgeSearchTool

__all__ = ["ProcessorAgent"]


def _parse_json_response(raw: str) -> dict:
    """从 LLM 响应中提取 JSON，兼容 markdown 代码块包裹。"""
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
    if match:
        return json.loads(match.group(1).strip())
    return json.loads(raw)

# 处理提示词模板
_PROCESSOR_SYSTEM_PROMPT = """\
你是一个专业的工单处理专家。请根据以下信息生成解决方案：

工单内容：{content}
工单分类：{category}
优先级：{priority}
{context_section}

要求：
1. 分析问题根因
2. 给出明确的解决步骤
3. 如果有参考资料，结合参考内容回答
4. 语言简洁专业

请严格按照以下 JSON 格式输出，不要添加任何额外内容：
{{"result": "解决方案的详细描述", "references": ["参考来源1", "参考来源2"]}}\
"""


class ProcessorAgent:
    """工单处理 Agent：查资料 + 生成解决方案。

    先通过知识库检索工具获取相关资料，再将检索结果作为上下文
    让 LLM 生成解决方案。

    Args:
        model: 模型名称
        knowledge_tool: 知识库检索工具实例
        api_key: API 密钥
        base_url: API 基础地址
    """

    def __init__(
        self,
        model: str,
        knowledge_tool: "KnowledgeSearchTool",
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._model = model
        self._knowledge_tool = knowledge_tool
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

    async def process(
        self,
        content: str,
        category: str,
        priority: str,
        context: str = "",
    ) -> dict:
        """处理工单，生成解决方案。

        Args:
            content: 工单内容文本
            category: 工单分类
            priority: 优先级
            context: 额外上下文信息

        Returns:
            包含 result 和 references 的字典
        """
        # 1. 检索知识库
        knowledge_refs = self._search_knowledge(content)

        # 2. 构建上下文
        knowledge_context = self._build_knowledge_context(knowledge_refs)
        if context:
            knowledge_context = f"{knowledge_context}\n附加上下文：{context}"

        # 3. LLM 生成解决方案（重试和降级由 @with_retry 装饰器处理）
        return await self._generate_solution(
            content, category, priority, knowledge_context
        )

    def _search_knowledge(self, query: str) -> list[dict]:
        """检索知识库获取相关资料。

        Args:
            query: 检索查询文本

        Returns:
            匹配的知识条目列表
        """
        try:
            return self._knowledge_tool.search(query, top_k=3, score_threshold=0.5)
        except Exception as e:
            logger.warning(f"知识库检索失败: {e}")
            return []

    @staticmethod
    def _build_knowledge_context(refs: list[dict]) -> str:
        """将知识库检索结果格式化为上下文文本。

        Args:
            refs: 知识库检索结果列表

        Returns:
            格式化后的上下文文本
        """
        if not refs:
            return ""

        parts: list[str] = []
        for idx, ref in enumerate(refs, 1):
            score = ref.get("score", 0)
            text = ref.get("content", "")
            parts.append(f"[参考资料{idx}]（相关度: {score:.2f}）\n{text}")

        return "参考资料：\n" + "\n".join(parts)

    @with_retry(
        max_retries=3,
        backoff_base=2.0,
        retryable_exceptions=(APIError, APIConnectionError, RateLimitError, RetryableError),
        fallback=lambda self, content, category, priority, knowledge_context="": fallback_registry.execute(
            "processor.generate_solution", content, category, priority
        ),
    )
    async def _generate_solution(
        self,
        content: str,
        category: str,
        priority: str,
        knowledge_context: str,
    ) -> dict:
        """通过 LLM 生成解决方案。

        由 @with_retry 装饰器统一处理重试和降级逻辑。

        Args:
            content: 工单内容
            category: 工单分类
            priority: 优先级
            knowledge_context: 知识库上下文

        Returns:
            包含 result 和 references 的字典

        Raises:
            RetryableError: OpenAI API 可重试错误
            NonRetryableError: 认证失败或 JSON 解析失败
        """
        context_section = (
            f"\n{knowledge_context}" if knowledge_context else "\n（无相关参考资料）"
        )
        system_prompt = _PROCESSOR_SYSTEM_PROMPT.format(
            content=content,
            category=category,
            priority=priority,
            context_section=context_section,
        )

        logger.info(f"[Processor] 调用 LLM 模型: {self._model}")
        logger.debug(f"[Processor] 知识库上下文:\n{knowledge_context}")

        try:
            response = await self.client.chat_completions_create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"请处理以下工单：\n{content}"},
                ],
                temperature=0.3,
                response_format={"type": "json_object"},
            )
        except AuthenticationError as e:
            raise NonRetryableError(f"API 认证失败: {e}", cause=e)
        except (APIError, APIConnectionError, RateLimitError) as e:
            raise RetryableError(f"API 调用失败: {e}", cause=e)

        raw = response.choices[0].message.content or "{}"
        logger.info(f"[Processor] LLM 响应: {raw}")

        try:
            result = _parse_json_response(raw)
        except json.JSONDecodeError as e:
            raise NonRetryableError(f"LLM 返回非法 JSON: {e}", cause=e)

        return {
            "result": result.get("result", "处理完成，但未生成明确方案"),
            "references": result.get("references", []),
        }

    @staticmethod
    def _fallback_process(content: str, category: str, priority: str) -> dict:
        """LLM 调用失败时的降级处理方案。

        Args:
            content: 工单内容
            category: 工单分类
            priority: 优先级

        Returns:
            降级处理结果字典
        """
        result_map = {
            TicketCategory.TECHNICAL.value: f"已排查技术问题，生成解决方案（优先级: {priority}）",
            TicketCategory.BILLING.value: f"已核实账单信息，生成处理方案（优先级: {priority}）",
        }
        result = result_map.get(
            category, f"已处理工单（分类: {category}, 优先级: {priority}）"
        )

        return {
            "result": result,
            "references": [],
        }

    @staticmethod
    def create_from_settings(
        knowledge_tool: "KnowledgeSearchTool | None" = None,
    ) -> "ProcessorAgent":
        """从 Settings 创建 ProcessorAgent 实例。

        Args:
            knowledge_tool: 知识库检索工具，不传时自动创建

        Returns:
            配置好的 ProcessorAgent 实例
        """
        from src.multi_agent_system.tools.knowledge_search import KnowledgeSearchTool

        settings = Settings()
        if knowledge_tool is None:
            knowledge_tool = KnowledgeSearchTool.create_from_settings()

        return ProcessorAgent(
            model=settings.llm_model,
            knowledge_tool=knowledge_tool,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )


# 模块级降级注册
fallback_registry.register("processor.generate_solution", ProcessorAgent._fallback_process)
