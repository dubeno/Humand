#!/usr/bin/env python3
"""
LangGraph 完整集成示例
====================

展示如何在 LangGraph 工作流中集成 Humand 审批系统。

场景：AI Agent 生成文章，需要人工审批后才能发布。
"""

import sys
from pathlib import Path
from typing import TypedDict, Annotated
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from langgraph.graph import StateGraph, END
from humand_sdk import (
    require_approval, 
    HumandClient,
    ApprovalConfig,
    ApprovalRejected,
    ApprovalTimeout
)


# ========================================
# 1. 定义状态
# ========================================

class ArticleState(TypedDict):
    """文章生成工作流状态"""
    topic: str                    # 文章主题
    draft: str                    # 草稿内容
    approved: bool                # 是否已批准
    approval_id: str              # 审批请求ID
    published: bool               # 是否已发布
    feedback: str                 # 审批反馈
    workflow_status: str          # 工作流状态


# ========================================
# 2. 工作流节点
# ========================================

def generate_article(state: ArticleState) -> ArticleState:
    """
    步骤 1: 生成文章草稿（模拟 AI 生成）
    """
    print(f"\n📝 生成文章草稿...")
    print(f"主题: {state['topic']}")
    
    # 模拟 AI 生成（实际应该调用 LLM）
    draft = f"""
# {state['topic']}

## 引言
这是一篇关于 {state['topic']} 的文章...

## 主要内容
详细介绍 {state['topic']} 的核心概念和应用场景...

## 结论
{state['topic']} 是一个重要的话题...

---
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """.strip()
    
    print(f"\n✅ 草稿已生成 ({len(draft)} 字符)")
    print(f"预览:\n{draft[:200]}...\n")
    
    return {
        **state,
        "draft": draft,
        "workflow_status": "draft_generated"
    }


def review_article(state: ArticleState) -> ArticleState:
    """
    步骤 2: 审批文章（需要人工审批）
    
    这个函数会：
    1. 创建审批请求
    2. 发送通知给审批人
    3. 等待审批结果
    4. 根据审批结果更新状态
    """
    from humand_sdk import HumandClient, ApprovalConfig
    
    print(f"\n⏳ 创建审批请求...")
    
    # 创建客户端
    client = HumandClient(base_url="http://localhost:8000")
    
    # 创建审批配置
    config = ApprovalConfig.simple(
        title=f"文章发布审批: {state['topic']}",
        approvers=["editor@company.com", "manager@company.com"],
        description="AI 生成的文章需要审批后才能发布",
        timeout_seconds=3600,  # 1小时
    )
    
    # 添加文章上下文信息
    context = {
        "topic": state.get("topic", ""),
        "draft_length": len(state.get("draft", "")),
        "draft_preview": state.get("draft", "")[:500],
        "generated_at": datetime.now().isoformat()
    }
    
    try:
        # 创建审批请求
        approval_request = client.create_approval(config, context=context)
        print(f"📋 审批请求已创建: {approval_request.id}")
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
                "workflow_status": "approved"
            }
        else:
            print(f"❌ 审批被拒绝")
            return {
                **state,
                "approved": False,
                "approval_id": approval_request.id,
                "workflow_status": "rejected",
                "feedback": result.comments[-1].get("content", "") if result.comments else ""
            }
    
    except ApprovalRejected as e:
        print(f"❌ 审批被拒绝: {e.rejection_reason}")
        return {
            **state,
            "approved": False,
            "workflow_status": "rejected",
            "feedback": e.rejection_reason or ""
        }
    except ApprovalTimeout as e:
        print(f"⏱️ 审批超时")
        return {
            **state,
            "approved": False,
            "workflow_status": "timeout"
        }
    except Exception as e:
        print(f"💥 审批过程出错: {e}")
        return {
            **state,
            "approved": False,
            "workflow_status": "error",
            "feedback": str(e)
        }


