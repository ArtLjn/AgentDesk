#!/usr/bin/env python3
"""生成 bcrypt 密码哈希，写入 config.yaml 的 auth_password_hash 字段。

用法：
    python scripts/hash_password.py
    （交互式输入密码）
或：
    python scripts/hash_password.py "你的密码"
"""

import getpass
import sys

from src.multi_agent_system.core.auth import hash_password


def main() -> None:
    if len(sys.argv) > 1:
        password = sys.argv[1]
    else:
        password = getpass.getpass("请输入管理员密码: ")
        confirm = getpass.getpass("再次确认: ")
        if password != confirm:
            print("两次输入不一致", file=sys.stderr)
            sys.exit(1)

    if len(password) < 6:
        print("密码至少 6 位", file=sys.stderr)
        sys.exit(1)

    hashed = hash_password(password)
    print()
    print("请把以下值写入 config.yaml 的 auth_password_hash 字段：")
    print()
    print(f'auth_password_hash: "{hashed}"')
    print()


if __name__ == "__main__":
    main()
