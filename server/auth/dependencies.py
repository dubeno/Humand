"""
认证依赖
========

FastAPI 依赖注入，用于用户认证和权限检查
"""

from typing import Optional
from fastapi import Depends, Request, HTTPException, status
from functools import wraps

from .models import User, UserRole, Permission
from .storage import user_storage


async def get_current_user(request: Request) -> Optional[User]:
    """获取当前登录用户"""
    session_id = request.cookies.get("session_id")
    
    if not session_id:
        return None
    
    session = user_storage.get_session(session_id)
    if not session:
        return None
    
    user_id = session.get('user_id')
    if not user_id:
        return None
    
    user = user_storage.get_user(user_id)
    return user


async def require_login(request: Request) -> User:
    """要求用户登录"""
    user = await get_current_user(request)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或会话已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用"
        )
    
    return user


def require_permission(permission: Permission):
    """要求特定权限的装饰器工厂"""
    async def dependency(user: User = Depends(require_login)):
        if not user.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"缺少权限: {permission.value}"
            )
        return user
    return dependency


def require_role(role: UserRole):
    """要求特定角色的装饰器工厂"""
    async def dependency(user: User = Depends(require_login)):
        if user.role != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"需要 {role.value} 角色"
            )
        return user
    return dependency


def require_admin():
    """要求管理员权限"""
    return require_role(UserRole.ADMIN)


async def optional_user(request: Request) -> Optional[User]:
    """可选的用户认证（不抛出异常）"""
    try:
        session_id = request.cookies.get("session_id")
        if not session_id:
            return None
        
        session = user_storage.get_session(session_id)
        if not session:
            return None
        
        user_id = session.get('user_id')
        if not user_id:
            return None
        
        return user_storage.get_user(user_id)
    except Exception:
        return None


