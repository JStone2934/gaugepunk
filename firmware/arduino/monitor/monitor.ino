/*
 * Arduino IDE 版本: 内容与 firmware/platformio/src/main.cpp 完全等价.
 *
 * Arduino IDE 设置:
 *   - 开发板: ESP32 Arduino -> "ESP32 Dev Module" (或你板子的型号)
 *   - 端口  : /dev/ttyUSB0
 *   - 上传速率: 921600
 *
 * 如果同时维护两个版本嫌麻烦, 也可以在 Arduino IDE 里直接
 * "文件 -> 打开" 选 firmware/platformio/src/main.cpp, 然后另存为 .ino 即可.
 */

#include <Arduino.h>

static const int       PIN_CPU         = 25;
static const int       PIN_GPU         = 26;
static const int       LEDC_CH_CPU     = 0;
static const int       LEDC_CH_GPU     = 1;
static const uint32_t  PWM_FREQ_HZ     = 32000; // 32 kHz 超出人耳, 消除线圈啸叫
static const uint8_t   PWM_RES_BITS    = 10;    // 1024 级, 对模拟指针足够
static const float     PWM_DUTY_CAP_CPU = 13.5f;  // CPU 通道占空比上限 (0~100)
static const float     PWM_DUTY_CAP_GPU = 100.0f; // GPU 通道占空比上限 (0~100)
static const uint32_t  PWM_MAX_DUTY_CPU = (uint32_t)(((1u << PWM_RES_BITS) - 1) * PWM_DUTY_CAP_CPU / 100.0f);
static const uint32_t  PWM_MAX_DUTY_GPU = (uint32_t)(((1u << PWM_RES_BITS) - 1) * PWM_DUTY_CAP_GPU / 100.0f);
static const float     SMOOTH_ALPHA    = 0.2f;
static const uint32_t  LINK_TIMEOUT_MS = 3000;
static const uint32_t  BAUD            = 115200;

static float    g_cpu_smooth = 0.0f;
static float    g_gpu_smooth = 0.0f;
static uint32_t g_last_frame_ms = 0;

static void writePercent(int channel, float percent, uint32_t max_duty) {
    if (percent < 0) percent = 0;
    if (percent > 100) percent = 100;
    uint32_t duty = (uint32_t)((percent / 100.0f) * max_duty + 0.5f);
    if (duty > max_duty) duty = max_duty;
    ledcWrite(channel, duty);
}

static bool parseLine(const String& line, int& outCpu, int& outGpu) {
    int cpuIdx = line.indexOf("CPU:");
    int gpuIdx = line.indexOf("GPU:");
    if (cpuIdx < 0 || gpuIdx < 0 || gpuIdx < cpuIdx) return false;
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
    Serial.println("[boot] monitor firmware (arduino)");
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
            if (line.length() > 64) line = "";
        }
    }

    if (millis() - g_last_frame_ms > LINK_TIMEOUT_MS) {
        g_cpu_smooth *= (1.0f - SMOOTH_ALPHA);
        g_gpu_smooth *= (1.0f - SMOOTH_ALPHA);
    }

    writePercent(LEDC_CH_CPU, g_cpu_smooth, PWM_MAX_DUTY_CPU);
    writePercent(LEDC_CH_GPU, g_gpu_smooth, PWM_MAX_DUTY_GPU);

    delay(10);
}
