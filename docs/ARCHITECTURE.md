# Architecture

## System Design

```
┌─────────────────────────────────────────┐
│         Client Application              │
│  ┌────────────────────────────────┐     │
│  │  @require_approval decorator   │     │
│  └──────────┬─────────────────────┘     │
└─────────────┼───────────────────────────┘
              │ HTTP
┌─────────────▼───────────────────────────┐
│         Humand Server                   │
│  ┌────────────┐  ┌─────────────┐       │
│  │  FastAPI   │  │   Storage   │       │
│  │  + Web UI  │  │ Redis/Memory│       │
│  └────────────┘  └─────────────┘       │
└─────────────────────────────────────────┘
```

## Core Components

### 1. SDK (`humand_sdk/`)
- `decorators.py`: `@require_approval` implementation
- `client.py`: HTTP client for server communication
- `config.py`: Approval configuration
- `exceptions.py`: Error types

### 2. Server (`server/`)
- `web/app.py`: FastAPI routes + templates
- `core/`: Business logic
- `storage/`: Redis + Memory fallback
- `notification/`: Multi-platform notifications
- `utils/`: Auth, diagnostics, config

### 3. Examples
- `langgraph_complete_example.py`: Full LangGraph workflow

## Data Flow

1. **Client** calls decorated function
2. **Decorator** creates approval request via HTTP
3. **Server** stores request, sends notification
4. **Human** approves via Web UI
5. **Client** polls for result, executes if approved

## Storage Strategy

Auto-fallback:
```python
try:
    redis.ping()
    use_redis()
except:
    use_memory()  # Zero-config
```

## Design Principles

1. **Framework-agnostic**: Standard Python, no framework lock-in
2. **Zero-config**: Works out of box
3. **Production-ready**: Auth, RBAC, audit logs
4. **Extensible**: Plugin storage, notifications

## Performance

- API response: <100ms
- Memory usage: <200MB
- Concurrent requests: 1000+ req/s

## Security

- JWT authentication
- RBAC permissions
- Audit logging
- HTTPS support
