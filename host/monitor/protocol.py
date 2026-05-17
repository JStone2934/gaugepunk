"""上位机 <-> ESP32 串口协议封装.

协议非常简单: 每帧一行 ASCII 文本, 以 \n 结束.
    "CPU:<0-100>,GPU:<0-100>\n"

理由:
- ASCII 便于在 Arduino 串口监视器中调试.
- 行分隔保证 ESP32 在任何时刻接入也能在下一行同步.
- 解析极其简单, 无需 CRC: 即便偶发丢字符也只是一帧失效.

注: 协议中的百分比是 "上位机校准后的 PWM 占空比百分比" (固件 cap 已经
直通=100, 不再做缩放). 如果调用方传入 cpu_cap / gpu_cap, 这里会按
   actual = round(raw * cap / 100)
做软件端缩放, 让协议 100% 对应表头物理满偏. 不传则等价于 cap=100, 即
直接发送原始百分比 (主要供 calibrate.py 测试硬件用).
"""
from __future__ import annotations

from .stats import Sample


def encode(sample: Sample, *, cpu_cap: float = 100.0, gpu_cap: float = 100.0) -> bytes:
    """把 Sample 编码为可直接写入串口的字节, 可选按通道 cap 缩放."""
    cpu = max(0, min(100, int(round(sample.cpu * cpu_cap / 100.0))))
    gpu = max(0, min(100, int(round(sample.gpu * gpu_cap / 100.0))))
    return f"CPU:{cpu},GPU:{gpu}\n".encode("ascii")
