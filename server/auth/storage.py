"""
用户存储管理
============

管理用户数据的持久化存储
"""

import json
import os
from typing import Optional, List, Dict
from datetime import datetime
from pathlib import Path
import hashlib
import base64
import hmac
import secrets

from .models import User, UserRole
from ..utils.config import config


class UserStorage:
    """用户存储类"""
    
    def __init__(self, storage_dir: str = "data/users"):
        """初始化用户存储
        
        Args:
            storage_dir: 存储目录路径
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.users_file = self.storage_dir / "users.json"
        self.sessions_file = self.storage_dir / "sessions.json"
        
        # 确保文件存在
        if not self.users_file.exists():
            self._save_users({})
        
        if not self.sessions_file.exists():
            self._save_sessions({})
        
        # 初始化时创建默认管理员账户
        self._ensure_default_admin()
    
    def _ensure_default_admin(self):
        """确保存在默认管理员账户"""
        users = self._load_users()
        
        # 检查是否已有管理员
        has_admin = any(user.get('role') == UserRole.ADMIN.value for user in users.values())
        
        if not has_admin:
            # 创建默认管理员
            import uuid
            admin_id = str(uuid.uuid4())
            default_password = os.getenv("HUMAND_BOOTSTRAP_ADMIN_PASSWORD", "").strip()

            if not default_password:
                # 生产环境禁止使用硬编码默认密码
                if getattr(config, "ENV", "development") == "production":
                    raise RuntimeError(
                        "生产环境必须设置 HUMAND_BOOTSTRAP_ADMIN_PASSWORD 以初始化管理员账户"
                    )
                # 开发环境生成随机密码（仅用于首次启动引导）
                default_password = secrets.token_urlsafe(12)
            
            admin = User(
                user_id=admin_id,
                username="admin",
                email="admin@humand.com",
                password_hash=self._hash_password(default_password),
                full_name="系统管理员",
                role=UserRole.ADMIN,
                is_active=True,
                is_verified=True,
                department="系统部",
                position="管理员"
            )
            
            users[admin_id] = admin.dict()
            self._save_users(users)
            
            print(f"✅ 已创建默认管理员账户")
            print(f"   用户名: admin")
            if getattr(config, "ENV", "development") == "production":
                print("   密码已通过环境变量 HUMAND_BOOTSTRAP_ADMIN_PASSWORD 设置")
            else:
                print(f"   密码: {default_password}")
                print(f"   请及时修改密码！")
    
    def _load_users(self) -> Dict[str, dict]:
        """加载所有用户"""
        try:
            with open(self.users_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载用户失败: {e}")
            return {}
    
    def _save_users(self, users: Dict[str, dict]):
        """保存所有用户"""
        try:
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump(users, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            print(f"保存用户失败: {e}")
    
    def _load_sessions(self) -> Dict[str, dict]:
        """加载所有会话"""
        try:
            with open(self.sessions_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    
    def _save_sessions(self, sessions: Dict[str, dict]):
        """保存所有会话"""
        try:
            with open(self.sessions_file, 'w', encoding='utf-8') as f:
                json.dump(sessions, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            print(f"保存会话失败: {e}")
    
    @staticmethod
    def _hash_password(password: str) -> str:
        """哈希密码（PBKDF2-HMAC-SHA256）"""
        iterations = 200_000
        salt = secrets.token_bytes(16)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return "pbkdf2_sha256${}${}${}".format(
            iterations,
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(dk).decode("ascii"),
        )

    @staticmethod
    def _verify_password(password: str, stored_hash: str) -> bool:
        """验证密码（兼容旧版 sha256 十六进制哈希）"""
        if stored_hash.startswith("pbkdf2_sha256$"):
            try:
                _, it_str, salt_b64, dk_b64 = stored_hash.split("$", 3)
                iterations = int(it_str)
                salt = base64.b64decode(salt_b64.encode("ascii"))
                expected = base64.b64decode(dk_b64.encode("ascii"))
                actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
                return hmac.compare_digest(actual, expected)
            except Exception:
                return False

        # Legacy: sha256 hex digest
        legacy = hashlib.sha256(password.encode("utf-8")).hexdigest()
        return hmac.compare_digest(legacy, stored_hash)
    
    def create_user(self, user: User) -> bool:
        """创建用户"""
        users = self._load_users()
        
        # 检查用户名是否已存在
        if any(u.get('username') == user.username for u in users.values()):
            return False
        
        # 检查邮箱是否已存在
        if any(u.get('email') == user.email for u in users.values()):
            return False
        
        users[user.user_id] = user.dict()
        self._save_users(users)
        return True
    
    def get_user(self, user_id: str) -> Optional[User]:
        """获取用户"""
        users = self._load_users()
        user_data = users.get(user_id)
        if user_data:
            return User(**user_data)
        return None
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """通过用户名获取用户"""
        users = self._load_users()
        for user_data in users.values():
            if user_data.get('username') == username:
                return User(**user_data)
        return None
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """通过邮箱获取用户"""
        users = self._load_users()
        for user_data in users.values():
            if user_data.get('email') == email:
                return User(**user_data)
        return None
    
    def update_user(self, user_id: str, updates: dict) -> bool:
        """更新用户信息"""
        users = self._load_users()
        
        if user_id not in users:
            return False
        
        users[user_id].update(updates)
        users[user_id]['updated_at'] = datetime.now().isoformat()
        self._save_users(users)
        return True
    
    def delete_user(self, user_id: str) -> bool:
        """删除用户"""
        users = self._load_users()
        
        if user_id in users:
            del users[user_id]
            self._save_users(users)
            return True
        return False
    
    def list_users(self, role: Optional[UserRole] = None, 
                   active_only: bool = False) -> List[User]:
        """列出用户"""
        users = self._load_users()
        result = []
        
        for user_data in users.values():
            user = User(**user_data)
            
            # 角色筛选
            if role and user.role != role:
                continue
            
            # 状态筛选
            if active_only and not user.is_active:
                continue
            
            result.append(user)
        
        return result
    
    def verify_password(self, username: str, password: str) -> Optional[User]:
        """验证用户密码"""
        user = self.get_user_by_username(username)
        
        if not user:
            return None
        
        if not user.is_active:
            return None
        
        if self._verify_password(password, user.password_hash):
            # 更新最后登录时间
            self.update_user(user.user_id, {
                'last_login': datetime.now().isoformat()
            })
            # 旧哈希命中则顺便升级到 PBKDF2
            if not user.password_hash.startswith("pbkdf2_sha256$"):
                self.update_user(user.user_id, {"password_hash": self._hash_password(password)})
            return user
        
        return None
    
    def change_password(self, user_id: str, old_password: str, 
                       new_password: str) -> bool:
        """修改密码"""
        user = self.get_user(user_id)
        
        if not user:
            return False
        
        # 验证旧密码
        if not self._verify_password(old_password, user.password_hash):
            return False
        
        # 更新密码
        return self.update_user(user_id, {'password_hash': self._hash_password(new_password)})
    
    def reset_password(self, user_id: str, new_password: str) -> bool:
        """重置密码（管理员操作）"""
        return self.update_user(user_id, {'password_hash': self._hash_password(new_password)})
    
    def increment_approval_count(self, user_id: str, approved: bool):
        """增加审批统计"""
        user = self.get_user(user_id)
        if user:
            updates = {
                'total_approvals': user.total_approvals + 1
            }
            if approved:
                updates['approved_count'] = user.approved_count + 1
            else:
                updates['rejected_count'] = user.rejected_count + 1
            
            self.update_user(user_id, updates)
    
    # 会话管理
    def create_session(self, session_id: str, user_id: str, data: dict, ttl_seconds: Optional[int] = None) -> bool:
        """创建会话"""
        sessions = self._load_sessions()
        ttl = int(ttl_seconds or getattr(config, "SESSION_TTL_SECONDS", 86400))
        expires_at = datetime.now().timestamp() + ttl
        sessions[session_id] = {
            'user_id': user_id,
            'data': data,
            'created_at': datetime.now().isoformat(),
            'expires_at': expires_at
        }
        self._save_sessions(sessions)
        return True
    
    def get_session(self, session_id: str) -> Optional[dict]:
        """获取会话"""
        sessions = self._load_sessions()
        session = sessions.get(session_id)
        if not session:
            return None

        # 过期检查
        try:
            expires_at = session.get("expires_at")
            if expires_at is not None and datetime.now().timestamp() > float(expires_at):
                self.delete_session(session_id)
                return None
        except Exception:
            # 如果会话数据损坏，直接删除
            self.delete_session(session_id)
            return None

        return session
    
    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        sessions = self._load_sessions()
        if session_id in sessions:
            del sessions[session_id]
            self._save_sessions(sessions)
            return True
        return False
    
    def get_user_sessions(self, user_id: str) -> List[str]:
        """获取用户的所有会话ID"""
        sessions = self._load_sessions()
        return [
            session_id for session_id, data in sessions.items()
            if data.get('user_id') == user_id
        ]


# 全局用户存储实例
user_storage = UserStorage()

