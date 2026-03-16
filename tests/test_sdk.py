"""
SDK 单元测试
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from humand_sdk import HumandClient, require_approval, ApprovalConfig
from humand_sdk.exceptions import ApprovalRejected, ApprovalTimeout, APIError
from humand_sdk.config import HumandClientConfig


class TestHumandClient:
    """测试 HumandClient"""
    
    def test_client_initialization(self):
        """测试客户端初始化"""
        client = HumandClient(base_url="http://localhost:8000")
        assert client.config.base_url == "http://localhost:8000"
    
    def test_client_with_config(self):
        """测试使用配置对象初始化"""
        config = HumandClientConfig(
            base_url="http://test.com",
            api_key="test-key"
        )
        client = HumandClient(config=config)
        assert client.config.base_url == "http://test.com"
        assert client.config.api_key == "test-key"
    
    @patch('requests.Session.post')
    def test_create_approval(self, mock_post):
        """测试创建审批请求"""
        # Mock 响应
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": "test-123",
            "title": "Test Approval",
            "status": "pending",
            "approvers": ["admin@test.com"],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "web_url": "http://localhost:8000/approval/test-123"
        }
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        # 创建客户端和审批配置
        client = HumandClient(base_url="http://localhost:8000")
        config = ApprovalConfig.simple(
            title="Test Approval",
            approvers=["admin@test.com"]
        )
        
        # 创建审批请求
        request = client.create_approval(config, context={"test": "data"})
        
        assert request.id == "test-123"
        assert request.title == "Test Approval"
        assert request.status == "pending"
    
    @patch('requests.Session.get')
    def test_get_approval_status(self, mock_get):
        """测试获取审批状态"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": "test-123",
            "title": "Test",
            "status": "approved",
            "approvers": ["admin@test.com"],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        client = HumandClient(base_url="http://localhost:8000")
        request = client.get_approval("test-123")
        
        assert request.id == "test-123"
        assert request.is_approved


class TestApprovalConfig:
    """测试 ApprovalConfig"""
    
    def test_simple_config(self):
        """测试简单配置"""
        config = ApprovalConfig.simple(
            title="Test",
            approvers=["user@test.com"]
        )
        
        assert config.title == "Test"
        assert "user@test.com" in config.approvers
        assert config.timeout_seconds == 3600
    
    def test_custom_config(self):
        """测试自定义配置"""
        config = ApprovalConfig.custom(
            title="Custom Test",
            approvers=["user1@test.com", "user2@test.com"],
            timeout_seconds=7200,
            require_all_approvers=True
        )
        
        assert config.title == "Custom Test"
        assert len(config.approvers) == 2
        assert config.timeout_seconds == 7200
        assert config.require_all_approvers is True


class TestRequireApprovalDecorator:
    """测试 @require_approval 装饰器"""
    
    @patch('humand_sdk.decorators.HumandClient')
    def test_decorator_basic(self, mock_client_class):
        """测试基本装饰器功能"""
        # Mock 客户端
        mock_client = Mock()
        mock_request = Mock()
        mock_request.id = "test-123"
        mock_request.is_approved = True
        mock_client.create_approval.return_value = mock_request
        mock_client.wait_for_approval.return_value = mock_request
        mock_client_class.return_value = mock_client
        
        # 使用装饰器
        @require_approval(
            title="Test Function",
            approvers=["admin@test.com"]
        )
        def test_function(x, y):
            return x + y
        
        # 执行函数
        result = test_function(2, 3)
        
        assert result == 5
        assert mock_client.create_approval.called
    
    @patch('humand_sdk.decorators.HumandClient')
    def test_decorator_rejection(self, mock_client_class):
        """测试审批被拒绝"""
        mock_client = Mock()
        mock_request = Mock()
        mock_request.id = "test-123"
        mock_request.is_rejected = True
        mock_request.is_approved = False
        mock_client.create_approval.return_value = mock_request
        mock_client.wait_for_approval.return_value = mock_request
        mock_client_class.return_value = mock_client
        
        @require_approval(title="Test", approvers=["admin@test.com"])
        def test_function():
            return "success"
        
        # 应该抛出 ApprovalRejected 异常
        with pytest.raises(ApprovalRejected):
            test_function()
    
    @patch('humand_sdk.decorators.HumandClient')
    def test_decorator_with_context(self, mock_client_class):
        """测试带上下文的装饰器"""
        mock_client = Mock()
        mock_request = Mock()
        mock_request.id = "test-123"
        mock_request.is_approved = True
        mock_client.create_approval.return_value = mock_request
        mock_client.wait_for_approval.return_value = mock_request
        mock_client_class.return_value = mock_client
        
        @require_approval(
            title="Test",
            approvers=["admin@test.com"],
            context_builder=lambda *args, **kwargs: {"args": args, "kwargs": kwargs}
        )
        def test_function(a, b, c=None):
            return f"{a}-{b}-{c}"
        
        result = test_function(1, 2, c=3)
        
        assert result == "1-2-3"
        
        # 检查上下文是否正确传递
        call_args = mock_client.create_approval.call_args
        context = call_args[1]['context']
        assert 'args' in context
        assert 'kwargs' in context


class TestExceptions:
    """测试异常类"""
    
    def test_approval_rejected(self):
        """测试 ApprovalRejected 异常"""
        error = ApprovalRejected("test-123", "Not allowed")
        assert "test-123" in str(error)
        assert "Not allowed" in str(error)
    
    def test_approval_timeout(self):
        """测试 ApprovalTimeout 异常"""
        error = ApprovalTimeout("test-123", 3600)
        assert "test-123" in str(error)
        assert "3600" in str(error)
    
    def test_api_error(self):
        """测试 APIError 异常"""
        error = APIError(500, "Server Error")
        assert error.status_code == 500
        assert "Server Error" in str(error)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

