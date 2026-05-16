# Monitor — CPU/GPU 模拟电压表显示器

> Ubuntu 把当前 CPU 和 GPU 占用率通过 USB 串口发给 ESP32-WROOM, 由 ESP32 用 PWM + RC 低通驱动两块模拟指针电压表显示.

## 目录结构

```
monitor/
├── README.md                 本文档
├── environment.yml           conda 环境定义
├── requirements.txt          pip 依赖 (备用)
├── host/                     Ubuntu 上位机 (Python)
│   ├── main.py
│   ├── config.yaml
│   └── monitor/
│       ├── stats.py          CPU/GPU 采集
│       ├── serial_link.py    串口连接 + 自动重连
│       └── protocol.py       帧编码
├── firmware/                 ESP32 固件
│   ├── platformio/           PlatformIO 工程
│   │   ├── platformio.ini
│   │   └── src/main.cpp
│   └── arduino/monitor/      Arduino IDE 工程
│       └── monitor.ino
└── docs/
    └── wiring.md             接线图与元件清单
```

## 快速开始

### 1. Ubuntu 端

#### 1.1 串口权限 (只需做一次)

```bash
sudo usermod -aG dialout $USER
# 注销当前会话再登录, 让所有终端都获得 dialout 组
```

#### 1.2 conda 环境

如果还没有环境:

```bash
conda env create -f environment.yml
```

之后每次:

```bash
conda activate monitor
```

#### 1.3 配置

编辑 `host/config.yaml`:

```yaml
serial:
  port: auto          # 或写死 "/dev/ttyUSB0"
  baudrate: 115200
sampling:
  interval: 0.2       # 5 Hz, 适合指针表
gpu:
  vendor: NVIDIA      # NVIDIA / AMD / INTEL / NONE
  index: 0
```

#### 1.4 运行

```bash
# 干跑 (不开串口, 只在终端打印, 用于本机调试)
python host/main.py --dry-run --echo

# 正式运行
python host/main.py
```

按 Ctrl+C 退出.

### 2. ESP32 端

#### PlatformIO (推荐)

```bash
cd firmware/platformio
pio run -t upload          # 编译 + 烧录
pio device monitor -b 115200   # 看串口输出 (会被上位机抢占, 仅用于调试)
```

#### Arduino IDE

打开 `firmware/arduino/monitor/monitor.ino`, 选择:

- 开发板: **ESP32 Dev Module** (或你板子的实际型号)
- 端口  : `/dev/ttyUSB0`
- 上传速率: 921600

点上传即可.

### 3. 接线

见 [`docs/wiring.md`](docs/wiring.md). 简版:

```
GPIO25 -- 1kΩ -- + -- 电压表(+)         GPIO26 -- 1kΩ -- + -- 电压表(+)
                 |                                       |
                10µF                                    10µF
                 |                                       |
                GND                                     GND
```

## 协议

上位机每隔 `interval` 秒向串口写一行 ASCII:

```
CPU:42,GPU:78\n
```

数值是 0~100 的整数百分比. ESP32 端用 `String.indexOf` 解析, 不需要 CRC -- 偶发丢字符只会让本帧失效, 下一行就同步.

## 打包部署 / 开机自启 (Linux)

项目自带 `scripts/` 一键脚本, 用 systemd 实现:
- 开机即启动 (不依赖桌面登录)
- 上位机崩溃后自动重启
- ESP32 拔插后自动重连
- 进程日志进 journald, 用 `journalctl` 直接看

### 安装 (一次性, 需 sudo)

```bash
cd ~/project/monitor
sudo ./scripts/install-service.sh
```

脚本会自动:
1. 把 `scripts/monitor.service.template` 渲染成 `/etc/systemd/system/monitor.service`
2. 通过 `SupplementaryGroups=dialout` 注入串口权限 (无需依赖登录会话)
3. `systemctl enable --now monitor` 启用并立即启动

### 日常运维

```bash
sudo systemctl status monitor          # 状态
sudo systemctl stop monitor            # 停止
sudo systemctl start monitor           # 启动
sudo systemctl restart monitor         # 重启
sudo journalctl -u monitor -f          # 实时日志 (Ctrl+C 退出)
sudo journalctl -u monitor -n 100      # 最近 100 行
```

### 临时手动启动 (不走 systemd, 适合调试)

```bash
./scripts/start.sh                     # 前台运行 + 实时打印每帧, Ctrl+C 退出
```

> ⚠️ 手动启动前请先 `sudo systemctl stop monitor`, 否则两个进程会抢同一个串口.

### 卸载

```bash
sudo ./scripts/uninstall-service.sh
```

### 修改 conda 环境名

默认 service 调用 `monitor` 这个 conda 环境. 如果你换了名字:

```bash
sudo systemctl edit monitor    # 加入 [Service]\nEnvironment=MONITOR_CONDA_ENV=<新名字>
sudo systemctl restart monitor
```

## 故障排查

| 现象 | 可能原因 | 处理 |
| --- | --- | --- |
| `Permission denied` 打不开串口 | 未加入 dialout 组 | `sudo usermod -aG dialout $USER`, 重新登录 |
| 串口能打开但 ESP32 没反应 | 烧错引脚 / 没共地 / RC 滤波电容方向反 | 在 ESP32 串口监视器看 `[rx]` 行 |
| 指针抖得厉害 | `SMOOTH_ALPHA` 太大 | 改为 0.1 或 0.05 |
| 指针响应太慢 | `SMOOTH_ALPHA` 太小 | 改回 0.2~0.3 |
| 满载时指针不到底 | 电压表量程 > 3.3V | 换 3V 表, 或加运放放大 (见 wiring.md) |
| 上位机崩了指针卡在高位 | 没触发超时回零 | 检查固件 `LINK_TIMEOUT_MS` |

## 关于 GPU 监控

- **NVIDIA**: 使用官方 `nvidia-ml-py` (NVML), 已在 RTX 5070 Ti 上验证.
- **AMD**: 读取 `/sys/class/drm/card{index}/device/gpu_busy_percent`, 需要内核 amdgpu 驱动.
- **Intel**: 占位实现, 实际启用需要给 `intel_gpu_top` 提权或者用 `perf_event_open`. 暂未优先支持.

## 后续可玩

- 给电压表表盘**重画 0~100% 刻度纸** (用 Inkscape, 网上有现成模板).
- 加一颗 RGB LED, 占用率 >80% 变红.
- 用 OLED 同时显示数字, 表头显模拟.
- 把协议改成二进制 + CRC, 用于工业级稳定性.
- 通过 BLE/Wi-Fi 让 ESP32 自己拉数据, 摆脱 USB 线.
