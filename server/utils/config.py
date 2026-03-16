import os
from typing import List
from dotenv import load_dotenv

load_dotenv()

class Config:
    # 运行环境
    ENV = os.getenv("HUMAND_ENV", "development").lower()  # development / production

    # API Key（用于 SDK 调用 /api/v1/* 时的简单鉴权；为空则不校验，便于本地开发）
    HUMAND_API_KEY = os.getenv("HUMAND_API_KEY", "")

    # 企业微信机器人配置
    WECHAT_WEBHOOK_URL = os.getenv("WECHAT_WEBHOOK_URL", "")
    
    # Redis配置
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB = int(os.getenv("REDIS_DB", "0"))
    
    # 审批系统配置
    APPROVAL_TIMEOUT = int(os.getenv("APPROVAL_TIMEOUT", "3600"))  # 1小时
    WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
    WEB_PORT = int(os.getenv("WEB_PORT", "8000"))

    # Cookie 安全参数
    COOKIE_SECURE = os.getenv("HUMAND_COOKIE_SECURE", "").lower() == "true" or ENV == "production"
    SESSION_TTL_SECONDS = int(os.getenv("HUMAND_SESSION_TTL_SECONDS", "86400"))  # 1天
    
    # 审批员配置
    APPROVERS = os.getenv("APPROVERS", "admin@company.com").split(",")
    
    @classmethod
    def get_approvers(cls) -> List[str]:
        return [approver.strip() for approver in cls.APPROVERS]

config = Config() 



