"""鉴权模块：bcrypt 密码校验 + FastAPI 登录依赖。"""

from typing import Any

import bcrypt
from fastapi import Depends, HTTPException, status
from starlette.requests import HTTPConnection

from src.multi_agent_system.config import Settings

__all__ = ["verify_password", "hash_password", "require_login", "get_current_user"]

_PUBLIC_PATHS = {"/api/auth/login", "/api/auth/logout", "/api/auth/me"}


def hash_password(plain: str) -> str:
    """生成 bcrypt 哈希。"""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """校验密码与哈希是否匹配。"""
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def is_authenticated(request: HTTPConnection) -> bool:
    """检查当前 session 是否已登录。"""
    user = request.session.get("user") if hasattr(request, "session") else None
    return bool(user)


def get_current_user(request: HTTPConnection) -> dict[str, Any] | None:
    """获取当前登录用户信息，未登录返回 None。"""
    if not hasattr(request, "session"):
        return None
    user = request.session.get("user")
    return user if isinstance(user, dict) else None


async def require_login(request: HTTPConnection) -> dict[str, Any]:
    """FastAPI 依赖：要求已登录，否则 401。

    用法：
        @router.get("/...", dependencies=[Depends(require_login)])
        或 router = APIRouter(dependencies=[Depends(require_login)])
    """
    settings = Settings()
    if not settings.auth_enabled:
        return {"username": "anonymous", "auth_disabled": True}

    user = get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或会话已过期",
            headers={"Location": "/login"},
        )
    return user


# 让 import require_login 的代码也能拿到 Depends 形式
require_login_dep = Depends(require_login)
