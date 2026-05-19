"""工单处理 Agent 模块。

默认导出 ReActProcessorAgent（新实现）。
如需回退到旧实现，可从 processor_legacy 导入 LegacyProcessorAgent。
"""

from src.multi_agent_system.agents.processor_react import ReActProcessorAgent

# Backward compatibility: ProcessorAgent is now ReActProcessorAgent
ProcessorAgent = ReActProcessorAgent

__all__ = ["ProcessorAgent", "ReActProcessorAgent"]
