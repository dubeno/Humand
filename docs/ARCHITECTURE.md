# Architecture

## Overview

Humand now treats approval delivery as a server-side concern:

```text
SDK / REST clients
        |
        v
FastAPI routes
        |
        v
Approval lifecycle service
        |
        +--> storage
        +--> notification provider registry
```

This keeps the public SDK stable while letting the server evolve from a simple approval page into an interactive approval inbox for AI agents.

## Core Pieces

### SDK

- `humand_sdk/decorators.py`
- `humand_sdk/client.py`

The SDK creates approval requests, waits for decisions, and can now emit progress updates. It does not know how Feishu or any other channel works.

### Approval Lifecycle

- `server/core/service.py`
- `server/core/models.py`

This layer owns:

- approval creation
- progress event recording
- approval / rejection state transitions
- notification fan-out after state changes

All approval entry points should route through this service so the rules stay consistent across Web UI actions, API calls, and Feishu callbacks.

### Provider Layer

- `server/notification/base.py`
- `server/notification/feishu.py`

Providers implement a small interface:

```python
send_approval_request(...)
send_progress_update(...)
update_approval_status(...)
```

The registry resolves which providers should receive a request based on runtime configuration and optional per-request channel hints.

Current implementations:

- `feishu`: app-bot delivery with interactive cards
- `wechat`: webhook delivery
- `dingtalk`: webhook delivery
- `simulator`: local fallback

## Feishu Flow

1. Humand creates and stores an `ApprovalRequest`.
2. The notifier registry selects `FeishuProvider`.
3. `FeishuProvider` sends an interactive card and stores delivery metadata such as:
   - `message_id`
   - `decision_token`
   - sync timestamps and status
4. Feishu posts card actions to `/api/v1/providers/feishu/callback`.
5. Humand validates the callback, maps it back to the approval request, updates internal status, and patches the card to its final state.

The stored `decision_token` gives Humand a request-scoped guard against replaying or mixing callbacks across approval requests.

## Storage Notes

`ApprovalRequest` now persists channel-related metadata:

- `notification_channels`
- `provider_metadata`
- `progress_updates`
- `timeout_seconds`

This is enough to correlate a Feishu action back to the Humand request and keep message/card lifecycle state attached to the approval itself.

## Design Tradeoffs

- Channel logic stays on the server to avoid SDK churn.
- The provider interface is intentionally small so new channels remain easy to add.
- Feishu callback encryption is not implemented yet; the current integration relies on callback verification tokens plus request-scoped decision tokens.
- Webhook channels remain lightweight while Feishu gets the richer interactive-card experience.

## Next Logical Extensions

- Slack provider using the same interface
- email digests / inbox routing
- stronger callback signature verification for Feishu
- richer per-request channel targeting and escalation rules
