"""Windows 用户级开机自启动管理 (注册表 HKCU\\...\\Run).

设计:
- 只动 HKCU (当前用户), 不动 HKLM, 因此**不需要管理员权限**.
- 键名固定为 GaugePunk, 值为 EXE 的完整路径 (引号包裹防空格).
- is_enabled() 同时校验存储路径是否还指向当前 EXE, 防止用户移动了 EXE 之后菜单状态错位.
- 非 Windows 平台所有方法都返回安全默认值, 不抛错, 便于跨平台代码透明调用.
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Optional

log = logging.getLogger(__name__)

_REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "GaugePunk"

_IS_WINDOWS = sys.platform.startswith("win")


def _current_exe() -> str:
    """返回当前进程的可执行路径.

    打包态: 直接是 EXE.
    开发态: 是 python.exe (这种情况开机自启意义不大, 但接口完整性保留).
    """
    return sys.executable


def _quote_path(path: str) -> str:
    """注册表里路径含空格必须加引号."""
    path = os.path.abspath(path)
    if path.startswith('"') and path.endswith('"'):
        return path
    return f'"{path}"'


def is_supported() -> bool:
    """当前平台是否支持自启动管理."""
    return _IS_WINDOWS


def get_registered_command() -> Optional[str]:
    """读注册表里 GaugePunk 当前的启动命令, 没有则返回 None."""
    if not _IS_WINDOWS:
        return None
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_PATH, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, _VALUE_NAME)
            return value
    except FileNotFoundError:
        return None
    except OSError as exc:
        log.warning("读取 Run 项失败: %s", exc)
        return None


def is_enabled() -> bool:
    """是否已设置开机自启 (并且指向当前 EXE)."""
    cmd = get_registered_command()
    if cmd is None:
        return False
    expected = _quote_path(_current_exe())
    return cmd.strip().lower() == expected.lower()


def enable(exe_path: Optional[str] = None) -> bool:
    """启用开机自启, 把当前 EXE 路径写进注册表. 成功返回 True."""
    if not _IS_WINDOWS:
        log.warning("非 Windows 平台不支持注册表自启")
        return False
    import winreg

    path = _quote_path(exe_path or _current_exe())
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _REG_PATH, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, _VALUE_NAME, 0, winreg.REG_SZ, path)
        log.info("已启用开机自启: %s", path)
        return True
    except OSError as exc:
        log.warning("写入 Run 项失败: %s", exc)
        return False


def disable() -> bool:
    """关闭开机自启, 删除注册表项. 已经不存在也算成功."""
    if not _IS_WINDOWS:
        return True
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _REG_PATH, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, _VALUE_NAME)
        log.info("已关闭开机自启")
        return True
    except FileNotFoundError:
        return True
    except OSError as exc:
        log.warning("删除 Run 项失败: %s", exc)
        return False
