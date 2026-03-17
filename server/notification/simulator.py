"""
Local simulator / inbox for Humand demos and provider debugging.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from flask import Flask, jsonify, redirect, render_template, request, url_for


class IMPlatform(str, Enum):
    WECHAT = "wechat"
    FEISHU = "feishu"
    DINGTALK = "dingtalk"
    HUMAND = "humand"


@dataclass
class IMMessage:
    """Message record kept for raw event inspection."""

    id: str
    platform: IMPlatform
    webhook_url: str
    content: str
    message_type: str
    timestamp: datetime
    sender: str = "Humand Local Inbox"
    status: str = "sent"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "platform": self.platform.value,
            "webhook_url": self.webhook_url,
            "content": self.content,
            "message_type": self.message_type,
            "timestamp": self.timestamp.isoformat(),
            "sender": self.sender,
            "status": self.status,
        }


class IMSimulator:
    """Approval-aware local simulator used for the one-click demo."""

    STATUS_META = {
        "pending": ("Pending review", "warning"),
        "approved": ("Approved", "success"),
        "rejected": ("Rejected", "danger"),
        "timeout": ("Timed out", "secondary"),
    }

    def __init__(self) -> None:
        self.messages: List[IMMessage] = []
        self.webhooks: Dict[str, Dict[str, Any]] = {}
        self.approvals: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.RLock()

        template_dir = Path(__file__).parent / "templates"
        self.app = Flask(__name__, template_folder=str(template_dir))

        self.server_url = os.getenv("HUMAND_SERVER_URL", "http://localhost:8000").rstrip("/")
        self.public_server_url = os.getenv("HUMAND_PUBLIC_SERVER_URL", self.server_url).rstrip("/")
        self.api_key = os.getenv("HUMAND_API_KEY", "").strip()
        self.default_approver = os.getenv("HUMAND_SIMULATOR_APPROVER", "Local Demo Reviewer")
        self.demo_web_login = os.getenv("HUMAND_DEMO_WEB_LOGIN", "")

        self.setup_routes()

    def setup_routes(self) -> None:
        @self.app.route("/")
        def index():
            return render_template(
                "simulator_inbox.html",
                approvals=self.list_approvals(),
                summary=self.get_summary(),
                messages=list(reversed(self.messages[-12:])),
                default_approver=self.default_approver,
                public_server_url=self.public_server_url,
                demo_web_login=self.demo_web_login,
                current_message=request.args.get("message"),
                current_error=request.args.get("error"),
            )

        @self.app.route("/health")
        def health():
            return jsonify(
                {
                    "status": "healthy",
                    "server_url": self.server_url,
                    "approvals": len(self.approvals),
                    "messages": len(self.messages),
                    "timestamp": datetime.now().isoformat(),
                }
            )

        @self.app.route("/webhook/<platform>/<webhook_id>", methods=["POST"])
        def receive_webhook(platform: str, webhook_id: str):
            try:
                data = request.get_json(silent=True) or {}
                webhook_url = f"/webhook/{platform}/{webhook_id}"
                message = self.parse_message(platform, webhook_url, data)
                if message:
                    self._append_message(message)
                return self.get_platform_response(platform)
            except Exception as exc:
                return jsonify({"errcode": 1, "errmsg": str(exc)}), 500

        @self.app.route("/api/messages")
        def get_messages():
            return jsonify([msg.to_dict() for msg in self.messages])

        @self.app.route("/api/clear", methods=["POST"])
        def clear_messages():
            self.messages.clear()
            return jsonify({"success": True})

        @self.app.route("/api/webhook/create", methods=["POST"])
        def create_webhook():
            data = request.get_json(silent=True) or {}
            platform = data.get("platform", "wechat")
            webhook_id = str(uuid.uuid4())
            webhook_url = f"http://localhost:5000/webhook/{platform}/{webhook_id}"

            self.webhooks[webhook_id] = {
                "id": webhook_id,
                "platform": platform,
                "url": webhook_url,
                "created_at": datetime.now().isoformat(),
            }

            return jsonify(
                {
                    "webhook_id": webhook_id,
                    "webhook_url": webhook_url,
                    "platform": platform,
                }
            )

        @self.app.route("/api/inbox/sync", methods=["POST"])
        def sync_inbox():
            data = request.get_json(silent=True) or {}
            approval = data.get("approval")
            if not isinstance(approval, dict) or not approval.get("id"):
                return jsonify({"success": False, "error": "approval payload with id is required"}), 400

            stored = self.sync_approval(approval, event=data.get("event", "approval.sync"))
            return jsonify({"success": True, "approval": stored})

        @self.app.route("/api/inbox/approvals")
        def list_inbox_approvals():
            with self.lock:
                approvals = list(self.approvals.values())
            approvals.sort(key=self._approval_sort_key, reverse=True)
            return jsonify(approvals)

        @self.app.route("/approvals/<approval_id>/approve", methods=["POST"])
        def approve_approval(approval_id: str):
            return self._browser_decision(approval_id, "approve")

        @self.app.route("/approvals/<approval_id>/reject", methods=["POST"])
        def reject_approval(approval_id: str):
            return self._browser_decision(approval_id, "reject")

        @self.app.route("/api/approvals/<approval_id>/decision", methods=["POST"])
        def api_decision(approval_id: str):
            payload = request.get_json(silent=True) or {}
            action = (payload.get("action") or "").strip().lower()
            if action not in {"approve", "reject"}:
                return jsonify({"success": False, "error": "action must be approve or reject"}), 400

            approver = (payload.get("approver") or self.default_approver).strip() or self.default_approver
            comment = (payload.get("comment") or "").strip()

            try:
                result = self.process_decision(
                    approval_id,
                    action=action,
                    approver=approver,
                    comment=comment,
                )
                return jsonify(result)
            except RuntimeError as exc:
                return jsonify({"success": False, "error": str(exc)}), 502

    def _browser_decision(self, approval_id: str, action: str):
        approver = (request.form.get("approver") or self.default_approver).strip() or self.default_approver
        comment = (request.form.get("comment") or "").strip()

        try:
            result = self.process_decision(
                approval_id,
                action=action,
                approver=approver,
                comment=comment,
            )
        except RuntimeError as exc:
            return redirect(url_for("index", error=str(exc)))

        approval = result.get("approval", {})
        title = approval.get("title") or approval_id
        verb = "approved" if action == "approve" else "rejected"
        return redirect(url_for("index", message=f"{title} was {verb} locally."))

    def _auth_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _append_message(self, message: IMMessage) -> None:
        self.messages.append(message)
        if len(self.messages) > 200:
            self.messages = self.messages[-200:]

    def _append_system_event(self, approval_id: str, event: str, approval: Dict[str, Any]) -> None:
        payload = {
            "event": event,
            "approval_id": approval_id,
            "status": approval.get("status"),
            "updated_at": approval.get("updated_at"),
            "progress_updates": len(approval.get("progress_updates", [])),
        }
        self._append_message(
            IMMessage(
                id=str(uuid.uuid4()),
                platform=IMPlatform.HUMAND,
                webhook_url="/api/inbox/sync",
                content=json.dumps(payload, ensure_ascii=False, indent=2),
                message_type=event,
                timestamp=datetime.now(),
            )
        )

    def _normalize_approval(self, approval: Dict[str, Any], event: str) -> Dict[str, Any]:
        approval_id = str(approval.get("id", "")).strip()
        now_iso = datetime.now().isoformat()
        normalized = {
            "id": approval_id,
            "title": approval.get("title") or "Approval request",
            "description": approval.get("description") or "No description provided",
            "requester": approval.get("requester") or "Humand",
            "status": approval.get("status") or "pending",
            "approvers": approval.get("approvers") or [],
            "created_at": approval.get("created_at") or now_iso,
            "updated_at": approval.get("updated_at") or approval.get("created_at") or now_iso,
            "approved_by": approval.get("approved_by") or [],
            "rejected_by": approval.get("rejected_by") or [],
            "comments": approval.get("comments") or [],
            "metadata": approval.get("metadata") or {},
            "progress_updates": approval.get("progress_updates") or [],
            "notification_channels": approval.get("notification_channels") or [],
            "web_url": approval.get("web_url") or f"{self.public_server_url}/approval/{approval_id}",
            "api_url": approval.get("api_url") or f"{self.public_server_url}/api/v1/approvals/{approval_id}",
            "approval_comment": approval.get("approval_comment") or "",
            "timeout_seconds": approval.get("timeout_seconds"),
            "last_event": event,
            "last_synced_at": now_iso,
        }
        return normalized

    def sync_approval(self, approval: Dict[str, Any], event: str = "approval.sync") -> Dict[str, Any]:
        with self.lock:
            normalized = self._normalize_approval(approval, event)
            self.approvals[normalized["id"]] = normalized

        self._append_system_event(normalized["id"], event, normalized)
        return normalized

    def get_summary(self) -> Dict[str, int]:
        with self.lock:
            approvals = list(self.approvals.values())

        return {
            "total": len(approvals),
            "pending": sum(1 for item in approvals if item.get("status") == "pending"),
            "approved": sum(1 for item in approvals if item.get("status") == "approved"),
            "rejected": sum(1 for item in approvals if item.get("status") == "rejected"),
        }

    def list_approvals(self) -> List[Dict[str, Any]]:
        with self.lock:
            approvals = [self._build_view_approval(item) for item in self.approvals.values()]

        approvals.sort(
            key=lambda item: (0 if item["status"] == "pending" else 1, -self._approval_sort_key(item)),
        )
        return approvals

    def _approval_sort_key(self, approval: Dict[str, Any]) -> float:
        value = approval.get("updated_at") or approval.get("created_at") or ""
        try:
            return datetime.fromisoformat(value).timestamp()
        except ValueError:
            return 0.0

    def _format_timestamp(self, value: Optional[str]) -> str:
        if not value:
            return "unknown time"
        try:
            return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            return value

    def _render_value(self, value: Any) -> str:
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    def _latest_comment(self, approval: Dict[str, Any]) -> str:
        comment = approval.get("approval_comment")
        if comment:
            return comment

        comments = approval.get("comments") or []
        for item in reversed(comments):
            text = item.get("content") or item.get("comment")
            if text:
                return str(text)
        return "No comment provided."

    def _build_view_approval(self, approval: Dict[str, Any]) -> Dict[str, Any]:
        status = approval.get("status", "pending")
        status_label, badge_class = self.STATUS_META.get(status, (status.title(), "secondary"))

        metadata_items = []
        for index, (key, value) in enumerate((approval.get("metadata") or {}).items()):
            if index >= 6:
                break
            metadata_items.append({"key": key.replace("_", " "), "value": self._render_value(value)})

        progress_items = []
        last_progress_percent = None
        for update in approval.get("progress_updates") or []:
            if update.get("progress_percent") is not None:
                last_progress_percent = update["progress_percent"]
            progress_items.append(
                {
                    "message": update.get("message") or "Progress update",
                    "stage": update.get("stage"),
                    "progress_percent": update.get("progress_percent"),
                    "created_at_display": self._format_timestamp(update.get("created_at")),
                }
            )

        if status == "approved":
            actor = (approval.get("approved_by") or ["an approver"])[0]
            decision_summary = f"Approved by {actor}. {self._latest_comment(approval)}"
        elif status == "rejected":
            actor = (approval.get("rejected_by") or ["an approver"])[0]
            decision_summary = f"Rejected by {actor}. {self._latest_comment(approval)}"
        elif status == "timeout":
            decision_summary = "The approval timed out before anyone handled it."
        else:
            decision_summary = "Still waiting for a local decision from the simulator inbox."

        return {
            **approval,
            "status_label": status_label,
            "badge_class": badge_class,
            "metadata_items": metadata_items,
            "progress_items": progress_items,
            "last_progress_percent": last_progress_percent,
            "created_at_display": self._format_timestamp(approval.get("created_at")),
            "updated_at_display": self._format_timestamp(approval.get("updated_at")),
            "decision_summary": decision_summary,
        }

    def process_decision(
        self,
        approval_id: str,
        *,
        action: str,
        approver: str,
        comment: str,
    ) -> Dict[str, Any]:
        response = requests.post(
            f"{self.server_url}/api/approval/{approval_id}/process",
            json={
                "request_id": approval_id,
                "action": action,
                "approver": approver,
                "comment": comment,
            },
            headers=self._auth_headers(),
            timeout=10,
        )

        if not response.ok:
            detail = response.text
            try:
                payload = response.json()
                detail = payload.get("detail") or payload.get("error") or detail
            except ValueError:
                pass
            raise RuntimeError(f"Humand server rejected the local decision: {detail}")

        payload = response.json()
        approval = payload.get("approval")
        if isinstance(approval, dict):
            self.sync_approval(approval, event=f"decision.{action}")
        return payload

    def parse_message(self, platform: str, webhook_url: str, data: Dict[str, Any]) -> Optional[IMMessage]:
        try:
            platform_enum = IMPlatform(platform)
        except ValueError:
            return None

        if platform_enum == IMPlatform.WECHAT:
            msg_type = data.get("msgtype", "text")
            if msg_type == "text":
                content = data.get("text", {}).get("content", "")
            elif msg_type == "markdown":
                content = data.get("markdown", {}).get("content", "")
            else:
                content = json.dumps(data, ensure_ascii=False)
        elif platform_enum == IMPlatform.FEISHU:
            msg_type = data.get("msg_type", "text")
            if msg_type == "text":
                content = data.get("content", {}).get("text", "")
            else:
                content = json.dumps(data, ensure_ascii=False)
        else:
            msg_type = data.get("msgtype", "text")
            if msg_type == "text":
                content = data.get("text", {}).get("content", "")
            elif msg_type == "markdown":
                content = data.get("markdown", {}).get("text", "")
            else:
                content = json.dumps(data, ensure_ascii=False)

        return IMMessage(
            id=str(uuid.uuid4()),
            platform=platform_enum,
            webhook_url=webhook_url,
            content=content,
            message_type=msg_type,
            timestamp=datetime.now(),
            sender="Webhook Debugger",
        )

    def get_platform_response(self, platform: str):
        if platform == IMPlatform.WECHAT:
            return jsonify({"errcode": 0, "errmsg": "ok"})
        if platform == IMPlatform.FEISHU:
            return jsonify({"StatusCode": 0, "StatusMessage": "success"})
        if platform == IMPlatform.DINGTALK:
            return jsonify({"errcode": 0, "errmsg": "ok"})
        return jsonify({"success": True})

    def run(self, host: str = "localhost", port: int = 5000, debug: bool = True) -> None:
        print(f"Starting Humand local simulator at http://{host}:{port}")
        print("This inbox accepts local approval sync events and generic webhook captures.")
        self.app.run(host=host, port=port, debug=debug)


im_simulator = IMSimulator()
app = im_simulator.app


if __name__ == "__main__":
    im_simulator.run()
