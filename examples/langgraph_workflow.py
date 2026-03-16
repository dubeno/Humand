#!/usr/bin/env python3
"""
LangGraph Workflow Example
==========================

This example demonstrates how to integrate Humand approval nodes
into LangGraph workflows for human-in-the-loop AI applications.
"""

import os
import sys
from typing import Dict, Any, TypedDict, List
from datetime import datetime

# Add the parent directory to the path so we can import humand_sdk
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from langgraph.graph import StateGraph, END
    LANGGRAPH_AVAILABLE = True
except ImportError:
    print("⚠️ LangGraph not available. Install with: pip install langgraph")
    LANGGRAPH_AVAILABLE = False
    sys.exit(1)

from humand_sdk import (
    HumandClient,
    ApprovalConfig,
    ApprovalRejected,
    ApprovalTimeout
)


# Define the workflow state
class DataProcessingState(TypedDict):
    """State for data processing workflow."""
    # Input data
    data_source: str
    processing_type: str
    user_id: str
    
    # Processing state
    current_step: str
    data_collected: bool
    data_processed: bool
    results_generated: bool
    
    # Approval state
    approval_id: str
    approval_status: str
    approved: bool
    approver: str
    
    # Results
    raw_data: Dict[str, Any]
    processed_data: Dict[str, Any]
    final_results: Dict[str, Any]
    
    # Metadata
    started_at: str
    completed_at: str
    error_message: str


def collect_data_node(state: DataProcessingState) -> DataProcessingState:
    """Collect data from the specified source."""
    print(f"📊 Collecting data from: {state['data_source']}")
    
    # Simulate data collection
    raw_data = {
        "source": state["data_source"],
        "records": 1500,
        "size_mb": 25.6,
        "collected_at": datetime.now().isoformat(),
        "contains_pii": state["data_source"] in ["customer_db", "user_profiles"]
    }
    
    print(f"✅ Data collected: {raw_data['records']} records ({raw_data['size_mb']} MB)")
    
    return {
        **state,
        "current_step": "data_collected",
        "data_collected": True,
        "raw_data": raw_data
    }


def process_data_node(state: DataProcessingState) -> DataProcessingState:
    """Process the collected data."""
    print(f"⚙️ Processing data with method: {state['processing_type']}")
    
    raw_data = state["raw_data"]
    
    # Simulate data processing
    processed_data = {
        "source": raw_data["source"],
        "original_records": raw_data["records"],
        "processed_records": raw_data["records"] - 50,  # Some filtering
        "processing_method": state["processing_type"],
        "processed_at": datetime.now().isoformat(),
        "quality_score": 0.95
    }
    
    print(f"✅ Data processed: {processed_data['processed_records']} records")
    print(f"📈 Quality score: {processed_data['quality_score']}")
    
    return {
        **state,
        "current_step": "data_processed",
        "data_processed": True,
        "processed_data": processed_data
    }


def generate_results_node(state: DataProcessingState) -> DataProcessingState:
    """Generate final results and insights."""
    print(f"📊 Generating final results...")
    
    processed_data = state["processed_data"]
    
    # Simulate result generation
    final_results = {
        "summary": {
            "total_records": processed_data["processed_records"],
            "processing_method": processed_data["processing_method"],
            "quality_score": processed_data["quality_score"]
        },
        "insights": [
            "Data quality is excellent (95% score)",
            "Processing completed successfully",
            f"Ready for {state['processing_type']} analysis"
        ],
        "recommendations": [
            "Consider automated processing for similar datasets",
            "Archive raw data after 30 days",
            "Schedule regular quality checks"
        ],
        "generated_at": datetime.now().isoformat()
    }
    
    print(f"✅ Results generated with {len(final_results['insights'])} insights")
    
    return {
        **state,
        "current_step": "results_generated",
        "results_generated": True,
        "final_results": final_results,
        "completed_at": datetime.now().isoformat()
    }


