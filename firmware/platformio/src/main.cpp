/*
 * ESP32-WROOM 端固件: 接收上位机串口数据 "CPU:xx,GPU:yy\n", 用 PWM 驱动两块电压表.
 *
 * 接线 (默认):
 *     GPIO25 -> RC低通 (1kΩ + 10uF) -> CPU 电压表 (+)
 *     GPIO26 -> RC低通 (1kΩ + 10uF) -> GPU 电压表 (+)
 *     电压表 (-) -> GND
 *
 * 关键参数 (在下方 const 区域调整):
 *   PWM_FREQ_HZ    : PWM 频率, 5kHz 既能让 RC 滤波平滑, 又远低于 ESP32 LEDC 上限.
 *   PWM_RES_BITS   : 占空比分辨率, 12 -> 0..4095.
 *   PWM_MAX_DUTY   : 软件限制的最大占空比, 用于把电压表"满偏"对齐到 100%.
 *                    例如电压表满量程 5V 但 ESP32 只能输出 3.3V, 那么:
 *                      - 如果你买的就是 3V 量程的表, 设为 (1<<PWM_RES_BITS)-1 (即 4095).
 *                      - 如果是 5V 表, 你想让 100% 时指针刚到底, 必须外加放大器,
 *                        本固件无法靠软件补偿. 这里软件上限只能 "保护机芯" 别撞针.
 *   SMOOTH_ALPHA   : 一阶低通滤波系数 (0..1), 越小指针越平稳但响应越慢. 0.2 比较舒服.
 *   LINK_TIMEOUT_MS: 多久没收到帧就回零, 避免上位机崩了指针卡在 100%.
 */

#include <Arduino.h>

// ----------------- 用户可调参数 -----------------
static const int       PIN_CPU         = 25;       // CPU 表头 PWM 引脚
static const int       PIN_GPU         = 26;       // GPU 表头 PWM 引脚
static const int       LEDC_CH_CPU     = 0;        // LEDC 通道
static const int       LEDC_CH_GPU     = 1;
// 32 kHz 已超出人耳听觉范围 (~20 kHz), 可消除电流表线圈机械啸叫.
// LEDC 在该频率下 10 位分辨率足够 (1024 级 >> 模拟指针视觉分辨极限).
static const uint32_t  PWM_FREQ_HZ     = 32000;
static const uint8_t   PWM_RES_BITS    = 10;       // 0..1023

// 软件占空比上限 (0~100): 协议中的"100%"对应物理 PWM 占空比的这个百分比.
// 两块模拟表头灵敏度通常不同, 分别给 CPU 和 GPU 独立校准.
// 用 host/calibrate.py 测试: 若指针撞针就调小; 若到不了满偏就调大.
static const float     PWM_DUTY_CAP_CPU = 13.5f;
static const float     PWM_DUTY_CAP_GPU = 100.0f;
static const uint32_t  PWM_MAX_DUTY_CPU = (uint32_t)(((1u << PWM_RES_BITS) - 1) * PWM_DUTY_CAP_CPU / 100.0f);
static const uint32_t  PWM_MAX_DUTY_GPU = (uint32_t)(((1u << PWM_RES_BITS) - 1) * PWM_DUTY_CAP_GPU / 100.0f);

static const float     SMOOTH_ALPHA    = 0.2f;     // 0~1, 越小越平滑
static const uint32_t  LINK_TIMEOUT_MS = 3000;     // 超时回零
static const uint32_t  BAUD            = 115200;
// ------------------------------------------------

static float    g_cpu_smooth = 0.0f;
static float    g_gpu_smooth = 0.0f;
static uint32_t g_last_frame_ms = 0;

// 把 0..100 的百分比按通道独立的 PWM 上限写出去.
static void writePercent(int channel, float percent, uint32_t max_duty) {
    if (percent < 0) percent = 0;
    if (percent > 100) percent = 100;
    uint32_t duty = (uint32_t)((percent / 100.0f) * max_duty + 0.5f);
    if (duty > max_duty) duty = max_duty;
    ledcWrite(channel, duty);
}

