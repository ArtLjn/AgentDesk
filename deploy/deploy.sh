#!/usr/bin/env bash
# AgentDesk 一键部署到腾讯云生产机
#
# 用法：
#   bash deploy/deploy.sh                # 默认行为：构建前端 + 同步 + 重启
#   bash deploy/deploy.sh --skip-build   # 跳过前端构建（用已有 web/dist）
#   bash deploy/deploy.sh --no-caddy     # 跳过 Caddy 配置（首次域名未解析时用）
#
# 服务器要求（已在记忆中）：
#   - root@43.155.217.74，SSH 免密
#   - Python 3.12 在 /usr/bin/python3.12
#   - Caddy v2.x 已装且 systemd 启用
#
# 产出：
#   - 后端：/root/workspace/ai-agent-learning/，systemd 服务 ai-agent-learning
#   - 前端：/root/workspace/static/agent-desk/
#   - 入口：https://work.order.lllcnm.cn

set -euo pipefail

# ============================================================================
# 配置
# ============================================================================
SERVER="root@43.155.217.74"
REMOTE_DIR="/root/workspace/ai-agent-learning"
STATIC_DIR="/root/workspace/static/agent-desk"
SERVICE_NAME="ai-agent-learning"
DOMAIN="workorder.lllcnm.cn"
BACKEND_PORT="9001"
PYTHON_BIN="python3.12"

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEPLOY_DIR="${PROJECT_ROOT}/deploy"

# 颜色
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*" >&2; }
step() { echo -e "\n${BLUE}=== $* ===${NC}"; }

# 参数解析
SKIP_BUILD=0
SKIP_CADDY=0
for arg in "$@"; do
	case "$arg" in
		--skip-build) SKIP_BUILD=1 ;;
		--no-caddy)   SKIP_CADDY=1 ;;
		*) err "未知参数: $arg"; exit 1 ;;
	esac
done

# ============================================================================
# Step 1: 本地前端构建
# ============================================================================
if [[ "$SKIP_BUILD" -eq 0 ]]; then
	step "构建前端"
	cd "${PROJECT_ROOT}/web"
	[[ -f package.json ]] || { err "未找到 web/package.json"; exit 1; }
	[[ -d node_modules ]] || npm install
	npm run build
	[[ -d dist ]] || { err "前端构建失败：dist 目录不存在"; exit 1; }
	log "前端构建完成：web/dist/"
else
	warn "跳过前端构建（使用已有 web/dist）"
	[[ -d "${PROJECT_ROOT}/web/dist" ]] || { err "web/dist 不存在，请先构建"; exit 1; }
fi

# ============================================================================
# Step 2: 远程目录准备
# ============================================================================
step "准备远程目录"
ssh "$SERVER" "mkdir -p ${REMOTE_DIR} ${STATIC_DIR}"
log "远程目录就绪：${REMOTE_DIR}, ${STATIC_DIR}"

# ============================================================================
# Step 3: 同步后端代码
# ============================================================================
step "同步后端代码"
cd "${PROJECT_ROOT}"
rsync -avz --delete \
	--exclude='__pycache__/' \
	--exclude='*.pyc' \
	--exclude='.git/' \
	--exclude='venv/' \
	--exclude='.venv/' \
	--exclude='node_modules/' \
	--exclude='web/' \
	--exclude='tests/' \
	--exclude='archive/' \
	--exclude='openspec/' \
	--exclude='docs/' \
	--exclude='.worktrees/' \
	--exclude='logs/*.log' \
	--exclude='data/*.db' \
	--exclude='.claude/' \
	-e ssh \
	./ "${SERVER}:${REMOTE_DIR}/"
log "后端代码同步完成"

# ============================================================================
# Step 4: 同步前端静态资源
# ============================================================================
step "同步前端静态资源"
rsync -avz --delete \
	-e ssh \
	"${PROJECT_ROOT}/web/dist/" "${SERVER}:${STATIC_DIR}/"
log "前端资源同步完成"

