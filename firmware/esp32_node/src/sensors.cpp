#include "sensors.h"
#include "config.h"
#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_BME280.h>

static Adafruit_BME280 bme;
static bool bme_ok = false;

void sensors_init() {
    Wire.begin(PIN_BME_SDA, PIN_BME_SCL);

    // incearca ambele adrese posibile — depinde de starea pinului SDO al modulului
    bme_ok = bme.begin(0x76);
    if (!bme_ok) bme_ok = bme.begin(0x77);

    if (!bme_ok) {
        Serial.println("[SENSORS] BME280 negasit la 0x76 si 0x77 - verifica cablajul");
    } else {
        bme.setSampling(
            Adafruit_BME280::MODE_NORMAL,
            Adafruit_BME280::SAMPLING_X2,
            Adafruit_BME280::SAMPLING_X16,
            Adafruit_BME280::SAMPLING_X1,
            Adafruit_BME280::FILTER_X16,
            Adafruit_BME280::STANDBY_MS_0_5
        );
        Serial.println("[SENSORS] BME280 OK");
    }

    pinMode(PIN_MQ2, INPUT);
    analogReadResolution(12);  // ADC 12-bit: 0-4095
    Serial.println("[SENSORS] MQ configurat - citiri stabile dupa ~30s de incalzire");
}

SensorData sensors_read() {
    SensorData d;
    d.valid = false;

    if (bme_ok) {
        d.temperature = bme.readTemperature();
        d.humidity    = bme.readHumidity();
        d.pressure    = bme.readPressure() / 100.0f;  // Pa -> hPa
    } else {
        d.temperature = 25.0f;
        d.humidity    = 50.0f;
        d.pressure    = 1013.0f;
    }

    // media a 4 citiri ADC consecutive pentru reducerea zgomotului electric
    int sum = 0;
    for (int i = 0; i < 4; i++) { sum += analogRead(PIN_MQ2); delay(2); }
    d.gasValue = sum / 4;

    // temperatura in afara domeniului valid inseamna senzor deconectat sau defect
    d.valid = (d.temperature > -40.0f && d.temperature < 125.0f);
    return d;
}

GasLevel classifyGasLevel(int gasValue, const GasThresholds& t) {
    if (gasValue >= t.criticalMin) return GAS_CRITICAL;
    if (gasValue <= t.normalMax)   return GAS_NORMAL;
    if (gasValue <= t.lowMax)      return GAS_LOW;
    if (gasValue <= t.mediumMax)   return GAS_MEDIUM;
    return GAS_HIGH;
}

bool shouldActivateBuzzer(GasLevel level, const GasThresholds& t) {
    if (level == GAS_CRITICAL)               return true;
    if (level == GAS_HIGH && t.buzzerOnHigh) return true;
    return false;
}
