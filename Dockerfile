FROM python:3.12-slim

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖（利用 Docker 层缓存，依赖不变时无需重新安装）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 应用代码
COPY src/ src/

# 脚本（知识库初始化等）
COPY scripts/ scripts/

# 数据目录（知识库向量数据等）
COPY data/ data/

# 环境变量（包含 API key 等敏感信息，生产环境建议改用环境变量注入）
COPY .env .

EXPOSE 8000

# API 服务
CMD ["uvicorn", "src.multi_agent_system.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
