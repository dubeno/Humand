"""
多平台通知器
支持企业微信、飞书、钉钉等多种IM平台的消息推送
"""
import requests
import json
from typing import Dict, Any, List, Optional
from ..core.models import ApprovalRequest
from ..utils.config import config
from enum import Enum

class PlatformType(str, Enum):
    WECHAT = "wechat"
    FEISHU = "feishu"
    DINGTALK = "dingtalk"
    SIMULATOR = "simulator"

class MultiPlatformNotifier:
    """多平台通知器"""
    
    def __init__(self):
        self.webhook_urls = self._load_webhook_urls()
        self.simulator_url = "http://localhost:5000"  # IM模拟器地址
    
    def _load_webhook_urls(self) -> Dict[str, str]:
        """加载各平台的Webhook URL"""
        urls = {}
        
        # 从环境变量加载各平台URL
        if config.WECHAT_WEBHOOK_URL:
            urls[PlatformType.WECHAT] = config.WECHAT_WEBHOOK_URL
        
        # 可以添加更多平台的配置
        # urls[PlatformType.FEISHU] = os.getenv("FEISHU_WEBHOOK_URL", "")
        # urls[PlatformType.DINGTALK] = os.getenv("DINGTALK_WEBHOOK_URL", "")
        
        return urls
    
    def send_approval_request(self, request: ApprovalRequest) -> bool:
        """发送审批请求到所有配置的平台"""
        success_count = 0
        total_platforms = 0
        
        # 发送到真实平台
        for platform, webhook_url in self.webhook_urls.items():
            if webhook_url:
                total_platforms += 1
                if self._send_to_platform(platform, webhook_url, request, "approval_request"):
                    success_count += 1
        
        # 如果没有配置真实平台，发送到模拟器
        if total_platforms == 0:
            total_platforms = 1
            if self._send_to_simulator(request, "approval_request"):
                success_count += 1
        
        print(f"📨 审批通知发送完成: {success_count}/{total_platforms} 个平台成功")
        return success_count > 0
    
    def send_approval_result(self, request: ApprovalRequest) -> bool:
        """发送审批结果通知"""
        success_count = 0
        total_platforms = 0
        
        # 发送到真实平台
        for platform, webhook_url in self.webhook_urls.items():
            if webhook_url:
                total_platforms += 1
                if self._send_to_platform(platform, webhook_url, request, "approval_result"):
                    success_count += 1
        
        # 如果没有配置真实平台，发送到模拟器
        if total_platforms == 0:
            total_platforms = 1
            if self._send_to_simulator(request, "approval_result"):
                success_count += 1
        
        return success_count > 0
    
    def _send_to_platform(self, platform: str, webhook_url: str, request: ApprovalRequest, message_type: str) -> bool:
        """发送消息到指定平台"""
        try:
            if platform == PlatformType.WECHAT:
                return self._send_wechat_message(webhook_url, request, message_type)
            elif platform == PlatformType.FEISHU:
                return self._send_feishu_message(webhook_url, request, message_type)
            elif platform == PlatformType.DINGTALK:
                return self._send_dingtalk_message(webhook_url, request, message_type)
            else:
                print(f"⚠️ 不支持的平台: {platform}")
                return False
        except Exception as e:
            print(f"❌ 发送到{platform}失败: {e}")
            return False
    
    def _send_to_simulator(self, request: ApprovalRequest, message_type: str) -> bool:
        """发送消息到模拟器"""
        try:
            # 随机选择一个平台类型进行模拟
            import random
            platform = random.choice([PlatformType.WECHAT, PlatformType.FEISHU, PlatformType.DINGTALK])
            
            # 构建模拟器Webhook URL
            webhook_id = "default-webhook"
            simulator_webhook = f"{self.simulator_url}/webhook/{platform}/{webhook_id}"
            
            return self._send_wechat_message(simulator_webhook, request, message_type)
        except Exception as e:
            print(f"❌ 发送到模拟器失败: {e}")
            return False
    
    def _send_wechat_message(self, webhook_url: str, request: ApprovalRequest, message_type: str) -> bool:
        """发送企业微信消息"""
        try:
            if message_type == "approval_request":
                content = self._build_wechat_approval_message(request)
            else:
                content = self._build_wechat_result_message(request)
            
            message = {
                "msgtype": "markdown",
                "markdown": {"content": content}
            }
            
            response = requests.post(
                webhook_url,
                json=message,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("errcode", 0) == 0
            
            return False
            
        except Exception as e:
            print(f"❌ 企业微信消息发送失败: {e}")
            return False
    
    def _send_feishu_message(self, webhook_url: str, request: ApprovalRequest, message_type: str) -> bool:
        """发送飞书消息"""
        try:
            if message_type == "approval_request":
                content = self._build_feishu_approval_message(request)
            else:
                content = self._build_feishu_result_message(request)
            
            message = {
                "msg_type": "text",
                "content": {"text": content}
            }
            
            response = requests.post(
                webhook_url,
                json=message,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("StatusCode", 0) == 0
            
            return False
            
        except Exception as e:
            print(f"❌ 飞书消息发送失败: {e}")
            return False
    
    def _send_dingtalk_message(self, webhook_url: str, request: ApprovalRequest, message_type: str) -> bool:
        """发送钉钉消息"""
        try:
            if message_type == "approval_request":
                content = self._build_dingtalk_approval_message(request)
            else:
                content = self._build_dingtalk_result_message(request)
            
            message = {
                "msgtype": "markdown",
                "markdown": {
                    "title": "AI Agent 审批通知",
                    "text": content
                }
            }
            
            response = requests.post(
                webhook_url,
                json=message,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("errcode", 0) == 0
            
            return False
            
        except Exception as e:
            print(f"❌ 钉钉消息发送失败: {e}")
            return False
    
    def _build_wechat_approval_message(self, request: ApprovalRequest) -> str:
        """构建企业微信审批消息"""
        approval_url = f"http://{config.WEB_HOST}:{config.WEB_PORT}/approval/{request.request_id}"
        
        params_str = ""
        if request.tool_params:
            params_str = "\n".join([f"- **{k}**: {v}" for k, v in request.tool_params.items()])
        
        return f"""
## 🤖 AI Agent 工具执行审批

**工具名称**: {request.tool_name}
**申请人**: {request.requester}
**申请时间**: {request.created_at.strftime('%Y-%m-%d %H:%M:%S')}
**申请原因**: {request.reason}

### 工具参数
{params_str or '无参数'}

### 审批操作
请点击以下链接进行审批：
[点击此处审批]({approval_url})

⚠️ **注意**: 此请求将在 {config.APPROVAL_TIMEOUT // 60} 分钟后自动超时

---
*请谨慎审批，确保AI操作的安全性*
"""
    
    def _build_wechat_result_message(self, request: ApprovalRequest) -> str:
        """构建企业微信结果消息"""
        status_text = {
            "approved": "✅ 已批准",
            "rejected": "❌ 已拒绝", 
            "timeout": "⏰ 已超时"
        }.get(request.status, "❓ 未知状态")
        
        return f"""
## 🔔 审批结果通知

**工具名称**: {request.tool_name}
**申请人**: {request.requester}
**申请原因**: {request.reason}
**审批状态**: {status_text}
**审批人**: {request.approver or "系统"}
**审批时间**: {request.approved_at.strftime('%Y-%m-%d %H:%M:%S') if request.approved_at else '未知'}
**审批意见**: {request.approval_comment or '无'}

---
*AI Agent 审批系统*
"""
    
    def _build_feishu_approval_message(self, request: ApprovalRequest) -> str:
        """构建飞书审批消息"""
        approval_url = f"http://{config.WEB_HOST}:{config.WEB_PORT}/approval/{request.request_id}"
        
        params_str = ""
        if request.tool_params:
            params_str = "\n".join([f"- {k}: {v}" for k, v in request.tool_params.items()])
        
        return f"""🤖 AI Agent 工具执行审批

工具名称: {request.tool_name}
申请人: {request.requester}
申请时间: {request.created_at.strftime('%Y-%m-%d %H:%M:%S')}
申请原因: {request.reason}

工具参数:
{params_str or '无参数'}

审批链接: {approval_url}

⚠️ 注意: 此请求将在 {config.APPROVAL_TIMEOUT // 60} 分钟后自动超时

请谨慎审批，确保AI操作的安全性"""
    
    def _build_feishu_result_message(self, request: ApprovalRequest) -> str:
        """构建飞书结果消息"""
        status_text = {
            "approved": "✅ 已批准",
            "rejected": "❌ 已拒绝", 
            "timeout": "⏰ 已超时"
        }.get(request.status, "❓ 未知状态")
        
        return f"""🔔 审批结果通知

工具名称: {request.tool_name}
申请人: {request.requester}
申请原因: {request.reason}
审批状态: {status_text}
审批人: {request.approver or "系统"}
审批时间: {request.approved_at.strftime('%Y-%m-%d %H:%M:%S') if request.approved_at else '未知'}
审批意见: {request.approval_comment or '无'}

AI Agent 审批系统"""
    
    def _build_dingtalk_approval_message(self, request: ApprovalRequest) -> str:
        """构建钉钉审批消息"""
        approval_url = f"http://{config.WEB_HOST}:{config.WEB_PORT}/approval/{request.request_id}"
        
        params_str = ""
        if request.tool_params:
            params_str = "\n".join([f"- **{k}**: {v}" for k, v in request.tool_params.items()])
        
        return f"""
## 🤖 AI Agent 工具执行审批

**工具名称**: {request.tool_name}  
**申请人**: {request.requester}  
**申请时间**: {request.created_at.strftime('%Y-%m-%d %H:%M:%S')}  
**申请原因**: {request.reason}  

### 工具参数
{params_str or '无参数'}

### 审批操作
[点击此处审批]({approval_url})

> ⚠️ **注意**: 此请求将在 {config.APPROVAL_TIMEOUT // 60} 分钟后自动超时

---
*请谨慎审批，确保AI操作的安全性*
"""
    
    def _build_dingtalk_result_message(self, request: ApprovalRequest) -> str:
        """构建钉钉结果消息"""
        status_text = {
            "approved": "✅ 已批准",
            "rejected": "❌ 已拒绝", 
            "timeout": "⏰ 已超时"
        }.get(request.status, "❓ 未知状态")
        
        return f"""
## 🔔 审批结果通知

**工具名称**: {request.tool_name}  
**申请人**: {request.requester}  
**申请原因**: {request.reason}  
**审批状态**: {status_text}  
**审批人**: {request.approver or "系统"}  
**审批时间**: {request.approved_at.strftime('%Y-%m-%d %H:%M:%S') if request.approved_at else '未知'}  
**审批意见**: {request.approval_comment or '无'}  

---
*AI Agent 审批系统*
"""
    
    def test_connection(self) -> Dict[str, bool]:
        """测试所有平台连接"""
        results = {}
        
        # 测试真实平台
        for platform, webhook_url in self.webhook_urls.items():
            if webhook_url:
                results[platform] = self._test_platform_connection(platform, webhook_url)
        
        # 测试模拟器
        results["simulator"] = self._test_simulator_connection()
        
        return results
    
    def _test_platform_connection(self, platform: str, webhook_url: str) -> bool:
        """测试平台连接"""
        try:
            if platform == PlatformType.WECHAT:
                message = {
                    "msgtype": "markdown",
                    "markdown": {"content": "## 🔧 AI Agent 审批系统测试\n\n系统连接正常！"}
                }
            elif platform == PlatformType.FEISHU:
                message = {
                    "msg_type": "text",
                    "content": {"text": "🔧 AI Agent 审批系统测试\n\n系统连接正常！"}
                }
            elif platform == PlatformType.DINGTALK:
                message = {
                    "msgtype": "markdown",
                    "markdown": {
                        "title": "AI Agent 审批系统测试",
                        "text": "## 🔧 AI Agent 审批系统测试\n\n系统连接正常！"
                    }
                }
            else:
                return False
            
            response = requests.post(
                webhook_url,
                json=message,
                headers={"Content-Type": "application/json"},
                timeout=5
            )
            
            return response.status_code == 200
            
        except Exception as e:
            print(f"❌ 测试{platform}连接失败: {e}")
            return False
    
    def _test_simulator_connection(self) -> bool:
        """测试模拟器连接"""
        try:
            response = requests.get(f"{self.simulator_url}/api/messages", timeout=5)
            return response.status_code == 200
        except Exception as e:
            print(f"❌ 测试模拟器连接失败: {e}")
            return False

# 全局通知器实例
multi_platform_notifier = MultiPlatformNotifier() 



