#!/usr/bin/env bash
# 启动包装: 由 systemd 调用. 完成 conda 环境激活后 exec main.py.
# 也可以手动直接运行该脚本以验证.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_NAME="${MONITOR_CONDA_ENV:-monitor}"

# 找一个可用的 conda 安装
for cand in \
    "$HOME/miniconda3/etc/profile.d/conda.sh" \
    "$HOME/anaconda3/etc/profile.d/conda.sh" \
    "$HOME/miniforge3/etc/profile.d/conda.sh" \
    "/opt/miniconda3/etc/profile.d/conda.sh" \
    "/opt/anaconda3/etc/profile.d/conda.sh"
do
    if [[ -f "$cand" ]]; then
        # shellcheck disable=SC1090
        source "$cand"
        break
    fi
done

if ! command -v conda >/dev/null 2>&1; then
    echo "[monitor-run] 找不到 conda. 设置 MONITOR_CONDA_ENV 或修改本脚本." >&2
    exit 1
fi

conda activate "$ENV_NAME"
cd "$PROJECT_DIR"

# exec 让 PID 直接是 Python 进程, systemd 可以正确管理信号/重启
exec python host/main.py "$@"
