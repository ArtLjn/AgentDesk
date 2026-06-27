"""鉴权路由：登录 / 退出 / 查当前用户。"""

from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from src.multi_agent_system.config import Settings
from src.multi_agent_system.core.auth import get_current_user, verify_password

__all__ = ["router", "LoginRequest"]

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    """登录请求体。"""
    username: str
    password: str


class LoginResponse(BaseModel):
    """登录响应。"""
    username: str
    logged_in: bool = True


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request) -> LoginResponse:
    """用户名 + 密码登录，成功后写入 session。"""
    settings = Settings()
    ok = (
        body.username == settings.auth_username
        and verify_password(body.password, settings.auth_password_hash)
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    request.session["user"] = {"username": body.username}
    return LoginResponse(username=body.username)


@router.post("/logout")
async def logout(request: Request) -> dict[str, Any]:
    """退出登录，清空 session。"""
    request.session.clear()
    return {"logged_out": True}


@router.get("/me")
async def me(request: Request) -> dict[str, Any]:
    """查当前登录状态。无需鉴权依赖，直接读 session。"""
    user = get_current_user(request)
    settings = Settings()
    if user:
        return {"logged_in": True, "username": user.get("username"), "auth_enabled": settings.auth_enabled}
    return {"logged_in": False, "username": None, "auth_enabled": settings.auth_enabled}
