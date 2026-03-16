import redis
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from ..core.models import ApprovalRequest, ApprovalStatus
from ..utils.config import config

class ApprovalStorage:
    def __init__(self):
        self.redis_client = redis.Redis(
            host=config.REDIS_HOST,
            port=config.REDIS_PORT,
            db=config.REDIS_DB,
            decode_responses=True
        )
        # 索引列表：用于历史/统计（key 本身会过期，列表里会残留无效 id，读取时会清理）
        self._all_ids_key = "approvals_all"
        self._pending_ids_key = "pending_approvals"
    
    def save_approval_request(self, request: ApprovalRequest) -> bool:
        """保存审批请求"""
        try:
            key = f"approval:{request.request_id}"
            data = request.model_dump_json()
            # 设置过期时间
            self.redis_client.setex(key, config.APPROVAL_TIMEOUT, data)
            
            # 添加到待审批列表
            self.redis_client.lrem(self._pending_ids_key, 0, request.request_id)
            self.redis_client.lpush(self._pending_ids_key, request.request_id)

            # 维护全量索引（用于历史/统计）
            self.redis_client.lrem(self._all_ids_key, 0, request.request_id)
            self.redis_client.lpush(self._all_ids_key, request.request_id)
            # 控制列表长度，避免无限增长（MVP 默认保留最近 5000 条）
            self.redis_client.ltrim(self._all_ids_key, 0, 4999)
            
            return True
        except Exception as e:
            print(f"Error saving approval request: {e}")
            return False
    
    def get_approval_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """获取审批请求"""
        try:
            key = f"approval:{request_id}"
            data = self.redis_client.get(key)
            if data:
                return ApprovalRequest.model_validate_json(data)
            return None
        except Exception as e:
            print(f"Error getting approval request: {e}")
            return None
    
    def update_approval_status(self, request_id: str, status: ApprovalStatus, 
                             approver: str = None, comment: str = None) -> bool:
        """更新审批状态"""
        try:
            request = self.get_approval_request(request_id)
            if not request:
                return False
            
            request.status = status
            current_time = datetime.now()
            
            # 根据状态更新相应字段
            if status == ApprovalStatus.APPROVED:
                if approver and approver not in request.approved_by:
                    request.approved_by.append(approver)
                request.approved_at = current_time
            elif status == ApprovalStatus.REJECTED:
                if approver and approver not in request.rejected_by:
                    request.rejected_by.append(approver)
                request.rejected_at = current_time
            
            # 添加评论
            if comment:
                request.comments.append({
                    "user": approver or "System",
                    "content": comment,
                    "timestamp": current_time.isoformat()
                })
            
            # 保持向后兼容
            request.approver = approver
            request.approval_comment = comment
            
            # 更新存储
            key = f"approval:{request_id}"
            self.redis_client.setex(key, config.APPROVAL_TIMEOUT, request.model_dump_json())
            
            # 从待审批列表移除
            if status != ApprovalStatus.PENDING:
                self.redis_client.lrem(self._pending_ids_key, 0, request_id)
            
            return True
        except Exception as e:
            print(f"Error updating approval status: {e}")
            return False
    
    def get_pending_approvals(self) -> List[ApprovalRequest]:
        """获取所有待审批的请求"""
        try:
            pending_ids = self.redis_client.lrange(self._pending_ids_key, 0, -1)
            requests = []
            
            for request_id in pending_ids:
                request = self.get_approval_request(request_id)
                if request and request.status == ApprovalStatus.PENDING:
                    # 检查是否超时
                    if datetime.now() - request.created_at > timedelta(seconds=config.APPROVAL_TIMEOUT):
                        self.update_approval_status(request_id, ApprovalStatus.TIMEOUT)
                    else:
                        requests.append(request)
                else:
                    # 清理无效的请求ID
                    self.redis_client.lrem(self._pending_ids_key, 0, request_id)
            
            return requests
        except Exception as e:
            print(f"Error getting pending approvals: {e}")
            return []

    def get_all_approvals(self, limit: int = 100) -> List[ApprovalRequest]:
        """获取所有审批请求（按创建时间倒序）"""
        try:
            ids = self.redis_client.lrange(self._all_ids_key, 0, max(limit - 1, 0))
            result: List[ApprovalRequest] = []
            for request_id in ids:
                req = self.get_approval_request(request_id)
                if req:
                    result.append(req)
                else:
                    # 清理已过期或丢失的 ID
                    self.redis_client.lrem(self._all_ids_key, 0, request_id)

            # created_at 倒序（列表本身也是倒序，但这里做一次兜底排序）
            result.sort(key=lambda r: r.created_at, reverse=True)
            return result
        except Exception as e:
            print(f"Error getting all approvals: {e}")
            return []

    def delete_approval_request(self, request_id: str) -> bool:
        """删除审批请求"""
        try:
            key = f"approval:{request_id}"
            self.redis_client.delete(key)
            self.redis_client.lrem(self._pending_ids_key, 0, request_id)
            self.redis_client.lrem(self._all_ids_key, 0, request_id)
            return True
        except Exception as e:
            print(f"Error deleting approval request: {e}")
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息（近似：基于索引列表中可读取的数据）"""
        try:
            approvals = self.get_all_approvals(limit=5000)
            total = len(approvals)
            pending = sum(1 for r in approvals if r.status == ApprovalStatus.PENDING)
            approved = sum(1 for r in approvals if r.status == ApprovalStatus.APPROVED)
            rejected = sum(1 for r in approvals if r.status == ApprovalStatus.REJECTED)
            timeout = sum(1 for r in approvals if r.status == ApprovalStatus.TIMEOUT)
            return {
                "total": total,
                "pending": pending,
                "approved": approved,
                "rejected": rejected,
                "timeout": timeout,
                "approval_rate": round(approved / total * 100, 2) if total > 0 else 0,
                "storage_type": "redis",
            }
        except Exception as e:
            print(f"Error getting statistics: {e}")
            return {}

    def ping(self) -> bool:
        """检查 Redis 是否可用"""
        try:
            return bool(self.redis_client.ping())
        except Exception:
            return False

    def clear_all(self) -> bool:
        """清空所有数据（仅用于测试/开发）"""
        try:
            # 删除索引列表
            self.redis_client.delete(self._pending_ids_key)
            self.redis_client.delete(self._all_ids_key)

            # 删除所有审批 key（使用 scan 避免阻塞）
            for key in self.redis_client.scan_iter(match="approval:*", count=200):
                self.redis_client.delete(key)
            return True
        except Exception as e:
            print(f"Error clearing approvals: {e}")
            return False
    
    def cleanup_expired_requests(self):
        """清理过期的审批请求"""
        try:
            pending_ids = self.redis_client.lrange(self._pending_ids_key, 0, -1)
            for request_id in pending_ids:
                if not self.redis_client.exists(f"approval:{request_id}"):
                    self.redis_client.lrem(self._pending_ids_key, 0, request_id)
        except Exception as e:
            print(f"Error cleaning up expired requests: {e}")

# 全局存储实例
approval_storage = ApprovalStorage() 
