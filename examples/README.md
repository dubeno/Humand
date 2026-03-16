# Humand SDK Examples

本目录包含 Humand SDK 的各种使用示例，展示如何在不同场景中集成人工审批流程。

## 🚀 快速开始

在运行示例之前，请确保：

1. **启动 Humand 服务器**
```bash
python server/main.py
```

2. **访问 Web 界面** 
打开浏览器访问: http://localhost:8000

3. **运行示例**
```bash
# 基础函数审批示例
python examples/basic_function_approval.py

# LangGraph 集成示例
python examples/langgraph_complete_example.py

# LangGraph 工作流示例
python examples/langgraph_workflow.py

# DeepSeek AI 集成示例
python examples/deepseek_recipe_demo.py
```

## 📚 示例说明

### 1. `basic_function_approval.py` - 基础函数审批

展示如何使用 `@require_approval` 装饰器为任何 Python 函数添加审批需求。

**功能演示:**
- ✅ 简单审批配置
- ✅ 带元数据提取的审批
- ✅ 自动审批条件
- ✅ 不同审批类型（数据访问、财务、系统操作）
- ✅ 异常处理

```python
from humand_sdk import require_approval

@require_approval(
    title="Delete User Account",
    approvers=["manager@company.com"],
    timeout_seconds=1800
)
def delete_user_account(user_id: str):
    # 此函数执行前需要审批
    return perform_deletion(user_id)
```

### 2. `langgraph_complete_example.py` - LangGraph 完整集成

完整的 AI 工作流示例：AI 生成内容 → 人工审批 → 发布

**场景:** AI Agent 生成文章，需要人工审批后才能发布

**工作流程:**
1. 生成文章草稿
2. 创建审批请求
3. 等待人工审批
4. 根据审批结果发布或拒绝

```python
# 工作流集成审批
def review_article(state: ArticleState) -> ArticleState:
    client = HumandClient(base_url="http://localhost:8000")
    config = ApprovalConfig.simple(
        title="文章发布审批",
        approvers=["editor@company.com"]
    )
    approval = client.create_approval(config)
    result = client.wait_for_approval(approval.id)
    return update_state(state, result)
```

### 3. `langgraph_workflow.py` - LangGraph 工作流示例

演示如何在 LangGraph 工作流中集成 Humand 审批节点。

**功能演示:**
- ✅ 单个审批门控
- ✅ 多阶段审批流程
- ✅ 基于审批结果的条件路由
- ✅ 拒绝和超时处理
- ✅ 不同审批人的多级审批

**架构:**
```
数据收集 → 审批 → 数据处理 → 生成结果
         ↓ (拒绝)
       处理拒绝
```

### 4. `deepseek_recipe_demo.py` - DeepSeek AI 集成示例

结合 DeepSeek AI 模型和 Humand 审批系统的食谱生成器。

**功能演示:**
- ✅ AI 内容生成
- ✅ 工作流中断和审批
- ✅ 基于反馈的内容改进
- ✅ 多轮审批迭代

**工作流程:**
1. DeepSeek AI 生成食谱
2. 提交人工审批
3. 如果拒绝，根据反馈改进
4. 审批通过后保存

## 🔧 框架无关性

Humand SDK 可以集成到**任何** Python 应用中：

```python
# ✅ 纯 Python 函数
@require_approval(title="Operation", approvers=["admin@company.com"])
def any_function():
    pass

# ✅ FastAPI
@app.post("/delete")
@require_approval(title="Delete", approvers=["admin@company.com"])
async def delete_endpoint():
    pass

# ✅ Django
@require_approval(title="Action", approvers=["admin@company.com"])
def django_view(request):
    pass

# ✅ 异步函数
@require_approval(title="Async Op", approvers=["admin@company.com"])
async def async_function():
    pass

# ✅ LangGraph
def workflow_node(state):
    client = HumandClient()
    config = ApprovalConfig.simple(...)
    approval = client.create_approval(config)
    result = client.wait_for_approval(approval.id)
    return update_state(state, result)
```

**一个装饰器，零框架依赖**

## 📖 更多资源

- **SDK 文档:** 查看 `humand_sdk/` 目录
- **服务器文档:** 查看 `server/` 目录
- **API 参考:** 访问 http://localhost:8000/docs

## 💡 最佳实践

1. **总是设置合理的超时时间** - 避免工作流无限等待
2. **使用元数据提取** - 为审批人提供充足的上下文信息
3. **处理异常** - 妥善处理 `ApprovalRejected` 和 `ApprovalTimeout`
4. **使用合适的审批类型** - 选择匹配场景的审批类型
5. **测试审批流程** - 在开发环境充分测试审批逻辑

## 🤝 贡献

欢迎提交新的示例！请确保：
- 代码清晰易懂
- 包含详细注释
- 添加到此 README 中
