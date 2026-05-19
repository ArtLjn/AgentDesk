"""ReAct 模式 ProcessorAgent：多步推理 + 动态工具调用。"""

import json
import re
from typing import TYPE_CHECKING, Any

from loguru import logger
from openai import APIConnectionError, APIError, AuthenticationError, RateLimitError

from src.multi_agent_system.config import Settings
from src.multi_agent_system.core import CachedLLMClient, fallback_registry, track_agent_execution, with_retry
from src.multi_agent_system.core.context_manager import ContextManager
from src.multi_agent_system.core.exceptions import NonRetryableError, RetryableError
from src.multi_agent_system.core.json_parser import parse_json_response
from src.multi_agent_system.core.memory import MemoryManager

if TYPE_CHECKING:
    from src.multi_agent_system.core.tool_base import ToolRegistry

__all__ = ["ReActProcessorAgent"]

# ReAct 系统提示词
_REACT_SYSTEM_PROMPT = """\
你是一个专业的工单处理专家。请通过推理和工具调用解决用户问题。

可用工具：
{tools_description}

工作流程：
1. Thought: 分析当前情况，决定下一步行动
2. Action: 如果需要工具，输出 JSON 格式调用：{{"tool": "工具名", "params": {{参数}}}}
3. Observation: 工具返回结果会自动提供
4. 重复以上步骤，直到可以给出最终答案
5. Final Answer: 给出完整解决方案

当前工单信息：
{ticket_info}

用户历史上下文：
{user_context}

要求：
- 每个 Thought 必须基于已有信息
- 工具参数必须严格符合 Schema
- 如果已有足够信息，直接给出 Final Answer
- 回答使用中文，简洁专业
"""


