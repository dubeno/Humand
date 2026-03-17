"""
Humand SDK Client
================

Main client for interacting with the Humand API.
"""

import time
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import HumandClientConfig, ApprovalConfig
from .exceptions import (
    APIError, 
    ApprovalRejected, 
    ApprovalTimeout,
    RateLimitExceeded,
    InvalidApprovalState
)


class ApprovalRequest:
    """Represents an approval request."""
    
    def __init__(self, data: Dict[str, Any]):
        self.id = data["id"]
        self.title = data["title"]
        self.description = data.get("description")
        self.status = data["status"]
        self.approvers = data["approvers"]
        self.created_at = datetime.fromisoformat(data["created_at"])
        self.updated_at = datetime.fromisoformat(data["updated_at"])
        self.approved_by = data.get("approved_by", [])
        self.rejected_by = data.get("rejected_by", [])
        self.comments = data.get("comments", [])
        self.metadata = data.get("metadata", {})
        self.progress_updates = data.get("progress_updates", [])
        self.notification_channels = data.get("notification_channels", [])
        self.provider_metadata = data.get("provider_metadata", {})
        self.web_url = data.get("web_url")
        
    @property
    def is_pending(self) -> bool:
        """Check if the approval is still pending."""
        return self.status == "pending"
    
    @property
    def is_approved(self) -> bool:
        """Check if the approval has been approved."""
        return self.status == "approved"
    
    @property
    def is_rejected(self) -> bool:
        """Check if the approval has been rejected."""
        return self.status == "rejected"
    
    @property
    def is_timeout(self) -> bool:
        """Check if the approval has timed out."""
        return self.status == "timeout"
    
    def __repr__(self):
        return f"ApprovalRequest(id='{self.id}', title='{self.title}', status='{self.status}')"