def publish_article(state: ArticleState) -> ArticleState:
    """
    步骤 3: 发布文章
    """
    print(f"\n🚀 发布文章...")
    
    # 模拟发布操作
    article_id = f"article_{datetime.now().timestamp():.0f}"
    print(f"文章 ID: {article_id}")
    print(f"发布时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    print(f"\n✅ 文章已成功发布！")
    
    return {
        **state,
        "published": True,
        "workflow_status": "published"
    }


def handle_rejection(state: ArticleState) -> ArticleState:
    """
    步骤 4: 处理拒绝（如果审批被拒绝）
    """
    print(f"\n❌ 文章审批被拒绝")
    feedback = state.get('feedback', '无反馈')
    print(f"💬 反馈意见: {feedback}")
    print(f"📝 可以根据反馈修改文章后重新提交")
    
    return {
        **state,
        "approved": False,
        "published": False,
        "workflow_status": "rejected"
    }


# ========================================
# 3. 条件路由
# ========================================

def should_publish(state: ArticleState) -> str:
    """
    决定下一步：发布还是拒绝
    """
    if state.get("approved", False):
        return "publish"
    else:
        return "reject"


# ========================================
# 4. 构建工作流
# ========================================

def create_article_workflow():
    """
    创建文章生成和审批工作流
    
    流程:
    1. generate_article (生成草稿)
    2. review_article (人工审批) ← 暂停点
    3. publish_article (发布) 或 handle_rejection (拒绝)
    """
    # 创建状态图
    workflow = StateGraph(ArticleState)
    
    # 添加节点
    workflow.add_node("generate", generate_article)
    workflow.add_node("review", review_article)
    workflow.add_node("publish", publish_article)
    workflow.add_node("reject", handle_rejection)
    
    # 设置入口点
    workflow.set_entry_point("generate")
    
    # 添加边
    workflow.add_edge("generate", "review")
    
    # 条件边：根据审批结果决定下一步
    workflow.add_conditional_edges(
        "review",
        should_publish,
        {
            "publish": "publish",
            "reject": "reject"
        }
    )
    
    # 添加结束边
    workflow.add_edge("publish", END)
    workflow.add_edge("reject", END)
    
    return workflow.compile()


# ========================================
# 5. 主函数
# ========================================

def main():
    """
    主函数：运行完整的文章生成和审批流程
    """
    print("=" * 60)
    print("🎯 LangGraph + Humand 集成示例")
    print("场景: AI 生成文章 → 人工审批 → 发布")
    print("=" * 60)
    
    # 创建工作流
    app = create_article_workflow()
    
    # 初始状态
    initial_state: ArticleState = {
        "topic": "人工智能在医疗领域的应用",
        "draft": "",
        "approved": False,
        "approval_id": "",
        "published": False,
        "feedback": "",
        "workflow_status": "starting"
    }
    
    try:
        # 运行工作流
        print("\n🚀 启动工作流...\n")
        
        result = app.invoke(initial_state)
        
        # 显示最终结果
        print("\n" + "=" * 60)
        print("📊 工作流执行结果")
        print("=" * 60)
        print(f"主题: {result['topic']}")
        print(f"状态: {result['workflow_status']}")
        print(f"已批准: {'是' if result.get('approved') else '否'}")
        print(f"已发布: {'是' if result.get('published') else '否'}")
        
        if result.get('published'):
            print("\n✅ 成功！文章已发布")
            print(f"📋 审批 ID: {result.get('approval_id', 'N/A')}")
        else:
            print("\n❌ 失败！文章未发布")
            print(f"📊 工作流状态: {result.get('workflow_status', 'unknown')}")
            if result.get('feedback'):
                print(f"💬 反馈: {result['feedback']}")
        
    except KeyboardInterrupt:
        print(f"\n👋 用户中断操作")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


# ========================================
# 6. 替代方案：使用装饰器简化审批逻辑
# ========================================

def create_workflow_with_decorator():
    """
    使用装饰器方式创建工作流（更简洁的实现）
    """
    
    @require_approval(
        title="文章发布审批",
        approvers=["editor@company.com", "manager@company.com"],
        description="AI 生成的文章需要审批后才能发布",
        timeout_seconds=3600,
        sync=True  # 同步等待审批
    )
    def publish_with_approval(state: ArticleState) -> ArticleState:
        """发布文章（带审批）"""
        print(f"\n🚀 发布文章: {state.get('topic', 'Unknown')}")
        return publish_article(state)
    
    # 创建状态图
    workflow = StateGraph(ArticleState)
    
    # 添加节点
    workflow.add_node("generate", generate_article)
    workflow.add_node("publish_approved", publish_with_approval)  # 使用带装饰器的函数
    
    # 设置流程
    workflow.set_entry_point("generate")
    workflow.add_edge("generate", "publish_approved")
    workflow.add_edge("publish_approved", END)
    
    return workflow.compile()


# ========================================
# 7. 运行示例
# ========================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("💡 使用前准备:")
    print("="*60)
    print("1. 确保 Humand 服务器正在运行:")
    print("   python server/main.py")
    print("\n2. 服务器启动后，访问以下地址进行审批:")
    print("   http://localhost:8000")
    print("\n3. 本示例将展示完整的 LangGraph + Humand 集成")
    print("="*60)
    
    input("\n按 Enter 开始运行示例...")
    
    main()


# ========================================
# 8. 其他框架示例（框架无关性）
# ========================================

"""
========================================
示例：FastAPI 集成
========================================
"""

def fastapi_example():
    from fastapi import FastAPI
    
    app = FastAPI()
    
    @app.post("/articles/publish")
    @require_approval(
        title="发布文章",
        approvers=["editor@company.com"]
    )
    async def publish_article_api(article_id: str):
        # 发布文章逻辑
        return {"status": "published", "article_id": article_id}


"""
========================================
示例：Django 集成
========================================
"""

def django_example():
    from django.http import JsonResponse
    
    @require_approval(
        title="删除文章",
        approvers=["admin@company.com"]
    )
    def delete_article_view(request, article_id):
        # 删除文章逻辑
        return JsonResponse({"status": "deleted"})


"""
========================================
示例：纯 Python 函数
========================================
"""

@require_approval(
    title="清理缓存",
    approvers=["ops@company.com"]
)
def clear_cache():
    """清理缓存（需要审批）"""
    # 清理逻辑
    return {"status": "cleared"}


"""
========================================
示例：异步函数
========================================
"""

@require_approval(
    title="异步数据处理",
    approvers=["admin@company.com"]
)
async def process_data_async(data):
    """异步处理数据（需要审批）"""
    # 异步处理逻辑
    return {"status": "processed"}


print("""
========================================
💡 框架无关性说明
========================================

Humand 可以集成到任何 Python 应用：

1. ✅ LangGraph（本示例）
2. ✅ FastAPI
3. ✅ Django
4. ✅ Flask
5. ✅ 纯 Python 函数
6. ✅ 异步应用
7. ✅ 任何其他框架

只需一行装饰器：
@require_approval(...)

========================================
""")