class ReActProcessorAgent:
    """ReAct 模式工单处理 Agent：多步推理 + 动态工具调用。

    通过 Thought-Action-Observation 循环处理复杂工单，
    支持查知识库、查用户历史、查用户信息等多种工具。

    Args:
        model: 模型名称
        tool_registry: 工具注册表
        knowledge_tool: 知识库检索工具（兼容旧接口）
        api_key: API 密钥
        base_url: API 基础地址
        max_iterations: ReAct 最大迭代次数，默认 10
    """

    def __init__(
        self,
        model: str,
        tool_registry: "ToolRegistry | None" = None,
        knowledge_tool: Any = None,  # backward compat
        api_key: str | None = None,
        base_url: str | None = None,
        task_type: str = "process",
        max_iterations: int = 10,
        client: CachedLLMClient | None = None,
    ) -> None:
        self._model = model
        self._tool_registry = tool_registry
        self._knowledge_tool = knowledge_tool
        self._api_key = api_key
        self._base_url = base_url
        self._task_type = task_type
        self._max_iterations = max_iterations
        self._client: CachedLLMClient | None = client
        self._context_manager = ContextManager()

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

    @track_agent_execution("processor")
    async def process(
        self,
        content: str,
        category: str,
        priority: str,
        context: str = "",
        user_id: str | None = None,
        memory: MemoryManager | None = None,
    ) -> dict:
        """处理工单，生成解决方案（ReAct 循环）。

        保持与原始 ProcessorAgent 的接口兼容。

        Args:
            content: 工单内容文本
            category: 工单分类
            priority: 优先级
            context: 额外上下文信息
            user_id: 用户 ID（用于加载长期记忆）
            memory: 记忆管理器（用于记录 ReAct 步骤）

        Returns:
            包含 result 和 references 的字典
        """
        return await self._process_by_react(
            content, category, priority, context, user_id, memory
        )

    @with_retry(
        max_retries=3,
        backoff_base=2.0,
        retryable_exceptions=(APIError, APIConnectionError, RateLimitError, RetryableError),
        fallback=lambda self, content, category, priority, context="", user_id=None, memory=None: fallback_registry.execute(
            "processor.generate_solution", content, category, priority
        ),
    )
    async def _process_by_react(
        self,
        content: str,
        category: str,
        priority: str,
        context: str = "",
        user_id: str | None = None,
        memory: MemoryManager | None = None,
    ) -> dict:
        """通过 ReAct 循环处理工单。"""

        # Build ticket info
        ticket_info = f"内容: {content}\n分类: {category}\n优先级: {priority}"
        if context:
            ticket_info += f"\n附加上下文: {context}"

        # Load user context
        user_context_str = "无"
        if memory and user_id:
            user_ctx = await memory.load_user_context(user_id)
            if user_ctx:
                user_context_str = self._context_manager.build_system_context(
                    {"ticket_id": "", "category": category, "priority": priority},
                    user_ctx,
                )

        # Build tools description
        tools_description = "无可用工具"
        if self._tool_registry:
            schemas = self._tool_registry.get_schemas()
            if schemas:
                parts = []
                for s in schemas:
                    params = s["parameters"]["properties"]
                    param_desc = ", ".join(f"{k}({v.get('type', 'any')})" for k, v in params.items())
                    parts.append(f"- {s['name']}: {s['description']} 参数: {param_desc}")
                tools_description = "\n".join(parts)

        system_prompt = _REACT_SYSTEM_PROMPT.format(
            tools_description=tools_description,
            ticket_info=ticket_info,
            user_context=user_context_str,
        )

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请处理以下工单：\n{content}"},
        ]

        # ReAct loop
        for iteration in range(self._max_iterations):
            logger.info(f"[ReAct] Iteration {iteration + 1}/{self._max_iterations}")

            # Trim context before each call
            messages = self._context_manager.trim_messages(messages)

            try:
                response = await self.client.chat_completions_create(
                    messages=messages,
                    temperature=0.3,
                    task_type=self._task_type,
                )
            except AuthenticationError as e:
                raise NonRetryableError(f"API 认证失败: {e}", cause=e)
            except (APIError, APIConnectionError, RateLimitError) as e:
                raise RetryableError(f"API 调用失败: {e}", cause=e)

            raw = response.choices[0].message.content or ""
            logger.info(f"[ReAct] LLM response: {raw[:200]}...")

            # Check for Final Answer
            if "Final Answer:" in raw:
                answer = raw.split("Final Answer:")[-1].strip()

                # Record in memory
                if memory:
                    memory.add_thought(f"Completed in {iteration + 1} iterations", iteration)

                return {
                    "result": answer,
                    "references": [],
                }

            # Try to parse as direct JSON result (backward compat)
            if raw.strip().startswith("{"):
                try:
                    parsed = parse_json_response(raw)
                    if "result" in parsed:
                        return {
                            "result": parsed.get("result", ""),
                            "references": parsed.get("references", []),
                        }
                except json.JSONDecodeError:
                    pass

            # Parse Thought and Action
            thought = self._extract_thought(raw)
            action = self._extract_action(raw)

            if memory:
                memory.add_thought(thought or f"Iteration {iteration + 1}", iteration)

            if action:
                tool_name = action.get("tool", "")
                params = action.get("params", {})

                if memory:
                    memory.add_action(tool_name, params, iteration)

                # Execute tool
                observation = await self._execute_tool(tool_name, params)

                if memory:
                    memory.add_observation(str(observation), iteration)

                # Add to conversation
                messages.append({"role": "assistant", "content": raw})
                messages.append({
                    "role": "user",
                    "content": f"Observation: {observation}",
                })
            else:
                # No action found, just add response and continue
                messages.append({"role": "assistant", "content": raw})
                messages.append({
                    "role": "user",
                    "content": "Observation: 未识别到工具调用，请继续思考或直接给出 Final Answer。",
                })

        # Max iterations reached
        logger.warning(f"[ReAct] Max iterations ({self._max_iterations}) reached")
        return {
            "result": "问题较复杂，已尝试多次推理仍未解决，建议升级至人工处理。",
            "references": [],
        }

    def _extract_thought(self, text: str) -> str:
        """从响应中提取 Thought。"""
        match = re.search(r"Thought:\s*(.+?)(?=\nAction:|\nFinal Answer:|$)", text, re.DOTALL)
        return match.group(1).strip() if match else ""

    def _extract_action(self, text: str) -> dict[str, Any] | None:
        """从响应中提取 Action JSON。"""
        # Try JSON format first
        json_match = re.search(r"Action:\s*(\{.+?\})", text, re.DOTALL)
        if json_match:
            try:
                return parse_json_response(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try legacy format: Action: tool_name(params_json)
        legacy_match = re.search(r"Action:\s*(\w+)\((.*?)\)", text, re.DOTALL)
        if legacy_match:
            tool_name = legacy_match.group(1)
            params_str = legacy_match.group(2).strip().strip('"\'')
            try:
                params = parse_json_response(params_str)
                if isinstance(params, dict):
                    return {"tool": tool_name, "params": params}
            except json.JSONDecodeError:
                pass
            return {"tool": tool_name, "params": {"query": params_str}}

        return None

    async def _execute_tool(self, tool_name: str, params: dict[str, Any]) -> str:
        """执行工具调用，含校验和降级。"""
        if not self._tool_registry or tool_name not in self._tool_registry:
            return f"错误: 工具 '{tool_name}' 未注册"

        tool = self._tool_registry.get(tool_name)
        assert tool is not None

        # Validate params
        try:
            validated = tool.validate_params(params)
        except Exception as e:
            error_msg = tool.format_validation_error(e) if hasattr(e, "errors") else str(e)
            return f"参数错误: {error_msg}"

        # Execute
        try:
            result = await tool.execute(**validated.model_dump())
            return str(result)
        except Exception as e:
            logger.warning(f"[ReAct] Tool {tool_name} failed: {e}, trying fallback")
            try:
                fallback_result = await tool.fallback(**validated.model_dump())
                return str(fallback_result)
            except Exception as fb_e:
                return f"工具执行失败: {e}; 降级也失败: {fb_e}"

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
        from src.multi_agent_system.models.ticket import TicketCategory

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
        tool_registry: "ToolRegistry | None" = None,
        knowledge_tool: Any = None,
    ) -> "ReActProcessorAgent":
        """从 Settings 创建 ReActProcessorAgent 实例。"""
        settings = Settings()
        return ReActProcessorAgent(
            model=settings.llm_model,
            tool_registry=tool_registry,
            knowledge_tool=knowledge_tool,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )


# 模块级降级注册
fallback_registry.register("processor.generate_solution", ReActProcessorAgent._fallback_process)
