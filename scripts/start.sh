#!/usr/bin/env bash
# 手动前台启动 monitor (调试或临时使用). Ctrl+C 退出.
# 与 systemd service 互斥, 别同时跑.
set -e
"$(dirname "${BASH_SOURCE[0]}")/monitor-run.sh" --echo
