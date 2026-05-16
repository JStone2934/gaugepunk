#!/usr/bin/env bash
# 安装 system 级 systemd 服务. 需要 sudo, 只需运行一次.
# 之后即开机自启, 重启 / 拔插 ESP32 自动重连.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVICE_NAME="monitor.service"
SERVICE_DST="/etc/systemd/system/$SERVICE_NAME"
TEMPLATE="$SCRIPT_DIR/$SERVICE_NAME.template"

if [[ $EUID -ne 0 ]]; then
    echo "需要 sudo 权限. 重试: sudo $0" >&2
    exit 1
fi

# sudo 时 $USER 是 root, 真实用户在 $SUDO_USER 里
REAL_USER="${SUDO_USER:-${USER}}"
if [[ -z "$REAL_USER" || "$REAL_USER" == "root" ]]; then
    echo "无法识别真实用户名, 请用 sudo (而非 su) 调用本脚本." >&2
    exit 1
fi
REAL_HOME="$(getent passwd "$REAL_USER" | cut -d: -f6)"

if [[ ! -f "$TEMPLATE" ]]; then
    echo "找不到模板: $TEMPLATE" >&2
    exit 1
fi

echo "[install] 用户: $REAL_USER, 家目录: $REAL_HOME, 项目: $PROJECT_DIR"
echo "[install] 写入 $SERVICE_DST"
sed -e "s|@PROJECT_DIR@|$PROJECT_DIR|g" \
    -e "s|@USER@|$REAL_USER|g" \
    -e "s|@HOME@|$REAL_HOME|g" \
    "$TEMPLATE" > "$SERVICE_DST"
chmod 644 "$SERVICE_DST"
chmod +x "$SCRIPT_DIR/monitor-run.sh"

echo "[install] daemon-reload"
systemctl daemon-reload

echo "[install] enable --now $SERVICE_NAME"
systemctl enable --now "$SERVICE_NAME"

echo ""
echo "服务状态:"
systemctl --no-pager status "$SERVICE_NAME" | head -15 || true

cat <<EOF

------------------------------------------------------------------
常用命令 (后续不再需要 sudo, 除非 stop/start):
  实时日志:       sudo journalctl -u monitor -f
  最近 50 条日志: sudo journalctl -u monitor -n 50
  停止 / 启动:    sudo systemctl stop|start monitor
  禁用自启:       sudo systemctl disable monitor
  完全卸载:       sudo ./scripts/uninstall-service.sh
------------------------------------------------------------------
EOF
