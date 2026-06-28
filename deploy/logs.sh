#!/usr/bin/env bash
# AgentDesk 远程日志查看脚本
#
# 用法：
#   bash deploy/logs.sh                   # 默认：最近 200 行应用日志
#   bash deploy/logs.sh -f                # 实时跟踪应用日志（tail -f）
#   bash deploy/logs.sh -n 500            # 最近 500 行
#   bash deploy/logs.sh -k ERROR          # 含 ERROR 的最近 200 行
#   bash deploy/logs.sh -k ERROR -n 50    # 最近 50 条 ERROR
#   bash deploy/logs.sh -kf ERROR         # 实时跟踪 ERROR
#   bash deploy/logs.sh --boot            # systemd 启动日志（最近 200 行）
#   bash deploy/logs.sh --boot -f         # 实时跟踪 systemd 日志
#   bash deploy/logs.sh --boot --since "1h"   # 最近 1 小时
#   bash deploy/logs.sh --caddy           # Caddy 访问日志
#
# 源切换：
#   - 默认源是应用日志 /var/log/ai-agent-learning.log
#   - --boot 切到 journalctl（systemd，支持 --since）
#   - --caddy 切到 Caddy 访问日志
#
# 关键字过滤：grep -iE（不区分大小写，支持正则）。
# 非跟踪模式：先 grep 全量再 tail，取"最近的 N 条匹配"；
# 跟踪模式：tail -f | grep。

set -euo pipefail

# ============================================================================
# 配置（与 deploy.sh 一致）
# ============================================================================
SERVER="root@43.155.217.74"
SERVICE_NAME="ai-agent-learning"
APP_LOG="/var/log/ai-agent-learning.log"
CADDY_LOG="/var/log/caddy/access.log"

# 颜色
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${GREEN}[INFO]${NC} $*" >&2; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*" >&2; }
err()  { echo -e "${RED}[ERROR]${NC} $*" >&2; }
header() { echo -e "\n${BLUE}=== $* ===${NC}" >&2; }

# ============================================================================
# 参数解析
# ============================================================================
LINES=200
FOLLOW=0
KEYWORD=""
SOURCE="app"        # app | boot | caddy
SINCE=""

while [[ $# -gt 0 ]]; do
	case "$1" in
		-n|--lines)   LINES="$2"; shift 2 ;;
		-f|--follow)  FOLLOW=1; shift ;;
		-k|--grep)    KEYWORD="$2"; shift 2 ;;
		# 组合短选项：-kf KEYWORD = -k KEYWORD -f
		-kf)          KEYWORD="$2"; FOLLOW=1; shift 2 ;;
		-fk)          KEYWORD="$2"; FOLLOW=1; shift 2 ;;
		--boot)       SOURCE="boot"; shift ;;
		--caddy)      SOURCE="caddy"; shift ;;
		--since)      SINCE="$2"; shift 2 ;;
		-h|--help)
			sed -n '2,24p' "$0" | sed 's/^# \{0,1\}//'
			exit 0
			;;
		*) err "未知参数: $1"; exit 1 ;;
	esac
done

# ============================================================================
# 组装远程命令
# ============================================================================
REMOTE_CMD=""

build_filter() {
	# $1: 文件路径
	local path="$1"
	if [[ "$FOLLOW" -eq 1 ]]; then
		if [[ -n "$KEYWORD" ]]; then
			echo "tail -f -n 0 '${path}' | grep -iE '${KEYWORD}'"
		else
			echo "tail -f -n ${LINES} '${path}'"
		fi
	else
		if [[ -n "$KEYWORD" ]]; then
			# 先全量 grep 再取尾 N 行：得到"最近的 N 条匹配"
			echo "grep -iE '${KEYWORD}' '${path}' | tail -n ${LINES}"
		else
			echo "tail -n ${LINES} '${path}'"
		fi
	fi
}

case "$SOURCE" in
	app)
		if [[ -n "$SINCE" ]]; then
			warn "--since 仅对 --boot（journalctl）有效，已忽略"
		fi
		REMOTE_CMD="$(build_filter "$APP_LOG")"
		;;
	boot)
		JOPTS=(-u "$SERVICE_NAME" --no-pager)
		[[ -n "$SINCE" ]] && JOPTS+=(--since "$SINCE")
		if [[ "$FOLLOW" -eq 1 ]]; then
			JOPTS+=(-f)
		else
			JOPTS+=(-n "$LINES")
		fi
		if [[ -n "$KEYWORD" ]]; then
			# shellcheck disable=SC2068
			REMOTE_CMD="journalctl ${JOPTS[@]} | grep -iE '${KEYWORD}' | tail -n ${LINES}"
		else
			# shellcheck disable=SC2068
			REMOTE_CMD="journalctl ${JOPTS[@]}"
		fi
		;;
	caddy)
		if [[ -n "$SINCE" ]]; then
			warn "--since 仅对 --boot（journalctl）有效，已忽略"
		fi
		REMOTE_CMD="$(build_filter "$CADDY_LOG")"
		;;
esac

# ============================================================================
# 执行
# ============================================================================
SOURCE_DESC="$SOURCE"
[[ "$FOLLOW"      -eq 1 ]] && SOURCE_DESC="${SOURCE_DESC} (follow)"
[[ -n "$KEYWORD" ]] && SOURCE_DESC="${SOURCE_DESC} grep='${KEYWORD}'"
[[ -n "$SINCE"   && "$SOURCE" == "boot" ]] && SOURCE_DESC="${SOURCE_DESC} since='${SINCE}'"

header "源: ${SOURCE_DESC}"
log "服务器: ${SERVER}"
log "命令:   ${REMOTE_CMD}"
echo >&2

# follow / grep 模式允许 SIGINT 退出、grep 无匹配返回非 0，都不应被 set -e 误判为失败
if [[ "$FOLLOW" -eq 1 || -n "$KEYWORD" ]]; then
	ssh "$SERVER" "$REMOTE_CMD" || true
else
	ssh "$SERVER" "$REMOTE_CMD"
fi
