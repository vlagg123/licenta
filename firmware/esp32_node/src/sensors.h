#pragma once
#include <stdint.h>

struct SensorData {
    float temperature;  // °C
    float humidity;     // %
    float pressure;     // hPa
    int   gasValue;     // ADC raw 0-4095
    bool  valid;
};

// ── Gas Level (5-level classification) ───────────────────────────────────
enum GasLevel : uint8_t {
    GAS_NORMAL   = 0,
    GAS_LOW      = 1,
    GAS_MEDIUM   = 2,
    GAS_HIGH     = 3,
    GAS_CRITICAL = 4,
};

struct GasThresholds {
    int normalMax;
    int lowMax;
    int mediumMax;
    int highMax;
    bool buzzerOnHigh;
    // DE MODIFICAT PENTRU PARTEA HARDWARE:
    // adauga campul criticalMin si actualizeaza classifyGasLevel() din sensors.cpp
    // ca sa foloseasca explicit pragul, la fel cum face backend-ul Python
    // momentan CRITICAL = tot ce e > highMax (echivalent cu criticalMin = highMax + 1)
};

void     sensors_init();
SensorData sensors_read();
GasLevel classifyGasLevel(int gasValue, const GasThresholds& t);
bool     shouldActivateBuzzer(GasLevel level, const GasThresholds& t);
