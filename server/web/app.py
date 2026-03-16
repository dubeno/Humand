from fastapi import FastAPI, Request, Form, HTTPException, Depends, Header, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import List, Optional
import json
import uuid
from datetime import datetime

from ..core.models import ApprovalRequest, ApprovalResponse, ApprovalStatus
from ..storage import approval_storage
from ..notification.base import multi_platform_notifier
from ..utils.config import config
from ..auth import (
    User, UserRole, Permission, UserCreate, UserLogin,
    user_storage, get_current_user, require_login, require_permission, require_role
)

app = FastAPI(title="Humand 审批系统", version="1.0.0", description="专业的人工审批服务")

# 配置模板和静态文件
import os
template_dir = os.path.join(os.path.dirname(__file__), "templates")
static_dir = os.path.join(os.path.dirname(__file__), "static")
templates = Jinja2Templates(directory=template_dir)

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory=static_dir), name="static")

def require_api_key(authorization: Optional[str] = Header(None)):
    """
    简单的 API Key 鉴权（与 SDK 的 Authorization: Bearer <api_key> 对齐）。
    - 当 config.HUMAND_API_KEY 为空时，默认放行（便于本地开发）。
    """
    expected = (config.HUMAND_API_KEY or "").strip()
    if not expected:
        return

    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少 Authorization")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer" or parts[1] != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API Key 无效")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, user: User = Depends(require_login)):
    """首页 - 显示所有待审批的请求"""
    pending_requests = approval_storage.get_pending_approvals()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "pending_requests": pending_requests,
        "config": config,
        "current_user": user
    })

@app.get("/monitor", response_class=HTMLResponse)
async def monitor(request: Request, user: User = Depends(require_login)):
    """监控页面 - 实时监控审批请求"""
    pending_requests = approval_storage.get_pending_approvals()
    return templates.TemplateResponse("monitor.html", {
        "request": request,
        "pending_requests": pending_requests,
        "config": config,
        "current_user": user
    })

@app.get("/statistics", response_class=HTMLResponse)
async def statistics(
    request: Request,
    user: User = Depends(require_permission(Permission.VIEW_STATISTICS)),
):
    """统计页面 - 显示审批统计数据"""
    stats = approval_storage.get_statistics()
    return templates.TemplateResponse("statistics.html", {
        "request": request,
        "stats": stats,
        "current_user": user
    })

@app.get("/history", response_class=HTMLResponse)
async def history(
    request: Request,
    page: int = 1,
    limit: int = 20,
    user: User = Depends(require_permission(Permission.VIEW_REQUEST)),
):
    """历史记录页面 - 显示所有审批历史"""
    # 获取所有审批记录
    all_approvals = approval_storage.get_all_approvals(limit=1000)
    
    # 筛选已完成的
    history_items = [
        req for req in all_approvals 
        if req.status in [ApprovalStatus.APPROVED, ApprovalStatus.REJECTED, ApprovalStatus.TIMEOUT]
    ]
    
    # 分页
    total = len(history_items)
    total_pages = (total + limit - 1) // limit
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    page_items = history_items[start_idx:end_idx]
    
    # 获取工具列表
    tools = list(set(req.tool_name for req in history_items))
    
    # 计算通过率
    approved_count = sum(1 for req in history_items if req.status == ApprovalStatus.APPROVED)
    approval_rate = round(approved_count / total * 100, 1) if total > 0 else 0
    
    return templates.TemplateResponse("history.html", {
        "request": request,
        "history_items": page_items,
        "history_count": total,
        "current_page": page,
        "total_pages": total_pages,
        "tools": tools,
        "approval_rate": approval_rate,
        "current_user": user
    })

@app.get("/approval/{request_id}", response_class=HTMLResponse)
async def approval_detail(
    request: Request,
    request_id: str,
    user: User = Depends(require_permission(Permission.VIEW_REQUEST)),
):
    """审批详情页"""
    approval_request = approval_storage.get_approval_request(request_id)
    
    if not approval_request:
        raise HTTPException(status_code=404, detail="审批请求不存在")
    
    # 获取查询参数
    approved = request.query_params.get('approved') == 'true'
    rejected = request.query_params.get('rejected') == 'true'
    
    return templates.TemplateResponse("approval_detail_enhanced.html", {
        "request": request,
        "approval_request": approval_request,
        "params_json": json.dumps(approval_request.tool_params, indent=2, ensure_ascii=False),
        "approved": approved,
        "rejected": rejected,
        "current_user": user
    })

