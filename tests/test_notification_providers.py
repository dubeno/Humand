from datetime import datetime

from fastapi.testclient import TestClient

import server.web.app as web_app_module
from server.core.models import ApprovalRequest, ApprovalStatus
from server.core.service import approval_service
from server.notification.base import MultiPlatformNotifier, NotificationProvider, multi_platform_notifier
from server.notification.feishu import FeishuCallbackAction, FeishuProvider
from server.storage.memory import MemoryStorage
from server.utils.config import config
from server.web.app import app


def make_request(notification_channels=None, provider_metadata=None):
    now = datetime.now()
    return ApprovalRequest(
        request_id="approval-123",
        tool_name="Deploy Release",
        tool_params={"service": "api", "risk_level": "high"},
        requester="agent@test.com",
        reason="Deploy the latest release candidate",
        approvers=["owner@test.com"],
        request_time=now,
        created_at=now,
        updated_at=now,
        status=ApprovalStatus.PENDING,
        notification_channels=notification_channels or [],
        provider_metadata=provider_metadata or {},
    )


class DummyProvider(NotificationProvider):
    def __init__(self, name: str):
        super().__init__(name)
        self.approval_calls = 0
        self.progress_calls = 0
        self.status_calls = 0

    def is_configured(self) -> bool:
        return True

    def send_approval_request(self, request: ApprovalRequest) -> bool:
        self.approval_calls += 1
        self.set_metadata(request, status="sent")
        return True

    def send_progress_update(self, request: ApprovalRequest, update: dict) -> bool:
        self.progress_calls += 1
        self.set_metadata(request, last_progress=update["message"])
        return True

    def update_approval_status(self, request: ApprovalRequest) -> bool:
        self.status_calls += 1
        self.set_metadata(request, last_synced_status=request.status.value)
        return True


class StubFeishuProvider(FeishuProvider):
    def __init__(self):
        super().__init__()
        self.status_updates = []
        self.callback_action = FeishuCallbackAction(
            request_id="approval-123",
            action="approve",
            approver="owner@test.com",
            approver_id="ou_owner",
            decision_token="decision-token",
            message_id="om_approval",
            raw_payload={},
        )

    def is_configured(self) -> bool:
        return True

    def handle_url_verification(self, payload):
        if payload.get("challenge"):
            return {"challenge": payload["challenge"]}
        return None

    def parse_callback(self, payload):
        return self.callback_action

    def validate_callback_action(self, request, action):
        return None

    def send_approval_request(self, request: ApprovalRequest) -> bool:
        return True

    def send_progress_update(self, request: ApprovalRequest, update: dict) -> bool:
        return True

    def update_approval_status(self, request: ApprovalRequest) -> bool:
        self.status_updates.append(request.request_id)
        return True

    def build_callback_response(self, request: ApprovalRequest, *, toast_type: str, toast_message: str):
        return {
            "toast": {"type": toast_type, "content": toast_message},
            "card": {"title": request.tool_name, "status": request.status.value},
        }


