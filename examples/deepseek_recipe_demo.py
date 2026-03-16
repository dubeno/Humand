#!/usr/bin/env python3
"""
DeepSeek LangGraph Recipe Generator with Humand Approval
=======================================================

基于文章示例，使用 DeepSeek 模型和 Humand 审批系统的食谱生成器。
这个演示展示了如何将 LangGraph 的中断机制与 Humand 审批系统完美集成。

参考文章: https://sangeethasaravanan.medium.com/build-llm-workflows-with-langgraph-breakpoints-and-interrupts-for-human-in-the-loop-control-bb311ce681c3
"""

import os
import sys
import time
import requests
from pathlib import Path
from typing import TypedDict, List, Dict, Any

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from langgraph.graph import StateGraph, END
    from langgraph.checkpoint.memory import MemorySaver
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage
    LANGGRAPH_AVAILABLE = True
except ImportError:
    print("⚠️ LangGraph 依赖未安装，请运行: pip install langgraph langchain-openai")
    LANGGRAPH_AVAILABLE = False

from humand_sdk import (
    require_approval,
    HumandClient,
    ApprovalConfig,
    ApprovalRejected,
    ApprovalTimeout
)


class RecipeState(TypedDict):
    """食谱状态定义"""
    ingredients: List[str]
    recipe_name: str
    recipe_steps: List[str]
    approved: bool
    notes: List[str]
    user_feedback: str
    iteration_count: int
    workflow_status: str