@app.post("/approval/{request_id}/approve")
async def approve_request(request_id: str, 
                         approver: str = Form("Web User"),
                         comment: str = Form(""),
                         action_type: str = Form("approve"),
                         guidance_priority: str = Form("suggestion"),
                         user: User = Depends(require_permission(Permission.APPROVE_REQUEST))):
    """批准请求（支持指导）"""
    # 以登录用户为准，忽略前端传入的 approver
    approver = user.username
    approval_request = approval_storage.get_approval_request(request_id)
    
    if not approval_request:
        raise HTTPException(status_code=404, detail="审批请求不存在")
    
    # 根据操作类型处理
    if action_type == "approve_with_guidance":
        # 批准并提供指导
        approval_request.comments.append({
            "type": "guidance",
            "approver": approver,
            "comment": comment,
            "priority": guidance_priority,
            "timestamp": datetime.now().isoformat()
        })
        # 在工具参数中添加指导信息
        approval_request.tool_params["guidance"] = {
            "comment": comment,
            "priority": guidance_priority,
            "approver": approver
        }
    
    success = approval_storage.update_approval_status(
        request_id, ApprovalStatus.APPROVED, approver, comment
    )
    
    if success:
        # 发送结果通知
        updated_request = approval_storage.get_approval_request(request_id)
        if updated_request:
            multi_platform_notifier.send_approval_result(updated_request)
    
    return RedirectResponse(
        url=f"/approval/{request_id}?approved=true", 
        status_code=303
    )

@app.post("/approval/{request_id}/reject")
async def reject_request(request_id: str, 
                        approver: str = Form("Web User"),
                        comment: str = Form(""),
                        reject_category: str = Form("other"),
                        user: User = Depends(require_permission(Permission.REJECT_REQUEST))):
    """拒绝请求"""
    approver = user.username
    approval_request = approval_storage.get_approval_request(request_id)
    
    if approval_request:
        # 添加拒绝详情
        approval_request.comments.append({
            "type": "rejection",
            "approver": approver,
            "comment": comment,
            "category": reject_category,
            "timestamp": datetime.now().isoformat()
        })
        approval_storage.save_approval_request(approval_request)
    
    success = approval_storage.update_approval_status(
        request_id, ApprovalStatus.REJECTED, approver, comment
    )
    
    if success:
        # 发送结果通知
        updated_request = approval_storage.get_approval_request(request_id)
        if updated_request:
            multi_platform_notifier.send_approval_result(updated_request)
    
    return RedirectResponse(
        url=f"/approval/{request_id}?rejected=true", 
        status_code=303
    )

@app.post("/approval/{request_id}/request-changes")
async def request_changes(request_id: str,
                         approver: str = Form(...),
                         comment: str = Form(...),
                         change_deadline: str = Form("immediate"),
                         user: User = Depends(require_permission(Permission.APPROVE_REQUEST))):
    """要求修改"""
    approver = user.username
    approval_request = approval_storage.get_approval_request(request_id)
    
    if not approval_request:
        raise HTTPException(status_code=404, detail="审批请求不存在")
    
    if approval_request.status != ApprovalStatus.PENDING:
        raise HTTPException(status_code=400, detail="请求已处理")
    
    # 添加修改要求到评论中
    approval_request.comments.append({
        "type": "change_request",
        "approver": approver,
        "comment": comment,
        "deadline": change_deadline,
        "timestamp": datetime.now().isoformat()
    })
    
    # 在工具参数中添加修改要求
    approval_request.tool_params["change_requested"] = True
    approval_request.tool_params["change_requirements"] = comment
    approval_request.tool_params["change_deadline"] = change_deadline
    approval_request.tool_params["change_requester"] = approver
    
    approval_storage.save_approval_request(approval_request)
    
    return RedirectResponse(
        url=f"/approval/{request_id}?changes_requested=true", 
        status_code=303
    )

# =============================================================================
# API 端点 - 专注于审批功能
# =============================================================================

@app.get("/api/pending", response_model=List[ApprovalRequest])
async def get_pending_approvals(user: User = Depends(require_permission(Permission.VIEW_REQUEST))):
    """API: 获取待审批请求"""
    return approval_storage.get_pending_approvals()

