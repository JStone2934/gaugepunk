"""路径解析: 区分"打包内只读资源"和"用户可写的运行目录".

- 打包态 (PyInstaller 单文件): 资源被解压到 sys._MEIPASS, exe 自身在 sys.executable.
  我们让 config.yaml / gaugepunk.log 与 exe 同目录, 方便用户编辑和查看.
- 开发态 (直接跑 python host/main.py): 项目根就是可写目录, host/assets 是只读资源.

资源 (gaugepunk.ico, 默认 config.yaml 模板) 都打到 bundle 里; 第一次运行如果 exe
同目录没有 config.yaml, 自动从 bundle 复制一份出来.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def is_frozen() -> bool:
    """是否以 PyInstaller 打包后的 EXE 形式在跑."""
    return bool(getattr(sys, "frozen", False))


def bundle_dir() -> Path:
    """打包内只读资源根目录 (PyInstaller _MEIPASS 或开发态项目根)."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", os.path.dirname(sys.executable)))
    return Path(__file__).resolve().parent.parent.parent


def runtime_dir() -> Path:
    """用户可写的运行目录 (放 config.yaml 和 gaugepunk.log).

    打包: EXE 所在目录.
    开发: 项目根 (host/ 的上一级).
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


def resource_path(rel: str) -> Path:
    """打包内只读资源的绝对路径, rel 相对 bundle 根."""
    return bundle_dir() / rel


def ensure_user_config(default_rel: str = "host/config.yaml") -> Path:
    """确保用户可写目录里有 config.yaml; 没有就从 bundle 复制一份, 返回最终路径.

    打包态: <exe_dir>/config.yaml
    开发态: <repo>/host/config.yaml (原地直接用)
    """
    if not is_frozen():
        return resource_path(default_rel)

    target = runtime_dir() / "config.yaml"
    if not target.exists():
        src = resource_path(default_rel)
        shutil.copyfile(src, target)
    return target


def log_path() -> Path:
    """日志文件路径. 打包态: exe 同目录/gaugepunk.log; 开发态: 项目根/gaugepunk.log."""
    return runtime_dir() / "gaugepunk.log"


def icon_path() -> Path:
    """托盘图标路径."""
    return resource_path("host/assets/gaugepunk.ico")
