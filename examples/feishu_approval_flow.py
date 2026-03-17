#!/usr/bin/env python3
"""
Feishu approval flow example.

This example creates an approval request, waits for a Feishu decision,
and then publishes progress updates back to the same approval card.
"""

import os
import sys
import time

from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from humand_sdk import ApprovalConfig, HumandClient, ApprovalRejected, ApprovalTimeout
from humand_sdk.config import NotificationChannel, NotificationConfig


def main() -> None:
    client = HumandClient(
        base_url=os.getenv("HUMAND_SERVER_URL", os.getenv("HUMAND_BASE_URL", "http://localhost:8000")),
        api_key=os.getenv("HUMAND_API_KEY", ""),
    )

    config = ApprovalConfig.simple(
        title="Deploy release to production",
        approvers=["owner@company.com"],
        description="Production deploy requires human approval in Feishu.",
        timeout_seconds=1800,
        notification_config=NotificationConfig(
            channels=[NotificationChannel.FEISHU],
        ),
        metadata={
            "service": "api",
            "release": "2026.03.17",
            "risk_level": "medium",
        },
    )

    approval = client.create_approval(config)
    print(f"Approval created: {approval.id}")
    print(f"Open in Humand: {approval.web_url}")
    print("Approve or reject the card in Feishu, then this script will continue.")

    try:
        client.wait_for_approval(approval.id, poll_interval=3)
    except ApprovalRejected as exc:
        print(f"Rejected: {exc}")
        return
    except ApprovalTimeout as exc:
        print(f"Timed out: {exc}")
        return

    stages = [
        ("build", 20, "Building release artifact"),
        ("deploy", 55, "Rolling out canary"),
        ("verify", 85, "Running post-deploy verification"),
        ("complete", 100, "Deployment finished"),
    ]
    for stage, percent, message in stages:
        updated = client.send_progress_update(
            approval.id,
            message,
            progress_percent=percent,
            stage=stage,
            metadata={"service": "api"},
        )
        print(f"Progress sent: {stage} {percent}% -> {updated.status}")
        time.sleep(1)


if __name__ == "__main__":
    main()
