# Humand 服务端

提供 Web 审批界面和 API 服务。

## 目录结构

```
server/
├── auth/           # 用户认证与权限
├── core/           # 核心业务逻辑（模型、审批）
├── web/            # FastAPI 应用 + 模板
├── storage/        # Redis / 内存存储
├── notification/   # 多平台通知 + IM 模拟器
├── utils/          # 配置、诊断
└── main.py         # 启动入口
```

## 启动

```bash
pip install -r requirements.txt   # 根目录
python server/main.py
```

- Web 界面: http://localhost:8000
- IM 模拟器: http://localhost:5000
- API 文档: http://localhost:8000/docs
