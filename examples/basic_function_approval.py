#!/usr/bin/env python3
"""
Basic Function Approval Example
===============================

This example demonstrates how to use the @require_approval decorator
to add human approval requirements to any Python function.
"""

import os
import sys
from typing import Dict, Any

# Add the parent directory to the path so we can import humand_sdk
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from humand_sdk import (
    require_approval, 
    HumandClient, 
    ApprovalConfig,
    ApprovalRejected,
    ApprovalTimeout
)


# Example 1: Simple approval with basic configuration
@require_approval(
    title="Delete User Account",
    approvers=["manager@company.com"],
    description="This action will permanently delete a user account",
    timeout_seconds=1800  # 30 minutes
)
def delete_user_account(user_id: str, reason: str = "User request") -> Dict[str, Any]:
    """
    Delete a user account - requires manager approval.
    
    Args:
        user_id: ID of the user to delete
        reason: Reason for deletion
        
    Returns:
        Result of the deletion operation
    """
    print(f"🗑️ Deleting user account: {user_id}")
    print(f"📝 Reason: {reason}")
    
    # Simulate deletion logic
    return {
        "status": "deleted",
        "user_id": user_id,
        "deleted_at": "2024-01-15T10:30:00Z",
        "reason": reason
    }


# Example 2: Financial approval with metadata extraction
def extract_financial_metadata(amount: float, currency: str, **kwargs) -> Dict[str, Any]:
    """Extract metadata for financial approvals."""
    return {
        "amount": amount,
        "currency": currency,
        "risk_level": "high" if amount > 10000 else "medium" if amount > 1000 else "low",
        "requires_compliance_check": amount > 5000
    }


@require_approval(
    title="Process Payment",
    approvers=["finance@company.com", "manager@company.com"],
    description="Large payment requires dual approval",
    timeout_seconds=3600,  # 1 hour
    require_comment=True,
    metadata_extractor=extract_financial_metadata
)
def process_payment(amount: float, currency: str = "USD", 
                   recipient: str = "", description: str = "") -> Dict[str, Any]:
    """
    Process a payment - requires finance and manager approval for large amounts.
    
    Args:
        amount: Payment amount
        currency: Currency code
        recipient: Payment recipient
        description: Payment description
        
    Returns:
        Payment processing result
    """
    print(f"💰 Processing payment: {currency} {amount:,.2f}")
    print(f"👤 Recipient: {recipient}")
    print(f"📝 Description: {description}")
    
    # Simulate payment processing
    return {
        "status": "processed",
        "transaction_id": f"TXN_{hash(f'{amount}{recipient}') % 100000:05d}",
        "amount": amount,
        "currency": currency,
        "recipient": recipient,
        "processed_at": "2024-01-15T10:30:00Z"
    }


# Example 3: Data access approval with auto-approve conditions
def should_auto_approve_data_access(data_type: str, user_role: str, **kwargs) -> bool:
    """Check if data access should be auto-approved."""
    # Auto-approve for admins accessing non-sensitive data
    if user_role == "admin" and data_type in ["logs", "metrics"]:
        return True
    # Auto-approve for analysts accessing analytics data
    if user_role == "analyst" and data_type == "analytics":
        return True
    return False


@require_approval(
    title="Access Sensitive Data",
    approvers=["dpo@company.com", "security@company.com"],
    description="Access to sensitive customer data requires approval",
    timeout_seconds=7200,  # 2 hours
    require_comment=True,
    auto_approve_conditions=should_auto_approve_data_access
)
def access_customer_data(data_type: str, user_role: str, 
                        purpose: str = "") -> Dict[str, Any]:
    """
    Access customer data - requires DPO approval unless auto-approved.
    
    Args:
        data_type: Type of data being accessed
        user_role: Role of the user requesting access
        purpose: Purpose of data access
        
    Returns:
        Data access result
    """
    print(f"🔐 Accessing customer data: {data_type}")
    print(f"👤 User role: {user_role}")
    print(f"🎯 Purpose: {purpose}")
    
    # Simulate data access
    return {
        "status": "access_granted",
        "data_type": data_type,
        "user_role": user_role,
        "purpose": purpose,
        "accessed_at": "2024-01-15T10:30:00Z",
        "records_accessed": 1250
    }


# Example 4: System operation with conditional approval based on severity
def should_auto_approve_system_op(operation: str, severity: str, **kwargs) -> bool:
    """Auto-approve low-severity operations."""
    return severity == "low"


