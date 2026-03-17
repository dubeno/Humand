"""
Humand SDK Decorators
====================

Decorators for adding approval requirements to functions.
"""

import functools
import inspect
from typing import Callable, Optional, List, Dict, Any, Union

from .client import HumandClient
from .config import ApprovalConfig, HumandClientConfig
from .exceptions import ApprovalRequired, ApprovalRejected, ApprovalTimeout, ConfigurationError


def require_approval(
    title: Optional[str] = None,
    approvers: Optional[Union[str, List[str]]] = None,
    description: Optional[str] = None,
    timeout_seconds: int = 3600,
    client: Optional[HumandClient] = None,
    config: Optional[ApprovalConfig] = None,
    approval_type: str = "general",
    require_comment: bool = False,
    metadata_extractor: Optional[Callable] = None,
    context_builder: Optional[Callable] = None,
    sync: bool = True,
    auto_approve_conditions: Optional[Callable] = None
):
    """
    Decorator that requires approval before executing a function.
    
    Args:
        title: Title for the approval request (defaults to function name)
        approvers: List of approver email addresses
        description: Description of what needs approval
        timeout_seconds: How long to wait for approval
        client: Humand client instance
        config: Full approval configuration (overrides other params)
        approval_type: Type of approval request
        require_comment: Whether approvers must provide a comment
        metadata_extractor: Function to extract metadata from function args
        sync: Whether to wait synchronously for approval
        auto_approve_conditions: Function to check if auto-approval should apply
    
    Usage:
        @require_approval(
            title="Delete User Data",
            approvers=["manager@company.com", "dpo@company.com"],
            timeout_seconds=3600
        )
        def delete_user_data(user_id: str):
            return perform_deletion(user_id)
    """
    
    def decorator(func: Callable) -> Callable:
        # Validate configuration
        if config is None and not approvers:
            raise ConfigurationError("Either 'config' or 'approvers' must be provided")
        
        # Get or create client
        nonlocal client
        if client is None:
            # Try to get client from environment
            try:
                import os
                server_url = os.getenv("HUMAND_SERVER_URL", "http://localhost:8000")
                client = HumandClient(base_url=server_url)
            except Exception as e:
                raise ConfigurationError(f"No Humand client configured. Please provide a client or set HUMAND_SERVER_URL environment variable: {e}")
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Extract function metadata
            func_title = title or f"Execute {func.__name__}"
            func_description = description or f"Approval required to execute {func.__name__}"
            
            # Check auto-approve conditions
            if auto_approve_conditions and auto_approve_conditions(*args, **kwargs):
                print(f"🚀 Auto-approved: {func_title}")
                return func(*args, **kwargs)
            
            # Extract metadata if extractor provided
            metadata = {}
            extractor = metadata_extractor or context_builder
            if extractor:
                try:
                    if inspect.ismethod(extractor):
                        # Method extractor (has self parameter)
                        metadata = extractor(args[0] if args else None, *args, **kwargs)
                    else:
                        # Function extractor
                        metadata = extractor(*args, **kwargs)
                except Exception as e:
                    print(f"⚠️ Metadata extraction failed: {e}")
            
            # Add function signature to metadata
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            
            # Safely serialize function arguments, handling complex objects
            safe_args = {}
            for key, value in bound_args.arguments.items():
                try:
                    # Skip 'self' parameter for methods
                    if key == 'self':
                        safe_args[key] = f"<{value.__class__.__name__} instance>"
                        continue
                    
                    # Try to JSON serialize the value to check if it's safe
                    import json
                    json.dumps(value)
                    safe_args[key] = value
                except (TypeError, ValueError):
                    # If not JSON serializable, use string representation
                    safe_args[key] = str(value)
            
            metadata.update({
                "function_name": func.__name__,
                "function_args": safe_args,
                "function_module": func.__module__
            })
            
            # Create approval configuration
            if config:
                approval_config = config
            else:
                approver_list = approvers if isinstance(approvers, list) else [approvers]
                approval_config = ApprovalConfig(
                    title=func_title,
                    approvers=approver_list,
                    description=func_description,
                    timeout_seconds=timeout_seconds,
                    require_comment=require_comment,
                    metadata=metadata
                )
            
            try:
                # Create approval request
                print(f"📋 Creating approval request: {func_title}")
                approval_request = client.create_approval(approval_config, context=metadata)
                print(f"✅ Approval request created: {approval_request.id}")
                print(f"🔗 Approval URL: {approval_request.web_url}")
                
                if sync:
                    # Wait for approval synchronously
                    print(f"⏳ Waiting for approval...")
                    approved_request = client.wait_for_approval(
                        approval_request.id, 
                        timeout_seconds=timeout_seconds
                    )
                    if getattr(approved_request, "is_rejected", False) is True:
                        raise ApprovalRejected(
                            approval_request.id,
                            "Rejected",
                        )
                    if getattr(approved_request, "is_timeout", False) is True:
                        raise ApprovalTimeout(approval_request.id, timeout_seconds)

                    approved_by = getattr(approved_request, "approved_by", None) or []
                    if not isinstance(approved_by, list):
                        approved_by = [str(approved_by)]
                    approver_label = ", ".join(approved_by) if approved_by else "unknown approver"
                    print(f"✅ Approval granted by: {approver_label}")
                    
                    # Execute the original function
                    result = func(*args, **kwargs)
                    print(f"🎉 Function executed successfully")
                    return result
                else:
                    # Async mode - raise exception with approval info
                    raise ApprovalRequired(
                        approval_request.id,
                        approval_request.web_url,
                        func_title,
                        func_description
                    )
                    
            except (ApprovalRejected, ApprovalTimeout) as e:
                print(f"❌ Approval failed: {e}")
                raise
            except Exception as e:
                print(f"💥 Unexpected error during approval: {e}")
                raise
        
        # Add approval metadata to the function
        wrapper._humand_approval_config = config or ApprovalConfig.simple(
            title="Auto Approval",
            approvers=["system@humand.io"],
            description="Default approval config for SDK"
        )
        wrapper._humand_client = client
        wrapper._is_approval_required = True
        
        return wrapper
    
    return decorator


def approval_required(func: Callable) -> bool:
    """Check if a function requires approval."""
    return getattr(func, '_is_approval_required', False)


def get_approval_config(func: Callable) -> Optional[ApprovalConfig]:
    """Get the approval configuration for a function."""
    return getattr(func, '_humand_approval_config', None)


# Production SDK - no mock implementations

# Convenience decorators for common scenarios
def require_data_access_approval(approvers: Union[str, List[str]], 
                                data_description: str, **kwargs):
    """Convenience decorator for data access approvals."""
    return require_approval(
        title=f"Data Access: {data_description}",
        approvers=approvers,
        approval_type="data_access",
        require_comment=True,
        **kwargs
    )


def require_financial_approval(approvers: Union[str, List[str]], 
                              amount: float, currency: str = "USD", **kwargs):
    """Convenience decorator for financial approvals."""
    return require_approval(
        title=f"Financial Approval: {currency} {amount:,.2f}",
        approvers=approvers,
        approval_type="financial",
        require_comment=True,
        metadata_extractor=lambda *args, **kwargs: {
            "amount": amount,
            "currency": currency
        },
        **kwargs
    )


def require_system_operation_approval(approvers: Union[str, List[str]], 
                                    operation_description: str, **kwargs):
    """Convenience decorator for system operation approvals."""
    return require_approval(
        title=f"System Operation: {operation_description}",
        approvers=approvers,
        approval_type="system_operation",
        require_comment=True,
        **kwargs
    )