def approval_node(state: DataProcessingState) -> DataProcessingState:
    """Request approval for data processing."""
    print(f"\n📋 创建审批请求...")
    
    # 创建客户端
    client = HumandClient(base_url="http://localhost:8000")
    
    # 创建审批配置
    config = ApprovalConfig.data_access(
        title="Data Processing Approval",
        approvers=["data_manager@company.com", "privacy_officer@company.com"],
        data_description=f"Processing {state['data_source']} with {state['processing_type']} method"
    )
    
    # 添加上下文
    context = {
        "data_source": state["data_source"],
        "processing_type": state["processing_type"],
        "user_id": state["user_id"],
        "contains_pii": state["raw_data"].get("contains_pii", False) if state["raw_data"] else False
    }
    
    try:
        # 创建审批请求
        approval_request = client.create_approval(config, context=context)
        print(f"✅ 审批请求已创建: {approval_request.id}")
        print(f"🔗 审批链接: {approval_request.web_url}")
        
        # 等待审批
        print(f"⏳ 等待审批...")
        result = client.wait_for_approval(approval_request.id, poll_interval=5)
        
        if result.is_approved:
            print(f"✅ 审批通过！")
            print(f"👤 审批人: {', '.join(result.approved_by)}")
            return {
                **state,
                "approved": True,
                "approval_id": approval_request.id,
                "approval_status": "approved",
                "approver": result.approved_by[0] if result.approved_by else ""
            }
        else:
            print(f"❌ 审批被拒绝")
            return {
                **state,
                "approved": False,
                "approval_id": approval_request.id,
                "approval_status": "rejected",
                "approver": result.rejected_by[0] if result.rejected_by else ""
            }
    
    except ApprovalRejected as e:
        print(f"❌ 审批被拒绝: {e.rejection_reason}")
        return {
            **state,
            "approved": False,
            "approval_status": "rejected",
            "approver": e.rejected_by or ""
        }
    except ApprovalTimeout as e:
        print(f"⏱️ 审批超时")
        return {
            **state,
            "approved": False,
            "approval_status": "timeout"
        }
    except Exception as e:
        print(f"💥 审批过程出错: {e}")
        return {
            **state,
            "approved": False,
            "approval_status": "error"
        }


def check_approval_status(state: DataProcessingState) -> str:
    """Check if the approval was granted."""
    return state.get("approval_status", "pending")


def handle_rejection_node(state: DataProcessingState) -> DataProcessingState:
    """Handle approval rejection."""
    print(f"❌ Processing request was rejected")
    print(f"👤 Rejected by: {state.get('approver', 'Unknown')}")
    
    return {
        **state,
        "current_step": "rejected",
        "completed_at": datetime.now().isoformat(),
        "error_message": "Processing rejected by approver"
    }


def handle_timeout_node(state: DataProcessingState) -> DataProcessingState:
    """Handle approval timeout."""
    print(f"⏰ Approval request timed out")
    
    return {
        **state,
        "current_step": "timeout",
        "completed_at": datetime.now().isoformat(),
        "error_message": "Approval request timed out"
    }


def create_data_processing_workflow() -> StateGraph:
    """Create the data processing workflow with approval gates."""
    
    # Create the state graph
    builder = StateGraph(DataProcessingState)
    
    # Add processing nodes
    builder.add_node("collect_data", collect_data_node)
    builder.add_node("approval", approval_node)  # Humand approval integration
    builder.add_node("process_data", process_data_node)
    builder.add_node("generate_results", generate_results_node)
    builder.add_node("handle_rejection", handle_rejection_node)
    builder.add_node("handle_timeout", handle_timeout_node)
    
    # Set up the workflow flow
    builder.set_entry_point("collect_data")
    
    # After data collection, request approval
    builder.add_edge("collect_data", "approval")
    
    # Route based on approval result
    builder.add_conditional_edges(
        "approval",
        check_approval_status,
        {
            "approved": "process_data",
            "rejected": "handle_rejection",
            "timeout": "handle_timeout"
        }
    )
    
    # Continue processing after approval
    builder.add_edge("process_data", "generate_results")
    
    # End states
    builder.add_edge("generate_results", END)
    builder.add_edge("handle_rejection", END)
    builder.add_edge("handle_timeout", END)
    
    return builder.compile()


