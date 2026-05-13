"""
命令行研究助手 - 基于 Plan-React 混合模式

Plan 阶段分解复杂任务，Execute 阶段每步用 ReAct 灵活推理+工具调用。

使用方法：
    python examples/plan_react_assistant.py

功能：
    - 支持自然语言提问
    - 自动规划任务步骤，每步灵活调用工具
    - 多轮对话，输入 'quit' 或 'exit' 退出
"""

import os
import sys

# 添加项目根目录到 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from loguru import logger

load_dotenv()

from src.basic_agents.plan_react_agent import PlanReactAgent, _sanitize_text
from src.basic_agents.tools.calculator import calculator
from src.basic_agents.tools.search import search
from src.basic_agents.tools.web_scraper import web_scraper


def main() -> None:
    """主函数，创建Agent并进入交互循环"""
    # 配置日志
    logger.remove()
    logger.add(
        sys.stderr,
        level="DEBUG",
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )
    logger.add(
        "logs/plan_react_assistant_{time:YYYY-MM-DD}.log",
        level="DEBUG",
        rotation="10 MB",
        retention="7 days",
        encoding="utf-8",
    )

    # 从环境变量获取配置
    model = os.getenv("OPENAI_MODEL", "deepseek-chat")
    base_url = os.getenv("OPENAI_BASE_URL", "")
    api_key = os.getenv("OPENAI_API_KEY", "")

    logger.info(f"配置: model={model}, base_url={base_url}")
    logger.info(f"API Key: {'已配置' if api_key else '未配置'}")

    # 创建 Plan-React 混合 Agent
    agent = PlanReactAgent(model=model)
    logger.info("Plan-React Agent 创建成功")

    # 注册工具（自动同步到内部 ReActAgent）
    agent.register_tool("calculator", calculator, "数学计算器")
    agent.register_tool("search", search, "网络搜索")
    agent.register_tool("web_scraper", web_scraper, "网页内容抓取")
    logger.info(f"已注册 {len(agent.tools)} 个工具: {list(agent.tools.keys())}")

    print("=" * 60)
    print("  AI 研究助手 - 基于 Plan-React 混合模式")
    print("  Plan: 全局任务分解 | ReAct: 每步灵活推理+工具调用")
    print("  可用工具: 计算器 | 搜索 | 网页抓取")
    print("  输入 'quit' 或 'exit' 退出")
    print("=" * 60)

    while True:
        try:
            query = _sanitize_text(input("\n> ").strip())
            if not query:
                continue
            if query.lower() in ("quit", "exit", "q"):
                print("再见！")
                break

            print("\n思考中...\n")
            logger.debug(f"收到查询: {query}")
            result = agent.run(query)
            logger.debug(f"最终回答: {result[:200]}...")
            print(f"回答:\n{result}")
        except KeyboardInterrupt:
            print("\n再见！")
            break
        except Exception as e:
            logger.exception(f"发生错误: {e}")
            print(f"错误: {str(e)}")


if __name__ == "__main__":
    main()
