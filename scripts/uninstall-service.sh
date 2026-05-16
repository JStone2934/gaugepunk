#!/usr/bin/env bash
# 卸载 system 级 systemd 服务. 需要 sudo.
set -euo pipefail

SERVICE_NAME="monitor.service"
SERVICE_DST="/etc/systemd/system/$SERVICE_NAME"

if [[ $EUID -ne 0 ]]; then
    echo "需要 sudo 权限. 重试: sudo $0" >&2
    exit 1
fi

echo "[uninstall] 停止并禁用 $SERVICE_NAME"
systemctl stop "$SERVICE_NAME" 2>/dev/null || true
systemctl disable "$SERVICE_NAME" 2>/dev/null || true

if [[ -f "$SERVICE_DST" ]]; then
    rm -f "$SERVICE_DST"
    echo "[uninstall] 已删除 $SERVICE_DST"
fi

systemctl daemon-reload
echo "[uninstall] 完成"