def create_approval_node_for_stage(stage: str, config: ApprovalConfig):
    """Helper to create approval nodes for different stages."""
    def approval_stage_node(state: DataProcessingState) -> DataProcessingState:
        print(f"\n📋 创建 {stage} 审批请求...")
        
        client = HumandClient(base_url="http://localhost:8000")
        
        # 添加当前阶段的上下文
        context = {
            "stage": stage,
            "data_source": state.get("data_source", ""),
            "processing_type": state.get("processing_type", ""),
            "user_id": state.get("user_id", "")
        }
        
        try:
            approval_request = client.create_approval(config, context=context)
            print(f"✅ {stage} 审批请求已创建: {approval_request.id}")
            print(f"🔗 审批链接: {approval_request.web_url}")
            
            print(f"⏳ 等待审批...")
            result = client.wait_for_approval(approval_request.id, poll_interval=5)
            
            if result.is_approved:
                print(f"✅ {stage} 审批通过！")
                return {
                    **state,
                    "approved": True,
                    "approval_status": "approved",
                    "approver": result.approved_by[0] if result.approved_by else ""
                }
            else:
                print(f"❌ {stage} 审批被拒绝")
                return {
                    **state,
                    "approved": False,
                    "approval_status": "rejected"
                }
        except (ApprovalRejected, ApprovalTimeout) as e:
            print(f"❌ {stage} 审批失败: {e}")
            return {
                **state,
                "approved": False,
                "approval_status": "rejected" if isinstance(e, ApprovalRejected) else "timeout"
            }
    
    return approval_stage_node


def create_multi_approval_workflow() -> StateGraph:
    """Create a workflow with multiple approval gates."""
    
    builder = StateGraph(DataProcessingState)
    
    # Add processing nodes
    builder.add_node("collect_data", collect_data_node)
    builder.add_node("process_data", process_data_node)
    builder.add_node("generate_results", generate_results_node)
    builder.add_node("handle_rejection", handle_rejection_node)
    
    # Create approval configurations for each stage
    data_access_config = ApprovalConfig.data_access(
        title="Data Access Approval",
        approvers=["dpo@company.com"],
        data_description="Customer database access for analytics"
    )
    
    processing_config = ApprovalConfig.simple(
        title="Data Processing Approval",
        approvers=["data_manager@company.com"],
        description="Approval to process collected data"
    )
    
    publication_config = ApprovalConfig.simple(
        title="Results Publication Approval",
        approvers=["manager@company.com"],
        description="Approval to publish analysis results"
    )
    
    # Add approval nodes for each stage
    builder.add_node("data_access_approval", 
                    create_approval_node_for_stage("Data Access", data_access_config))
    builder.add_node("processing_approval", 
                    create_approval_node_for_stage("Processing", processing_config))
    builder.add_node("publication_approval", 
                    create_approval_node_for_stage("Publication", publication_config))
    
    # Set up multi-gate workflow
    builder.set_entry_point("data_access_approval")
    
    # First approval gate: data access
    builder.add_conditional_edges(
        "data_access_approval",
        check_approval_status,
        {
            "approved": "collect_data",
            "rejected": "handle_rejection",
            "timeout": "handle_rejection"
        }
    )
    
    # After data collection, second approval gate
    builder.add_edge("collect_data", "processing_approval")
    builder.add_conditional_edges(
        "processing_approval",
        check_approval_status,
        {
            "approved": "process_data",
            "rejected": "handle_rejection",
            "timeout": "handle_rejection"
        }
    )
    
    # After processing, third approval gate
    builder.add_edge("process_data", "publication_approval")
    builder.add_conditional_edges(
        "publication_approval",
        check_approval_status,
        {
            "approved": "generate_results",
            "rejected": "handle_rejection",
            "timeout": "handle_rejection"
        }
    )
    
    # End states
    builder.add_edge("generate_results", END)
    builder.add_edge("handle_rejection", END)
    
    return builder.compile()


