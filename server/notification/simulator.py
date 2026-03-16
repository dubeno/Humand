"""
IM平台模拟器
模拟企业微信、飞书、钉钉等平台的消息推送和Webhook接收
"""
import json
import time
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import threading
from flask import Flask, request, jsonify, render_template_string
import requests

class IMPlatform(str, Enum):
    WECHAT = "wechat"
    FEISHU = "feishu"
    DINGTALK = "dingtalk"

@dataclass
class IMMessage:
    """IM消息数据结构"""
    id: str
    platform: IMPlatform
    webhook_url: str
    content: str
    message_type: str
    timestamp: datetime
    sender: str = "AI Agent 审批系统"
    status: str = "sent"
    
    def to_dict(self):
        return {
            "id": self.id,
            "platform": self.platform,
            "webhook_url": self.webhook_url,
            "content": self.content,
            "message_type": self.message_type,
            "timestamp": self.timestamp.isoformat(),
            "sender": self.sender,
            "status": self.status
        }

class IMSimulator:
    """IM平台模拟器"""
    
    def __init__(self):
        self.messages: List[IMMessage] = []
        self.webhooks: Dict[str, Dict] = {}
        self.app = Flask(__name__)
        self.setup_routes()
        
    def setup_routes(self):
        """设置Flask路由"""
        
        @self.app.route('/')
        def index():
            return render_template_string(self.get_dashboard_template(), 
                                        messages=self.messages,
                                        webhooks=self.webhooks)
        
        @self.app.route('/webhook/<platform>/<webhook_id>', methods=['POST'])
        def receive_webhook(platform, webhook_id):
            """接收Webhook消息"""
            try:
                data = request.get_json()
                webhook_url = f"/webhook/{platform}/{webhook_id}"
                
                # 解析不同平台的消息格式
                message = self.parse_message(platform, webhook_url, data)
                if message:
                    self.messages.append(message)
                    print(f"📨 收到{platform}消息: {message.content[:50]}...")
                
                # 模拟平台响应
                return self.get_platform_response(platform)
                
            except Exception as e:
                print(f"❌ Webhook处理失败: {e}")
                return jsonify({"errcode": 1, "errmsg": str(e)}), 500
        
        @self.app.route('/api/messages')
        def get_messages():
            """获取所有消息"""
            return jsonify([msg.to_dict() for msg in self.messages])
        
        @self.app.route('/api/clear', methods=['POST'])
        def clear_messages():
            """清空消息"""
            self.messages.clear()
            return jsonify({"success": True})
        
        @self.app.route('/api/webhook/create', methods=['POST'])
        def create_webhook():
            """创建新的Webhook"""
            data = request.get_json()
            platform = data.get('platform', 'wechat')
            webhook_id = str(uuid.uuid4())
            webhook_url = f"http://localhost:5000/webhook/{platform}/{webhook_id}"
            
            self.webhooks[webhook_id] = {
                "id": webhook_id,
                "platform": platform,
                "url": webhook_url,
                "created_at": datetime.now().isoformat()
            }
            
            return jsonify({
                "webhook_id": webhook_id,
                "webhook_url": webhook_url,
                "platform": platform
            })
    
    def parse_message(self, platform: str, webhook_url: str, data: Dict) -> Optional[IMMessage]:
        """解析不同平台的消息格式"""
        try:
            platform_enum = IMPlatform(platform)
            
            if platform_enum == IMPlatform.WECHAT:
                return self.parse_wechat_message(webhook_url, data)
            elif platform_enum == IMPlatform.FEISHU:
                return self.parse_feishu_message(webhook_url, data)
            elif platform_enum == IMPlatform.DINGTALK:
                return self.parse_dingtalk_message(webhook_url, data)
            
        except Exception as e:
            print(f"❌ 消息解析失败: {e}")
            return None
    
    def parse_wechat_message(self, webhook_url: str, data: Dict) -> IMMessage:
        """解析企业微信消息"""
        msgtype = data.get('msgtype', 'text')
        
        if msgtype == 'text':
            content = data.get('text', {}).get('content', '')
        elif msgtype == 'markdown':
            content = data.get('markdown', {}).get('content', '')
        else:
            content = json.dumps(data, ensure_ascii=False)
        
        return IMMessage(
            id=str(uuid.uuid4()),
            platform=IMPlatform.WECHAT,
            webhook_url=webhook_url,
            content=content,
            message_type=msgtype,
            timestamp=datetime.now()
        )
    
    def parse_feishu_message(self, webhook_url: str, data: Dict) -> IMMessage:
        """解析飞书消息"""
        msg_type = data.get('msg_type', 'text')
        
        if msg_type == 'text':
            content = data.get('content', {}).get('text', '')
        elif msg_type == 'interactive':
            content = json.dumps(data.get('card', {}), ensure_ascii=False)
        else:
            content = json.dumps(data, ensure_ascii=False)
        
        return IMMessage(
            id=str(uuid.uuid4()),
            platform=IMPlatform.FEISHU,
            webhook_url=webhook_url,
            content=content,
            message_type=msg_type,
            timestamp=datetime.now()
        )
    
    def parse_dingtalk_message(self, webhook_url: str, data: Dict) -> IMMessage:
        """解析钉钉消息"""
        msgtype = data.get('msgtype', 'text')
        
        if msgtype == 'text':
            content = data.get('text', {}).get('content', '')
        elif msgtype == 'markdown':
            content = data.get('markdown', {}).get('text', '')
        else:
            content = json.dumps(data, ensure_ascii=False)
        
        return IMMessage(
            id=str(uuid.uuid4()),
            platform=IMPlatform.DINGTALK,
            webhook_url=webhook_url,
            content=content,
            message_type=msgtype,
            timestamp=datetime.now()
        )
    
    def get_platform_response(self, platform: str) -> Dict:
        """获取平台响应格式"""
        if platform == IMPlatform.WECHAT:
            return jsonify({"errcode": 0, "errmsg": "ok"})
        elif platform == IMPlatform.FEISHU:
            return jsonify({"StatusCode": 0, "StatusMessage": "success"})
        elif platform == IMPlatform.DINGTALK:
            return jsonify({"errcode": 0, "errmsg": "ok"})
        else:
            return jsonify({"success": True})
    
    def get_dashboard_template(self) -> str:
        """获取仪表板HTML模板"""
        return """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IM平台模拟器</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.8.1/font/bootstrap-icons.css" rel="stylesheet">
    <style>
        .message-card {
            border-left: 4px solid #007bff;
            margin-bottom: 1rem;
        }
        .platform-badge {
            font-size: 0.8em;
        }
        .message-content {
            max-height: 200px;
            overflow-y: auto;
            background-color: #f8f9fa;
            border-radius: 4px;
            padding: 0.5rem;
        }
        .webhook-item {
            background-color: #f8f9fa;
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 0.5rem;
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="#">
                <i class="bi bi-chat-dots"></i> IM平台模拟器
            </a>
            <div class="navbar-nav ms-auto">
                <button class="btn btn-outline-light btn-sm" onclick="clearMessages()">
                    <i class="bi bi-trash"></i> 清空消息
                </button>
                <button class="btn btn-outline-light btn-sm ms-2" onclick="location.reload()">
                    <i class="bi bi-arrow-clockwise"></i> 刷新
                </button>
            </div>
        </div>
    </nav>

    <div class="container mt-4">
        <div class="row">
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header">
                        <h5><i class="bi bi-link-45deg"></i> Webhook管理</h5>
                    </div>
                    <div class="card-body">
                        <div class="mb-3">
                            <label class="form-label">平台类型</label>
                            <select class="form-select" id="platformSelect">
                                <option value="wechat">企业微信</option>
                                <option value="feishu">飞书</option>
                                <option value="dingtalk">钉钉</option>
                            </select>
                        </div>
                        <button class="btn btn-primary w-100" onclick="createWebhook()">
                            <i class="bi bi-plus"></i> 创建Webhook
                        </button>
                        
                        <div class="mt-3">
                            <h6>已创建的Webhook:</h6>
                            <div id="webhookList">
                                {% for webhook_id, webhook in webhooks.items() %}
                                <div class="webhook-item">
                                    <div class="d-flex justify-content-between align-items-center">
                                        <span class="badge bg-secondary">{{ webhook.platform }}</span>
                                        <button class="btn btn-sm btn-outline-primary" onclick="copyToClipboard('{{ webhook.url }}')">
                                            <i class="bi bi-clipboard"></i>
                                        </button>
                                    </div>
                                    <small class="text-muted d-block mt-1">{{ webhook.url }}</small>
                                </div>
                                {% endfor %}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="col-md-8">
                <div class="card">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <h5><i class="bi bi-chat-left-text"></i> 消息记录</h5>
                        <span class="badge bg-primary">{{ messages|length }} 条消息</span>
                    </div>
                    <div class="card-body" style="max-height: 600px; overflow-y: auto;">
                        {% if messages %}
                            {% for message in messages|reverse %}
                            <div class="message-card card">
                                <div class="card-body">
                                    <div class="d-flex justify-content-between align-items-start mb-2">
                                        <div>
                                            <span class="badge bg-info platform-badge">{{ message.platform }}</span>
                                            <span class="badge bg-secondary platform-badge">{{ message.message_type }}</span>
                                        </div>
                                        <small class="text-muted">{{ message.timestamp.strftime('%H:%M:%S') }}</small>
                                    </div>
                                    <div class="message-content">
                                        <pre style="white-space: pre-wrap; margin: 0;">{{ message.content }}</pre>
                                    </div>
                                </div>
                            </div>
                            {% endfor %}
                        {% else %}
                            <div class="text-center py-5">
                                <i class="bi bi-inbox" style="font-size: 3rem; color: #6c757d;"></i>
                                <h5 class="mt-3 text-muted">暂无消息</h5>
                                <p class="text-muted">等待接收IM平台消息...</p>
                            </div>
                        {% endif %}
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        function createWebhook() {
            const platform = document.getElementById('platformSelect').value;
            
            fetch('/api/webhook/create', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ platform: platform })
            })
            .then(response => response.json())
            .then(data => {
                alert('Webhook创建成功！\\n' + data.webhook_url);
                location.reload();
            })
            .catch(error => {
                console.error('Error:', error);
                alert('创建失败: ' + error);
            });
        }
        
        function clearMessages() {
            if (confirm('确定要清空所有消息吗？')) {
                fetch('/api/clear', {
                    method: 'POST'
                })
                .then(() => {
                    location.reload();
                })
                .catch(error => {
                    console.error('Error:', error);
                });
            }
        }
        
        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(() => {
                alert('已复制到剪贴板: ' + text);
            });
        }
        
        // 自动刷新
        setInterval(() => {
            location.reload();
        }, 10000);
    </script>
</body>
</html>
        """
    
    def run(self, host='localhost', port=5000, debug=True):
        """运行模拟器"""
        print(f"🚀 启动IM平台模拟器: http://{host}:{port}")
        print("支持的平台: 企业微信、飞书、钉钉")
        self.app.run(host=host, port=port, debug=debug)

# 全局模拟器实例
im_simulator = IMSimulator()
app = im_simulator.app  # 导出app供外部使用

if __name__ == "__main__":
    im_simulator.run() 
