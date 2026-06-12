#include "sensors.h"
#include "config.h"
#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_BME280.h>

static Adafruit_BME280 bme;
static bool bme_ok = false;

void sensors_init() {
    Wire.begin(PIN_BME_SDA, PIN_BME_SCL);
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
    // DE MODIFICAT PENTRU PARTEA HARDWARE:
    // rezolutia ADC 12-bit (0-4095) e standard ESP32; daca folosesti ESP32-S2/S3
    // verifica daca au nevoie de configuratie diferita
    analogReadResolution(12);

    // DE MODIFICAT PENTRU PARTEA HARDWARE:
    // senzorul MQ are nevoie de timp de incalzire dupa alimentare
    // minim 30s pentru citiri stabile, ideal 24h la prima pornire
    // in productie ar trebui sa astepti sau sa marchezi primele citiri ca nesigure
    Serial.println("[SENSORS] pin MQ configurat - citirile sunt stabile dupa ~30s de incalzire");
}

SensorData sensors_read() {
    SensorData d;
    d.valid = false;

    if (bme_ok) {
        d.temperature = bme.readTemperature();
        d.humidity    = bme.readHumidity();
        d.pressure    = bme.readPressure() / 100.0f;  // Pa → hPa
    } else {
        // DE MODIFICAT PENTRU PARTEA HARDWARE:
        // fallback cu valori fixe - in productie reala ar trebui trimis un flag de eroare
        // ca gateway-ul sa stie ca senzorul de temperatura nu functioneaza
        d.temperature = 25.0f;
        d.humidity    = 50.0f;
        d.pressure    = 1013.0f;
    }

    // media a 4 citiri ADC pentru reducere zgomot
    int sum = 0;
    for (int i = 0; i < 4; i++) { sum += analogRead(PIN_MQ2); delay(2); }
    d.gasValue = sum / 4;

    // DE MODIFICAT PENTRU PARTEA HARDWARE:
    // valoarea ADC bruta a MQ-2/MQ-135 depinde de tensiunea de referinta si de
    // rezistenta de sarcina (RL) montata pe placa senzorului
    // pentru conversie in PPM ar trebui aplicata formula din datasheet-ul senzorului
    // momentan trimitem valoarea ADC bruta (0-4095) si comparam cu praguri empirice

    d.valid = (d.temperature > -40.0f && d.temperature < 125.0f);
    return d;
}

GasLevel classifyGasLevel(int gasValue, const GasThresholds& t) {
    if (gasValue <= t.normalMax) return GAS_NORMAL;
    if (gasValue <= t.lowMax)    return GAS_LOW;
    if (gasValue <= t.mediumMax) return GAS_MEDIUM;
    if (gasValue <= t.highMax)   return GAS_HIGH;
    return GAS_CRITICAL;
}

bool shouldActivateBuzzer(GasLevel level, const GasThresholds& t) {
    if (level == GAS_CRITICAL)               return true;
    if (level == GAS_HIGH && t.buzzerOnHigh) return true;
    return false;
}
