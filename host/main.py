"""上位机主程序: 周期性采集 CPU/GPU 占用率并通过串口发送给 ESP32.

使用方式:
    conda activate monitor
    python host/main.py                       # 使用默认配置 host/config.yaml
    python host/main.py --config other.yaml   # 指定配置文件
    python host/main.py --dry-run             # 只打印, 不打开串口 (调试用)
    python host/main.py --echo                # 打印同时仍发送串口
"""
from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from pathlib import Path
from typing import Any

import yaml

# 让脚本既能 `python host/main.py` 也能 `python -m monitor.main`
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from monitor.protocol import encode  # noqa: E402
from monitor.serial_link import SerialLink  # noqa: E402
from monitor.stats import Sampler, build_gpu_monitor  # noqa: E402


def _load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="CPU/GPU usage -> ESP32 voltmeters")
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


_running = True


def _handle_sigint(signum: int, frame: Any) -> None:  # noqa: ARG001
    global _running
    _running = False


def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    log = logging.getLogger("main")

    cfg = _load_config(args.config)
    serial_cfg = cfg.get("serial", {})
    sampling_cfg = cfg.get("sampling", {})
    gpu_cfg = cfg.get("gpu", {})

    interval = float(sampling_cfg.get("interval", 0.2))
    cpu_window = float(sampling_cfg.get("cpu_window", 0.1))

    gpu = build_gpu_monitor(
        vendor=gpu_cfg.get("vendor", "NONE"),
        index=int(gpu_cfg.get("index", 0)),
    )
    sampler = Sampler(gpu=gpu, cpu_window=cpu_window)

    link: SerialLink | None = None
    if not args.dry_run:
        link = SerialLink(
            port=str(serial_cfg.get("port", "auto")),
            baudrate=int(serial_cfg.get("baudrate", 115200)),
            write_timeout=float(serial_cfg.get("write_timeout", 1.0)),
        )

    signal.signal(signal.SIGINT, _handle_sigint)
    signal.signal(signal.SIGTERM, _handle_sigint)

    log.info("开始采集, 周期 %.3fs (Ctrl+C 退出)", interval)
    next_tick = time.monotonic()
    try:
        while _running:
            sample = sampler.read()
            payload = encode(sample)
            sent = True
            if link is not None:
                sent = link.send(payload)
            if args.echo or args.dry_run:
                tag = "TX" if sent else "--"
                print(f"[{tag}] {payload.decode().rstrip()}", flush=True)
            elif not sent:
                log.warning("发送失败 (等待重连): %s", payload.decode().rstrip())

            # 漂移补偿: 与系统时钟同步, 而不是简单 sleep(interval)
            next_tick += interval
            sleep_for = next_tick - time.monotonic()
            if sleep_for > 0:
                time.sleep(sleep_for)
            else:
                # 落后了一拍, 立即重置, 不补打多帧
                next_tick = time.monotonic()
    finally:
        log.info("退出, 释放资源")
        if link is not None:
            link.close()
        sampler.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
