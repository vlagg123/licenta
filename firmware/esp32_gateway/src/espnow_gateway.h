#pragma once
#include <stdint.h>

// aceeasi structura de pachet ca in firmware-ul nodurilor senzoriale
#define MAX_HOPS 4

struct SensorPacket {
    char     packetId[9];    // ID hex pe 8 caractere + terminator
    uint8_t  sourceId;       // ID-ul nodului sursa
    uint8_t  destinationId;  // 0 = gateway
    uint8_t  messageType;    // 0=NORMAL 1=WARNING 2=ALERT
    uint8_t  priority;       // 0=LOW 1=NORMAL 2=HIGH
    float    temperature;
    float    humidity;
    float    pressure;
    int16_t  gasValue;
    uint8_t  riskScore;
    uint8_t  hopCount;
    int8_t   rssi;
    uint8_t  battery;
    uint32_t timestampMs;
    uint8_t  route[MAX_HOPS];
    uint8_t  routeLen;
    uint8_t  tempSensorOk;   // 1 = senzor temperatura OK, 0 = defect/absent
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
