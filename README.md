# Humand

Human-in-the-loop approvals for AI agents and Python workflows.

Humand started as a lightweight approval decorator. It now also exposes a server-side notification provider layer, so approval requests can be delivered into interactive inbox channels such as Feishu while keeping the SDK API stable.

## What You Get

- Python SDK with `@require_approval`
- FastAPI approval server with Web UI and API
- Pluggable notification providers for approval delivery
- Feishu interactive approval cards as a first-class provider
- Redis storage with in-memory fallback for local development

## Quick Start

```bash
pip install -r requirements.txt
pip install -e .
python server/main.py
```

```python
from humand_sdk import require_approval


@require_approval(
    title="Delete Customer Workspace",
    approvers=["owner@company.com"],
    timeout_seconds=1800,
)
def delete_workspace(workspace_id: str):
    return {"deleted": workspace_id}
```

## Supported Channels

- `web`: built-in Humand Web UI
- `feishu`: interactive card approvals with callback handling
- `wechat`: webhook notifications
- `dingtalk`: webhook notifications
- `simulator`: local fallback when no real provider is configured

## Architecture

```text
SDK / API client
        |
        v
FastAPI approval service
        |
        v
Approval lifecycle service
        |
        v
Notification provider registry
        |
        +--> Feishu interactive cards
        +--> Webhook-based providers
        +--> Local simulator fallback
        |
        v
Redis / in-memory storage
```

The provider interface currently supports:

- `send_approval_request(...)`
- `send_progress_update(...)`
- `update_approval_status(...)`

This keeps channel delivery concerns in the server, not the SDK, and gives Humand a clear path to future Slack, email, or DingTalk implementations.

## Feishu Setup

Copy `env.example` to `.env` and set:

```bash
HUMAND_PUBLIC_BASE_URL=http://localhost:8000
HUMAND_NOTIFICATION_PROVIDERS=feishu

FEISHU_APP_ID=
FEISHU_APP_SECRET=
FEISHU_RECEIVE_ID=
FEISHU_RECEIVE_ID_TYPE=chat_id
FEISHU_CALLBACK_VERIFICATION_TOKEN=
```

Notes:

- `FEISHU_RECEIVE_ID` is the chat or user identifier Humand should deliver cards to.
- `FEISHU_RECEIVE_ID_TYPE=chat_id` is the simplest shared-inbox setup.
- If Feishu is not configured, Humand still works and falls back to the local simulator.

## Progress Updates

The SDK now includes an additive `send_progress_update(...)` helper:

```python
from humand_sdk import HumandClient

client = HumandClient(base_url="http://localhost:8000")
client.send_progress_update(
    approval_id,
    "Rolling out migration",
    progress_percent=60,
    stage="deploy",
)
```

Feishu reuses the same approval card and updates it in place when possible.

## Example

See `examples/feishu_approval_flow.py` for a minimal end-to-end flow:

1. Create an approval request
2. Deliver it to Feishu
3. Wait for approval or rejection
4. Emit progress updates while the task runs

## Local Callback Testing

You can simulate a Feishu approve action without real Feishu traffic:

```bash
curl -X POST http://localhost:8000/api/v1/providers/feishu/callback \
  -H 'Content-Type: application/json' \
  -d '{
    "token": "your-verification-token",
    "event": {
      "action": {
        "value": {
          "action": "approve",
          "request_id": "approval-request-id",
          "decision_token": "decision-token-from-provider-metadata"
        }
      },
      "operator": {
        "open_id": "ou_test",
        "name": "Local Tester"
      },
      "open_message_id": "om_test"
    }
  }'
```

In development mode, you can query `GET /api/v1/approvals/{id}` and inspect `provider_metadata.feishu` to capture the `decision_token`.

## Development

```bash
python3 -m pytest tests -q
```

Key files:

- `server/core/service.py`
- `server/notification/base.py`
- `server/notification/feishu.py`
- `server/web/app.py`

## Docs

- `docs/ARCHITECTURE.md`
- `examples/README.md`

## License

MIT
