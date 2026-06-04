#pragma once
#include <stdint.h>

// Reuse the same packet struct from node firmware
#define MAX_HOPS 4

struct SensorPacket {
    char    packetId[9];
    uint8_t sourceId;
    uint8_t destinationId;
    uint8_t messageType;
    uint8_t priority;
    float   temperature;
    float   humidity;
    float   pressure;
    int16_t gasValue;
    uint8_t riskScore;
    uint8_t hopCount;
    int8_t  rssi;
    uint8_t battery;
    uint32_t timestampMs;
    uint8_t  route[MAX_HOPS];
    uint8_t  routeLen;
};

struct CommandPacket {
    char    commandId[9];
    uint8_t targetNode;
    uint8_t commandType;
    float   param1;
    float   param2;
};

void     espnow_init();
bool     espnow_send_command(const CommandPacket& cmd, const uint8_t* destMac);
void     espnow_register_packet_callback(void (*cb)(const SensorPacket&, int8_t rssi));
