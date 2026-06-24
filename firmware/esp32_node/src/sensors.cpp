#include "sensors.h"
#include "config.h"
#include <Arduino.h>
#include <Wire.h>
#include <math.h>
#include <Adafruit_BME280.h>

static Adafruit_BME280 bme;
static bool bme_ok = false;

void sensors_init() {
    Wire.begin(PIN_BME_SDA, PIN_BME_SCL);

    // incearca ambele adrese posibile - depinde de starea pinului SDO al modulului
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
    d.tempValid = false;

    if (bme_ok) {
        float t = bme.readTemperature();
        float h = bme.readHumidity();
        float p = bme.readPressure() / 100.0f;  // Pa -> hPa
        // BME280 poate returna NaN daca s-a deconectat dupa initializare;
        // o citire in afara domeniului fizic inseamna la fel senzor defect
        if (!isnan(t) && t > -40.0f && t < 125.0f) {
            d.temperature = t;
            d.humidity    = isnan(h) ? 0.0f : h;
            d.pressure    = isnan(p) ? 0.0f : p;
            d.tempValid   = true;
        }
    }

    if (!d.tempValid) {
        // senzor termic indisponibil - trimitem valori neutre marcate ca nevalide,
        // ca monitorizarea gazului sa continue iar defectul sa fie vizibil pe dashboard
        d.temperature = 0.0f;
        d.humidity    = 0.0f;
        d.pressure    = 0.0f;
    }

    // media a 4 citiri ADC consecutive pentru reducerea zgomotului electric
    int sum = 0;
    for (int i = 0; i < 4; i++) { sum += analogRead(PIN_MQ2); delay(2); }
    d.gasValue = sum / 4;

    // gazul e mereu disponibil pe ADC, deci pachetul merita trimis chiar daca
    // senzorul de temperatura e defect - gazul nu trebuie pierdut niciodata
    d.valid = true;
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
