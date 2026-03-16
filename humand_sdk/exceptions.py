"""
Humand SDK Exceptions
====================

Custom exceptions for the Humand SDK.
"""

from typing import Optional, Dict, Any


class HumandError(Exception):
    """Base exception for all Humand SDK errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigurationError(HumandError):
    """Raised when there's a configuration error."""
    pass


class APIError(HumandError):
    """Raised when there's an API communication error."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, 
                 response_data: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data or {}


class ApprovalRejected(HumandError):
    """Raised when an approval request is rejected."""
    
    def __init__(self, message: str, approval_id: str, 
                 rejected_by: Optional[str] = None, 
                 rejection_reason: Optional[str] = None):
        super().__init__(message)
        self.approval_id = approval_id
        self.rejected_by = rejected_by
        self.rejection_reason = rejection_reason


class ApprovalTimeout(HumandError):
    """Raised when an approval request times out."""
    
    def __init__(self, message: str, approval_id: str, timeout_seconds: int):
        super().__init__(message)
        self.approval_id = approval_id
        self.timeout_seconds = timeout_seconds


class ApprovalRequired(Exception):
    """
    Special exception that indicates approval is required.
    This is used internally by the decorator system.
    """
    
    def __init__(self, approval_id: str, approval_url: str, 
                 title: str, description: Optional[str] = None):
        self.approval_id = approval_id
        self.approval_url = approval_url
        self.title = title
        self.description = description
        super().__init__(f"Approval required: {title} (ID: {approval_id})")


class InvalidApprovalState(HumandError):
    """Raised when an approval is in an invalid state for the requested operation."""
    
    def __init__(self, message: str, approval_id: str, current_state: str):
        super().__init__(message)
        self.approval_id = approval_id
        self.current_state = current_state


class RateLimitExceeded(APIError):
    """Raised when API rate limits are exceeded."""
    
    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message, status_code=429)
        self.retry_after = retry_after
