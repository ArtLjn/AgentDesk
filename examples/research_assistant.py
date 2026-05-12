"""
命令行研究助手 - 基于ReAct Agent的多工具研究助手

使用方法：
    python examples/research_assistant.py

功能：
    - 支持自然语言提问
    - 自动调用计算器、搜索、网页抓取工具
    - 多轮对话，输入 'quit' 或 'exit' 退出
"""

import os
import sys

# 添加项目根目录到 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from loguru import logger

load_dotenv()

from src.basic_agents.react_agent import ReActAgent
from src.basic_agents.tools.calculator import calculator
from src.basic_agents.tools.search import search
from src.basic_agents.tools.web_scraper import web_scraper


def main() -> None:
    """主函数，创建Agent并进入交互循环"""
    # 配置日志
    logger.remove()
    logger.add(sys.stderr, level="INFO")

    # 从环境变量获取配置
    model = os.getenv("OPENAI_MODEL", "deepseek-chat")

    # 创建Agent
    agent = ReActAgent(model=model)

    # 注册工具
    agent.register_tool("calculator", calculator, "数学计算器")
    agent.register_tool("search", search, "网络搜索")
    agent.register_tool("web_scraper", web_scraper, "网页内容抓取")

    print("=" * 60)
    print("  AI 研究助手 - 基于ReAct模式")
    print("  可用工具: 计算器 | 搜索 | 网页抓取")
    print("  输入 'quit' 或 'exit' 退出")
    print("=" * 60)

    while True:
        try:
            query = input("\n> ").strip()
            if not query:
                continue
            if query.lower() in ("quit", "exit", "q"):
                print("再见！")
                break

            print("\n思考中...\n")
            result = agent.run(query)
            print(f"回答: {result}")
        except KeyboardInterrupt:
            print("\n再见！")
            break
        except Exception as e:
            logger.error(f"发生错误: {e}")
            print(f"错误: {str(e)}")


if __name__ == "__main__":
    main()
