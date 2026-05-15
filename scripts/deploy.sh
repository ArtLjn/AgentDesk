#!/bin/bash
# 部署脚本：将 ai-agent-learning 部署到 HomeUbuntu
# 用法: ./scripts/deploy.sh

set -e

REMOTE_HOST="172.16.58.68"
REMOTE_USER="junnan"
REMOTE_DIR="~/ai-agent-learning"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== 构建部署包 ==="
cd "$PROJECT_DIR"
git archive --format=tar.gz HEAD > /tmp/agent-study-deploy.tar.gz

echo "=== 上传到 $REMOTE_HOST ==="
scp /tmp/agent-study-deploy.tar.gz "$REMOTE_USER@$REMOTE_HOST:/tmp/"

echo "=== 在远程服务器解压并部署 ==="
ssh "$REMOTE_USER@$REMOTE_HOST" bash -s << 'REMOTE_SCRIPT'
set -e
REMOTE_DIR="~/ai-agent-learning"

echo "清理旧代码..."
rm -rf "$REMOTE_DIR"
mkdir -p "$REMOTE_DIR"

echo "解压代码..."
tar -xzf /tmp/agent-study-deploy.tar.gz -C "$REMOTE_DIR"

echo "创建虚拟环境..."
cd "$REMOTE_DIR"
python3 -m venv venv
source venv/bin/activate

echo "安装依赖..."
pip install -r requirements.txt -q

echo "验证安装..."
python -c "from src.multi_agent_system.core import *; print('核心模块导入成功')"
python -c "from src.multi_agent_system.api.app import app; print('API 导入成功')"

echo "运行测试..."
python -m pytest tests/core/ -q

echo "=== 部署完成 ==="
echo "启动命令: cd $REMOTE_DIR && source venv/bin/activate && uvicorn src.multi_agent_system.api.app:app --host 0.0.0.0 --port 8000"
REMOTE_SCRIPT

echo "=== 本地清理 ==="
rm /tmp/agent-study-deploy.tar.gz

echo "部署完成！"
