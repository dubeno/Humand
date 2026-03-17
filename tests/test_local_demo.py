from types import SimpleNamespace

from examples.local_demo_flow import (
    DEMO_SLUG,
    build_demo_config,
    create_or_reuse_demo,
    emit_progress_updates,
)
from humand_sdk.config import NotificationChannel


class DummyApproval(SimpleNamespace):
    pass


class DummyClient:
    def __init__(self, approvals=None):
        self.approvals = approvals or []
        self.created = []
        self.progress_calls = []

    def list_approvals(self, status=None, limit=25):
        return self.approvals

    def create_approval(self, config):
        approval = DummyApproval(id="demo-123", metadata=config.metadata, status="pending")
        self.created.append(config)
        return approval

    def send_progress_update(self, approval_id, message, progress_percent=None, stage=None, metadata=None):
        self.progress_calls.append(
            {
                "approval_id": approval_id,
                "message": message,
                "progress_percent": progress_percent,
                "stage": stage,
                "metadata": metadata or {},
            }
        )
        return DummyApproval(status="approved")


def test_build_demo_config_targets_simulator():
    config = build_demo_config(
        approver="local-reviewer@humand.local",
        public_base_url="http://localhost:8000",
        public_simulator_url="http://localhost:5000",
        timeout_seconds=1800,
    )

    assert config.notification_config.channels == [NotificationChannel.SIMULATOR]
    assert config.metadata["demo_slug"] == DEMO_SLUG
    assert config.metadata["channel"] == "simulator"


def test_create_or_reuse_demo_prefers_existing_pending_request():
    existing = DummyApproval(id="existing-demo", metadata={"demo_slug": DEMO_SLUG})
    client = DummyClient(approvals=[existing])
    config = build_demo_config(
        approver="local-reviewer@humand.local",
        public_base_url="http://localhost:8000",
        public_simulator_url="http://localhost:5000",
        timeout_seconds=1800,
    )

    approval, created = create_or_reuse_demo(client, config, reuse_pending=True)

    assert approval.id == "existing-demo"
    assert created is False
    assert client.created == []


def test_emit_progress_updates_uses_expected_stage_metadata(monkeypatch):
    monkeypatch.setattr("examples.local_demo_flow.time.sleep", lambda _: None)
    client = DummyClient()

    emit_progress_updates(client, "demo-123", delay_seconds=0)

    assert len(client.progress_calls) == 4
    assert client.progress_calls[0]["approval_id"] == "demo-123"
    assert client.progress_calls[0]["metadata"]["demo_slug"] == DEMO_SLUG
    assert client.progress_calls[-1]["progress_percent"] == 100