@app.post("/api/v1/approvals")
async def create_approval_api(approval_data: dict, _=Depends(require_api_key)):
    """API: 创建审批请求"""
    try:
        # 创建审批请求对象
        import uuid
        current_time = datetime.now()
        title = approval_data.get("title", "Approval Required")
        description = approval_data.get("description", "") or "No description provided"
        approvers = approval_data.get("approvers", []) or []
        metadata = approval_data.get("metadata", {}) or {}
        approval_request = ApprovalRequest(
            request_id=str(uuid.uuid4()),
            tool_name=title,
            tool_params=metadata,
            requester=approval_data.get("requester") or metadata.get("requester") or "SDK Client",
            reason=description,
            approvers=approvers,
            request_time=current_time,
            created_at=current_time
        )
        
        # 保存到存储
        approval_storage.save_approval_request(approval_request)
        
        # 发送通知
        multi_platform_notifier.send_approval_request(approval_request)
        
        return {
            "id": approval_request.request_id,
            "title": title,
            "description": description,
            "status": approval_request.status.value,
            "approvers": approvers,
            "created_at": approval_request.created_at.isoformat(),
            "updated_at": approval_request.created_at.isoformat(),
            "approved_by": approval_request.approved_by,
            "rejected_by": approval_request.rejected_by,
            "comments": approval_request.comments,
            "metadata": metadata,
            "web_url": f"http://localhost:8000/approval/{approval_request.request_id}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建审批请求失败: {str(e)}")

@app.get("/api/v1/approvals/{request_id}")
async def get_approval_request(request_id: str, _=Depends(require_api_key)):
    """API: 获取特定审批请求"""
    approval_request = approval_storage.get_approval_request(request_id)
    
    if not approval_request:
        raise HTTPException(status_code=404, detail="审批请求不存在")
    
    # 返回 SDK 兼容的格式
    return {
        "id": approval_request.request_id,
        "title": approval_request.tool_name,
        "description": approval_request.reason,
        "status": approval_request.status.value,
        "approvers": approval_request.approvers,
        "created_at": approval_request.created_at.isoformat(),
        "updated_at": (approval_request.approved_at or approval_request.rejected_at or approval_request.created_at).isoformat(),
        "approved_by": approval_request.approved_by,
        "rejected_by": approval_request.rejected_by,
        "comments": approval_request.comments,
        "metadata": approval_request.tool_params,
        "web_url": f"http://localhost:8000/approval/{approval_request.request_id}"
    }

@app.post("/api/approval/{request_id}/process")
async def process_approval(request_id: str, response: ApprovalResponse, _=Depends(require_api_key)):
    """API: 处理审批请求"""
    approval_request = approval_storage.get_approval_request(request_id)
    
    if not approval_request:
        raise HTTPException(status_code=404, detail="审批请求不存在")
    
    if approval_request.status != ApprovalStatus.PENDING:
        raise HTTPException(status_code=400, detail="请求已经被处理")
    
    # 确定新状态
    new_status = ApprovalStatus.APPROVED if response.action == "approve" else ApprovalStatus.REJECTED
    
    # 更新审批状态
    success = approval_storage.update_approval_status(
        request_id, new_status, response.approver, response.comment
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="更新审批状态失败")
    
    # 发送结果通知
    updated_request = approval_storage.get_approval_request(request_id)
    if updated_request:
        multi_platform_notifier.send_approval_result(updated_request)
    
    return {"success": True, "status": new_status}

@app.get("/test/platforms")
async def test_platforms(user: User = Depends(require_role(UserRole.ADMIN))):
    """测试所有平台连接"""
    results = multi_platform_notifier.test_connection()
    return {"results": results, "message": "平台连接测试完成"}

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "timestamp": datetime.now()}

# =============================================================================
# 用户认证路由
# =============================================================================

@app.get("/auth/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None, success: str = None):
    """登录页面"""
    # 如果已登录，重定向到首页
    current_user = await get_current_user(request)
    if current_user:
        return RedirectResponse(url="/", status_code=303)
    
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": error,
        "success": success
    })

