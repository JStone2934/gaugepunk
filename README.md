# GaugePunk

> *用复古的模拟仪表显示数字时代的脉搏.*
>
> Ubuntu 把当前 CPU 和 GPU 占用率通过 USB 串口发给 ESP32-WROOM, 由 ESP32 用 PWM 驱动两块模拟指针电流表显示——两根指针随着系统负载摇摆, 蒸汽朋克味的桌面装饰.

## 目录结构

```
gaugepunk/
├── README.md                      本文档
├── environment.yml                conda 环境定义 (name: gaugepunk)
├── requirements.txt               pip 依赖 (备用)
├── host/                          Ubuntu 上位机 (Python)
│   ├── main.py                    主程序
│   ├── calibrate.py               手动校准工具
│   ├── config.yaml                端口/采样/GPU 厂商配置
│   └── monitor/
│       ├── stats.py               CPU/GPU 采集
│       ├── serial_link.py         串口连接 + 自动重连
│       └── protocol.py            帧编码
├── firmware/                      ESP32 固件
│   ├── platformio/                PlatformIO 工程 (推荐)
│   │   ├── platformio.ini
│   │   └── src/main.cpp
│   └── arduino/gaugepunk/         Arduino IDE 工程 (等价)
│       └── gaugepunk.ino
├── scripts/                       打包部署
│   ├── gaugepunk-run.sh           启动包装 (conda activate + exec)
│   ├── gaugepunk.service.template systemd unit 模板
│   ├── install-service.sh         一键装服务
│   ├── uninstall-service.sh       一键卸服务
│   └── start.sh                   手动前台启动 (调试用)
└── docs/
    └── wiring.md                  接线图与元件清单
```

## 快速开始

### 1. Ubuntu 端

#### 1.1 串口权限 (只需做一次)

```bash
sudo usermod -aG dialout $USER
# 注销当前会话再登录, 让所有终端都获得 dialout 组
```

#### 1.2 conda 环境

```bash
conda env create -f environment.yml   # 第一次安装
conda activate gaugepunk              # 之后每次
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
pio run -t upload                  # 编译 + 烧录
pio device monitor -b 115200       # 看串口输出 (会被上位机抢占, 仅用于调试)
```

#### Arduino IDE

打开 `firmware/arduino/gaugepunk/gaugepunk.ino`, 选择:

- 开发板: **ESP32 Dev Module** (或你板子的实际型号)
- 端口  : `/dev/ttyUSB0`
- 上传速率: 921600

### 3. 校准

第一次接好电流表后, 用 `host/calibrate.py` 调整 `PWM_DUTY_CAP_CPU` / `PWM_DUTY_CAP_GPU`:

```bash
python host/calibrate.py 100 0     # 只锁 CPU 满载, 观察 CPU 表指针
python host/calibrate.py 0 100     # 只锁 GPU 满载, 观察 GPU 表指针
python host/calibrate.py --sweep   # 0 -> 100 -> 0 扫描
```

记下两块表"刚好满偏"对应的协议百分比 X / Y, 在固件里:
```
new_cap = old_cap × X / 100
```

调好后重新烧录, 即一次到位.

### 4. 接线

见 [`docs/wiring.md`](docs/wiring.md). 简版 (针对 5mA 电流表):

```
ESP32 GPIO25 ── [1kΩ] ── 电流表 CPU (+)        ESP32 GPIO26 ── [1kΩ] ── 电流表 GPU (+)
                         电流表 CPU (-) ── GND                          电流表 GPU (-) ── GND
```

## 协议

上位机每隔 `interval` 秒向串口写一行 ASCII:

```
CPU:42,GPU:78\n
```

数值是 0~100 的整数百分比. ESP32 端用 `String.indexOf` 解析, 不需要 CRC—偶发丢字符只会让本帧失效, 下一行就同步.

## 打包部署 / 开机自启 (Linux)

