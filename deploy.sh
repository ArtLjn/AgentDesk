#!/bin/bash
# 部署多Agent工单处理系统到 HomeUbuntu 服务器
# 用法: ./deploy.sh
# 前提: 本机已安装 sshpass

set -euo pipefail

# 服务器配置
REMOTE_HOST="172.16.58.68"
REMOTE_USER="ljn"
REMOTE_PASS="ljnnb666"
REMOTE_DIR="/home/ljn/ai-agent-learning"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查 sshpass 是否安装
if ! command -v sshpass &> /dev/null; then
    log_error "sshpass 未安装，请先安装: brew install sshpass (macOS)"
    exit 1
fi

# 检查 rsync 是否安装
if ! command -v rsync &> /dev/null; then
    log_error "rsync 未安装，请先安装: brew install rsync (macOS)"
    exit 1
fi

SSH_CMD="sshpass -p ${REMOTE_PASS} ssh -o StrictHostKeyChecking=no ${REMOTE_USER}@${REMOTE_HOST}"
RSYNC_CMD="sshpass -p ${REMOTE_PASS} rsync -avz --progress"

log_info "开始部署到 ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}"

# 1. 同步代码到服务器
log_info "同步代码到服务器（排除 venv/、__pycache__/、.git/、.idea/）..."
$RSYNC_CMD \
    --exclude='venv/' \
    --exclude='__pycache__/' \
    --exclude='.git/' \
    --exclude='.idea/' \
    --exclude='.ruff_cache/' \
    --exclude='.claude/' \
    --exclude='logs/' \
    --exclude='*.pyc' \
    --exclude='.DS_Store' \
    ./ "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/"

log_info "代码同步完成"

# 2. 确保服务器上的 data 目录存在
log_info "确保 data 目录存在..."
$SSH_CMD "mkdir -p ${REMOTE_DIR}/data"

# 3. SSH 到服务器执行 docker compose 构建和启动
log_info "在服务器上构建并启动 Docker 容器..."
$SSH_CMD "cd ${REMOTE_DIR} && echo '${REMOTE_PASS}' | sudo -S docker compose up -d --build"

log_info "等待服务启动..."
sleep 5

# 4. 检查容器运行状态
log_info "检查容器运行状态..."
$SSH_CMD "cd ${REMOTE_DIR} && echo '${REMOTE_PASS}' | sudo -S docker compose ps"

log_info "部署完成！"
echo ""
echo "服务地址:"
echo "  API:      http://${REMOTE_HOST}:8000"
echo "  API 文档: http://${REMOTE_HOST}:8000/docs"
echo "  Qdrant:   http://${REMOTE_HOST}:6333/dashboard"
