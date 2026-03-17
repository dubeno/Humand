# Examples

These scripts show how to use Humand from plain Python and LangGraph-style workflows.

## Available Examples

- `local_demo_flow.py`: one-click local demo seeding plus approval/progress flow through the simulator inbox
- `basic_function_approval.py`: minimal `@require_approval` usage
- `feishu_approval_flow.py`: server-backed approval plus Feishu progress updates
- `langgraph_complete_example.py`: full workflow example
- `langgraph_workflow.py`: approval gating inside a graph
- `deepseek_recipe_demo.py`: content generation with review

## Run Locally

Start the server first:

```bash
python server/main.py
```

Then run an example:

```bash
python examples/local_demo_flow.py
python examples/basic_function_approval.py
python examples/feishu_approval_flow.py
```

If you want the fully seeded reviewer experience without a second terminal, prefer `make demo` from the repo root. That starts Docker Compose, seeds the approval automatically, and routes everything through the local simulator inbox at `http://localhost:5000`.

## Feishu Example

`feishu_approval_flow.py` demonstrates:

1. creating an approval request
2. waiting for a human decision
3. sending progress updates while the task runs
4. surfacing the same request in Humand Web UI and Feishu

To use the Feishu path, configure the environment variables in `env.example` and enable `HUMAND_NOTIFICATION_PROVIDERS=feishu`.
