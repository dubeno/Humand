"""
Feishu notification provider backed by app bot messages and interactive cards.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import requests

from ..core.models import ApprovalRequest, ApprovalStatus
from ..utils.config import config
from .base import NotificationProvider


@dataclass
class FeishuCallbackAction:
    request_id: str
    action: str
    approver: str
    approver_id: str
    decision_token: Optional[str]
    message_id: Optional[str]
    raw_payload: Dict[str, Any]


class FeishuProvider(NotificationProvider):
    def __init__(self) -> None:
        super().__init__("feishu")
        self.base_url = config.FEISHU_OPEN_BASE_URL.rstrip("/")
        self.session = requests.Session()
        self._tenant_access_token: Optional[str] = None
        self._tenant_access_token_expires_at = datetime.min

    def is_configured(self) -> bool:
        return bool(
            config.FEISHU_APP_ID
            and config.FEISHU_APP_SECRET
            and config.FEISHU_RECEIVE_ID
        )

    def _get_tenant_access_token(self, force_refresh: bool = False) -> str:
        if (
            not force_refresh
            and self._tenant_access_token
            and datetime.now() < self._tenant_access_token_expires_at
        ):
            return self._tenant_access_token

        response = self.session.post(
            f"{self.base_url}/auth/v3/tenant_access_token/internal",
            json={
                "app_id": config.FEISHU_APP_ID,
                "app_secret": config.FEISHU_APP_SECRET,
            },
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code", 0) != 0:
            raise RuntimeError(payload.get("msg", "Failed to fetch Feishu access token"))

        self._tenant_access_token = payload["tenant_access_token"]
        expires_in = int(payload.get("expire", 7200))
        self._tenant_access_token_expires_at = datetime.now() + timedelta(
            seconds=max(expires_in - 120, 60)
        )
        return self._tenant_access_token

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        response = self.session.request(
            method=method,
            url=f"{self.base_url}/{path.lstrip('/')}",
            params=params,
            json=payload,
            headers={
                "Authorization": f"Bearer {self._get_tenant_access_token()}",
                "Content-Type": "application/json; charset=utf-8",
            },
            timeout=10,
        )
        response.raise_for_status()
        body = response.json()
        if body.get("code", 0) != 0:
            raise RuntimeError(body.get("msg", f"Feishu API error on {path}"))
        return body

    def _deadline_text(self, request: ApprovalRequest) -> str:
        timeout_seconds = request.timeout_seconds or config.APPROVAL_TIMEOUT
        deadline = request.created_at + timedelta(seconds=timeout_seconds)
        return deadline.strftime("%Y-%m-%d %H:%M:%S")

    def _format_metadata_lines(self, request: ApprovalRequest) -> str:
        if not request.tool_params:
            return "- No additional context"

        lines = []
        for key, value in list(request.tool_params.items())[:8]:
            if isinstance(value, (dict, list)):
                rendered = json.dumps(value, ensure_ascii=False)
            else:
                rendered = str(value)
            lines.append(f"- **{key}**: {rendered[:220]}")
        return "\n".join(lines)

    def _format_progress_lines(self, request: ApprovalRequest) -> Optional[str]:
        if not request.progress_updates:
            return None

        rendered = []
        for update in request.progress_updates[-5:]:
            percent = ""
            if update.get("progress_percent") is not None:
                percent = f" ({update['progress_percent']}%)"
            stage = f"[{update['stage']}] " if update.get("stage") else ""
            rendered.append(
                f"- {update['created_at'][:19]} {stage}{update['message']}{percent}"
            )
        return "\n".join(rendered)

    def build_card(
        self,
        request: ApprovalRequest,
        include_actions: Optional[bool] = None,
    ) -> Dict[str, Any]:
        provider_state = self.metadata_for(request)
        include_actions = (
            request.status == ApprovalStatus.PENDING if include_actions is None else include_actions
        )
        header_template = {
            ApprovalStatus.PENDING: "orange",
            ApprovalStatus.APPROVED: "green",
            ApprovalStatus.REJECTED: "red",
            ApprovalStatus.TIMEOUT: "grey",
        }.get(request.status, "blue")

        elements = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": (
                        f"**Status**: {self.status_label(request)}\n"
                        f"**Requester**: {request.requester}\n"
                        f"**Approvers**: {', '.join(request.approvers) if request.approvers else 'Not specified'}\n"
                        f"**Deadline**: {self._deadline_text(request)}\n"
                        f"**Reason**: {request.reason}"
                    ),
                },
            },
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**Context**\n{self._format_metadata_lines(request)}",
                },
            },
        ]

        progress_lines = self._format_progress_lines(request)
        if progress_lines:
            elements.append(
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**Progress**\n{progress_lines}",
                    },
                }
            )

        if include_actions:
            elements.append(
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "type": "primary",
                            "text": {"tag": "plain_text", "content": "Approve"},
                            "value": {
                                "action": "approve",
                                "request_id": request.request_id,
                                "decision_token": provider_state.get("decision_token"),
                            },
                        },
                        {
                            "tag": "button",
                            "type": "danger",
                            "text": {"tag": "plain_text", "content": "Reject"},
                            "value": {
                                "action": "reject",
                                "request_id": request.request_id,
                                "decision_token": provider_state.get("decision_token"),
                            },
                        },
                    ],
                }
            )
        else:
            decision_actor = request.approver or "Unknown approver"
            decision_note = request.approval_comment or "No comment provided"
            elements.append(
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"**Final Decision**: {self.status_label(request)}\n"
                            f"**Handled By**: {decision_actor}\n"
                            f"**Comment**: {decision_note}"
                        ),
                    },
                }
            )

        elements.append(
            {
                "tag": "note",
                "elements": [
                    {
                        "tag": "lark_md",
                        "content": (
                            f"Request ID: `{request.request_id}`  |  "
                            f"[Open in Humand]({self.approval_url(request)})"
                        ),
                    }
                ],
            }
        )

        return {
            "config": {
                "wide_screen_mode": True,
                "enable_forward": True,
            },
            "header": {
                "template": header_template,
                "title": {
                    "tag": "plain_text",
                    "content": f"Humand Approval: {request.tool_name}",
                },
            },
            "elements": elements,
        }

    def send_approval_request(self, request: ApprovalRequest) -> bool:
        if not self.is_configured():
            return False

        provider_state = self.metadata_for(request)
        provider_state.setdefault("decision_token", secrets.token_urlsafe(18))
        provider_state["receive_id"] = config.FEISHU_RECEIVE_ID
        provider_state["receive_id_type"] = config.FEISHU_RECEIVE_ID_TYPE

        try:
            response = self._request(
                "POST",
                "/im/v1/messages",
                params={"receive_id_type": config.FEISHU_RECEIVE_ID_TYPE},
                payload={
                    "receive_id": config.FEISHU_RECEIVE_ID,
                    "msg_type": "interactive",
                    "content": json.dumps(self.build_card(request), ensure_ascii=False),
                },
            )
            data = response.get("data", {})
            self.set_metadata(
                request,
                decision_token=provider_state["decision_token"],
                message_id=data.get("message_id"),
                status="sent",
                last_synced_status=request.status.value,
                sent_at=datetime.now().isoformat(),
            )
            return True
        except Exception as exc:
            self.set_metadata(request, status="failed", last_error=str(exc))
            print(f"❌ Failed to send Feishu approval request: {exc}")
            return False

    def _patch_card(self, request: ApprovalRequest, include_actions: bool) -> bool:
        provider_state = self.metadata_for(request)
        message_id = provider_state.get("message_id")
        if not message_id:
            return False

        try:
            self._request(
                "PATCH",
                f"/im/v1/messages/{message_id}",
                payload={
                    "msg_type": "interactive",
                    "content": json.dumps(
                        self.build_card(request, include_actions=include_actions),
                        ensure_ascii=False,
                    ),
                },
            )
            self.set_metadata(
                request,
                status=request.status.value if request.status != ApprovalStatus.PENDING else "updated",
                last_synced_status=request.status.value,
                last_error=None,
            )
            return True
        except Exception as exc:
            self.set_metadata(request, status="failed", last_error=str(exc))
            print(f"❌ Failed to update Feishu card: {exc}")
            return False

    def send_progress_update(self, request: ApprovalRequest, update: Dict[str, Any]) -> bool:
        if not self.is_configured():
            return False

        if self.metadata_for(request).get("message_id"):
            return self._patch_card(
                request,
                include_actions=request.status == ApprovalStatus.PENDING,
            )

        return self.send_approval_request(request)

    def update_approval_status(self, request: ApprovalRequest) -> bool:
        if not self.is_configured():
            return False
        return self._patch_card(request, include_actions=False)

    def test_connection(self) -> bool:
        try:
            return bool(self._get_tenant_access_token())
        except Exception:
            return False

    def _verify_callback_token(self, payload: Dict[str, Any]) -> None:
        expected = (config.FEISHU_CALLBACK_VERIFICATION_TOKEN or "").strip()
        if not expected:
            return

        actual = payload.get("token") or payload.get("header", {}).get("token")
        if actual != expected:
            raise PermissionError("Invalid Feishu callback token")

    def _normalize_callback_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if "encrypt" in payload:
            raise ValueError(
                "Encrypted Feishu callbacks are not supported yet. Disable payload encryption for local integration."
            )

        self._verify_callback_token(payload)
        return payload

    def handle_url_verification(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        normalized = self._normalize_callback_payload(payload)
        if normalized.get("type") == "url_verification" or (
            normalized.get("challenge") and normalized.get("token")
        ):
            return {"challenge": normalized["challenge"]}
        return None

    def parse_callback(self, payload: Dict[str, Any]) -> FeishuCallbackAction:
        normalized = self._normalize_callback_payload(payload)
        event = normalized.get("event") if isinstance(normalized.get("event"), dict) else normalized
        action_container = event.get("action") if isinstance(event.get("action"), dict) else event
        value = (
            action_container.get("value")
            if isinstance(action_container.get("value"), dict)
            else event.get("value", {})
        )
        operator = event.get("operator") if isinstance(event.get("operator"), dict) else normalized.get("operator", {})

        request_id = value.get("request_id") or event.get("request_id")
        action_name = value.get("action") or value.get("decision") or action_container.get("name")
        if not request_id or action_name not in {"approve", "reject"}:
            raise ValueError("Unsupported Feishu callback payload")

        approver_id = (
            operator.get("open_id")
            or operator.get("user_id")
            or normalized.get("open_id")
            or normalized.get("employee_id")
            or "feishu_user"
        )
        approver = operator.get("name") or approver_id
        message_id = (
            event.get("open_message_id")
            or normalized.get("open_message_id")
            or normalized.get("message_id")
        )

        return FeishuCallbackAction(
            request_id=request_id,
            action=action_name,
            approver=approver,
            approver_id=approver_id,
            decision_token=value.get("decision_token") or value.get("callback_token"),
            message_id=message_id,
            raw_payload=normalized,
        )

    def validate_callback_action(self, request: ApprovalRequest, action: FeishuCallbackAction) -> None:
        provider_state = self.metadata_for(request)
        expected_token = provider_state.get("decision_token")
        if expected_token and expected_token != action.decision_token:
            raise PermissionError("Feishu callback token does not match approval request")

        message_id = provider_state.get("message_id")
        if message_id and action.message_id and message_id != action.message_id:
            raise PermissionError("Feishu message id does not match approval request")

    def build_callback_response(
        self,
        request: ApprovalRequest,
        *,
        toast_type: str,
        toast_message: str,
    ) -> Dict[str, Any]:
        return {
            "toast": {
                "type": toast_type,
                "content": toast_message,
            },
            "card": self.build_card(
                request,
                include_actions=request.status == ApprovalStatus.PENDING,
            ),
        }
