"""模拟表头校准工具.

用法:
    # 持续发送 CPU=100, GPU=100, 看指针打在表头哪个位置
    python host/calibrate.py 100

    # 分别给 CPU/GPU 指定不同的值
    python host/calibrate.py 80 50

    # 阶梯扫描 0 -> 100 -> 0, 观察指针运动范围
    python host/calibrate.py --sweep

校准流程:
    1. 先用 `--sweep` 看指针扫描运动, 确认硬件接线正常.
    2. 再用固定百分比 (如 100) 确认协议 100% 时指针的位置.
       - 若指针**超过**表头满偏: 编辑固件 main.cpp 中 PWM_DUTY_CAP_PCT 调低 (如 30).
       - 若指针**未到**表头满偏: 调高 (如 70).
    3. 反复调整 + 重烧固件, 直到协议 100% 正好对应表头物理满偏.
"""
from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from monitor.protocol import encode  # noqa: E402
from monitor.serial_link import SerialLink  # noqa: E402
from monitor.stats import Sample  # noqa: E402


_running = True


def _stop(*_a: object) -> None:
    global _running
    _running = False


def _send_loop(link: SerialLink, cpu: int, gpu: int, duration: float) -> None:
    """持续发送固定 CPU/GPU 帧, 直到时间到或 Ctrl+C."""
    print(f"  -> 发送 CPU={cpu:3d}, GPU={gpu:3d}, 持续 {duration:.1f}s (Ctrl+C 退出)")
    end = time.monotonic() + duration
    while _running and time.monotonic() < end:
        link.send(encode(Sample(cpu=cpu, gpu=gpu)))
        time.sleep(0.2)


def _sweep(link: SerialLink) -> None:
    """0 -> 100 -> 0 阶梯扫描, 每档 1.5s 停留观察."""
    steps = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100,
             90, 80, 70, 60, 50, 40, 30, 20, 10, 0]
    print("扫描模式: 0 -> 100 -> 0, 每档 1.5s")
    for v in steps:
        if not _running:
            break
        print(f"  --> {v:3d}%")
        end = time.monotonic() + 1.5
        while _running and time.monotonic() < end:
            link.send(encode(Sample(cpu=v, gpu=v)))
            time.sleep(0.2)


def main() -> int:
    p = argparse.ArgumentParser(description="模拟表头校准工具")
    p.add_argument("cpu", type=int, nargs="?", default=100, help="CPU 百分比 0-100 (默认 100)")
    p.add_argument("gpu", type=int, nargs="?", default=None, help="GPU 百分比 0-100 (默认与 CPU 相同)")
    p.add_argument("--sweep", action="store_true", help="0->100->0 阶梯扫描模式")
    p.add_argument("--duration", type=float, default=999999, help="固定帧持续秒数")
    p.add_argument("--port", default="auto")
    args = p.parse_args()

    if args.gpu is None:
        args.gpu = args.cpu
    if not (0 <= args.cpu <= 100) or not (0 <= args.gpu <= 100):
        print("CPU/GPU 必须在 0..100 之间", file=sys.stderr)
        return 2

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    link = SerialLink(port=args.port)
    try:
        if args.sweep:
            _sweep(link)
        else:
            _send_loop(link, args.cpu, args.gpu, args.duration)
    finally:
        link.close()
        print("\n已退出, 串口关闭")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
