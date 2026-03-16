"""
用户认证模型
============

定义用户、角色和权限的数据模型
"""

from enum import Enum
from typing import Optional, List, Dict
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class UserRole(str, Enum):
    """用户角色枚举"""
    ADMIN = "admin"              # 管理员 - 完全权限
    APPROVER = "approver"        # 审批员 - 审批权限
    VIEWER = "viewer"            # 查看者 - 只读权限
    REQUESTER = "requester"      # 申请人 - 提交审批请求


class Permission(str, Enum):
    """权限枚举"""
    # 审批权限
    APPROVE_REQUEST = "approve_request"      # 批准审批请求
    REJECT_REQUEST = "reject_request"        # 拒绝审批请求
    VIEW_REQUEST = "view_request"            # 查看审批请求
    CREATE_REQUEST = "create_request"        # 创建审批请求
    
    # 用户管理权限
    MANAGE_USERS = "manage_users"            # 管理用户
    VIEW_USERS = "view_users"                # 查看用户列表
    
    # 系统权限
    VIEW_STATISTICS = "view_statistics"      # 查看统计数据
    MANAGE_SETTINGS = "manage_settings"      # 管理系统设置
    VIEW_LOGS = "view_logs"                  # 查看日志


# 角色权限映射
ROLE_PERMISSIONS: Dict[UserRole, List[Permission]] = {
    UserRole.ADMIN: [
        Permission.APPROVE_REQUEST,
        Permission.REJECT_REQUEST,
        Permission.VIEW_REQUEST,
        Permission.CREATE_REQUEST,
        Permission.MANAGE_USERS,
        Permission.VIEW_USERS,
        Permission.VIEW_STATISTICS,
        Permission.MANAGE_SETTINGS,
        Permission.VIEW_LOGS,
    ],
    UserRole.APPROVER: [
        Permission.APPROVE_REQUEST,
        Permission.REJECT_REQUEST,
        Permission.VIEW_REQUEST,
        Permission.VIEW_STATISTICS,
    ],
    UserRole.VIEWER: [
        Permission.VIEW_REQUEST,
        Permission.VIEW_STATISTICS,
    ],
    UserRole.REQUESTER: [
        Permission.CREATE_REQUEST,
        Permission.VIEW_REQUEST,
    ],
}


class User(BaseModel):
    """用户模型"""
    user_id: str = Field(..., description="用户ID")
    username: str = Field(..., description="用户名", min_length=3, max_length=50)
    email: EmailStr = Field(..., description="邮箱")
    password_hash: str = Field(..., description="密码哈希")
    full_name: str = Field(..., description="全名")
    
    role: UserRole = Field(default=UserRole.REQUESTER, description="用户角色")
    is_active: bool = Field(default=True, description="是否激活")
    is_verified: bool = Field(default=False, description="是否已验证邮箱")
    
    avatar_url: Optional[str] = Field(default=None, description="头像URL")
    department: Optional[str] = Field(default=None, description="部门")
    position: Optional[str] = Field(default=None, description="职位")
    phone: Optional[str] = Field(default=None, description="电话")
    
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    last_login: Optional[datetime] = Field(default=None, description="最后登录时间")
    
    # 统计数据
    total_approvals: int = Field(default=0, description="总审批数")
    approved_count: int = Field(default=0, description="批准数")
    rejected_count: int = Field(default=0, description="拒绝数")
    
    class Config:
        use_enum_values = True
    
    def has_permission(self, permission: Permission) -> bool:
        """检查用户是否有某个权限"""
        role_perms = ROLE_PERMISSIONS.get(UserRole(self.role), [])
        return permission in role_perms
    
    def has_any_permission(self, permissions: List[Permission]) -> bool:
        """检查用户是否有任意一个权限"""
        return any(self.has_permission(perm) for perm in permissions)
    
    def has_all_permissions(self, permissions: List[Permission]) -> bool:
        """检查用户是否有所有权限"""
        return all(self.has_permission(perm) for perm in permissions)
    
    def get_permissions(self) -> List[Permission]:
        """获取用户的所有权限"""
        return ROLE_PERMISSIONS.get(UserRole(self.role), [])
    
    def dict_safe(self) -> dict:
        """返回不包含敏感信息的字典"""
        data = self.dict()
        data.pop('password_hash', None)
        return data


class UserCreate(BaseModel):
    """创建用户请求"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: str
    role: UserRole = UserRole.REQUESTER
    department: Optional[str] = None
    position: Optional[str] = None
    phone: Optional[str] = None


class UserUpdate(BaseModel):
    """更新用户请求"""
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    department: Optional[str] = None
    position: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None
    avatar_url: Optional[str] = None


class UserLogin(BaseModel):
    """用户登录请求"""
    username: str
    password: str
    remember_me: bool = False


class PasswordChange(BaseModel):
    """修改密码请求"""
    old_password: str
    new_password: str = Field(..., min_length=6)


class SessionData(BaseModel):
    """会话数据"""
    user_id: str
    username: str
    role: UserRole
    login_time: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


