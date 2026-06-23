#pragma once
#include "espnow_gateway.h"

void serial_bridge_init();

// apelata in loop() — verifica daca au sosit comenzi de la Raspberry Pi
void serial_bridge_poll();

// serialzeaza un pachet senzorial ca JSON si il trimite catre Raspberry Pi
void serial_bridge_send_packet(const SensorPacket& pkt, int8_t rssi);