项目自带 `scripts/` 一键脚本, 用 systemd 实现:
- 开机即启动 (不依赖桌面登录)
- 上位机崩溃后自动重启
- ESP32 拔插后自动重连
- 进程日志进 journald, 用 `journalctl` 直接看

### 安装 (一次性, 需 sudo)

```bash
cd ~/project/gaugepunk
sudo ./scripts/install-service.sh
```

脚本会自动:
1. 把 `scripts/gaugepunk.service.template` 渲染成 `/etc/systemd/system/gaugepunk.service`
2. 通过 `SupplementaryGroups=dialout` 注入串口权限 (无需依赖登录会话)
3. `systemctl enable --now gaugepunk` 启用并立即启动

### 日常运维

```bash
sudo systemctl status gaugepunk          # 状态
sudo systemctl stop gaugepunk            # 停止
sudo systemctl start gaugepunk           # 启动
sudo systemctl restart gaugepunk         # 重启
sudo journalctl -u gaugepunk -f          # 实时日志 (Ctrl+C 退出)
sudo journalctl -u gaugepunk -n 100      # 最近 100 行
```

### 临时手动启动 (不走 systemd, 适合调试)

```bash
./scripts/start.sh                       # 前台运行 + 实时打印每帧, Ctrl+C 退出
```

> ⚠️ 手动启动前请先 `sudo systemctl stop gaugepunk`, 否则两个进程会抢同一个串口.

### 卸载

```bash
sudo ./scripts/uninstall-service.sh
```

### 修改 conda 环境名

默认 service 调用 `gaugepunk` 这个 conda 环境. 如果你换了名字:

```bash
sudo systemctl edit gaugepunk    # 加入 [Service]\nEnvironment=GAUGEPUNK_CONDA_ENV=<新名字>
sudo systemctl restart gaugepunk
```

## 故障排查

| 现象 | 可能原因 | 处理 |
| --- | --- | --- |
| `Permission denied` 打不开串口 | 未加入 dialout 组 | `sudo usermod -aG dialout $USER`, 重新登录 |
| 串口能打开但 ESP32 没反应 | 烧错引脚 / 没共地 | 在 ESP32 串口监视器看 `[rx]` 行 |
| 指针抖得厉害 | `SMOOTH_ALPHA` 太大 | 改为 0.1 或 0.05 |
| 指针响应太慢 | `SMOOTH_ALPHA` 太小 | 改回 0.2~0.3 |
| 满载时指针不到底 | 电流表实际量程比标称低, 或限流电阻太大 | 把 `PWM_DUTY_CAP_*` 调高, 极限是 100% (软件已经无法补偿就换更小的限流电阻) |
| 满载时撞钉 | `PWM_DUTY_CAP_*` 太高 | 降低, 用 `calibrate.py` 找精确值 |
| 通电时听到啸叫 | PWM 频率落在人耳听觉范围内 | 已默认 32 kHz, 如果仍有微弱啸叫推到 78 kHz |
| 上位机崩了指针卡在高位 | 没触发超时回零 | 检查固件 `LINK_TIMEOUT_MS` |

## 关于 GPU 监控

- **NVIDIA**: 使用官方 `nvidia-ml-py` (NVML), 已在 RTX 5070 Ti 上验证.
- **AMD**: 读取 `/sys/class/drm/card{index}/device/gpu_busy_percent`, 需要内核 amdgpu 驱动.
- **Intel**: 占位实现, 实际启用需要给 `intel_gpu_top` 提权或者用 `perf_event_open`. 暂未优先支持.

## 后续可玩

- 给电流表表盘**重画 0~100% 刻度纸** (用 Inkscape, 网上有现成模板).
- 加一颗 RGB LED, 占用率 >80% 变红.
- 用 OLED 同时显示数字, 表头显模拟.
- 把协议改成二进制 + CRC, 用于工业级稳定性.
- 通过 BLE/Wi-Fi 让 ESP32 自己拉数据, 摆脱 USB 线.
- 加第三块表显示内存占用 / 网络带宽 / 硬盘 IO.
