# Humand - Human-in-the-Loop for AI Agents

The simplest way to add human approval to any Python function or LangGraph workflow.

## Why?

AI agents need human oversight. Humand makes it trivial - one line of code.

## Quick Start

```bash
# Start server
docker-compose up -d

# Use in your code
pip install -e .
```

```python
from humand_sdk import require_approval

@require_approval(
    title="Delete User",
    approvers=["admin@company.com"]
)
def delete_user(user_id: str):
    return db.delete(user_id)
```

That's it. Function pauses, approval request created, execution waits until approved.

## Features

- **Framework-agnostic**: Works with any Python code (LangGraph, FastAPI, Django, Flask, pure functions)
- **Zero-config**: Auto-fallback to memory storage if Redis unavailable
- **Production-ready**: JWT auth, RBAC, audit logs
- **LangGraph native**: Deep integration with StateGraph interrupts

## LangGraph Example

```python
from langgraph.graph import StateGraph
from humand_sdk import require_approval

@require_approval(title="Publish Article", approvers=["editor@company.com"])
def publish_article(state):
    return publish(state["article"])

workflow = StateGraph(State)
workflow.add_node("publish", publish_article)
```

See `examples/langgraph_complete_example.py` for full example.

## Architecture

```
Client (SDK) → Server (FastAPI) → Storage (Redis/Memory)
     ↓              ↓                    ↓
Decorator    Web UI + API         Notifications
```

**Core Components**:
- `humand_sdk/`: Client SDK with `@require_approval` decorator
- `server/`: FastAPI server with approval logic
- `examples/`: LangGraph integration example

## API

```python
# Decorator (recommended)
@require_approval(title, approvers, timeout_seconds=3600)

# Client (advanced)
client = HumandClient(base_url="http://localhost:8000")
request = client.create_approval(config, context)
result = client.wait_for_approval(request.id)
```

## Configuration

Optional `.env`:
```bash
REDIS_HOST=localhost
REDIS_PORT=6379
APPROVERS=admin@company.com
```

No config needed - auto-fallback to memory storage.

## Development

```bash
# Install
pip install -r requirements.txt
pip install -e .

# Run tests
pytest tests/ -v

# Start server
python server/main.py
```

## Docs

- API Reference: `docs/API_REFERENCE.md`
- Architecture: `docs/ARCHITECTURE.md`
- Example: `examples/langgraph_complete_example.py`

## License

MIT