# ============================================================================
# Step 5: 远程 venv + 依赖
# ============================================================================
step "配置远程 Python 环境"
ssh "$SERVER" bash <<EOF
set -euo pipefail
cd "${REMOTE_DIR}"
if [[ ! -x venv/bin/python ]]; then
	echo "[remote] 创建 venv (${PYTHON_BIN})"
	${PYTHON_BIN} -m venv venv
fi
echo "[remote] 升级 pip"
venv/bin/pip install --upgrade pip --quiet
echo "[remote] 安装依赖"
venv/bin/pip install -r requirements.txt --quiet
echo "[remote] 依赖安装完成"
EOF
log "Python 环境就绪"

# ============================================================================
# Step 6: 安装 systemd 服务
# ============================================================================
step "安装 systemd 服务"
scp "${DEPLOY_DIR}/ai-agent-learning.service" \
	"${SERVER}:/etc/systemd/system/${SERVICE_NAME}.service"
ssh "$SERVER" bash <<EOF
set -euo pipefail
touch /var/log/ai-agent-learning.log
systemctl daemon-reload
systemctl enable ${SERVICE_NAME} >/dev/null 2>&1
systemctl restart ${SERVICE_NAME}
sleep 3
if systemctl is-active --quiet ${SERVICE_NAME}; then
	echo "[remote] 服务已启动"
else
	echo "[remote] 服务启动失败，最近日志："
	journalctl -u ${SERVICE_NAME} -n 30 --no-pager || tail -30 /var/log/ai-agent-learning.log
	exit 1
fi
EOF
log "systemd 服务运行中：${SERVICE_NAME}"

# ============================================================================
# Step 7: Caddy 配置
# ============================================================================
if [[ "$SKIP_CADDY" -eq 0 ]]; then
	step "配置 Caddy"

	# 上传站点片段到远程临时位置
	CADDY_TMP_REMOTE="/tmp/agent-desk-caddy-site.conf"
	scp "${DEPLOY_DIR}/caddy-site.conf" "${SERVER}:${CADDY_TMP_REMOTE}"

	ssh "$SERVER" bash <<EOF
set -euo pipefail
if grep -q "^${DOMAIN} {" /etc/caddy/Caddyfile; then
	echo "[remote] Caddyfile 已包含 ${DOMAIN} 站点，跳过追加"
else
	cp /etc/caddy/Caddyfile "/etc/caddy/Caddyfile.bak-\$(date +%Y%m%d-%H%M%S)-agent-desk"
	echo "" >> /etc/caddy/Caddyfile
	cat ${CADDY_TMP_REMOTE} >> /etc/caddy/Caddyfile
	echo "[remote] 已追加 ${DOMAIN} 站点到 Caddyfile"
fi
rm -f ${CADDY_TMP_REMOTE}

if caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null 2>&1; then
	systemctl reload caddy
	echo "[remote] Caddy 配置已校验并 reload"
else
	echo "[remote] Caddyfile 校验失败，请手动检查 /etc/caddy/Caddyfile"
	exit 1
fi
EOF
	log "Caddy 已 reload"
else
	warn "跳过 Caddy 配置"
fi

# ============================================================================
# Step 8: 健康检查
# ============================================================================
step "健康检查"
sleep 2
if ssh "$SERVER" "curl -fsS http://127.0.0.1:${BACKEND_PORT}/health"; then
	echo
	log "后端健康检查通过 (127.0.0.1:${BACKEND_PORT})"
else
	warn "后端健康检查失败，请查日志：ssh ${SERVER} journalctl -u ${SERVICE_NAME} -n 50"
fi

echo
log "部署完成"
echo -e "  前端入口:        ${GREEN}https://${DOMAIN}${NC}"
echo -e "  API 健康检查:     ${GREEN}https://${DOMAIN}/health${NC}"
echo -e "  日志查看:         ${YELLOW}ssh ${SERVER} journalctl -u ${SERVICE_NAME} -f${NC}"
