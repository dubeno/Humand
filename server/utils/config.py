import os
from typing import List

from dotenv import load_dotenv

load_dotenv()


class Config:
    ENV = os.getenv("HUMAND_ENV", "development").lower()

    HUMAND_API_KEY = os.getenv("HUMAND_API_KEY", "")
    HUMAND_PUBLIC_BASE_URL = os.getenv("HUMAND_PUBLIC_BASE_URL", "")
    HUMAND_NOTIFICATION_PROVIDERS = os.getenv("HUMAND_NOTIFICATION_PROVIDERS", "")

    WECHAT_WEBHOOK_URL = os.getenv("WECHAT_WEBHOOK_URL", "")
    FEISHU_WEBHOOK_URL = os.getenv("FEISHU_WEBHOOK_URL", "")
    DINGTALK_WEBHOOK_URL = os.getenv("DINGTALK_WEBHOOK_URL", "")

    FEISHU_OPEN_BASE_URL = os.getenv(
        "FEISHU_OPEN_BASE_URL",
        "https://open.feishu.cn/open-apis",
    )
    FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
    FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
    FEISHU_RECEIVE_ID = os.getenv("FEISHU_RECEIVE_ID", "")
    FEISHU_RECEIVE_ID_TYPE = os.getenv("FEISHU_RECEIVE_ID_TYPE", "chat_id")
    FEISHU_CALLBACK_VERIFICATION_TOKEN = os.getenv(
        "FEISHU_CALLBACK_VERIFICATION_TOKEN",
        "",
    )

    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB = int(os.getenv("REDIS_DB", "0"))

    APPROVAL_TIMEOUT = int(os.getenv("APPROVAL_TIMEOUT", "3600"))
    WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
    WEB_PORT = int(os.getenv("WEB_PORT", "8000"))
    SIMULATOR_URL = os.getenv("HUMAND_SIMULATOR_URL", "http://localhost:5000")

    COOKIE_SECURE = os.getenv("HUMAND_COOKIE_SECURE", "").lower() == "true" or ENV == "production"
    SESSION_TTL_SECONDS = int(os.getenv("HUMAND_SESSION_TTL_SECONDS", "86400"))

    APPROVERS = os.getenv("APPROVERS", "admin@company.com").split(",")

    @classmethod
    def get_approvers(cls) -> List[str]:
        return [approver.strip() for approver in cls.APPROVERS if approver.strip()]

    @classmethod
    def get_public_base_url(cls) -> str:
        if cls.HUMAND_PUBLIC_BASE_URL.strip():
            return cls.HUMAND_PUBLIC_BASE_URL.strip().rstrip("/")

        host = cls.WEB_HOST
        if host in {"0.0.0.0", "::", ""}:
            host = "localhost"
        return f"http://{host}:{cls.WEB_PORT}"

    @classmethod
    def get_notification_providers(cls) -> List[str]:
        raw = cls.HUMAND_NOTIFICATION_PROVIDERS.strip()
        if not raw:
            return []
        return [item.strip().lower() for item in raw.split(",") if item.strip()]


config = Config()
