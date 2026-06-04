#pragma once
#include "espnow_gateway.h"

void serial_bridge_init();

// Call in loop() to check for incoming commands from Raspberry Pi
void serial_bridge_poll(const uint8_t nodeMacs[][6], int nodeCount);

// Send a sensor packet as JSON to Raspberry Pi over Serial
void serial_bridge_send_packet(const SensorPacket& pkt, int8_t rssi);
