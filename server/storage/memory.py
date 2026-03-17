"""
In-memory storage backend used for local development and tests.
"""

from datetime import datetime, timedelta
from threading import RLock
from typing import Any, Dict, List, Optional

from ..core.models import ApprovalRequest, ApprovalStatus
from ..utils.config import config


class MemoryStorage:
    """Thread-safe in-memory storage."""

    def __init__(self) -> None:
        self._approvals: Dict[str, Dict[str, Any]] = {}
        self._lock = RLock()
        print("⚠️ Using in-memory storage mode (data will not survive restarts)")

    def _serialize_request(self, request: ApprovalRequest) -> Dict[str, Any]:
        return {
            "request_id": request.request_id,
            "tool_name": request.tool_name,
            "tool_params": request.tool_params,
            "requester": request.requester,
            "reason": request.reason,
            "approvers": request.approvers,
            "request_time": request.request_time.isoformat(),
            "created_at": request.created_at.isoformat(),
            "updated_at": request.updated_at.isoformat(),
            "timeout_seconds": request.timeout_seconds,
            "status": request.status.value,
            "approver": request.approver,
            "approved_by": request.approved_by,
            "rejected_by": request.rejected_by,
            "approved_at": request.approved_at.isoformat() if request.approved_at else None,
            "rejected_at": request.rejected_at.isoformat() if request.rejected_at else None,
            "approval_comment": request.approval_comment,
            "comments": request.comments,
            "progress_updates": request.progress_updates,
            "notification_channels": request.notification_channels,
            "provider_metadata": request.provider_metadata,
        }

    def _deserialize_request(self, data: Dict[str, Any]) -> ApprovalRequest:
        return ApprovalRequest(
            request_id=data["request_id"],
            tool_name=data["tool_name"],
            tool_params=data["tool_params"],
            requester=data["requester"],
            reason=data["reason"],
            approvers=data.get("approvers", []),
            request_time=datetime.fromisoformat(data["request_time"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data.get("updated_at") or data["created_at"]),
            timeout_seconds=data.get("timeout_seconds"),
            status=ApprovalStatus(data["status"]),
            approver=data.get("approver"),
            approved_by=data.get("approved_by", []),
            rejected_by=data.get("rejected_by", []),
            approved_at=datetime.fromisoformat(data["approved_at"]) if data.get("approved_at") else None,
            rejected_at=datetime.fromisoformat(data["rejected_at"]) if data.get("rejected_at") else None,
            approval_comment=data.get("approval_comment"),
            comments=data.get("comments", []),
            progress_updates=data.get("progress_updates", []),
            notification_channels=data.get("notification_channels", []),
            provider_metadata=data.get("provider_metadata", {}),
        )

    def save_approval_request(self, request: ApprovalRequest) -> bool:
        try:
            with self._lock:
                request.updated_at = datetime.now()
                self._approvals[request.request_id] = self._serialize_request(request)
                return True
        except Exception as exc:
            print(f"❌ Failed to save approval request: {exc}")
            return False

    def _timeout_if_needed(self, request_id: str, data: Dict[str, Any]) -> None:
        if data["status"] != ApprovalStatus.PENDING.value:
            return

        timeout_seconds = data.get("timeout_seconds") or config.APPROVAL_TIMEOUT
        created_at = datetime.fromisoformat(data["created_at"])
        if datetime.now() - created_at <= timedelta(seconds=timeout_seconds):
            return

        data["status"] = ApprovalStatus.TIMEOUT.value
        data["updated_at"] = datetime.now().isoformat()

    def get_approval_request(self, request_id: str) -> Optional[ApprovalRequest]:
        try:
            with self._lock:
                data = self._approvals.get(request_id)
                if not data:
                    return None

                self._timeout_if_needed(request_id, data)
                return self._deserialize_request(data)
        except Exception as exc:
            print(f"❌ Failed to get approval request: {exc}")
            return None

    def get_pending_approvals(self) -> List[ApprovalRequest]:
        try:
            with self._lock:
                pending_requests: List[ApprovalRequest] = []
                for request_id, data in list(self._approvals.items()):
                    self._timeout_if_needed(request_id, data)
                    if data["status"] == ApprovalStatus.PENDING.value:
                        pending_requests.append(self._deserialize_request(data))

                pending_requests.sort(key=lambda item: item.created_at, reverse=True)
                return pending_requests
        except Exception as exc:
            print(f"❌ Failed to get pending approvals: {exc}")
            return []

    def get_all_approvals(self, limit: int = 100) -> List[ApprovalRequest]:
        try:
            with self._lock:
                approvals: List[ApprovalRequest] = []
                for request_id in list(self._approvals.keys())[:limit]:
                    data = self._approvals.get(request_id)
                    if not data:
                        continue
                    self._timeout_if_needed(request_id, data)
                    approvals.append(self._deserialize_request(data))

                approvals.sort(key=lambda item: item.created_at, reverse=True)
                return approvals
        except Exception as exc:
            print(f"❌ Failed to get approvals: {exc}")
            return []

    def update_approval_status(
        self,
        request_id: str,
        status: ApprovalStatus,
        approver: str = "",
        comment: str = "",
    ) -> bool:
        try:
            with self._lock:
                data = self._approvals.get(request_id)
                if not data:
                    print(f"❌ Approval request does not exist: {request_id}")
                    return False

                current_status = ApprovalStatus(data["status"])
                if current_status != ApprovalStatus.PENDING and status != ApprovalStatus.PENDING:
                    return False

                now = datetime.now()
                data["status"] = status.value
                data["approver"] = approver
                data["approval_comment"] = comment
                data["updated_at"] = now.isoformat()

                if status == ApprovalStatus.APPROVED:
                    data["approved_at"] = now.isoformat()
                    if approver and approver not in data["approved_by"]:
                        data["approved_by"].append(approver)
                elif status == ApprovalStatus.REJECTED:
                    data["rejected_at"] = now.isoformat()
                    if approver and approver not in data["rejected_by"]:
                        data["rejected_by"].append(approver)

                if comment:
                    data["comments"].append(
                        {
                            "approver": approver or "System",
                            "comment": comment,
                            "timestamp": now.isoformat(),
                            "action": status.value,
                        }
                    )

                return True
        except Exception as exc:
            print(f"❌ Failed to update approval status: {exc}")
            return False

    def delete_approval_request(self, request_id: str) -> bool:
        try:
            with self._lock:
                if request_id not in self._approvals:
                    return False
                del self._approvals[request_id]
                return True
        except Exception as exc:
            print(f"❌ Failed to delete approval request: {exc}")
            return False

    def cleanup_old_approvals(self, days: int = 7) -> int:
        try:
            with self._lock:
                cutoff_time = datetime.now() - timedelta(days=days)
                to_delete = [
                    request_id
                    for request_id, data in self._approvals.items()
                    if datetime.fromisoformat(data["created_at"]) < cutoff_time
                ]
                for request_id in to_delete:
                    del self._approvals[request_id]
                return len(to_delete)
        except Exception as exc:
            print(f"❌ Failed to clean up approvals: {exc}")
            return 0

    def get_statistics(self) -> Dict[str, Any]:
        approvals = self.get_all_approvals(limit=5000)
        total = len(approvals)
        pending = sum(1 for item in approvals if item.status == ApprovalStatus.PENDING)
        approved = sum(1 for item in approvals if item.status == ApprovalStatus.APPROVED)
        rejected = sum(1 for item in approvals if item.status == ApprovalStatus.REJECTED)
        timeout = sum(1 for item in approvals if item.status == ApprovalStatus.TIMEOUT)
        return {
            "total": total,
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "timeout": timeout,
            "approval_rate": round(approved / total * 100, 2) if total > 0 else 0,
            "storage_type": "memory",
        }

    def ping(self) -> bool:
        return True

    def clear_all(self) -> bool:
        try:
            with self._lock:
                self._approvals.clear()
                return True
        except Exception as exc:
            print(f"❌ Failed to clear approvals: {exc}")
            return False
