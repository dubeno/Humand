from server.notification.simulator import IMSimulator


class FakeResponse:
    def __init__(self, payload, ok=True):
        self._payload = payload
        self.ok = ok
        self.text = str(payload)

    def json(self):
        return self._payload


def test_sync_endpoint_stores_approval_card():
    simulator = IMSimulator()
    client = simulator.app.test_client()

    response = client.post(
        "/api/inbox/sync",
        json={
            "event": "approval.created",
            "approval": {
                "id": "approval-123",
                "title": "Approve demo",
                "description": "Seeded for the local demo",
                "requester": "demo-runner",
                "status": "pending",
                "approvers": ["local-reviewer@humand.local"],
                "created_at": "2026-03-17T10:00:00",
                "updated_at": "2026-03-17T10:00:00",
                "metadata": {"demo_slug": "local-one-click-demo"},
                "progress_updates": [],
                "comments": [],
                "web_url": "http://localhost:8000/approval/approval-123",
                "api_url": "http://localhost:8000/api/v1/approvals/approval-123",
            },
        },
    )

    assert response.status_code == 200

    inbox = client.get("/api/inbox/approvals")
    assert inbox.status_code == 200
    payload = inbox.get_json()
    assert len(payload) == 1
    assert payload[0]["id"] == "approval-123"
    assert payload[0]["status"] == "pending"


def test_local_decision_endpoint_updates_synced_approval(monkeypatch):
    simulator = IMSimulator()
    simulator.sync_approval(
        {
            "id": "approval-123",
            "title": "Approve demo",
            "description": "Seeded for the local demo",
            "requester": "demo-runner",
            "status": "pending",
            "approvers": ["local-reviewer@humand.local"],
            "created_at": "2026-03-17T10:00:00",
            "updated_at": "2026-03-17T10:00:00",
            "metadata": {"demo_slug": "local-one-click-demo"},
            "progress_updates": [],
            "comments": [],
            "web_url": "http://localhost:8000/approval/approval-123",
            "api_url": "http://localhost:8000/api/v1/approvals/approval-123",
        }
    )

    def fake_post(url, json, headers, timeout):
        assert url.endswith("/api/approval/approval-123/process")
        assert json["action"] == "approve"
        return FakeResponse(
            {
                "success": True,
                "status": "approved",
                "approval": {
                    "id": "approval-123",
                    "title": "Approve demo",
                    "description": "Seeded for the local demo",
                    "requester": "demo-runner",
                    "status": "approved",
                    "approvers": ["local-reviewer@humand.local"],
                    "approved_by": ["Local Demo Reviewer"],
                    "rejected_by": [],
                    "comments": [],
                    "metadata": {"demo_slug": "local-one-click-demo"},
                    "progress_updates": [],
                    "created_at": "2026-03-17T10:00:00",
                    "updated_at": "2026-03-17T10:01:00",
                    "web_url": "http://localhost:8000/approval/approval-123",
                    "api_url": "http://localhost:8000/api/v1/approvals/approval-123",
                },
            }
        )

    monkeypatch.setattr("server.notification.simulator.requests.post", fake_post)
    client = simulator.app.test_client()

    response = client.post(
        "/api/approvals/approval-123/decision",
        json={"action": "approve", "approver": "Local Demo Reviewer", "comment": "Looks good"},
    )

    assert response.status_code == 200
    assert simulator.approvals["approval-123"]["status"] == "approved"
    assert simulator.approvals["approval-123"]["approved_by"] == ["Local Demo Reviewer"]
