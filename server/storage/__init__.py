"""
存储模块
========

自动选择最佳的存储后端：
1. 优先使用 Redis（生产环境推荐）
2. Redis 不可用时自动降级到内存存储（开发/测试环境）
"""

import os
from typing import Union


def create_storage() -> Union['ApprovalStorage', 'MemoryStorage']:
    """
    创建存储实例（自动选择最佳后端）
    
    Returns:
        存储实例（Redis 或内存存储）
    """
    # 检查是否强制使用内存存储
    if os.environ.get("HUMAND_FORCE_MEMORY_STORAGE", "").lower() == "true":
        print("💡 使用内存存储（环境变量配置）")
        from .memory import MemoryStorage
        return MemoryStorage()
    
    # 尝试使用 Redis
    try:
        from .redis import ApprovalStorage
        storage = ApprovalStorage()
        
        # 测试 Redis 连接
        storage.redis_client.ping()
        print("✅ 使用 Redis 存储")
        return storage
        
    except Exception as e:
        print(f"⚠️ Redis 不可用: {e}")
        print("💡 自动切换到内存存储模式")
        print("   提示：内存存储适合开发和测试，生产环境请使用 Redis")
        print("   启动 Redis: redis-server")
        print("   或使用 Docker: docker run -d -p 6379:6379 redis")
        
        # 降级到内存存储
        from .memory import MemoryStorage
        return MemoryStorage()


# 创建全局存储实例
approval_storage = create_storage()


__all__ = ['approval_storage', 'create_storage']