// 解析一行 "CPU:xx,GPU:yy", 成功填入 outCpu/outGpu 并返回 true.
static bool parseLine(const String& line, int& outCpu, int& outGpu) {
    int cpuIdx = line.indexOf("CPU:");
    int gpuIdx = line.indexOf("GPU:");
    if (cpuIdx < 0 || gpuIdx < 0 || gpuIdx < cpuIdx) {
        return false;
    }
    int cpuStart = cpuIdx + 4;
    int cpuEnd   = line.indexOf(',', cpuStart);
    if (cpuEnd < 0) return false;
    int gpuStart = gpuIdx + 4;
    int gpuEnd   = line.length();

    String cpuStr = line.substring(cpuStart, cpuEnd);
    String gpuStr = line.substring(gpuStart, gpuEnd);
    cpuStr.trim();
    gpuStr.trim();
    if (cpuStr.length() == 0 || gpuStr.length() == 0) return false;

    outCpu = cpuStr.toInt();
    outGpu = gpuStr.toInt();
    if (outCpu < 0 || outCpu > 100) return false;
    if (outGpu < 0 || outGpu > 100) return false;
    return true;
}

void setup() {
    Serial.begin(BAUD);
    delay(100);

    ledcSetup(LEDC_CH_CPU, PWM_FREQ_HZ, PWM_RES_BITS);
    ledcSetup(LEDC_CH_GPU, PWM_FREQ_HZ, PWM_RES_BITS);
    ledcAttachPin(PIN_CPU, LEDC_CH_CPU);
    ledcAttachPin(PIN_GPU, LEDC_CH_GPU);

    writePercent(LEDC_CH_CPU, 0, PWM_MAX_DUTY_CPU);
    writePercent(LEDC_CH_GPU, 0, PWM_MAX_DUTY_GPU);

    Serial.println();
    Serial.print("[boot] monitor firmware v");
#ifdef MONITOR_FW_VERSION
    Serial.println(MONITOR_FW_VERSION);
#else
    Serial.println("dev");
#endif
    Serial.printf("[boot] PWM freq=%uHz res=%ubit\n", (unsigned)PWM_FREQ_HZ, (unsigned)PWM_RES_BITS);
    Serial.printf("[boot] caps: CPU=%.1f%% (max_duty=%u), GPU=%.1f%% (max_duty=%u)\n",
                  PWM_DUTY_CAP_CPU, (unsigned)PWM_MAX_DUTY_CPU,
                  PWM_DUTY_CAP_GPU, (unsigned)PWM_MAX_DUTY_GPU);
    Serial.printf("[boot] pins: CPU=GPIO%d, GPU=GPIO%d\n", PIN_CPU, PIN_GPU);
    Serial.println("[boot] waiting for frames like 'CPU:42,GPU:78'");

    g_last_frame_ms = millis();
}

void loop() {
    static String line;
    while (Serial.available() > 0) {
        char c = (char)Serial.read();
        if (c == '\n' || c == '\r') {
            if (line.length() > 0) {
                int cpu = 0, gpu = 0;
                if (parseLine(line, cpu, gpu)) {
                    g_cpu_smooth = SMOOTH_ALPHA * cpu + (1.0f - SMOOTH_ALPHA) * g_cpu_smooth;
                    g_gpu_smooth = SMOOTH_ALPHA * gpu + (1.0f - SMOOTH_ALPHA) * g_gpu_smooth;
                    g_last_frame_ms = millis();
                    // 调试回显, 收到的原始值 + 滤波后的值
                    Serial.printf("[rx] cpu=%d gpu=%d  smooth: %.1f / %.1f\n",
                                  cpu, gpu, g_cpu_smooth, g_gpu_smooth);
                } else {
                    Serial.print("[warn] bad frame: ");
                    Serial.println(line);
                }
                line = "";
            }
        } else {
            line += c;
            if (line.length() > 64) {
                // 防止恶意/异常数据撑爆内存
                line = "";
            }
        }
    }

    // 超时回零, 防止上位机断开后指针卡住
    if (millis() - g_last_frame_ms > LINK_TIMEOUT_MS) {
        g_cpu_smooth *= (1.0f - SMOOTH_ALPHA);
        g_gpu_smooth *= (1.0f - SMOOTH_ALPHA);
    }

    writePercent(LEDC_CH_CPU, g_cpu_smooth, PWM_MAX_DUTY_CPU);
    writePercent(LEDC_CH_GPU, g_gpu_smooth, PWM_MAX_DUTY_GPU);

    delay(10); // ~100Hz 刷新即可
}
