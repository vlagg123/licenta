#include <Arduino.h>
#include "config.h"
#include "espnow_gateway.h"
#include "serial_bridge.h"

// MAC-urile nodurilor nu se mai configureaza manual: gateway-ul le invata automat
// din pachetele primite si trimite comenzile inapoi pe MAC-ul corect (vezi espnow_gateway.cpp)

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
    serial_bridge_poll();
    delay(10);
}
