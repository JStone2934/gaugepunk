"""上位机 CLI 入口: 周期性采集 CPU/GPU 占用率并通过串口发送给 ESP32.

使用方式:
    conda activate gaugepunk
    python host/main.py                       # 使用默认配置 host/config.yaml
    python host/main.py --config other.yaml   # 指定配置文件
    python host/main.py --dry-run             # 只采集, 不打开串口 (调试用)
    python host/main.py --echo                # 发送的同时把每帧打印到终端

Windows 用户更推荐双击 EXE 走托盘版 (host/tray.py), 这里 CLI 仅作命令行/服务/调试用.
"""
from __future__ import annotations

import argparse
import logging
import signal
import sys
import threading
from pathlib import Path
from typing import Any

import yaml

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from monitor.protocol import encode  # noqa: E402
from monitor.stats import Sample  # noqa: E402
from monitor.worker import WorkerConfig, run_loop  # noqa: E402


def _load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="CPU/GPU usage -> ESP32 voltmeters (CLI)")
    p.add_argument(
        "--config",
        type=Path,
        default=_HERE / "config.yaml",
        help="YAML 配置文件路径",
    )
    p.add_argument("--dry-run", action="store_true", help="只采集, 不开串口")
    p.add_argument("--echo", action="store_true", help="发送同时把每帧打印到终端")
    p.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    log = logging.getLogger("main")

    cfg = WorkerConfig.from_dict(_load_config(args.config))
    stop_event = threading.Event()

    def _handle_sig(signum: int, frame: Any) -> None:  # noqa: ARG001
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_sig)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_sig)

    def _on_sample(sample: Sample, sent: bool) -> None:
        if args.echo or args.dry_run:
            tag = "TX" if sent else "--"
            print(f"[{tag}] {encode(sample).decode().rstrip()}", flush=True)
        elif not sent:
            log.warning("发送失败 (等待重连): CPU=%d GPU=%d", sample.cpu, sample.gpu)

    log.info("开始采集 (Ctrl+C 退出)")
    run_loop(cfg, stop_event, dry_run=args.dry_run, on_sample=_on_sample)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
