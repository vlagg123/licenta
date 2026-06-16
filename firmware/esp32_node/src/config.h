#pragma once
#include <stdint.h>

// NODE_ID se seteaza individual in platformio.ini: build_flags = -DNODE_ID=1
// fiecare nod trebuie flashuit cu valoarea corecta (1, 2, 3 sau 4)
#ifndef NODE_ID
  #define NODE_ID 1
#endif

// MAC-ul gateway-ului — citit din Serial Monitor la primul flash al gateway-ului
// apare ca: "[GW] MAC: AA:BB:CC:DD:EE:FF"
static const uint8_t GATEWAY_MAC[6] = { 0xA4, 0xF0, 0x0F, 0x77, 0x57, 0x80 };

// Toti pinii sunt pe partea stanga a ESP32-WROOM-32
#define PIN_MQ2        34   // ADC1 — input-only, potrivit pentru senzor analogic
#define PIN_LED        2    // LED built-in
#define PIN_BUZZER     27   // controleaza VCC-ul buzzerului (HIGH = sunet, LOW = silentios)
#define PIN_BME_SDA    33   // I2C SDA pentru BME280
#define PIN_BME_SCL    32   // I2C SCL pentru BME280

// Adresa I2C a BME280: 0x76 daca SDO e la GND, 0x77 daca SDO e la VCC.
// sensors_init() incearca automat ambele, deci nu o fixam aici.

// Intervalul de trimitere scade in caz de alerta pentru reactie mai rapida
#define INTERVAL_NORMAL_MS   5000
#define INTERVAL_ALERT_MS    1000

// Timeout dupa care un vecin e considerat inactiv in tabela de rutare
#define OFFLINE_TIMEOUT_MS   15000

// Praguri locale pentru clasificarea statusului si controlul indicatorilor
#define TEMP_WARNING   45.0f
#define TEMP_ALERT     65.0f
#define GAS_WARNING    400
#define GAS_ALERT      700

// Clasificare gaz in 5 niveluri — valori ADC brute pentru MQ-2/MQ-135
// calibrate empiric dupa incalzire (~30s pentru citiri stabile, ~24h la prima pornire)
#define GAS_NORMAL_MAX   300
#define GAS_LOW_MAX      450
#define GAS_MEDIUM_MAX   600
#define GAS_HIGH_MAX     750
#define GAS_CRITICAL_MIN 751

// 0 = buzzer activ doar la CRITICAL, 1 = activ si la HIGH
#define BUZZER_ON_GAS_HIGH  0

#define ESPNOW_CHANNEL 1
