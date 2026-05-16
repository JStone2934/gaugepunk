"""CPU / GPU 占用率采集模块.

CPU 使用 psutil, GPU 优先使用 NVIDIA NVML, 也可以扩展 AMD / Intel.
"""
from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from typing import Optional

import psutil

log = logging.getLogger(__name__)


@dataclass
class Sample:
    """一次采样结果, cpu / gpu 都是 0~100 的整数百分比."""

    cpu: int
    gpu: int


class CpuMonitor:
    """对 psutil.cpu_percent 的薄封装, 处理首次调用返回 0 的问题."""

    def __init__(self, window: float = 0.1) -> None:
        self._window = max(window, 0.05)
        # 第一次调用以建立基线, 否则返回 0
        psutil.cpu_percent(interval=None)

    def read(self) -> int:
        # interval=None 表示与上一次调用相比, 几乎零阻塞
        return int(round(psutil.cpu_percent(interval=None)))


class GpuMonitor:
    """抽象 GPU 采集接口."""

    def read(self) -> int:  # 返回 0~100
        raise NotImplementedError

    def close(self) -> None:
        pass


class NvidiaGpuMonitor(GpuMonitor):
    """使用 NVML 读取 NVIDIA GPU 占用率."""

    def __init__(self, index: int = 0) -> None:
        import pynvml  # nvidia-ml-py 提供, 导入名仍为 pynvml

        self._pynvml = pynvml
        pynvml.nvmlInit()
        self._handle = pynvml.nvmlDeviceGetHandleByIndex(index)
        name = pynvml.nvmlDeviceGetName(self._handle)
        if isinstance(name, bytes):
            name = name.decode("utf-8", "replace")
        log.info("NVIDIA GPU #%d: %s", index, name)

    def read(self) -> int:
        util = self._pynvml.nvmlDeviceGetUtilizationRates(self._handle)
        return int(util.gpu)

    def close(self) -> None:
        try:
            self._pynvml.nvmlShutdown()
        except Exception:  # noqa: BLE001
            pass


class AmdGpuMonitor(GpuMonitor):
    """通过 /sys/class/drm/card*/device/gpu_busy_percent 读取 AMD GPU 占用率."""

    def __init__(self, index: int = 0) -> None:
        self._path = f"/sys/class/drm/card{index}/device/gpu_busy_percent"
        with open(self._path) as f:  # 提前打开校验
            f.read()

    def read(self) -> int:
        with open(self._path) as f:
            return int(f.read().strip())


class IntelGpuMonitor(GpuMonitor):
    """通过 `intel_gpu_top -J -s 200` 解析 Render/3D 引擎占用率.

    需要 sudo 或对 intel_gpu_top 设置 cap_perfmon=ep. 默认实现仅作占位.
    """

    def __init__(self) -> None:
        # 简单调用一次, 确认可执行
        subprocess.run(
            ["intel_gpu_top", "-h"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def read(self) -> int:  # 占位实现, 始终返回 0
        log.warning("Intel GPU 监控未实现, 返回 0")
        return 0


class DummyGpuMonitor(GpuMonitor):
    """无 GPU 或调试用, 始终返回 0."""

    def read(self) -> int:
        return 0


def build_gpu_monitor(vendor: str, index: int = 0) -> GpuMonitor:
    """根据配置创建对应的 GPU 监控器."""
    v = (vendor or "NONE").strip().upper()
    if v == "NVIDIA":
        return NvidiaGpuMonitor(index=index)
    if v == "AMD":
        return AmdGpuMonitor(index=index)
    if v == "INTEL":
        return IntelGpuMonitor()
    return DummyGpuMonitor()


class Sampler:
    """组合 CPU + GPU 采样, 输出 0~100 的 Sample."""

    def __init__(self, gpu: GpuMonitor, cpu_window: float = 0.1) -> None:
        self._cpu = CpuMonitor(window=cpu_window)
        self._gpu = gpu

    def read(self) -> Sample:
        cpu = max(0, min(100, self._cpu.read()))
        try:
            gpu = max(0, min(100, self._gpu.read()))
        except Exception as exc:  # noqa: BLE001
            log.warning("GPU 读取失败: %s, 本次取 0", exc)
            gpu = 0
        return Sample(cpu=cpu, gpu=gpu)

    def close(self) -> None:
        self._gpu.close()
