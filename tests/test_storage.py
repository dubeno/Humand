"""
存储模块单元测试
"""

import pytest
from datetime import datetime, timedelta
from server.core.models import ApprovalRequest, ApprovalStatus
from server.storage.memory import MemoryStorage


class TestMemoryStorage:
    """测试内存存储"""
    
    @pytest.fixture
    def storage(self):
        """创建存储实例"""
        return MemoryStorage()
    
    @pytest.fixture
    def sample_request(self):
        """创建示例审批请求"""
        return ApprovalRequest(
            request_id="test-123",
            tool_name="test_tool",
            tool_params={"param1": "value1"},
            requester="test-user",
            reason="test reason",
            request_time=datetime.now(),
            created_at=datetime.now(),
            status=ApprovalStatus.PENDING
        )
    
    def test_save_and_get(self, storage, sample_request):
        """测试保存和获取"""
        # 保存
        result = storage.save_approval_request(sample_request)
        assert result is True
        
        # 获取
        retrieved = storage.get_approval_request(sample_request.request_id)
        assert retrieved is not None
        assert retrieved.request_id == sample_request.request_id
        assert retrieved.tool_name == sample_request.tool_name
    
    def test_get_nonexistent(self, storage):
        """测试获取不存在的请求"""
        result = storage.get_approval_request("nonexistent-id")
        assert result is None
    
    def test_get_pending_approvals(self, storage):
        """测试获取待审批请求"""
        # 创建多个请求
        for i in range(3):
            request = ApprovalRequest(
                request_id=f"test-{i}",
                tool_name="test_tool",
                tool_params={},
                requester="test-user",
                reason="test",
                request_time=datetime.now(),
                created_at=datetime.now(),
                status=ApprovalStatus.PENDING
            )
            storage.save_approval_request(request)
        
        # 获取待审批请求
        pending = storage.get_pending_approvals()
        assert len(pending) == 3
    
    def test_update_status_approved(self, storage, sample_request):
        """测试更新为已批准状态"""
        # 保存请求
        storage.save_approval_request(sample_request)
        
        # 更新状态
        result = storage.update_approval_status(
            sample_request.request_id,
            ApprovalStatus.APPROVED,
            approver="admin@test.com",
            comment="Approved"
        )
        assert result is True
        
        # 验证更新
        updated = storage.get_approval_request(sample_request.request_id)
        assert updated.status == ApprovalStatus.APPROVED
        assert updated.approver == "admin@test.com"
        assert "admin@test.com" in updated.approved_by
        assert len(updated.comments) == 1
    
    def test_update_status_rejected(self, storage, sample_request):
        """测试更新为已拒绝状态"""
        storage.save_approval_request(sample_request)
        
        result = storage.update_approval_status(
            sample_request.request_id,
            ApprovalStatus.REJECTED,
            approver="admin@test.com",
            comment="Not allowed"
        )
        assert result is True
        
        updated = storage.get_approval_request(sample_request.request_id)
        assert updated.status == ApprovalStatus.REJECTED
        assert "admin@test.com" in updated.rejected_by

    def test_reject_after_approval_is_ignored(self, storage, sample_request):
        """测试终态后拒绝不会覆盖已批准结果"""
        storage.save_approval_request(sample_request)

        assert storage.update_approval_status(
            sample_request.request_id,
            ApprovalStatus.APPROVED,
            approver="admin@test.com",
            comment="Approved",
        ) is True

        assert storage.update_approval_status(
            sample_request.request_id,
            ApprovalStatus.REJECTED,
            approver="reviewer@test.com",
            comment="Too late",
        ) is False

        updated = storage.get_approval_request(sample_request.request_id)
        assert updated.status == ApprovalStatus.APPROVED
        assert "admin@test.com" in updated.approved_by
        assert "reviewer@test.com" not in updated.rejected_by
    
    def test_delete_request(self, storage, sample_request):
        """测试删除请求"""
        storage.save_approval_request(sample_request)
        
        result = storage.delete_approval_request(sample_request.request_id)
        assert result is True
        
        # 验证已删除
        retrieved = storage.get_approval_request(sample_request.request_id)
        assert retrieved is None
    
    def test_get_statistics(self, storage):
        """测试获取统计信息"""
        # 创建不同状态的请求
        statuses = [
            ApprovalStatus.PENDING,
            ApprovalStatus.PENDING,
            ApprovalStatus.APPROVED,
            ApprovalStatus.REJECTED
        ]
        
        for i, status in enumerate(statuses):
            request = ApprovalRequest(
                request_id=f"test-{i}",
                tool_name="test_tool",
                tool_params={},
                requester="test-user",
                reason="test",
                request_time=datetime.now(),
                created_at=datetime.now(),
                status=status
            )
            storage.save_approval_request(request)
        
        stats = storage.get_statistics()
        assert stats["total"] == 4
        assert stats["pending"] == 2
        assert stats["approved"] == 1
        assert stats["rejected"] == 1
        assert stats["storage_type"] == "memory"
    
    def test_cleanup_old_approvals(self, storage):
        """测试清理旧审批"""
        # 创建旧请求
        old_request = ApprovalRequest(
            request_id="old-request",
            tool_name="test_tool",
            tool_params={},
            requester="test-user",
            reason="test",
            request_time=datetime.now() - timedelta(days=10),
            created_at=datetime.now() - timedelta(days=10),
            status=ApprovalStatus.APPROVED
        )
        storage.save_approval_request(old_request)
        
        # 创建新请求
        new_request = ApprovalRequest(
            request_id="new-request",
            tool_name="test_tool",
            tool_params={},
            requester="test-user",
            reason="test",
            request_time=datetime.now(),
            created_at=datetime.now(),
            status=ApprovalStatus.PENDING
        )
        storage.save_approval_request(new_request)
        
        # 清理 7 天前的请求
        cleaned = storage.cleanup_old_approvals(days=7)
        assert cleaned == 1
        
        # 验证旧请求已删除，新请求仍存在
        assert storage.get_approval_request("old-request") is None
        assert storage.get_approval_request("new-request") is not None
    
    def test_ping(self, storage):
        """测试连接检查"""
        assert storage.ping() is True
    
    def test_clear_all(self, storage):
        """测试清空所有数据"""
        # 添加一些数据
        for i in range(3):
            request = ApprovalRequest(
                request_id=f"test-{i}",
                tool_name="test_tool",
                tool_params={},
                requester="test-user",
                reason="test",
                request_time=datetime.now(),
                created_at=datetime.now(),
                status=ApprovalStatus.PENDING
            )
            storage.save_approval_request(request)
        
        # 清空
        result = storage.clear_all()
        assert result is True
        
        # 验证已清空
        stats = storage.get_statistics()
        assert stats["total"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

