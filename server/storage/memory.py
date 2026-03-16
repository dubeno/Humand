"""
内存存储实现
============

当 Redis 不可用时的备用存储方案，适合开发和测试环境。
注意：数据只存在于内存中，重启后会丢失。
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from threading import Lock

from ..core.models import ApprovalRequest, ApprovalStatus


class MemoryStorage:
    """内存存储实现（线程安全）"""
    
    def __init__(self):
        """初始化内存存储"""
        self._approvals: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()
        print("⚠️ 使用内存存储模式（数据重启后会丢失）")
    
    def save_approval_request(self, request: ApprovalRequest) -> bool:
        """
        保存审批请求
        
        Args:
            request: 审批请求对象
            
        Returns:
            是否保存成功
        """
        try:
            with self._lock:
                approval_data = {
                    "request_id": request.request_id,
                    "tool_name": request.tool_name,
                    "tool_params": request.tool_params,
                    "requester": request.requester,
                    "reason": request.reason,
                    "approvers": request.approvers,
                    "request_time": request.request_time.isoformat(),
                    "created_at": request.created_at.isoformat(),
                    "status": request.status.value,
                    "approver": request.approver,
                    "approved_by": request.approved_by,
                    "rejected_by": request.rejected_by,
                    "approved_at": request.approved_at.isoformat() if request.approved_at else None,
                    "rejected_at": request.rejected_at.isoformat() if request.rejected_at else None,
                    "approval_comment": request.approval_comment,
                    "comments": request.comments,
                }
                
                self._approvals[request.request_id] = approval_data
                return True
                
        except Exception as e:
            print(f"❌ 保存审批请求失败: {e}")
            return False
    
    def get_approval_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """
        获取审批请求
        
        Args:
            request_id: 请求ID
            
        Returns:
            审批请求对象，如果不存在则返回 None
        """
        try:
            with self._lock:
                data = self._approvals.get(request_id)
                
                if not data:
                    return None
                
                # 将字典转换回对象
                return ApprovalRequest(
                    request_id=data["request_id"],
                    tool_name=data["tool_name"],
                    tool_params=data["tool_params"],
                    requester=data["requester"],
                    reason=data["reason"],
                    approvers=data.get("approvers", []),
                    request_time=datetime.fromisoformat(data["request_time"]),
                    created_at=datetime.fromisoformat(data["created_at"]),
                    status=ApprovalStatus(data["status"]),
                    approver=data["approver"],
                    approved_by=data["approved_by"],
                    rejected_by=data["rejected_by"],
                    approved_at=datetime.fromisoformat(data["approved_at"]) if data["approved_at"] else None,
                    rejected_at=datetime.fromisoformat(data["rejected_at"]) if data["rejected_at"] else None,
                    approval_comment=data["approval_comment"],
                    comments=data["comments"],
                )
                
        except Exception as e:
            print(f"❌ 获取审批请求失败: {e}")
            return None
    
    def get_pending_approvals(self) -> List[ApprovalRequest]:
        """
        获取所有待审批的请求
        
        Returns:
            待审批请求列表
        """
        try:
            with self._lock:
                pending_requests = []
                
                for request_id, data in self._approvals.items():
                    if data["status"] == ApprovalStatus.PENDING.value:
                        request = self.get_approval_request(request_id)
                        if request:
                            pending_requests.append(request)
                
                # 按创建时间倒序排序
                pending_requests.sort(key=lambda x: x.created_at, reverse=True)
                return pending_requests
                
        except Exception as e:
            print(f"❌ 获取待审批请求失败: {e}")
            return []
    
    def get_all_approvals(self, limit: int = 100) -> List[ApprovalRequest]:
        """
        获取所有审批请求
        
        Args:
            limit: 返回数量限制
            
        Returns:
            审批请求列表
        """
        try:
            with self._lock:
                all_requests = []
                
                for request_id in list(self._approvals.keys())[:limit]:
                    request = self.get_approval_request(request_id)
                    if request:
                        all_requests.append(request)
                
                # 按创建时间倒序排序
                all_requests.sort(key=lambda x: x.created_at, reverse=True)
                return all_requests
                
        except Exception as e:
            print(f"❌ 获取所有审批请求失败: {e}")
            return []
    
    def update_approval_status(self, request_id: str, status: ApprovalStatus, 
                              approver: str = "", comment: str = "") -> bool:
        """
        更新审批状态
        
        Args:
            request_id: 请求ID
            status: 新状态
            approver: 审批人
            comment: 审批意见
            
        Returns:
            是否更新成功
        """
        try:
            with self._lock:
                data = self._approvals.get(request_id)
                
                if not data:
                    print(f"❌ 审批请求不存在: {request_id}")
                    return False
                
                # 更新状态
                data["status"] = status.value
                data["approver"] = approver
                data["approval_comment"] = comment
                
                # 记录审批时间
                if status == ApprovalStatus.APPROVED:
                    data["approved_at"] = datetime.now().isoformat()
                    if approver and approver not in data["approved_by"]:
                        data["approved_by"].append(approver)
                elif status == ApprovalStatus.REJECTED:
                    data["rejected_at"] = datetime.now().isoformat()
                    if approver and approver not in data["rejected_by"]:
                        data["rejected_by"].append(approver)
                
                # 添加评论
                if comment:
                    data["comments"].append({
                        "approver": approver,
                        "comment": comment,
                        "timestamp": datetime.now().isoformat(),
                        "action": status.value
                    })
                
                return True
                
        except Exception as e:
            print(f"❌ 更新审批状态失败: {e}")
            return False
    
    def delete_approval_request(self, request_id: str) -> bool:
        """
        删除审批请求
        
        Args:
            request_id: 请求ID
            
        Returns:
            是否删除成功
        """
        try:
            with self._lock:
                if request_id in self._approvals:
                    del self._approvals[request_id]
                    return True
                return False
                
        except Exception as e:
            print(f"❌ 删除审批请求失败: {e}")
            return False
    
    def cleanup_old_approvals(self, days: int = 7) -> int:
        """
        清理旧的审批请求
        
        Args:
            days: 保留天数
            
        Returns:
            清理的请求数量
        """
        try:
            with self._lock:
                cutoff_time = datetime.now() - timedelta(days=days)
                to_delete = []
                
                for request_id, data in self._approvals.items():
                    created_at = datetime.fromisoformat(data["created_at"])
                    if created_at < cutoff_time:
                        to_delete.append(request_id)
                
                for request_id in to_delete:
                    del self._approvals[request_id]
                
                if to_delete:
                    print(f"🧹 清理了 {len(to_delete)} 个旧审批请求")
                
                return len(to_delete)
                
        except Exception as e:
            print(f"❌ 清理旧审批请求失败: {e}")
            return 0
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            统计信息字典
        """
        try:
            with self._lock:
                total = len(self._approvals)
                pending = sum(1 for d in self._approvals.values() if d["status"] == ApprovalStatus.PENDING.value)
                approved = sum(1 for d in self._approvals.values() if d["status"] == ApprovalStatus.APPROVED.value)
                rejected = sum(1 for d in self._approvals.values() if d["status"] == ApprovalStatus.REJECTED.value)
                timeout = sum(1 for d in self._approvals.values() if d["status"] == ApprovalStatus.TIMEOUT.value)
                
                return {
                    "total": total,
                    "pending": pending,
                    "approved": approved,
                    "rejected": rejected,
                    "timeout": timeout,
                    "approval_rate": round(approved / total * 100, 2) if total > 0 else 0,
                    "storage_type": "memory"
                }
                
        except Exception as e:
            print(f"❌ 获取统计信息失败: {e}")
            return {}
    
    def ping(self) -> bool:
        """
        检查存储是否可用
        
        Returns:
            是否可用
        """
        return True
    
    def clear_all(self) -> bool:
        """
        清空所有数据（仅用于测试）
        
        Returns:
            是否成功
        """
        try:
            with self._lock:
                self._approvals.clear()
                return True
        except Exception as e:
            print(f"❌ 清空数据失败: {e}")
            return False


# 创建全局内存存储实例
memory_storage = MemoryStorage()


