"""
用户认证模块
============
"""

from .models import User, UserRole, Permission, UserCreate, UserUpdate, UserLogin
from .storage import user_storage
from .dependencies import (
    get_current_user,
    require_login,
    require_permission,
    require_role,
    optional_user,
)

__all__ = [
    'User',
    'UserRole',
    'Permission',
    'UserCreate',
    'UserUpdate',
    'UserLogin',
    'user_storage',
    'get_current_user',
    'require_login',
    'require_permission',
    'require_role',
    'optional_user',
]