def run_workflow_example(workflow: StateGraph, workflow_name: str, 
                        initial_state: DataProcessingState):
    """Run a workflow example."""
    print(f"\n🚀 Running {workflow_name}")
    print("=" * 60)
    
    try:
        # Execute the workflow
        result = workflow.invoke(initial_state)
        
        print(f"\n📊 Workflow Results:")
        print(f"  Status: {result.get('current_step', 'unknown')}")
        print(f"  Started: {result.get('started_at', 'N/A')}")
        print(f"  Completed: {result.get('completed_at', 'N/A')}")
        
        if result.get('error_message'):
            print(f"  Error: {result['error_message']}")
        
        if result.get('final_results'):
            insights = result['final_results'].get('insights', [])
            print(f"  Insights: {len(insights)} generated")
            for insight in insights:
                print(f"    - {insight}")
        
        return result
        
    except Exception as e:
        print(f"❌ Workflow failed: {e}")
        return None


def main():
    """Run the LangGraph workflow examples."""
    print("🎯 Humand SDK - LangGraph Workflow Examples")
    print("=" * 60)
    
    print("\n📋 This example demonstrates:")
    print("  1. Single approval gate in LangGraph workflow")
    print("  2. Multiple approval gates with different approvers")
    print("  3. Conditional routing based on approval results")
    print("  4. Error handling for rejections and timeouts")
    print("  5. Integration of Humand client API in workflow nodes")
    
    print(f"\n💡 Note: Make sure Humand server is running at http://localhost:8000")
    print(f"   Start server: python server/main.py")
    
    # Example 1: Single approval workflow
    print(f"\n" + "="*60)
    print(f"📋 Example 1: Single Approval Gate Workflow")
    print("="*60)
    
    single_approval_workflow = create_data_processing_workflow()
    
    initial_state = DataProcessingState(
        data_source="customer_db",
        processing_type="analytics",
        user_id="analyst_001",
        current_step="starting",
        data_collected=False,
        data_processed=False,
        results_generated=False,
        approval_id="",
        approval_status="",
        approved=False,
        approver="",
        raw_data={},
        processed_data={},
        final_results={},
        started_at=datetime.now().isoformat(),
        completed_at="",
        error_message=""
    )
    
    result1 = run_workflow_example(
        single_approval_workflow,
        "Single Approval Workflow",
        initial_state
    )
    
    input("\nPress Enter to continue to multi-approval example...")
    
    # Example 2: Multi-approval workflow
    print(f"\n" + "="*60)
    print(f"📋 Example 2: Multi-Approval Gate Workflow")
    print("="*60)
    
    multi_approval_workflow = create_multi_approval_workflow()
    
    initial_state2 = DataProcessingState(
        data_source="sensitive_customer_data",
        processing_type="machine_learning",
        user_id="ml_engineer_001",
        current_step="starting",
        data_collected=False,
        data_processed=False,
        results_generated=False,
        approval_id="",
        approval_status="",
        approved=False,
        approver="",
        raw_data={},
        processed_data={},
        final_results={},
        started_at=datetime.now().isoformat(),
        completed_at="",
        error_message=""
    )
    
    result2 = run_workflow_example(
        multi_approval_workflow,
        "Multi-Approval Workflow",
        initial_state2
    )
    
    print(f"\n🎉 All workflow examples completed!")
    print(f"\n💡 Key takeaways:")
    print(f"  ✓ Humand client integrates seamlessly with LangGraph")
    print(f"  ✓ Approval gates control workflow execution flow")
    print(f"  ✓ Multiple approval types supported (simple, data access, financial)")
    print(f"  ✓ Conditional routing based on approval results")
    print(f"  ✓ Comprehensive error handling for rejections and timeouts")
    print(f"  ✓ Support for multi-stage approval workflows")
    
    print(f"\n🚀 Next steps:")
    print(f"  - Try basic function approvals: python examples/basic_function_approval.py")
    print(f"  - Check out article workflow: python examples/langgraph_complete_example.py")
    print(f"  - Explore DeepSeek integration: python examples/deepseek_recipe_demo.py")
    print(f"  - View approval requests at: http://localhost:8000")


if __name__ == "__main__":
    if LANGGRAPH_AVAILABLE:
        main()
    else:
        print("Please install LangGraph to run this example:")
        print("pip install humand-sdk[langgraph]")
