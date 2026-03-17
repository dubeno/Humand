"""
Notification provider abstraction and provider registry.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import requests

from ..core.models import ApprovalRequest
from ..utils.config import config


class PlatformType(str, Enum):
    WECHAT = "wechat"
    FEISHU = "feishu"
    DINGTALK = "dingtalk"
    SIMULATOR = "simulator"


class NotificationProvider(ABC):
    name: str

    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True when the provider has enough configuration to be used."""

    @abstractmethod
    def send_approval_request(self, request: ApprovalRequest) -> bool:
        """Send an approval request to the provider."""

    @abstractmethod
    def send_progress_update(self, request: ApprovalRequest, update: Dict[str, Any]) -> bool:
        """Send a progress update for an approval."""

    @abstractmethod
    def update_approval_status(self, request: ApprovalRequest) -> bool:
        """Synchronize the final approval status with the provider."""

    def test_connection(self) -> bool:
        return self.is_configured()

    def supports_channel(self, channel: str) -> bool:
        return channel.strip().lower() == self.name

    def metadata_for(self, request: ApprovalRequest) -> Dict[str, Any]:
        if self.name not in request.provider_metadata:
            request.provider_metadata[self.name] = {}
        metadata = request.provider_metadata[self.name]
        if not isinstance(metadata, dict):
            metadata = {"raw": metadata}
            request.provider_metadata[self.name] = metadata
        return metadata

    def set_metadata(self, request: ApprovalRequest, **values: Any) -> Dict[str, Any]:
        metadata = self.metadata_for(request)
        metadata.update(values)
        metadata["updated_at"] = datetime.now().isoformat()
        return metadata

    @staticmethod
    def approval_url(request: ApprovalRequest) -> str:
        return f"{config.get_public_base_url().rstrip('/')}/approval/{request.request_id}"

    @staticmethod
    def status_label(request: ApprovalRequest) -> str:
        return {
            "pending": "Pending",
            "approved": "Approved",
            "rejected": "Rejected",
            "timeout": "Timed Out",
        }.get(request.status.value, request.status.value)


class WebhookProvider(NotificationProvider):
    def __init__(
        self,
        name: str,
        webhook_url: str,
        approval_builder: Callable[[ApprovalRequest], Dict[str, Any]],
        progress_builder: Callable[[ApprovalRequest, Dict[str, Any]], Dict[str, Any]],
        result_builder: Callable[[ApprovalRequest], Dict[str, Any]],
        test_payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(name)
        self.webhook_url = webhook_url
        self.approval_builder = approval_builder
        self.progress_builder = progress_builder
        self.result_builder = result_builder
        self._test_payload = test_payload or self.approval_builder(self._fake_request())

    def _fake_request(self) -> ApprovalRequest:
        now = datetime.now()
        return ApprovalRequest(
            request_id="health-check",
            tool_name="Connection Test",
            tool_params={},
            requester="Humand",
            reason="Provider health check",
            approvers=[],
            request_time=now,
            created_at=now,
            updated_at=now,
        )

    def is_configured(self) -> bool:
        return bool(self.webhook_url)

    def _post(self, payload: Dict[str, Any]) -> bool:
        if not self.is_configured():
            return False

        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            return response.status_code == 200
        except Exception as exc:
            print(f"❌ Failed to send via {self.name}: {exc}")
            return False

    def send_approval_request(self, request: ApprovalRequest) -> bool:
        success = self._post(self.approval_builder(request))
        self.set_metadata(request, status="sent" if success else "failed", last_error=None if success else "send_failed")
        return success

    def send_progress_update(self, request: ApprovalRequest, update: Dict[str, Any]) -> bool:
        success = self._post(self.progress_builder(request, update))
        self.set_metadata(request, status="updated" if success else "failed", last_error=None if success else "progress_failed")
        return success

    def update_approval_status(self, request: ApprovalRequest) -> bool:
        success = self._post(self.result_builder(request))
        self.set_metadata(
            request,
            status=request.status.value if success else "failed",
            last_error=None if success else "status_sync_failed",
        )
        return success

    def test_connection(self) -> bool:
        return self._post(self._test_payload)


class SimulatorProvider(NotificationProvider):
    def __init__(self, simulator_url: str) -> None:
        super().__init__(PlatformType.SIMULATOR.value)
        self.simulator_url = simulator_url.rstrip("/")

    def is_configured(self) -> bool:
        return True

    def _post(self, payload: Dict[str, Any]) -> bool:
        webhook_url = f"{self.simulator_url}/webhook/feishu/default-webhook"
        try:
            response = requests.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            return response.status_code == 200
        except Exception:
            return False

    def send_approval_request(self, request: ApprovalRequest) -> bool:
        content = {
            "msg_type": "interactive",
            "card": {
                "header": {"title": {"tag": "plain_text", "content": f"Approval: {request.tool_name}"}},
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": (
                                f"**Requester**: {request.requester}\n"
                                f"**Reason**: {request.reason}\n"
                                f"[Open in Humand]({self.approval_url(request)})"
                            ),
                        },
                    }
                ],
            },
        }
        success = self._post(content)
        self.set_metadata(request, status="sent" if success else "failed")
        return success

    def send_progress_update(self, request: ApprovalRequest, update: Dict[str, Any]) -> bool:
        content = {
            "msg_type": "text",
            "content": {
                "text": f"{request.tool_name}: {update['message']}",
            },
        }
        return self._post(content)

    def update_approval_status(self, request: ApprovalRequest) -> bool:
        content = {
            "msg_type": "text",
            "content": {
                "text": f"{request.tool_name} is now {self.status_label(request)}",
            },
        }
        return self._post(content)

    def test_connection(self) -> bool:
        try:
            response = requests.get(f"{self.simulator_url}/api/messages", timeout=5)
            return response.status_code == 200
        except Exception:
            return False


