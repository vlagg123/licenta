#pragma once
#include <stdint.h>

struct SensorData {
    float temperature;  // grade Celsius
    float humidity;     // procent relativ
    float pressure;     // hPa
    int   gasValue;     // valoare ADC bruta 0-4095
    bool  valid;
};

// Clasificare in 5 niveluri, aliniata cu backend-ul Python
enum GasLevel : uint8_t {
    GAS_NORMAL   = 0,
    GAS_LOW      = 1,
    GAS_MEDIUM   = 2,
    GAS_HIGH     = 3,
    GAS_CRITICAL = 4,
};

struct GasThresholds {
    int  normalMax;
    int  lowMax;
    int  mediumMax;
    int  highMax;
    int  criticalMin;
    bool buzzerOnHigh;
};

void       sensors_init();
SensorData sensors_read();
GasLevel   classifyGasLevel(int gasValue, const GasThresholds& t);
bool       shouldActivateBuzzer(GasLevel level, const GasThresholds& t);