@app.post("/auth/login")
async def login(request: Request,
                username: str = Form(...),
                password: str = Form(...),
                remember_me: bool = Form(False)):
    """处理登录"""
    # 验证用户
    user = user_storage.verify_password(username, password)
    
    if not user:
        return RedirectResponse(
            url="/auth/login?error=" + "用户名或密码错误",
            status_code=303
        )
    
    # 创建会话
    session_id = str(uuid.uuid4())
    ttl_seconds = 30 * 24 * 60 * 60 if remember_me else config.SESSION_TTL_SECONDS
    user_storage.create_session(
        session_id,
        user.user_id,
        {
            "username": user.username,
            "role": user.role,
            "login_time": datetime.now().isoformat(),
        },
        ttl_seconds=ttl_seconds,
    )
    
    # 设置 Cookie
    response = RedirectResponse(url="/", status_code=303)
    max_age = 30 * 24 * 60 * 60 if remember_me else None  # 30天或会话
    response.set_cookie(
        key="session_id",
        value=session_id,
        max_age=max_age,
        httponly=True,
        secure=config.COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    
    return response

@app.get("/auth/logout")
async def logout(request: Request):
    """退出登录"""
    session_id = request.cookies.get("session_id")
    if session_id:
        user_storage.delete_session(session_id)
    
    response = RedirectResponse(url="/auth/login?success=已成功退出登录", status_code=303)
    response.delete_cookie("session_id")
    return response

@app.get("/auth/register", response_class=HTMLResponse)
async def register_page(request: Request, error: str = None):
    """注册页面"""
    # 如果已登录，重定向到首页
    current_user = await get_current_user(request)
    if current_user:
        return RedirectResponse(url="/", status_code=303)
    
    return templates.TemplateResponse("register.html", {
        "request": request,
        "error": error
    })

@app.post("/auth/register")
async def register(request: Request,
                   username: str = Form(...),
                   email: str = Form(...),
                   password: str = Form(...),
                   password_confirm: str = Form(...),
                   full_name: str = Form(...),
                   department: str = Form(None),
                   position: str = Form(None),
                   phone: str = Form(None)):
    """处理注册"""
    # 验证密码
    if password != password_confirm:
        return RedirectResponse(
            url="/auth/register?error=两次输入的密码不一致",
            status_code=303
        )
    
    # 检查用户名是否已存在
    if user_storage.get_user_by_username(username):
        return RedirectResponse(
            url="/auth/register?error=用户名已存在",
            status_code=303
        )
    
    # 检查邮箱是否已存在
    if user_storage.get_user_by_email(email):
        return RedirectResponse(
            url="/auth/register?error=邮箱已被注册",
            status_code=303
        )
    
    # 创建用户
    user_id = str(uuid.uuid4())
    password_hash = user_storage._hash_password(password)
    
    new_user = User(
        user_id=user_id,
        username=username,
        email=email,
        password_hash=password_hash,
        full_name=full_name,
        role=UserRole.REQUESTER,  # 默认角色
        department=department,
        position=position,
        phone=phone
    )
    
    if user_storage.create_user(new_user):
        return RedirectResponse(
            url="/auth/login?success=注册成功，请登录",
            status_code=303
        )
    else:
        return RedirectResponse(
            url="/auth/register?error=注册失败，请重试",
            status_code=303
        )

@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    """个人中心页面"""
    user = await require_login(request)
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": user,
        "current_user": user
    })

@app.post("/profile/update")
async def profile_update(request: Request,
                        email: str = Form(...),
                        phone: str = Form(None),
                        department: str = Form(None),
                        position: str = Form(None)):
    """更新个人信息"""
    user = await require_login(request)
    
    # 如果邮箱改变，检查是否已存在
    if email != user.email:
        existing = user_storage.get_user_by_email(email)
        if existing and existing.user_id != user.user_id:
            return RedirectResponse(
                url="/profile?error=邮箱已被使用",
                status_code=303
            )
    
    # 更新用户信息
    user_storage.update_user(user.user_id, {
        "email": email,
        "phone": phone,
        "department": department,
        "position": position
    })
    
    return RedirectResponse(url="/profile?success=更新成功", status_code=303)

@app.post("/profile/change-password")
async def change_password(request: Request,
                          old_password: str = Form(...),
                          new_password: str = Form(...),
                          new_password_confirm: str = Form(...)):
    """修改密码"""
    user = await require_login(request)
    
    if new_password != new_password_confirm:
        return RedirectResponse(
            url="/profile?error=两次输入的新密码不一致",
            status_code=303
        )
    
    if user_storage.change_password(user.user_id, old_password, new_password):
        return RedirectResponse(
            url="/profile?success=密码修改成功",
            status_code=303
        )
    else:
        return RedirectResponse(
            url="/profile?error=原密码错误",
            status_code=303
        )

# =============================================================================
# 更新现有路由，添加 current_user
# =============================================================================

# 更新其他视图函数，添加 current_user 参数
# （由于代码较长，这里仅演示关键部分，其余视图可类似更新）

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.WEB_HOST, port=config.WEB_PORT)
