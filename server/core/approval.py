import asyncio
import uuid
from datetime import datetime
from functools import wraps
from typing import Callable, Dict, Any, Optional
from .models import ApprovalStatus
from .service import approval_service
from ..storage import approval_storage
from ..utils.config import config

class ApprovalRequired(Exception):
    """需要审批的异常"""
    def __init__(self, message: str, request_id: str):
        self.message = message
        self.request_id = request_id
        super().__init__(message)

def require_approval(
    tool_name: str = None,
    timeout: int = None,
    auto_approve: bool = False,
    approvers: list = None
):
    """
    审批装饰器
    
    Args:
        tool_name: 工具名称，如果不提供则使用函数名
        timeout: 审批超时时间(秒)，如果不提供则使用默认配置
        auto_approve: 是否自动批准（用于测试）
        approvers: 特定的审批人列表
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await _handle_approval(func, tool_name, timeout, auto_approve, approvers, args, kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return asyncio.run(_handle_approval(func, tool_name, timeout, auto_approve, approvers, args, kwargs))
        
        # 根据函数是否为协程选择包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

async def _handle_approval(
    func: Callable,
    tool_name: str,
    timeout: int,
    auto_approve: bool,
    approvers: list,
    args: tuple,
    kwargs: dict
) -> Any:
    """处理审批逻辑"""
    
    # 获取工具名称
    actual_tool_name = tool_name or func.__name__
    
    # 生成请求ID
    request_id = str(uuid.uuid4())
    
    # 获取请求者信息（可以从参数中提取或使用默认值）
    requester = kwargs.get('requester', 'AI Agent')
    reason = kwargs.get('reason', f'执行工具: {actual_tool_name}')
    
    # 如果启用自动批准（测试模式）
    if auto_approve:
        print(f"[自动批准] 工具 {actual_tool_name} 已自动批准执行")
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)
    
    approval_request = approval_service.create_request(
        title=actual_tool_name,
        description=reason,
        requester=requester,
        metadata=_extract_tool_params(args, kwargs),
        approvers=approvers or config.get_approvers(),
        timeout_seconds=timeout or config.APPROVAL_TIMEOUT,
    )
    request_id = approval_request.request_id
    
    # 抛出审批异常，让调用者知道需要等待审批
    raise ApprovalRequired(
        f"工具 {actual_tool_name} 需要审批，请求ID: {request_id}",
        request_id
    )

def _extract_tool_params(args: tuple, kwargs: dict) -> Dict[str, Any]:
    """提取工具参数"""
    params = {}
    
    # 添加位置参数
    if args:
        for i, arg in enumerate(args):
            params[f"arg_{i}"] = str(arg)
    
    # 添加关键字参数（过滤掉内部参数）
    internal_params = {'requester', 'reason'}
    for key, value in kwargs.items():
        if key not in internal_params:
            params[key] = str(value)
    
    return params

async def wait_for_approval(request_id: str, check_interval: int = 5) -> bool:
    """
    等待审批结果
    
    Args:
        request_id: 审批请求ID
        check_interval: 检查间隔(秒)
    
    Returns:
        bool: 是否获得批准
    """
    while True:
        request = approval_storage.get_approval_request(request_id)
        
        if not request:
            print(f"审批请求 {request_id} 不存在")
            return False
        
        if request.status == ApprovalStatus.APPROVED:
            print(f"审批请求 {request_id} 已获得批准")
            return True
        elif request.status == ApprovalStatus.REJECTED:
            print(f"审批请求 {request_id} 已被拒绝: {request.approval_comment}")
            return False
        elif request.status == ApprovalStatus.TIMEOUT:
            print(f"审批请求 {request_id} 已超时")
            return False
        
        # 等待一段时间后再检查
        await asyncio.sleep(check_interval)

def execute_with_approval(func: Callable, *args, **kwargs) -> Any:
    """
    执行带审批的函数
    
    这是一个便捷函数，用于处理审批流程
    """
    try:
        if asyncio.iscoroutinefunction(func):
            return asyncio.run(func(*args, **kwargs))
        else:
            return func(*args, **kwargs)
    except ApprovalRequired as e:
        print(f"需要审批: {e.message}")
        print(f"请求ID: {e.request_id}")
        print("等待审批中...")
        
        # 等待审批结果
        approved = asyncio.run(wait_for_approval(e.request_id))
        
        if approved:
            print("审批通过，执行工具...")
            # 重新执行函数（这次应该不会触发审批）
            if asyncio.iscoroutinefunction(func):
                return asyncio.run(func(*args, **kwargs))
            else:
                return func(*args, **kwargs)
        else:
            print("审批被拒绝或超时，取消执行")
            return None 