def _render_markdown_details(request: ApprovalRequest) -> str:
    params_lines = []
    for key, value in list(request.tool_params.items())[:6]:
        rendered = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
        params_lines.append(f"- **{key}**: {rendered[:180]}")
    params_block = "\n".join(params_lines) or "- No extra metadata"
    timeout_minutes = int((request.timeout_seconds or config.APPROVAL_TIMEOUT) / 60)

    return (
        f"**Status**: {NotificationProvider.status_label(request)}\n"
        f"**Requester**: {request.requester}\n"
        f"**Reason**: {request.reason}\n"
        f"**Approvers**: {', '.join(request.approvers) if request.approvers else 'Not specified'}\n"
        f"**Timeout**: {timeout_minutes} min\n\n"
        f"**Metadata**\n{params_block}\n\n"
        f"[Open in Humand]({NotificationProvider.approval_url(request)})"
    )


def _build_wechat_payload(request: ApprovalRequest) -> Dict[str, Any]:
    return {
        "msgtype": "markdown",
        "markdown": {"content": f"## Approval Request\n\n{_render_markdown_details(request)}"},
    }


def _build_wechat_progress_payload(request: ApprovalRequest, update: Dict[str, Any]) -> Dict[str, Any]:
    progress = f"{update['progress_percent']}%" if update.get("progress_percent") is not None else "in progress"
    return {
        "msgtype": "markdown",
        "markdown": {
            "content": (
                f"## Progress Update\n\n"
                f"**Approval**: {request.tool_name}\n"
                f"**Progress**: {progress}\n"
                f"**Message**: {update['message']}\n"
            )
        },
    }


def _build_dingtalk_payload(request: ApprovalRequest) -> Dict[str, Any]:
    return {
        "msgtype": "markdown",
        "markdown": {"title": f"Approval: {request.tool_name}", "text": _render_markdown_details(request)},
    }


def _build_dingtalk_progress_payload(request: ApprovalRequest, update: Dict[str, Any]) -> Dict[str, Any]:
    progress = f"{update['progress_percent']}%" if update.get("progress_percent") is not None else "in progress"
    return {
        "msgtype": "markdown",
        "markdown": {
            "title": f"Progress: {request.tool_name}",
            "text": f"**Progress**: {progress}\n\n**Message**: {update['message']}",
        },
    }


