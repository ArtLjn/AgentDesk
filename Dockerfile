FROM python:3.12-slim

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖（利用 Docker 层缓存，依赖不变时无需重新安装）
ARG PIP_INDEX_URL=https://pypi.org/simple
COPY requirements.txt .
RUN pip install --no-cache-dir -i ${PIP_INDEX_URL} -r requirements.txt

# 应用代码
COPY src/ src/

# 脚本（知识库初始化等）
COPY scripts/ scripts/

# 数据目录（运行时通过 volume 挂载，镜像中仅创建空目录）
RUN mkdir -p data

# 环境变量通过 docker-compose 或运行时注入，不打包进镜像
EXPOSE 8000

# API 服务
CMD ["uvicorn", "src.multi_agent_system.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
