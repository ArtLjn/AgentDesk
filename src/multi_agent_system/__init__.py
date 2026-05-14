"""多 Agent 工单处理系统。"""

import sys

from loguru import logger

# 配置结构化日志格式，trace_id 缺失时显示 "-"
logger.configure(
    handlers=[
        {
            "sink": sys.stdout,
            "format": (
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "trace_id={extra[trace_id]} | {message}"
            ),
            "filter": lambda record: record["extra"].setdefault("trace_id", "-") or True,
        }
    ]
)

__all__: list[str] = []