class HumandClient:
    """Main client for the Humand API."""
    
    def __init__(self, config: Optional[HumandClientConfig] = None, 
                 api_key: Optional[str] = None, base_url: Optional[str] = None):
        """
        Initialize the Humand client.
        
        Args:
            config: Full configuration object
            api_key: API key (alternative to config)
            base_url: Base URL (alternative to config)
        """
        if config:
            self.config = config
        else:
            self.config = HumandClientConfig(
                api_key=api_key or "",
                base_url=base_url or "https://api.humand.io"
            )
        
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """Create a configured requests session."""
        session = requests.Session()
        
        # Set up retries
        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=self.config.retry_delay,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set default headers
        session.headers.update({
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "humand-sdk/0.1.0"
        })
        
        return session
    
    def _make_request(self, method: str, endpoint: str, 
                     data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make an API request."""
        url = f"{self.config.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        try:
            if method.upper() == "GET":
                response = self.session.get(url, timeout=self.config.timeout)
            elif method.upper() == "POST":
                response = self.session.post(url, json=data, timeout=self.config.timeout)
            elif method.upper() == "PUT":
                response = self.session.put(url, json=data, timeout=self.config.timeout)
            elif method.upper() == "DELETE":
                response = self.session.delete(url, timeout=self.config.timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                raise RateLimitExceeded(
                    "API rate limit exceeded", 
                    retry_after=retry_after
                )
            
            # Handle other errors
            if not response.ok:
                error_data = {}
                try:
                    error_data = response.json()
                except:
                    pass
                
                raise APIError(
                    f"API request failed: {response.status_code} {response.reason}",
                    status_code=response.status_code,
                    response_data=error_data
                )
            
            return response.json()
            
        except requests.RequestException as e:
            raise APIError(f"Request failed: {str(e)}")
    
    def create_approval(self, config: ApprovalConfig, 
                       context: Optional[Dict[str, Any]] = None) -> ApprovalRequest:
        """
        Create a new approval request.
        
        Args:
            config: Approval configuration
            context: Additional context data
            
        Returns:
            ApprovalRequest object
        """
        data = {
            "title": config.title,
            "description": config.description,
            "approvers": config.approvers,
            "approval_type": config.approval_type.value,
            "timeout_seconds": config.timeout_seconds,
            "require_all_approvers": config.require_all_approvers,
            "require_comment": config.require_comment,
            "allow_self_approval": config.allow_self_approval,
            "metadata": {**config.metadata, **(context or {})},
            "tags": config.tags,
            "notification_config": {
                "channels": [ch.value for ch in config.notification_config.channels]
            }
        }
        
        if config.escalation_rules:
            data["escalation_rules"] = [
                {
                    "timeout_seconds": rule.timeout_seconds,
                    "escalate_to": rule.escalate_to,
                    "notification_message": rule.notification_message
                }
                for rule in config.escalation_rules
            ]
        
        response_data = self._make_request("POST", "/api/v1/approvals", data)
        return ApprovalRequest(response_data)
    
    def get_approval(self, approval_id: str) -> ApprovalRequest:
        """
        Get an approval request by ID.
        
        Args:
            approval_id: The approval request ID
            
        Returns:
            ApprovalRequest object
        """
        response_data = self._make_request("GET", f"/api/v1/approvals/{approval_id}")
        return ApprovalRequest(response_data)

    def send_progress_update(
        self,
        approval_id: str,
        message: str,
        progress_percent: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        stage: Optional[str] = None,
    ) -> ApprovalRequest:
        """Send a progress update associated with an approval request."""
        response_data = self._make_request(
            "POST",
            f"/api/v1/approvals/{approval_id}/progress",
            {
                "message": message,
                "progress_percent": progress_percent,
                "stage": stage,
                "metadata": metadata or {},
            },
        )
        return ApprovalRequest(response_data)
    
    def wait_for_approval(self, approval_id: str, 
                         timeout_seconds: Optional[int] = None,
                         poll_interval: int = 5) -> ApprovalRequest:
        """
        Wait for an approval to be completed.
        
        Args:
            approval_id: The approval request ID
            timeout_seconds: Maximum time to wait (uses approval timeout if not specified)
            poll_interval: How often to check status (seconds)
            
        Returns:
            ApprovalRequest object
            
        Raises:
            ApprovalRejected: If the approval is rejected
            ApprovalTimeout: If the approval times out
        """
        start_time = time.time()
        
        while True:
            approval = self.get_approval(approval_id)
            
            if approval.is_approved:
                return approval
            elif approval.is_rejected:
                raise ApprovalRejected(
                    f"Approval {approval_id} was rejected",
                    approval_id=approval_id,
                    rejected_by=approval.rejected_by[0] if approval.rejected_by else None,
                    rejection_reason=approval.comments[-1].get("content") if approval.comments else None
                )
            elif approval.is_timeout:
                raise ApprovalTimeout(
                    f"Approval {approval_id} timed out",
                    approval_id=approval_id,
                    timeout_seconds=timeout_seconds or 3600
                )
            
            # Check our own timeout
            if timeout_seconds:
                elapsed = time.time() - start_time
                if elapsed >= timeout_seconds:
                    raise ApprovalTimeout(
                        f"Waiting for approval {approval_id} timed out after {elapsed:.1f} seconds",
                        approval_id=approval_id,
                        timeout_seconds=timeout_seconds
                    )
            
            time.sleep(poll_interval)
    
    def list_approvals(self, status: Optional[str] = None, 
                      limit: int = 100, offset: int = 0) -> List[ApprovalRequest]:
        """
        List approval requests.
        
        Args:
            status: Filter by status (pending, approved, rejected, timeout)
            limit: Maximum number of results
            offset: Offset for pagination
            
        Returns:
            List of ApprovalRequest objects
        """
        params = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        
        endpoint = "/api/v1/approvals"
        if params:
            param_str = "&".join(f"{k}={v}" for k, v in params.items())
            endpoint += f"?{param_str}"
        
        response_data = self._make_request("GET", endpoint)
        return [ApprovalRequest(item) for item in response_data["items"]]
    
    def cancel_approval(self, approval_id: str, reason: Optional[str] = None) -> ApprovalRequest:
        """
        Cancel a pending approval request.
        
        Args:
            approval_id: The approval request ID
            reason: Reason for cancellation
            
        Returns:
            ApprovalRequest object
        """
        data = {"reason": reason} if reason else {}
        response_data = self._make_request("POST", f"/api/v1/approvals/{approval_id}/cancel", data)
        return ApprovalRequest(response_data)
