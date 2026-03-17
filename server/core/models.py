from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"

class ApprovalRequest(BaseModel):
    request_id: str
    tool_name: str
    tool_params: Dict[str, Any]
    requester: str
    reason: str
    approvers: List[str] = Field(default_factory=list)
    request_time: datetime
    created_at: datetime
    updated_at: datetime = Field(default_factory=datetime.now)
    timeout_seconds: Optional[int] = None
    status: ApprovalStatus = ApprovalStatus.PENDING
    approver: Optional[str] = None
    approved_by: List[str] = Field(default_factory=list)
    rejected_by: List[str] = Field(default_factory=list)
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    approval_comment: Optional[str] = None
    comments: List[Dict[str, Any]] = Field(default_factory=list)
    progress_updates: List[Dict[str, Any]] = Field(default_factory=list)
    notification_channels: List[str] = Field(default_factory=list)
    provider_metadata: Dict[str, Any] = Field(default_factory=dict)

class ApprovalResponse(BaseModel):
    request_id: str
    action: str  # "approve" or "reject"
    comment: Optional[str] = None
    approver: str


class ApprovalProgressPayload(BaseModel):
    message: str
    progress_percent: Optional[int] = None
    stage: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ToolExecutionRequest(BaseModel):
    tool_name: str
    params: Dict[str, Any]
    requester: str
    reason: str

class WeChatMessage(BaseModel):
    msgtype: str = "markdown"
    markdown: Dict[str, str]

class ApprovalCard(BaseModel):
    title: str
    description: str
    tool_name: str
    tool_params: Dict[str, Any]
    requester: str
    reason: str
    request_id: str
    created_at: str 
