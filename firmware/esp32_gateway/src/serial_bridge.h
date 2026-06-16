#pragma once
#include "espnow_gateway.h"

void serial_bridge_init();

// apelata in loop() — verifica daca au sosit comenzi de la Raspberry Pi
void serial_bridge_poll(const uint8_t nodeMacs[][6], int nodeCount);

// serialzeaza un pachet senzorial ca JSON si il trimite catre Raspberry Pi
void serial_bridge_send_packet(const SensorPacket& pkt, int8_t rssi);
