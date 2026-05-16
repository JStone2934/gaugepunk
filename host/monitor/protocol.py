"""上位机 <-> ESP32 串口协议封装.

协议非常简单: 每帧一行 ASCII 文本, 以 \n 结束.
    "CPU:<0-100>,GPU:<0-100>\n"

理由:
- ASCII 便于在 Arduino 串口监视器中调试.
- 行分隔保证 ESP32 在任何时刻接入也能在下一行同步.
- 解析极其简单, 无需 CRC: 即便偶发丢字符也只是一帧失效.
"""
from __future__ import annotations

from .stats import Sample


def encode(sample: Sample) -> bytes:
    """把 Sample 编码为可直接写入串口的字节."""
    cpu = max(0, min(100, int(sample.cpu)))
    gpu = max(0, min(100, int(sample.gpu)))
    return f"CPU:{cpu},GPU:{gpu}\n".encode("ascii")
