# Humand 生产环境 Dockerfile
FROM python:3.9-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY server/ ./server/
COPY humand_sdk/ ./humand_sdk/
COPY examples/ ./examples/
COPY setup.py .
COPY README.md .

# 安装 SDK
RUN pip install -e .

# 创建数据和日志目录
RUN mkdir -p /app/data /app/logs

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["python", "server/main.py"]
