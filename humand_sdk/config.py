"""
Humand SDK Configuration
=======================

Configuration classes and utilities for the Humand SDK.
"""

from typing import List, Optional, Dict, Any, Union
from dataclasses import dataclass, field
from enum import Enum


class NotificationChannel(str, Enum):
    """Supported notification channels."""
    EMAIL = "email"
    SLACK = "slack"
    TEAMS = "teams"
    WEBHOOK = "webhook"
    WECHAT = "wechat"
    FEISHU = "feishu"
    DINGTALK = "dingtalk"


class ApprovalType(str, Enum):
    """Types of approval requests."""
    GENERAL = "general"
    DATA_ACCESS = "data_access"
    DATA_DELETION = "data_deletion"
    SYSTEM_OPERATION = "system_operation"
    FINANCIAL = "financial"
    SECURITY = "security"
    CONTENT_PUBLICATION = "content_publication"


@dataclass
class NotificationConfig:
    """Configuration for notifications."""
    
    channels: List[NotificationChannel] = field(default_factory=lambda: [NotificationChannel.EMAIL])
    email_settings: Optional[Dict[str, Any]] = None
    slack_settings: Optional[Dict[str, Any]] = None
    webhook_settings: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.channels:
            raise ValueError("At least one notification channel must be specified")


@dataclass
class EscalationRule:
    """Configuration for approval escalation."""
    
    timeout_seconds: int
    escalate_to: List[str]
    notification_message: Optional[str] = None
    
    def __post_init__(self):
        """Validate escalation rule."""
        if self.timeout_seconds <= 0:
            raise ValueError("Timeout must be positive")
        if not self.escalate_to:
            raise ValueError("Escalation targets must be specified")


@dataclass
class ApprovalConfig:
    """Main configuration for approval requests."""
    
    # Basic settings
    title: str
    approvers: List[str]
    description: Optional[str] = None
    approval_type: ApprovalType = ApprovalType.GENERAL
    
    # Timing
    timeout_seconds: int = 3600  # 1 hour default
    
    # Requirements
    require_all_approvers: bool = False
    require_comment: bool = False
    allow_self_approval: bool = False
    
    # Escalation
    escalation_rules: List[EscalationRule] = field(default_factory=list)
    
    # Notifications
    notification_config: NotificationConfig = field(default_factory=NotificationConfig)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.title.strip():
            raise ValueError("Title cannot be empty")
        if not self.approvers:
            raise ValueError("At least one approver must be specified")
        if self.timeout_seconds <= 0:
            raise ValueError("Timeout must be positive")
    
    @classmethod
    def simple(cls, title: str, approvers: Union[str, List[str]], 
               timeout_seconds: int = 3600, **kwargs) -> 'ApprovalConfig':
        """Create a simple approval configuration."""
        if isinstance(approvers, str):
            approvers = [approvers]
        
        return cls(
            title=title,
            approvers=approvers,
            timeout_seconds=timeout_seconds,
            **kwargs
        )
    
    @classmethod
    def data_access(cls, title: str, approvers: Union[str, List[str]], 
                   data_description: str, **kwargs) -> 'ApprovalConfig':
        """Create a data access approval configuration."""
        if isinstance(approvers, str):
            approvers = [approvers]
        
        return cls(
            title=title,
            approvers=approvers,
            approval_type=ApprovalType.DATA_ACCESS,
            description=f"Data access request: {data_description}",
            require_comment=True,
            **kwargs
        )
    
    @classmethod
    def financial(cls, title: str, approvers: Union[str, List[str]], 
                 amount: float, currency: str = "USD", **kwargs) -> 'ApprovalConfig':
        """Create a financial approval configuration."""
        if isinstance(approvers, str):
            approvers = [approvers]
        
        return cls(
            title=title,
            approvers=approvers,
            approval_type=ApprovalType.FINANCIAL,
            description=f"Financial approval for {currency} {amount:,.2f}",
            require_comment=True,
            metadata={"amount": amount, "currency": currency},
            **kwargs
        )


@dataclass
class HumandClientConfig:
    """Configuration for the Humand client."""
    
    api_key: str
    base_url: str = "http://localhost:8000"
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # Default approval settings
    default_timeout: int = 3600
    default_notification_channels: List[NotificationChannel] = field(
        default_factory=lambda: [NotificationChannel.EMAIL]
    )
    
    def __post_init__(self):
        """Validate client configuration."""
        # API key is optional for local server connections
        if self.base_url.startswith("https://") and not self.api_key.strip():
            raise ValueError("API key is required for remote connections")
        if not self.base_url.strip():
            raise ValueError("Base URL cannot be empty")
        if self.timeout <= 0:
            raise ValueError("Timeout must be positive")
        if self.max_retries < 0:
            raise ValueError("Max retries cannot be negative")
