# API Reference

## SDK

### Decorator (Recommended)

```python
from humand_sdk import require_approval

@require_approval(
    title: str,                        # Required
    approvers: List[str],              # Required
    description: str = "",             # Optional
    timeout_seconds: int = 3600,       # Optional, default 1h
    require_all_approvers: bool = False,  # Optional
    context_builder: Callable = None   # Optional
)
def your_function():
    pass
```

### Client (Advanced)

```python
from humand_sdk import HumandClient, ApprovalConfig

client = HumandClient(base_url="http://localhost:8000")

# Create approval
config = ApprovalConfig.simple(title="Op", approvers=["admin@company.com"])
request = client.create_approval(config, context={})

# Wait for approval
result = client.wait_for_approval(request.id, poll_interval=5)

# Send a progress update after approval
client.send_progress_update(
    request.id,
    "Deploying canary",
    progress_percent=50,
    stage="deploy"
)

# Check result
if result.is_approved:
    execute()
```

## Server API

### Create Approval
```http
POST /api/v1/approvals
Content-Type: application/json

{
  "title": "Delete User",
  "approvers": ["admin@company.com"],
  "timeout_seconds": 3600,
  "metadata": {...},
  "notification_config": {
    "channels": ["feishu"]
  }
}

Response: 200
{
  "id": "req_123",
  "status": "pending",
  "web_url": "http://localhost:8000/approval/req_123"
}
```

### Get Status
```http
GET /api/v1/approvals/{id}

Response: 200
{
  "id": "req_123",
  "status": "approved|rejected|pending|timeout",
  "approved_by": ["admin@company.com"],
  "progress_updates": []
}
```

### Append Progress
```http
POST /api/v1/approvals/{id}/progress
Content-Type: application/json

{
  "message": "Deploying canary",
  "progress_percent": 50,
  "stage": "deploy",
  "metadata": {
    "release": "2026.03.17"
  }
}
```

### Process Decision
```http
POST /api/approval/{id}/process
Content-Type: application/json

{
  "request_id": "req_123",
  "action": "approve",
  "comment": "Looks good",
  "approver": "admin@company.com"
}
```

### Web Approve
```http
POST /approval/{id}/approve
Content-Type: application/x-www-form-urlencoded

approver=admin@company.com&comment=OK
```

### Web Reject
```http
POST /approval/{id}/reject
Content-Type: application/x-www-form-urlencoded

approver=admin@company.com&comment=Denied
```

### Feishu Callback
```http
POST /api/v1/providers/feishu/callback
```

This endpoint receives Feishu interactive card callbacks and updates the corresponding approval request in storage.

## Web UI

- `/` - Approval dashboard
- `/approval/{id}` - Approval detail
- `/history` - Approval history
- `/statistics` - Stats

## Exceptions

```python
from humand_sdk.exceptions import (
    ApprovalRejected,   # Approval denied
    ApprovalTimeout,    # Approval timed out
    APIError           # Server error
)

try:
    result = approved_function()
except ApprovalRejected as e:
    print(f"Rejected: {e}")
except ApprovalTimeout as e:
    print(f"Timeout after {e.timeout_seconds}s")
```

## Configuration

Environment variables:
```bash
REDIS_HOST=localhost
REDIS_PORT=6379
APPROVERS=admin@company.com
WEB_PORT=8000
APPROVAL_TIMEOUT=3600
HUMAND_PUBLIC_BASE_URL=http://localhost:8000
HUMAND_NOTIFICATION_PROVIDERS=feishu
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_RECEIVE_ID=oc_xxx
FEISHU_RECEIVE_ID_TYPE=chat_id
FEISHU_CALLBACK_VERIFICATION_TOKEN=xxx
HUMAND_SIMULATOR_URL=http://localhost:5000
```

All optional - zero-config supported.
