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
  "context": {...}
}

Response: 201
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
  "approved_by": ["admin@company.com"]
}
```

### Approve
```http
POST /approval/{id}/approve
Content-Type: application/x-www-form-urlencoded

approver=admin@company.com&comment=OK
```

### Reject
```http
POST /approval/{id}/reject
Content-Type: application/x-www-form-urlencoded

approver=admin@company.com&comment=Denied
```

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
    print(f"Rejected: {e.reason}")
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
```

All optional - zero-config supported.