def _build_feishu_webhook_payload(request: ApprovalRequest) -> Dict[str, Any]:
    return {
        "msg_type": "text",
        "content": {
            "text": (
                f"Approval Request: {request.tool_name}\n"
                f"Requester: {request.requester}\n"
                f"Reason: {request.reason}\n"
                f"Open: {NotificationProvider.approval_url(request)}"
            )
        },
    }


def _build_feishu_webhook_progress_payload(request: ApprovalRequest, update: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "msg_type": "text",
        "content": {
            "text": f"Progress Update for {request.tool_name}: {update['message']}",
        },
    }


class MultiPlatformNotifier:
    def __init__(self) -> None:
        self.providers: Dict[str, NotificationProvider] = {}
        self.reload_providers()

    def reload_providers(self) -> None:
        providers: Dict[str, NotificationProvider] = {}

        from .feishu import FeishuProvider

        feishu_provider = FeishuProvider()
        if feishu_provider.is_configured():
            providers[PlatformType.FEISHU.value] = feishu_provider
        elif config.FEISHU_WEBHOOK_URL:
            providers[PlatformType.FEISHU.value] = WebhookProvider(
                name=PlatformType.FEISHU.value,
                webhook_url=config.FEISHU_WEBHOOK_URL,
                approval_builder=_build_feishu_webhook_payload,
                progress_builder=_build_feishu_webhook_progress_payload,
                result_builder=_build_feishu_webhook_payload,
            )

        if config.WECHAT_WEBHOOK_URL:
            providers[PlatformType.WECHAT.value] = WebhookProvider(
                name=PlatformType.WECHAT.value,
                webhook_url=config.WECHAT_WEBHOOK_URL,
                approval_builder=_build_wechat_payload,
                progress_builder=_build_wechat_progress_payload,
                result_builder=_build_wechat_payload,
            )

        if config.DINGTALK_WEBHOOK_URL:
            providers[PlatformType.DINGTALK.value] = WebhookProvider(
                name=PlatformType.DINGTALK.value,
                webhook_url=config.DINGTALK_WEBHOOK_URL,
                approval_builder=_build_dingtalk_payload,
                progress_builder=_build_dingtalk_progress_payload,
                result_builder=_build_dingtalk_payload,
            )

        providers[PlatformType.SIMULATOR.value] = SimulatorProvider(config.SIMULATOR_URL)
        self.providers = providers

    def get_provider(self, name: str) -> Optional[NotificationProvider]:
        return self.providers.get(name)

    def _configured_providers(self) -> List[NotificationProvider]:
        configured = [
            provider
            for name, provider in self.providers.items()
            if name != PlatformType.SIMULATOR.value and provider.is_configured()
        ]
        if configured:
            enabled = set(config.get_notification_providers())
            if enabled:
                configured = [provider for provider in configured if provider.name in enabled]
        return configured

    def _resolve_providers(self, channels: Optional[List[str]] = None) -> List[NotificationProvider]:
        configured = self._configured_providers()
        normalized_channels = [channel.strip().lower() for channel in (channels or []) if channel]

        if normalized_channels:
            matched = [
                provider
                for provider in configured
                if any(provider.supports_channel(channel) for channel in normalized_channels)
            ]
            if matched:
                return matched

        if configured:
            return configured

        simulator = self.providers.get(PlatformType.SIMULATOR.value)
        return [simulator] if simulator else []

    def send_approval_request(self, request: ApprovalRequest) -> bool:
        results = [provider.send_approval_request(request) for provider in self._resolve_providers(request.notification_channels)]
        return any(results) if results else False

    def send_progress_update(self, request: ApprovalRequest, update: Dict[str, Any]) -> bool:
        results = [provider.send_progress_update(request, update) for provider in self._resolve_providers(request.notification_channels)]
        return any(results) if results else False

    def update_approval_status(self, request: ApprovalRequest) -> bool:
        results = [provider.update_approval_status(request) for provider in self._resolve_providers(request.notification_channels)]
        return any(results) if results else False

    def send_approval_result(self, request: ApprovalRequest) -> bool:
        return self.update_approval_status(request)

    def test_connection(self) -> Dict[str, bool]:
        return {
            name: provider.test_connection()
            for name, provider in self.providers.items()
            if name == PlatformType.SIMULATOR.value or provider.is_configured()
        }


multi_platform_notifier = MultiPlatformNotifier()
