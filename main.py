"""项目启动入口。

用法：
    python main.py                 # 用 config.yaml 中的 api_host/api_port 启动
    python main.py --reload        # 开发热重载
    python main.py --port 9000     # 临时覆盖端口
"""

import argparse

import uvicorn

from src.multi_agent_system.config import Settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AgentDesk 多 Agent 工单处理系统")
    parser.add_argument("--host", help="监听地址，默认走 config.yaml")
    parser.add_argument("--port", type=int, help="监听端口，默认走 config.yaml")
    parser.add_argument("--reload", action="store_true", help="开发模式热重载")
    parser.add_argument("--log-level", default="info", help="日志级别")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = Settings()

    host = args.host or settings.api_host
    port = args.port or settings.api_port

    uvicorn.run(
        "src.multi_agent_system.api.app:app",
        host=host,
        port=port,
        reload=args.reload,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
