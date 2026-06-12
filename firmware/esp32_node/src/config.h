#pragma once
#include <stdint.h>

// DE MODIFICAT PENTRU PARTEA HARDWARE:
// NODE_ID se seteaza in platformio.ini cu build_flags = -DNODE_ID=1 (sau 2, 3, 4)
// fiecare nod fizic trebuie flashuit cu valoarea corecta, altfel coliziune de ID
#ifndef NODE_ID
  #define NODE_ID 1
#endif

// DE MODIFICAT PENTRU PARTEA HARDWARE:
// citeste MAC-ul gateway-ului din Serial Monitor dupa primul flash al gateway-ului
// (apare ca "[GW] MAC: AA:BB:CC:DD:EE:FF") si inlocuieste valorile de mai jos
static const uint8_t GATEWAY_MAC[6] = { 0xA4, 0xF0, 0x0F, 0x77, 0x57, 0x80 };

// DE MODIFICAT PENTRU PARTEA HARDWARE:
// verifica pinii pe schema electronica a placii tale de ESP32
// GPIO 34 e input-only (ADC1), bun pentru MQ; daca folosesti alta placa ajusteaza
#define PIN_MQ2        34   // intrare analogica MQ-2 / MQ-135 (ADC1)
#define PIN_LED        2    // LED built-in (activ HIGH pe majoritatea placilor)
#define PIN_BUZZER     4    // buzzer pasiv
#define PIN_BME_SDA    21   // I2C SDA pentru BME280
#define PIN_BME_SCL    22   // I2C SCL pentru BME280

// DE MODIFICAT PENTRU PARTEA HARDWARE:
// adresa I2C a BME280: 0x76 daca pinul SDO e la GND, 0x77 daca e la VCC
// masoara cu un I2C scanner sketch daca nu stii
#define BME280_ADDRESS 0x76

#define INTERVAL_NORMAL_MS   5000
#define INTERVAL_ALERT_MS    1000
#define OFFLINE_TIMEOUT_MS   15000

#define TEMP_WARNING   45.0f
#define TEMP_ALERT     65.0f
#define GAS_WARNING    400
#define GAS_ALERT      700
#define RISK_WARNING   40
#define RISK_ALERT     70

// DE MODIFICAT PENTRU PARTEA HARDWARE:
// pragurile de gaz de mai jos sunt valori estimate pentru MQ-2/MQ-135 in aer curat
// dupa montare senzorul trebuie lasat sa se incalzeasca ~24h, apoi calibrat
// citeste valorile ADC in aer curat si in prezenta fumului si ajusteaza pragurile
#define GAS_NORMAL_MAX   300
#define GAS_LOW_MAX      450
#define GAS_MEDIUM_MAX   600
#define GAS_HIGH_MAX     750
// GAS_CRITICAL: orice valoare >= critical_min din backend (default 751)

// Buzzer: 0 = doar la CRITICAL, 1 = si la HIGH
#define BUZZER_ON_GAS_HIGH  0

#define ESPNOW_CHANNEL 1