@require_approval(
    title="System Operation",  # Will be dynamically customized
    approvers=["sre@company.com", "manager@company.com"],
    description="System operation requires approval",
    timeout_seconds=3600,
    require_comment=True,
    metadata_extractor=lambda operation, severity, **kwargs: {
        "operation": operation,
        "severity": severity,
        "risk_level": "critical" if severity == "critical" else "elevated" if severity == "high" else "normal",
        "timestamp": "2024-01-15T10:30:00Z"
    },
    auto_approve_conditions=should_auto_approve_system_op
)
def perform_system_operation(operation: str, severity: str = "medium", 
                           parameters: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Perform system operation with dynamic approval requirements.
    
    Args:
        operation: Type of operation to perform
        severity: Severity level (low, medium, high, critical)
        parameters: Operation parameters
        
    Returns:
        Operation result
    """
    print(f"⚙️ Performing system operation: {operation}")
    print(f"🚨 Severity: {severity}")
    print(f"📋 Parameters: {parameters}")
    
    # Simulate system operation
    return {
        "status": "completed",
        "operation": operation,
        "severity": severity,
        "parameters": parameters or {},
        "completed_at": "2024-01-15T10:30:00Z",
        "duration_seconds": 45
    }


def main():
    """Run the basic function approval examples."""
    print("🎯 Humand SDK - Basic Function Approval Examples")
    print("=" * 60)
    
    print("\n📋 This example demonstrates:")
    print("  1. Simple function approval with @require_approval decorator")
    print("  2. Financial approval with metadata extraction")
    print("  3. Data access approval with auto-approve conditions")
    print("  4. System operation with conditional approval and severity levels")
    
    print(f"\n💡 Note: Make sure Humand server is running at http://localhost:8000")
    print(f"   Start server: python server/main.py")
    
    examples = [
        {
            "name": "Delete User Account",
            "function": delete_user_account,
            "args": ("user123",),
            "kwargs": {"reason": "Account closure request"}
        },
        {
            "name": "Process Payment",
            "function": process_payment,
            "args": (5000.0,),
            "kwargs": {
                "currency": "USD",
                "recipient": "Vendor Corp",
                "description": "Monthly service payment"
            }
        },
        {
            "name": "Access Customer Data (Auto-approved)",
            "function": access_customer_data,
            "args": ("analytics", "analyst"),
            "kwargs": {"purpose": "Monthly report generation"}
        },
        {
            "name": "Access Customer Data (Requires approval)",
            "function": access_customer_data,
            "args": ("pii", "developer"),
            "kwargs": {"purpose": "Debug customer issue"}
        },
        {
            "name": "System Operation (Low - Auto-approved)",
            "function": perform_system_operation,
            "args": ("log_rotation", "low"),
            "kwargs": {"parameters": {"max_size_mb": 100}}
        },
        {
            "name": "System Operation (Critical - Requires approval)",
            "function": perform_system_operation,
            "args": ("database_migration", "critical"),
            "kwargs": {"parameters": {"backup_created": True, "downtime_window": "2AM-4AM"}}
        }
    ]
    
    for i, example in enumerate(examples, 1):
        print(f"\n" + "="*60)
        print(f"📋 Example {i}: {example['name']}")
        print("="*60)
        
        try:
            result = example["function"](*example["args"], **example["kwargs"])
            print(f"✅ Result: {result}")
        except ApprovalRejected as e:
            print(f"❌ Approval rejected: {e.rejection_reason}")
            print(f"   Rejected by: {e.rejected_by}")
        except ApprovalTimeout as e:
            print(f"⏱️ Approval timeout: waited {e.timeout_seconds}s")
        except Exception as e:
            print(f"💥 Unexpected error: {e}")
        
        if i < len(examples):
            input("\nPress Enter to continue to next example...")
    
    print(f"\n🎉 All examples completed!")
    print(f"\n💡 Key features demonstrated:")
    print(f"  ✓ Simple approval requirements")
    print(f"  ✓ Metadata extraction from function arguments")
    print(f"  ✓ Auto-approval based on conditions")
    print(f"  ✓ Different approval types (data access, financial, system ops)")
    print(f"  ✓ Error handling for rejections and timeouts")
    print(f"\n🚀 Next steps:")
    print(f"  - Try the LangGraph integration: python examples/langgraph_complete_example.py")
    print(f"  - Check out DeepSeek demo: python examples/deepseek_recipe_demo.py")
    print(f"  - View approval requests at: http://localhost:8000")


if __name__ == "__main__":
    main()
