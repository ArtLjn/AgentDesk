"""多 Agent 工单处理系统。"""

import sys

from loguru import logger

# 配置结构化日志格式，trace_id / agent 缺失时显示 "-"
logger.configure(
    handlers=[
        {
            "sink": sys.stdout,
            "format": (
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "trace_id={extra[trace_id]} agent={extra[agent]} | "
                "{message}"
            ),
            "filter": lambda record: (
                record["extra"].setdefault("trace_id", "-") or True
            ) and (record["extra"].setdefault("agent", "-") or True),
        }
    ]
)

__all__: list[str] = []