class DeepSeekRecipeGenerator:
    """DeepSeek 食谱生成器"""
    
    def __init__(self, api_key: str = None, base_url: str = "https://api.deepseek.com"):
        """
        初始化 DeepSeek 客户端
        
        Args:
            api_key: DeepSeek API 密钥
            base_url: API 基础地址
        """
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            print("⚠️ 未找到 DEEPSEEK_API_KEY，使用模拟模式")
            self.llm = None
        else:
            # 使用 DeepSeek API（兼容 OpenAI 格式）
            self.llm = ChatOpenAI(
                model="deepseek-chat",
                api_key=self.api_key,
                base_url=base_url,
                temperature=0.7,
                max_tokens=2000
            )
        
        self.server_base_url = "http://localhost:8000"
        
    def create_workflow(self) -> StateGraph:
        """创建 LangGraph 工作流"""
        if not LANGGRAPH_AVAILABLE:
            raise ImportError("LangGraph 不可用")
        
        # 创建状态图
        builder = StateGraph(RecipeState)
        
        # 添加节点
        builder.add_node("generate_recipe", self.generate_recipe_node)
        builder.add_node("human_approval", self.create_approval_node())
        builder.add_node("refine_recipe", self.refine_recipe_node)
        builder.add_node("save_recipe", self.save_recipe_node)
        
        # 设置流程
        builder.set_entry_point("generate_recipe")
        
        # 生成食谱后进入审批
        builder.add_edge("generate_recipe", "human_approval")
        
        # 根据审批结果路由
        builder.add_conditional_edges(
            "human_approval",
            self.approval_router,
            {
                "approved": "save_recipe",
                "rejected": "refine_recipe", 
                "pending": "human_approval"
            }
        )
        
        # 优化后重新审批
        builder.add_edge("refine_recipe", "human_approval")
        
        # 保存后结束
        builder.add_edge("save_recipe", END)
        
        # 编译工作流
        # 注意: 如果需要持久化和中断支持，可以添加 checkpointer
        try:
            workflow = builder.compile(
                checkpointer=MemorySaver()
            )
        except Exception:
            # 如果MemorySaver不可用，使用基本编译
            workflow = builder.compile()
        
        return workflow
    
    def generate_recipe_node(self, state: RecipeState) -> RecipeState:
        """生成食谱节点"""
        print(f"\n🍳 正在生成食谱... (第 {state.get('iteration_count', 0) + 1} 次)")
        
        ingredients_text = ", ".join(state["ingredients"])
        
        if self.llm:
            # 使用 DeepSeek 生成
            prompt = f"""
请根据以下食材创建一个美味的食谱：{ingredients_text}

请提供：
1. 一个创意的食谱名称
2. 详细的烹饪步骤（3-6步）

请严格按照以下格式回复：
食谱名称: [名称]
烹饪步骤:
- 步骤 1
- 步骤 2  
- 步骤 3

注意：请确保食谱实用且美味。
"""
            
            try:
                response = self.llm.invoke([HumanMessage(content=prompt)])
                content = response.content
                
                # 解析响应
                if "食谱名称:" in content and "烹饪步骤:" in content:
                    name_section = content.split("食谱名称:")[1].split("烹饪步骤:")[0].strip()
                    steps_section = content.split("烹饪步骤:")[1].strip()
                    
                    recipe_name = name_section
                    recipe_steps = [
                        step.strip().lstrip("- ").lstrip("• ")
                        for step in steps_section.split("\n") 
                        if step.strip() and not step.strip().startswith("食谱名称")
                    ]
                else:
                    raise ValueError("响应格式不正确")
                    
            except Exception as e:
                print(f"⚠️ DeepSeek API 调用失败: {e}")
                # 回退到模拟模式
                recipe_name, recipe_steps = self._generate_mock_recipe(ingredients_text)
        else:
            # 模拟生成
            recipe_name, recipe_steps = self._generate_mock_recipe(ingredients_text)
        
        print(f"✅ 生成完成: {recipe_name}")
        
        return {
            **state,
            "recipe_name": recipe_name,
            "recipe_steps": recipe_steps,
            "iteration_count": state.get("iteration_count", 0) + 1,
            "workflow_status": "recipe_generated"
        }
    
    def _generate_mock_recipe(self, ingredients_text: str) -> tuple:
        """生成模拟食谱"""
        recipe_name = f"美味{ingredients_text.split(',')[0].strip()}料理"
        recipe_steps = [
            f"准备所有食材：{ingredients_text}",
            "将主要食材清洗并切成适当大小",
            "热锅加油，爆炒香料和调料",
            "加入主要食材翻炒至半熟",
            "调味并焖煮5-10分钟至完全熟透",
            "装盘享用美味佳肴"
        ]
        return recipe_name, recipe_steps
    
    def create_approval_node(self):
        """创建审批节点"""
        def approval_node_func(state: RecipeState) -> RecipeState:
            """审批节点函数"""
            print(f"\n📋 创建食谱审批请求...")
            
            iteration = state.get("iteration_count", 1)
            client = HumandClient(base_url=self.server_base_url)
            
            # 创建审批配置
            config = ApprovalConfig.simple(
                title=f"食谱审批 - {state.get('recipe_name', '未知食谱')}",
                approvers=["chef@restaurant.com", "manager@restaurant.com"],
                timeout_seconds=1800,  # 30分钟
                description=f"请审批第{iteration}次生成的食谱",
            )
            
            # 添加上下文
            context = {
                "ingredients": state.get("ingredients", []),
                "iteration": iteration,
                "recipe_name": state.get("recipe_name"),
                "steps_count": len(state.get("recipe_steps", [])),
                "recipe_preview": "\n".join(state.get("recipe_steps", [])[:3])
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
                        "workflow_status": "approved"
                    }
                else:
                    print(f"❌ 审批被拒绝")
                    feedback = result.comments[-1].get("content", "") if result.comments else ""
                    return {
                        **state,
                        "approved": False,
                        "workflow_status": "rejected",
                        "user_feedback": feedback
                    }
            
            except ApprovalRejected as e:
                print(f"❌ 审批被拒绝: {e.rejection_reason}")
                return {
                    **state,
                    "approved": False,
                    "workflow_status": "rejected",
                    "user_feedback": e.rejection_reason or ""
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
                    "user_feedback": str(e)
                }
        
        return approval_node_func
    
    def refine_recipe_node(self, state: RecipeState) -> RecipeState:
        """优化食谱节点"""
        print(f"\n🔄 根据反馈优化食谱...")
        
        if not state.get("user_feedback"):
            print("⚠️ 没有用户反馈，使用默认优化")
            state["user_feedback"] = "请让食谱更加详细和美味"
        
        ingredients_text = ", ".join(state["ingredients"])
        feedback = state["user_feedback"]
        
        if self.llm:
            prompt = f"""
请根据用户反馈改进以下食谱：

原食谱名称: {state["recipe_name"]}
使用食材: {ingredients_text}
原烹饪步骤:
{chr(10).join(f"- {step}" for step in state["recipe_steps"])}

用户反馈: {feedback}

请提供改进版本，格式如下：
食谱名称: [改进的名称]
烹饪步骤:
- 改进步骤 1
- 改进步骤 2
- 改进步骤 3

请确保根据反馈进行针对性改进。
"""
            
            try:
                response = self.llm.invoke([HumanMessage(content=prompt)])
                content = response.content
                
                if "食谱名称:" in content and "烹饪步骤:" in content:
                    name_section = content.split("食谱名称:")[1].split("烹饪步骤:")[0].strip()
                    steps_section = content.split("烹饪步骤:")[1].strip()
                    
                    recipe_name = name_section
                    recipe_steps = [
                        step.strip().lstrip("- ").lstrip("• ")
                        for step in steps_section.split("\n") 
                        if step.strip()
                    ]
                else:
                    raise ValueError("响应格式不正确")
                    
            except Exception as e:
                print(f"⚠️ DeepSeek API 调用失败: {e}")
                # 简单的文本改进
                recipe_name = state["recipe_name"] + " (改进版)"
                recipe_steps = [step + "（已优化）" for step in state["recipe_steps"]]
        else:
            # 模拟优化
            recipe_name = state["recipe_name"] + " (改进版)"
            recipe_steps = [step + "（根据反馈优化）" for step in state["recipe_steps"]]
        
        print(f"✅ 优化完成: {recipe_name}")
        
        return {
            **state,
            "recipe_name": recipe_name,
            "recipe_steps": recipe_steps,
            "approved": False,  # 重置审批状态
            "workflow_status": "recipe_refined"
        }
    
    def save_recipe_node(self, state: RecipeState) -> RecipeState:
        """保存食谱节点"""
        print(f"\n💾 保存食谱: {state['recipe_name']}")
        
        # 调用服务端API保存食谱
        try:
            recipe_data = {
                "name": state["recipe_name"],
                "ingredients": state["ingredients"],
                "steps": state["recipe_steps"],
                "notes": state.get("notes", []),
                "iteration_count": state.get("iteration_count", 1)
            }
            
            response = requests.post(
                f"{self.server_base_url}/api/recipes",
                json=recipe_data,
                timeout=10
            )
            
            if response.status_code == 200:
                print("✅ 食谱已保存到服务器")
                recipe_id = response.json().get("recipe_id")
            else:
                print(f"⚠️ 保存失败: {response.status_code}")
                recipe_id = None
                
        except Exception as e:
            print(f"⚠️ 服务器连接失败: {e}")
            recipe_id = None
        
        # 显示最终食谱
        print(f"\n🎉 最终食谱: {state['recipe_name']}")
        print(f"\n📝 食材:")
        for ingredient in state["ingredients"]:
            print(f"  - {ingredient}")
        
        print(f"\n👨‍🍳 制作步骤:")
        for i, step in enumerate(state["recipe_steps"], 1):
            print(f"  {i}. {step}")
        
        if state.get("notes"):
            print(f"\n📋 备注:")
            for note in state["notes"]:
                print(f"  - {note}")
        
        return {
            **state,
            "workflow_status": "completed",
            "recipe_id": recipe_id
        }
    
    def approval_router(self, state: RecipeState) -> str:
        """审批路由器"""
        workflow_status = state.get("workflow_status", "")
        if state.get("approved"):
            return "approved"
        elif workflow_status in ["rejected", "timeout", "error"]:
            return "rejected"
        else:
            return "pending"
    
    def run_interactive_demo(self):
        """运行交互式演示"""
        print("\n" + "="*60)
        print("🍳 DeepSeek LangGraph 食谱生成器 + Humand 审批系统")
        print("="*60)
        
        if not LANGGRAPH_AVAILABLE:
            print("❌ LangGraph 不可用，请安装依赖")
            return
        
        # 获取食材输入
        print("\n请输入食材 (用逗号分隔):")
        ingredients_input = input("> ")
        ingredients = [i.strip() for i in ingredients_input.split(",") if i.strip()]
        
        if not ingredients:
            ingredients = ["鸡肉", "西兰花", "生抽", "大蒜"]
            print(f"使用默认食材: {ingredients}")
        
        # 初始状态
        initial_state = {
            "ingredients": ingredients,
            "recipe_name": "",
            "recipe_steps": [],
            "approved": False,
            "notes": [],
            "user_feedback": "",
            "iteration_count": 0,
            "workflow_status": "starting"
        }
        
        # 创建工作流
        workflow = self.create_workflow()
        thread_id = f"recipe_{int(time.time())}"
        
        print(f"\n🚀 开始食谱生成工作流...")
        print(f"📋 使用食材: {ingredients}")
        
        try:
            # 第一步：生成食谱
            result = workflow.invoke(
                initial_state,
                config={"configurable": {"thread_id": thread_id}}
            )
            
            print(f"\n⏸️ 工作流在审批前暂停")
            print(f"✨ 生成的食谱: {result['recipe_name']}")
            print(f"📝 共 {len(result['recipe_steps'])} 个步骤")
            
            # 显示食谱详情
            self._display_recipe(result)
            
            input("\n按回车键继续到审批环节...")
            
            # 工作流完成
            print(f"\n📊 工作流执行结果:")
            print(f"状态: {result.get('workflow_status', 'unknown')}")
            print(f"已批准: {'是' if result.get('approved') else '否'}")
            
            if result.get("workflow_status") == "completed":
                print("\n✅ 成功！食谱已保存")
            elif result.get("workflow_status") == "rejected":
                print("\n❌ 食谱被拒绝")
                if result.get("user_feedback"):
                    print(f"💬 反馈: {result['user_feedback']}")
                print("\n💡 提示: 可以根据反馈改进后重新运行")
            elif result.get("workflow_status") == "timeout":
                print("\n⏱️ 审批超时")
            else:
                print(f"\n⚠️ 工作流未完成: {result.get('workflow_status', 'unknown')}")
        
        except KeyboardInterrupt:
            print("\n👋 用户取消操作")
        except Exception as e:
            print(f"\n❌ 工作流执行错误: {e}")
            import traceback
            traceback.print_exc()
    
    def _display_recipe(self, state: RecipeState):
        """显示食谱详情"""
        print(f"\n📖 食谱详情:")
        print(f"🏷️ 名称: {state['recipe_name']}")
        print(f"🥬 食材: {', '.join(state['ingredients'])}")
        print(f"📝 步骤:")
        for i, step in enumerate(state['recipe_steps'], 1):
            print(f"   {i}. {step}")


def main():
    """主函数"""
    print("\n" + "="*60)
    print("🍳 DeepSeek LangGraph 食谱生成器 + Humand 审批系统")
    print("="*60)
    
    print("\n💡 使用前准备:")
    print("1. 确保 Humand 服务器正在运行:")
    print("   python server/main.py")
    print("\n2. (可选) 设置 DeepSeek API Key 启用真实 AI 生成:")
    print("   export DEEPSEEK_API_KEY='your-key-here'")
    print("   当前将使用模拟模式演示工作流")
    print("\n3. 服务器启动后，访问以下地址进行审批:")
    print("   http://localhost:8000")
    print("="*60)
    
    # 检查环境变量
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    if deepseek_key:
        print("\n✅ 检测到 DEEPSEEK_API_KEY，将使用真实 AI 生成")
    else:
        print("\n⚠️ 未设置 DEEPSEEK_API_KEY，使用模拟模式")
    
    input("\n按 Enter 开始运行示例...")
    
    # 创建生成器并运行演示
    generator = DeepSeekRecipeGenerator()
    generator.run_interactive_demo()


if __name__ == "__main__":
    main()
