"""初始化腾讯云 MySQL 数据库：建库 + 建表。

幂等可重跑。流程：
  1. 用无库名 URL 连接，CREATE DATABASE IF NOT EXISTS
  2. 切到带库名 URL，Base.metadata.create_all() 建全部 7 张表
  3. 打印创建结果

用法：
  venv/bin/python scripts/init_mysql_db.py
  venv/bin/python scripts/init_mysql_db.py --url "mysql+aiomysql://user:pwd@host:port/dbname"
"""

import argparse
import asyncio
import sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse

# 把项目根目录加入 sys.path，便于直接执行
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy.ext.asyncio import create_async_engine

from src.multi_agent_system.config import Settings
from src.multi_agent_system.models.db import Base


def _split_server_only(url: str) -> tuple[str, str]:
    """从 mysql+aiomysql://user:pwd@host:port/dbname?args 中拆出无库名 URL 与库名。"""
    parsed = urlparse(url)
    db_name = parsed.path.lstrip("/").split("?")[0]
    # 重构成无 path 的 URL（保留 userinfo + host + port + query）
    server_parsed = parsed._replace(path="")
    server_url = urlunparse(server_parsed)
    if parsed.query:
        if "?" not in server_url:
            server_url += "?" + parsed.query
    return server_url, db_name


async def init_db(database_url: str) -> None:
    server_url, db_name = _split_server_only(database_url)
    if not db_name:
        print(f"[ERROR] URL 中未指定库名：{database_url}", file=sys.stderr)
        sys.exit(1)

    print(f"[1/3] 连接 MySQL Server（无库名）：{server_url.split('@')[-1]}")
    server_engine = create_async_engine(server_url)
    try:
        async with server_engine.connect() as conn:
            await conn.execute(
                # aiomysql 不支持在 text() 内执行多语句，逐条执行
                __import__("sqlalchemy").text(
                    f"CREATE DATABASE IF NOT EXISTS {db_name} "
                    f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            )
            await conn.commit()
        print(f"      ✓ 数据库 `{db_name}` 已就绪（utf8mb4 / utf8mb4_unicode_ci）")
    finally:
        await server_engine.dispose()

    print(f"[2/3] 连接目标库：{db_name}")
    db_engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with db_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print(f"      ✓ 已创建 {len(Base.metadata.tables)} 张表：")
        for table_name in sorted(Base.metadata.tables.keys()):
            cols = Base.metadata.tables[table_name].columns
            print(f"         - {table_name}  ({len(cols)} cols)")
    finally:
        await db_engine.dispose()

    print("[3/3] 完成。可执行 `pytest tests/core/test_database.py` 验证。")


def main() -> None:
    parser = argparse.ArgumentParser(description="初始化腾讯云 MySQL 数据库")
    parser.add_argument(
        "--url",
        default=Settings().database_url,
        help="SQLAlchemy URL（默认从 config.yaml 读取 database_url）",
    )
    args = parser.parse_args()

    if not args.url.startswith("mysql"):
        print(
            f"[ERROR] database_url 必须是 mysql+aiomysql:// 格式，当前：{args.url}",
            file=sys.stderr,
        )
        sys.exit(1)

    asyncio.run(init_db(args.url))


if __name__ == "__main__":
    main()
