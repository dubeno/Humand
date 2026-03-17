#!/usr/bin/env python3
"""
One-click local demo flow for Humand.

This script is friendly for both local terminals and a Docker Compose demo runner:
- waits for the server and simulator to become ready
- seeds a polished approval request into the local simulator inbox
- optionally waits for approval and then emits progress updates
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import requests

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from humand_sdk import ApprovalConfig, ApprovalRejected, ApprovalTimeout, HumandClient
from humand_sdk.config import NotificationChannel, NotificationConfig


DEMO_SLUG = "local-one-click-demo"
DEFAULT_APPROVER = "local-reviewer@humand.local"
DEFAULT_TITLE = "Approve the Humand local demo rollout"
DEFAULT_DESCRIPTION = (
    "A seeded local-first Humand demo. Approve or reject it in the simulator inbox. "
    "If you approve, the demo runner will post staged progress updates back into the same request."
)
DEFAULT_PROGRESS_STAGES = (
    ("validate", 20, "Validating the approval context"),
    ("dispatch", 45, "Dispatching the job to the local worker"),
    ("execute", 75, "Running the simulated protected action"),
    ("complete", 100, "Local demo finished successfully"),
)


def wait_for_http(
    url: str,
    *,
    label: str,
    timeout_seconds: int = 90,
    poll_interval: float = 2.0,
) -> None:
    deadline = time.time() + timeout_seconds
    last_error = "service did not answer yet"

    while time.time() < deadline:
        try:
            response = requests.get(url, timeout=5)
            if response.ok:
                return
            last_error = f"{response.status_code} {response.reason}"
        except requests.RequestException as exc:
            last_error = str(exc)

        time.sleep(poll_interval)

    raise RuntimeError(
        f"{label} did not become ready at {url} within {timeout_seconds} seconds. "
        f"Last error: {last_error}"
    )


def build_demo_config(
    *,
    approver: str,
    public_base_url: str,
    public_simulator_url: str,
    timeout_seconds: int,
) -> ApprovalConfig:
    return ApprovalConfig.simple(
        title=DEFAULT_TITLE,
        approvers=[approver],
        description=DEFAULT_DESCRIPTION,
        timeout_seconds=timeout_seconds,
        notification_config=NotificationConfig(channels=[NotificationChannel.SIMULATOR]),
        metadata={
            "demo_slug": DEMO_SLUG,
            "demo_type": "local-first",
            "channel": "simulator",
            "service": "payments-api",
            "operation": "customer export",
            "risk_level": "medium",
            "records": 1842,
            "expected_action": "Approve or reject in the local simulator inbox",
            "simulator_url": public_simulator_url.rstrip("/"),
            "server_url": public_base_url.rstrip("/"),
        },
        tags=["demo", "local", "simulator"],
    )


def find_existing_pending_demo(client: HumandClient) -> Optional[object]:
    try:
        pending = client.list_approvals(status="pending", limit=25)
    except Exception:
        return None

    for approval in pending:
        if approval.metadata.get("demo_slug") == DEMO_SLUG:
            return approval
    return None


def create_or_reuse_demo(
    client: HumandClient,
    config: ApprovalConfig,
    *,
    reuse_pending: bool = True,
) -> Tuple[object, bool]:
    if reuse_pending:
        existing = find_existing_pending_demo(client)
        if existing is not None:
            return existing, False

    created = client.create_approval(config)
    return created, True


def emit_progress_updates(
    client: HumandClient,
    approval_id: str,
    *,
    stages: Iterable[Tuple[str, int, str]] = DEFAULT_PROGRESS_STAGES,
    delay_seconds: float = 1.5,
) -> None:
    for stage, percent, message in stages:
        updated = client.send_progress_update(
            approval_id,
            message,
            progress_percent=percent,
            stage=stage,
            metadata={"demo_slug": DEMO_SLUG, "stage": stage},
        )
        print(f"Progress synced: {stage} -> {percent}% ({updated.status})", flush=True)
        time.sleep(delay_seconds)


def print_demo_urls(
    *,
    approval,
    public_base_url: str,
    public_simulator_url: str,
    demo_web_login: str,
) -> None:
    print("", flush=True)
    print("Humand local demo is ready.", flush=True)
    print(f"Simulator inbox: {public_simulator_url.rstrip('/')}", flush=True)
    print(f"Approval JSON: {public_base_url.rstrip('/')}/api/v1/approvals/{approval.id}", flush=True)
    print(f"API docs: {public_base_url.rstrip('/')}/docs", flush=True)
    if demo_web_login:
        print(
            f"Optional Web UI: {public_base_url.rstrip('/')} (login: {demo_web_login})",
            flush=True,
        )
    print(
        "Open the simulator inbox, review the seeded approval, and click Approve or Reject.",
        flush=True,
    )
    print("", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Humand one-click local demo flow.")
    parser.add_argument(
        "--base-url",
        default=os.getenv("HUMAND_SERVER_URL", "http://localhost:8000"),
        help="Humand server base URL used by the demo runner.",
    )
    parser.add_argument(
        "--simulator-url",
        default=os.getenv("HUMAND_SIMULATOR_URL", "http://localhost:5000"),
        help="Internal simulator URL used for readiness checks.",
    )
    parser.add_argument(
        "--public-base-url",
        default=os.getenv("HUMAND_DEMO_PUBLIC_SERVER_URL", "http://localhost:8000"),
        help="Browser-friendly Humand URL printed to the terminal.",
    )
    parser.add_argument(
        "--public-simulator-url",
        default=os.getenv("HUMAND_DEMO_PUBLIC_SIMULATOR_URL", "http://localhost:5000"),
        help="Browser-friendly simulator URL printed to the terminal.",
    )
    parser.add_argument(
        "--approver",
        default=os.getenv("HUMAND_DEMO_APPROVER", DEFAULT_APPROVER),
        help="Email or label shown as the demo approver.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=int(os.getenv("HUMAND_DEMO_TIMEOUT_SECONDS", "1800")),
        help="Approval timeout used when seeding the demo request.",
    )
    parser.add_argument(
        "--ready-timeout",
        type=int,
        default=int(os.getenv("HUMAND_DEMO_READY_TIMEOUT", "120")),
        help="How long to wait for the server and simulator to become healthy.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=float(os.getenv("HUMAND_DEMO_POLL_INTERVAL", "2")),
        help="Polling interval while waiting for approval.",
    )
    parser.add_argument(
        "--progress-delay",
        type=float,
        default=float(os.getenv("HUMAND_DEMO_PROGRESS_DELAY", "1.5")),
        help="Delay between demo progress updates after approval.",
    )
    parser.add_argument(
        "--seed-only",
        action="store_true",
        help="Seed the demo approval and exit without waiting for a decision.",
    )
    parser.add_argument(
        "--always-create",
        action="store_true",
        help="Create a fresh pending demo approval even if one already exists.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    demo_web_login = os.getenv("HUMAND_DEMO_WEB_LOGIN", "")

    print(f"Waiting for Humand server at {args.base_url.rstrip('/')}/health ...", flush=True)
    try:
        wait_for_http(
            f"{args.base_url.rstrip('/')}/health",
            label="Humand server",
            timeout_seconds=args.ready_timeout,
            poll_interval=args.poll_interval,
        )
        wait_for_http(
            f"{args.simulator_url.rstrip('/')}/health",
            label="local simulator",
            timeout_seconds=args.ready_timeout,
            poll_interval=args.poll_interval,
        )
    except RuntimeError as exc:
        print(str(exc), flush=True)
        print(
            "The demo runner is exiting cleanly. Once the services are healthy, rerun the same command.",
            flush=True,
        )
        return 1

    client = HumandClient(
        base_url=args.base_url,
        api_key=os.getenv("HUMAND_API_KEY", ""),
    )
    config = build_demo_config(
        approver=args.approver,
        public_base_url=args.public_base_url,
        public_simulator_url=args.public_simulator_url,
        timeout_seconds=args.timeout_seconds,
    )

    approval, created = create_or_reuse_demo(
        client,
        config,
        reuse_pending=not args.always_create,
    )
    if created:
        print(f"Seeded a new demo approval: {approval.id}", flush=True)
    else:
        print(f"Reusing the existing pending demo approval: {approval.id}", flush=True)

    print_demo_urls(
        approval=approval,
        public_base_url=args.public_base_url,
        public_simulator_url=args.public_simulator_url,
        demo_web_login=demo_web_login,
    )

    if args.seed_only:
        print("Seed-only mode enabled. Leaving the approval pending in the simulator inbox.", flush=True)
        return 0

    try:
        print("Waiting for a local approval decision...", flush=True)
        client.wait_for_approval(
            approval.id,
            timeout_seconds=args.timeout_seconds,
            poll_interval=max(args.poll_interval, 1),
        )
    except ApprovalRejected as exc:
        print(f"Demo request was rejected: {exc}", flush=True)
        return 0
    except ApprovalTimeout as exc:
        print(f"Demo request timed out while waiting for review: {exc}", flush=True)
        return 0

    print("Approval granted. Streaming demo progress updates...", flush=True)
    emit_progress_updates(
        client,
        approval.id,
        delay_seconds=args.progress_delay,
    )
    print("Local demo completed. The simulator inbox now shows the finished request and progress trail.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