class TestNotificationProviders:
    def test_requested_channel_uses_matching_provider(self):
        notifier = MultiPlatformNotifier()
        feishu = DummyProvider("feishu")
        simulator = DummyProvider("simulator")
        notifier.providers = {
            "feishu": feishu,
            "simulator": simulator,
        }

        request = make_request(notification_channels=["feishu"])
        assert notifier.send_approval_request(request) is True
        assert feishu.approval_calls == 1
        assert simulator.approval_calls == 0

    def test_explicit_simulator_channel_overrides_configured_provider(self):
        notifier = MultiPlatformNotifier()
        feishu = DummyProvider("feishu")
        simulator = DummyProvider("simulator")
        notifier.providers = {
            "feishu": feishu,
            "simulator": simulator,
        }

        request = make_request(notification_channels=["simulator"])
        assert notifier.send_approval_request(request) is True
        assert simulator.approval_calls == 1
        assert feishu.approval_calls == 0

    def test_falls_back_to_simulator_when_no_configured_provider(self):
        notifier = MultiPlatformNotifier()
        simulator = DummyProvider("simulator")
        notifier.providers = {"simulator": simulator}

        request = make_request()
        assert notifier.send_approval_request(request) is True
        assert simulator.approval_calls == 1

    def test_feishu_provider_send_and_patch_card(self, monkeypatch):
        config_type = type(config)
        monkeypatch.setattr(config_type, "FEISHU_APP_ID", "cli_app_id")
        monkeypatch.setattr(config_type, "FEISHU_APP_SECRET", "cli_app_secret")
        monkeypatch.setattr(config_type, "FEISHU_RECEIVE_ID", "oc_test_chat")
        monkeypatch.setattr(config_type, "FEISHU_RECEIVE_ID_TYPE", "chat_id")
        monkeypatch.setattr(config_type, "HUMAND_PUBLIC_BASE_URL", "http://localhost:8000")

        provider = FeishuProvider()
        calls = []

        def fake_request(method, path, params=None, payload=None):
            calls.append((method, path, params, payload))
            if method == "POST":
                return {"code": 0, "data": {"message_id": "om_approval"}}
            return {"code": 0, "data": {}}

        monkeypatch.setattr(provider, "_request", fake_request)

        request = make_request(notification_channels=["feishu"])
        assert provider.send_approval_request(request) is True
        assert request.provider_metadata["feishu"]["message_id"] == "om_approval"
        assert request.provider_metadata["feishu"]["decision_token"]

        request.progress_updates.append(
            {
                "message": "Deploy running",
                "progress_percent": 40,
                "metadata": {},
                "created_at": datetime.now().isoformat(),
            }
        )
        assert provider.send_progress_update(request, request.progress_updates[-1]) is True

        request.status = ApprovalStatus.APPROVED
        request.approver = "owner@test.com"
        assert provider.update_approval_status(request) is True
        assert any(method == "PATCH" and path == "/im/v1/messages/om_approval" for method, path, _, _ in calls)

    def test_feishu_callback_updates_approval_once(self, monkeypatch):
        storage = MemoryStorage()
        provider = StubFeishuProvider()
        request = make_request(
            notification_channels=["feishu"],
            provider_metadata={
                "feishu": {
                    "decision_token": "decision-token",
                    "message_id": "om_approval",
                }
            },
        )
        storage.save_approval_request(request)

        monkeypatch.setattr(web_app_module, "approval_storage", storage)
        monkeypatch.setattr(approval_service, "storage", storage)
        monkeypatch.setattr(web_app_module, "multi_platform_notifier", multi_platform_notifier)
        monkeypatch.setattr(approval_service, "notifier", multi_platform_notifier)
        monkeypatch.setattr(multi_platform_notifier, "providers", {"feishu": provider})

        client = TestClient(app)

        challenge = client.post(
            "/api/v1/providers/feishu/callback",
            json={"challenge": "abc123", "token": "test-token"},
        )
        assert challenge.status_code == 200
        assert challenge.json() == {"challenge": "abc123"}

        response = client.post(
            "/api/v1/providers/feishu/callback",
            json={"event": {"action": {"value": {"request_id": "approval-123", "action": "approve"}}}},
        )
        assert response.status_code == 200
        assert response.json()["toast"]["type"] == "success"

        updated = storage.get_approval_request("approval-123")
        assert updated is not None
        assert updated.status == ApprovalStatus.APPROVED
        assert updated.approver == "owner@test.com"
        assert provider.status_updates == ["approval-123"]

        duplicate = client.post(
            "/api/v1/providers/feishu/callback",
            json={"event": {"action": {"value": {"request_id": "approval-123", "action": "approve"}}}},
        )
        assert duplicate.status_code == 200
        assert duplicate.json()["toast"]["type"] == "info"
