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
├── gaugepunk.spec                 PyInstaller spec (打包 Windows EXE 用)
├── assets/
│   └── gaugepunk_icon_source.png  图标源文件 (1024 PNG)
├── host/                          上位机 (Python, Linux + Windows)
│   ├── main.py                    CLI 主程序
│   ├── tray.py                    Windows 托盘版主入口
│   ├── calibrate.py               手动校准工具
│   ├── config.yaml                端口/采样/GPU 厂商配置 (默认模板)
│   ├── assets/
│   │   └── gaugepunk.ico          托盘 + EXE 图标 (多分辨率 ICO)
│   └── monitor/
│       ├── stats.py               CPU/GPU 采集
│       ├── serial_link.py         串口连接 + 自动重连
│       ├── protocol.py            帧编码
│       ├── worker.py              采集 + 串口主循环 (供 CLI / 托盘复用)
│       ├── paths.py               打包/开发态资源路径解析
│       └── autostart.py           Windows 注册表自启动管理
├── firmware/                      ESP32 固件
│   ├── platformio/                PlatformIO 工程 (推荐)
│   │   ├── platformio.ini
│   │   └── src/main.cpp
│   └── arduino/gaugepunk/         Arduino IDE 工程 (等价)
│       └── gaugepunk.ino
├── scripts/                       打包部署
│   ├── build-windows.ps1          Windows 一键打包 (PyInstaller)
│   ├── make-icon.py               把 PNG 转 ICO (换图标时跑一次)
│   ├── gaugepunk-run.sh           Linux: 启动包装 (conda activate + exec)
│   ├── gaugepunk.service.template Linux: systemd unit 模板
│   ├── install-service.sh         Linux: 一键装服务
│   ├── uninstall-service.sh       Linux: 一键卸服务
│   └── start.sh                   Linux: 手动前台启动 (调试用)
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

### 1B. Windows 端

Windows 10 / 11 完整支持上位机 (CPU 监控 + NVIDIA GPU 监控 + USB 串口). AMD / Intel GPU 监控目前仅 Linux, 详见后文.

#### 1B.1 USB 串口驱动

ESP32-WROOM 板载多用 CP2102 或 CH340. Windows 10/11 多数能自动装好, 接上后在"设备管理器 -> 端口 (COM 和 LPT)" 里能看到 `Silicon Labs CP210x ... (COM3)` 或 `USB-SERIAL CH340 (COM3)` 这种条目即正常. 没识别就装:

- [Silicon Labs CP210x VCP](https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers)
- [WCH CH340 驱动](http://www.wch-ic.com/downloads/CH341SER_EXE.html)

#### 1B.2 conda 环境

PowerShell 或 Anaconda Prompt 都行 (推荐先装 [Miniconda](https://docs.conda.io/en/latest/miniconda.html)):

```powershell
conda env create -f environment.yml   # 第一次安装
conda activate gaugepunk              # 之后每次
```

#### 1B.3 配置

编辑 `host/config.yaml`:

```yaml
serial:
  port: auto          # 或写死 "COM3"
  baudrate: 115200
sampling:
  interval: 0.2
gpu:
  vendor: NVIDIA      # Windows 下只支持 NVIDIA / NONE
  index: 0
```

`port: auto` 通常就够了 (按 VID:PID 优先识别 CP2102 / CH340 / FT232 / ESP32-S2/S3 原生 USB). 如果你装了多个 USB 串口设备想精确指定, 在"设备管理器"里看到 `(COM3)` 就在配置里写 `port: COM3`.

#### 1B.4 运行

```powershell
# 干跑 (不开串口, 只在终端打印, 不需要硬件就能调试上位机)
python host\main.py --dry-run --echo

# 正式运行 (要先把 ESP32 插上)
python host\main.py --echo
```

按 Ctrl+C 退出.

#### 1B.5 校准 (用法与 Linux 一致)

```powershell
python host\calibrate.py 100 0     # 只锁 CPU 满载
python host\calibrate.py 0 100     # 只锁 GPU 满载
python host\calibrate.py --sweep   # 0 -> 100 -> 0 扫描
```

#### 1B.6 托盘版 (推荐桌面使用) 和打包成 EXE

Windows 上更推荐 **托盘版**: 不占控制台, 双击启动, 右下角一个仪表盘图标, 鼠标悬停看实时 CPU/GPU, 右键菜单可以切换"开机自启动"或"退出".

开发态运行:

```powershell
python host\tray.py
```

一键打包成单文件 `GaugePunk.exe` (~16MB):

```powershell
.\scripts\build-windows.ps1
```

产物在 `dist\GaugePunk.exe`. 双击启动:
- 第一次会在 EXE 同目录自动生成 `config.yaml` 和 `gaugepunk.log`
- 托盘图标出现在屏幕右下角
- 右键 → "开机自启动" 切换 (写注册表 `HKCU\...\Run\GaugePunk`, **不需要管理员权限**)
- 右键 → "退出" 干净关闭, 串口释放, 指针超时归零

> Windows 端不需要也用不上 `scripts/*.sh` (那是 Linux systemd 用的), 托盘版已经覆盖了"开机自启"需求.

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

- **NVIDIA**: 使用官方 `nvidia-ml-py` (NVML), 已在 RTX 5070 Ti 上验证. **Linux + Windows 均支持**.
- **AMD**: 读取 `/sys/class/drm/card{index}/device/gpu_busy_percent`, 需要内核 amdgpu 驱动. **仅 Linux**.
- **Intel**: 占位实现, 实际启用需要给 `intel_gpu_top` 提权或者用 `perf_event_open`. **仅 Linux**, 暂未优先支持.

> Windows 上若 `gpu.vendor` 设为 `AMD` 或 `INTEL`, 程序会在启动时直接抛错并提示改回 `NVIDIA` / `NONE`, 不会静默假数据.

## 后续可玩

- 给电流表表盘**重画 0~100% 刻度纸** (用 Inkscape, 网上有现成模板).
- 加一颗 RGB LED, 占用率 >80% 变红.
- 用 OLED 同时显示数字, 表头显模拟.
- 把协议改成二进制 + CRC, 用于工业级稳定性.
- 通过 BLE/Wi-Fi 让 ESP32 自己拉数据, 摆脱 USB 线.
- 加第三块表显示内存占用 / 网络带宽 / 硬盘 IO.
