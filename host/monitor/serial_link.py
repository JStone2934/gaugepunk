"""串口连接管理: 自动发现 ESP32, 断线自动重连."""
from __future__ import annotations

import logging
import time
from typing import Iterable, Optional

import serial
from serial.tools import list_ports

log = logging.getLogger(__name__)

# 常见 USB-UART 桥接芯片的 VID:PID, 用于在 port=auto 时优先识别
_KNOWN_VIDPID: set[tuple[int, int]] = {
    (0x10C4, 0xEA60),  # CP2102 / CP2102N
    (0x1A86, 0x7523),  # CH340
    (0x1A86, 0x55D4),  # CH9102
    (0x0403, 0x6001),  # FT232
    (0x303A, 0x1001),  # ESP32-S2/S3 原生 USB
}


def discover_port() -> Optional[str]:
    """扫描串口, 返回第一个看起来像 ESP32 的设备路径."""
    candidates: list[str] = []
    for p in list_ports.comports():
        vid, pid = p.vid, p.pid
        if vid is not None and pid is not None and (vid, pid) in _KNOWN_VIDPID:
            log.info("发现 ESP32 候选端口: %s (%04x:%04x %s)", p.device, vid, pid, p.description)
            return p.device
        # 兜底: /dev/ttyUSB* 和 /dev/ttyACM* 都收集起来
        if p.device.startswith(("/dev/ttyUSB", "/dev/ttyACM")):
            candidates.append(p.device)
    if candidates:
        log.info("未匹配到已知芯片, 退而使用第一个 USB/ACM 端口: %s", candidates[0])
        return candidates[0]
    return None


class SerialLink:
    """带自动重连的串口写入器."""

    def __init__(
        self,
        port: str = "auto",
        baudrate: int = 115200,
        write_timeout: float = 1.0,
        reconnect_interval: float = 2.0,
    ) -> None:
        self._port_cfg = port
        self._baudrate = baudrate
        self._write_timeout = write_timeout
        self._reconnect_interval = reconnect_interval
        self._serial: Optional[serial.Serial] = None
        self._last_attempt: float = 0.0

    def _resolve_port(self) -> Optional[str]:
        if self._port_cfg and self._port_cfg.lower() != "auto":
            return self._port_cfg
        return discover_port()

    def _connect(self) -> None:
        now = time.monotonic()
        if now - self._last_attempt < self._reconnect_interval:
            return
        self._last_attempt = now

        port = self._resolve_port()
        if not port:
            log.warning("没有可用串口, 等待 ESP32 接入...")
            return
        try:
            self._serial = serial.Serial(
                port=port,
                baudrate=self._baudrate,
                write_timeout=self._write_timeout,
            )
            log.info("已连接 %s @ %d bps", port, self._baudrate)
            # ESP32 在串口连接后有一个 boot 复位, 等它启动完
            time.sleep(1.5)
            try:
                self._serial.reset_input_buffer()
            except Exception:  # noqa: BLE001
                pass
        except (serial.SerialException, OSError) as exc:
            log.warning("打开串口失败: %s", exc)
            self._serial = None

    def send(self, payload: bytes) -> bool:
        """发送一帧, 失败返回 False 并安排重连."""
        if self._serial is None or not self._serial.is_open:
            self._connect()
        if self._serial is None:
            return False
        try:
            self._serial.write(payload)
            return True
        except (serial.SerialException, OSError) as exc:
            log.warning("写入失败, 关闭并尝试重连: %s", exc)
            self.close()
            return False

    def close(self) -> None:
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:  # noqa: BLE001
                pass
            self._serial = None

    def __enter__(self) -> "SerialLink":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
