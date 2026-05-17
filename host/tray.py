"""GaugePunk 托盘版主入口 (Windows 双击 EXE 默认走这里).

特性:
- 系统托盘显示仪表盘图标; tooltip 实时显示当前 CPU/GPU 百分比
- 右键菜单: 开机自启动 (可勾选) / 退出
- 后台线程跑采集 + 串口发送, pystray 在主线程跑 (Windows 消息循环要求)
- 日志写到 EXE 同目录的 gaugepunk.log, 双击运行时也能事后排错
"""
from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path
from typing import Optional

import yaml
from PIL import Image
import pystray

# 让 PyInstaller 打包态和开发态都能 `import monitor.xxx`
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from monitor import autostart  # noqa: E402
from monitor.paths import ensure_user_config, icon_path, log_path  # noqa: E402
from monitor.stats import Sample  # noqa: E402
from monitor.worker import WorkerConfig, run_loop  # noqa: E402


log = logging.getLogger("tray")


def _setup_logging() -> None:
    """日志写文件 + (开发态) 同时输出 stderr.

    打包态没有控制台, stderr 是黑洞; 但写文件总是有效.
    """
    handlers: list[logging.Handler] = [logging.FileHandler(log_path(), encoding="utf-8")]
    if not getattr(sys, "frozen", False):
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
        force=True,
    )


class TrayApp:
    """托盘应用.

    生命周期:
      __init__         加载图标 + 配置 + 构造 pystray.Icon
      start_worker()   后台线程开跑采集
      run()            阻塞跑 icon (主线程)
      _on_quit()       菜单"退出"回调, 设 stop_event + icon.stop()
    """

    def __init__(self, cfg_path: Path):
        self._cfg_path = cfg_path
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._last_sample: Optional[Sample] = None
        self._last_sent: bool = False

        with cfg_path.open("r", encoding="utf-8") as f:
            cfg_dict = yaml.safe_load(f) or {}
        self._cfg = WorkerConfig.from_dict(cfg_dict)

        image = Image.open(icon_path())
        self._icon = pystray.Icon(
            name="gaugepunk",
            icon=image,
            title=self._compose_tooltip(),
            menu=self._build_menu(),
        )

    def _compose_tooltip(self) -> str:
        if self._last_sample is None:
            return "GaugePunk (启动中...)"
        link_tag = "" if self._last_sent else "  [串口断开]"
        return (
            f"GaugePunk  CPU {self._last_sample.cpu:>3d}%  "
            f"GPU {self._last_sample.gpu:>3d}%{link_tag}"
        )

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem(
                lambda item: self._compose_tooltip(),  # 动态标题, 打开菜单时刷新
                None,
                enabled=False,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "开机自启动",
                self._on_toggle_autostart,
                checked=lambda item: autostart.is_enabled(),
                enabled=lambda item: autostart.is_supported(),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", self._on_quit),
        )

    def _on_sample(self, sample: Sample, sent_ok: bool) -> None:
        self._last_sample = sample
        self._last_sent = sent_ok
        self._icon.title = self._compose_tooltip()

    def _on_toggle_autostart(self, icon: "pystray.Icon", item: "pystray.MenuItem") -> None:
        if autostart.is_enabled():
            autostart.disable()
        else:
            autostart.enable()
        icon.update_menu()

    def _on_quit(self, icon: "pystray.Icon", item: "pystray.MenuItem") -> None:
        log.info("用户点击退出")
        self._stop_event.set()
        icon.stop()

    def _worker_main(self) -> None:
        try:
            run_loop(self._cfg, self._stop_event, on_sample=self._on_sample)
        except Exception:  # noqa: BLE001
            log.exception("worker 线程崩溃")

    def start_worker(self) -> None:
        self._worker_thread = threading.Thread(
            target=self._worker_main, name="gaugepunk-worker", daemon=True
        )
        self._worker_thread.start()

    def run(self) -> None:
        try:
            self._icon.run()
        finally:
            self._stop_event.set()
            if self._worker_thread is not None:
                self._worker_thread.join(timeout=3.0)


def main() -> int:
    _setup_logging()
    cfg_path = ensure_user_config()
    log.info("GaugePunk 托盘启动, 配置: %s, 日志: %s", cfg_path, log_path())

    app = TrayApp(cfg_path)
    app.start_worker()
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
