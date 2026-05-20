# ── 阶段 1: 构建 React 前端 ──
FROM node:20-slim AS node-build

WORKDIR /build/web

# 安装依赖（利用 Docker 层缓存）
COPY web/package.json web/package-lock.json ./
RUN npm ci --registry=https://registry.npmmirror.com

# 构建前端
COPY web/ ./
RUN npm run build

# ── 阶段 2: Python 运行时 ──
FROM python:3.12-slim

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖（利用 Docker 层缓存）
ARG PIP_INDEX_URL=https://pypi.org/simple
COPY requirements.txt .
RUN pip install --no-cache-dir -i ${PIP_INDEX_URL} -r requirements.txt

# 应用代码
COPY src/ src/

# 脚本
COPY scripts/ scripts/

# 从阶段 1 复制 React 构建产物
COPY --from=node-build /build/web/dist /app/web/dist

# 数据目录（运行时通过 volume 挂载）
RUN mkdir -p data

EXPOSE 8000

CMD ["uvicorn", "src.multi_agent_system.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
