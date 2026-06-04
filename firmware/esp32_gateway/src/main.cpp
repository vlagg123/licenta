#include <Arduino.h>
#include "config.h"
#include "espnow_gateway.h"
#include "serial_bridge.h"

// DE MODIFICAT PENTRU PARTEA HARDWARE:
// inlocuieste toate MAC-urile de mai jos cu valorile reale ale nodurilor senzoriale
// pasii:
//   1. flashuieste fiecare nod sensor
//   2. deschide Serial Monitor (115200 baud)
//   3. reseteaza nodul - va printa ceva de genul "[COMM] ESP-NOW pornit. Nod 1"
//      dar MAC-ul ESP32 apare de obicei inainte, la WiFi.mode() in comm_init
//      alternativ adauga Serial.println(WiFi.macAddress()) in comm_init
//   4. copiaza MAC-ul aici in formatul { 0xAA, 0xBB, ... }
static uint8_t NODE_MACS[5][6] = {
    {0x00, 0x00, 0x00, 0x00, 0x00, 0x00},  // 0 = gateway (self, nu e folosit)
    {0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0x01},  // 1 = Intrare  - DE MODIFICAT
    {0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0x02},  // 2 = Depozit  - DE MODIFICAT
    {0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0x03},  // 3 = Parcare  - DE MODIFICAT
    {0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0x04},  // 4 = Tablou   - DE MODIFICAT
};

static void onPacketReceived(const SensorPacket& pkt, int8_t rssi) {
    serial_bridge_send_packet(pkt, rssi);
}

void setup() {
    serial_bridge_init();
    espnow_init();
    espnow_register_packet_callback(onPacketReceived);
    Serial.println("{\"type\":\"gateway_ready\",\"msg\":\"Astept noduri senzoriale\"}");
}

void loop() {
    serial_bridge_poll(NODE_MACS, 5);
    delay(10);
}
