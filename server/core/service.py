from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from .models import ApprovalProgressPayload, ApprovalRequest, ApprovalStatus
from ..notification.base import multi_platform_notifier
from ..storage import approval_storage
from ..utils.config import config


class ApprovalNotFoundError(Exception):
    """Raised when an approval request cannot be found."""


class ApprovalLifecycleService:
    def __init__(self, storage=approval_storage, notifier=multi_platform_notifier) -> None:
        self.storage = storage
        self.notifier = notifier

    def create_request(
        self,
        title: str,
        description: str,
        requester: str,
        metadata: Optional[Dict[str, Any]] = None,
        approvers: Optional[List[str]] = None,
        timeout_seconds: Optional[int] = None,
        notification_channels: Optional[List[str]] = None,
    ) -> ApprovalRequest:
        current_time = datetime.now()
        approval_request = ApprovalRequest(
            request_id=str(uuid4()),
            tool_name=title,
            tool_params=metadata or {},
            requester=requester,
            reason=description or "No description provided",
            approvers=approvers or config.get_approvers(),
            request_time=current_time,
            created_at=current_time,
            updated_at=current_time,
            timeout_seconds=timeout_seconds or config.APPROVAL_TIMEOUT,
            notification_channels=notification_channels or [],
        )

        if not self.storage.save_approval_request(approval_request):
            raise RuntimeError("Failed to save approval request")

        self.notifier.send_approval_request(approval_request)
        self.storage.save_approval_request(approval_request)
        return approval_request

    def append_progress_update(
        self,
        request_id: str,
        payload: ApprovalProgressPayload,
    ) -> ApprovalRequest:
        approval_request = self.storage.get_approval_request(request_id)
        if not approval_request:
            raise ApprovalNotFoundError(request_id)

        progress_update = {
            "message": payload.message,
            "progress_percent": payload.progress_percent,
            "stage": payload.stage,
            "metadata": payload.metadata,
            "created_at": datetime.now().isoformat(),
        }
        approval_request.progress_updates.append(progress_update)
        approval_request.updated_at = datetime.now()

        self.notifier.send_progress_update(approval_request, progress_update)
        if not self.storage.save_approval_request(approval_request):
            raise RuntimeError("Failed to save progress update")

        return approval_request

    def process_decision(
        self,
        request_id: str,
        status: ApprovalStatus,
        approver: str,
        comment: str = "",
        source: str = "system",
        source_metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[ApprovalRequest, bool]:
        approval_request = self.storage.get_approval_request(request_id)
        if not approval_request:
            raise ApprovalNotFoundError(request_id)

        if approval_request.status != ApprovalStatus.PENDING:
            return approval_request, False

        if source_metadata:
            approval_request.comments.append(
                {
                    "type": "decision_source",
                    "source": source,
                    "metadata": source_metadata,
                    "timestamp": datetime.now().isoformat(),
                }
            )
            self.storage.save_approval_request(approval_request)

        success = self.storage.update_approval_status(
            request_id,
            status,
            approver=approver,
            comment=comment,
        )
        if not success:
            current = self.storage.get_approval_request(request_id)
            if current:
                return current, False
            raise RuntimeError("Failed to update approval status")

        updated_request = self.storage.get_approval_request(request_id)
        if not updated_request:
            raise RuntimeError("Approval request disappeared after update")

        self.notifier.update_approval_status(updated_request)
        self.storage.save_approval_request(updated_request)
        return updated_request, True


approval_service = ApprovalLifecycleService()
