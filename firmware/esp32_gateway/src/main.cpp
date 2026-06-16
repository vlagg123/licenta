#include <Arduino.h>
#include "config.h"
#include "espnow_gateway.h"
#include "serial_bridge.h"

// MAC-urile nodurilor senzoriale — citite din Serial Monitor dupa flashuirea fiecarui nod
// adauga Serial.println(WiFi.macAddress()) in comm_init() al nodului ca sa apara la boot
static uint8_t NODE_MACS[5][6] = {
    {0x00, 0x00, 0x00, 0x00, 0x00, 0x00},  // 0 = gateway (self, neutilizat)
    {0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0x01},  // 1 = Intrare
    {0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0x02},  // 2 = Depozit
    {0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0x03},  // 3 = Parcare
    {0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0x04},  // 4 = Tablou electric
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
