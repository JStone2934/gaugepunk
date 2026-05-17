"""采集 + 串口发送的后台工作循环, 可被 CLI (main.py) 或托盘 (tray.py) 复用.

设计:
- 不再用 signal, 全部走 threading.Event, 让调用方决定怎么停 (Ctrl+C / 托盘菜单 / 任何线程).
- on_sample 回调让 UI 层能即时拿到当前 cpu/gpu, 不用自己再采集一次.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from .protocol import encode
from .serial_link import SerialLink
from .stats import Sample, Sampler, build_gpu_monitor

log = logging.getLogger(__name__)


def _clamp_cap(v: float) -> float:
    """把表头 cap 钳到 [0, 100], 防止 yaml 写崩了直接撞针."""
    if v < 0:
        return 0.0
    if v > 100:
        return 100.0
    return v


@dataclass
class WorkerConfig:
    """从 config.yaml 抽出来的运行参数."""

    port: str = "auto"
    baudrate: int = 115200
    write_timeout: float = 1.0
    interval: float = 0.2
    cpu_window: float = 0.1
    gpu_vendor: str = "NVIDIA"
    gpu_index: int = 0
    # 协议百分比 100% 实际写出去的 PWM 占空比上限 (软件端缩放, 固件 cap 永远 100).
    cpu_cap_pct: float = 100.0
    gpu_cap_pct: float = 100.0

    @classmethod
    def from_dict(cls, cfg: dict[str, Any]) -> "WorkerConfig":
        s = cfg.get("serial", {}) or {}
        smp = cfg.get("sampling", {}) or {}
        g = cfg.get("gpu", {}) or {}
        m = cfg.get("meters", {}) or {}
        return cls(
            port=str(s.get("port", "auto")),
            baudrate=int(s.get("baudrate", 115200)),
            write_timeout=float(s.get("write_timeout", 1.0)),
            interval=float(smp.get("interval", 0.2)),
            cpu_window=float(smp.get("cpu_window", 0.1)),
            gpu_vendor=str(g.get("vendor", "NVIDIA")),
            gpu_index=int(g.get("index", 0)),
            cpu_cap_pct=_clamp_cap(float(m.get("cpu_cap_pct", 100.0))),
            gpu_cap_pct=_clamp_cap(float(m.get("gpu_cap_pct", 100.0))),
        )


OnSample = Callable[[Sample, bool], None]  # (sample, sent_ok)


def run_loop(
    cfg: WorkerConfig,
    stop_event: threading.Event,
    *,
    dry_run: bool = False,
    on_sample: Optional[OnSample] = None,
) -> None:
    """主循环. 阻塞调用方线程直到 stop_event 被设上."""
    gpu = build_gpu_monitor(vendor=cfg.gpu_vendor, index=cfg.gpu_index)
    sampler = Sampler(gpu=gpu, cpu_window=cfg.cpu_window)

    link: Optional[SerialLink] = None
    if not dry_run:
        link = SerialLink(
            port=cfg.port,
            baudrate=cfg.baudrate,
            write_timeout=cfg.write_timeout,
        )

    log.info(
        "采集开始, 周期 %.3fs, 表头 cap: CPU=%.1f%% GPU=%.1f%%",
        cfg.interval, cfg.cpu_cap_pct, cfg.gpu_cap_pct,
    )
    next_tick = time.monotonic()
    try:
        while not stop_event.is_set():
            sample = sampler.read()
            payload = encode(sample, cpu_cap=cfg.cpu_cap_pct, gpu_cap=cfg.gpu_cap_pct)
            sent = True
            if link is not None:
                sent = link.send(payload)
            if on_sample is not None:
                try:
                    on_sample(sample, sent)
                except Exception:  # noqa: BLE001
                    log.exception("on_sample 回调抛错, 不影响主循环")

            next_tick += cfg.interval
            sleep_for = next_tick - time.monotonic()
            if sleep_for > 0:
                # 用 stop_event.wait 而不是 time.sleep, 这样 stop 时能秒级响应
                if stop_event.wait(sleep_for):
                    break
            else:
                next_tick = time.monotonic()
    finally:
        log.info("采集结束, 释放资源")
        if link is not None:
            link.close()
        sampler.close()
