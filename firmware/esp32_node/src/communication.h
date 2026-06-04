#pragma once
#include <stdint.h>
#include <stdbool.h>

// ── ESP-NOW packet structure ───────────────────────────────────────────────
// Sent by sensor nodes to gateway (or next hop).
struct SensorPacket {
    char    packetId[9];     // 8-char hex + null
    uint8_t sourceId;
    uint8_t destinationId;   // 0 = gateway
    uint8_t messageType;     // 0=NORMAL 1=WARNING 2=ALERT
    uint8_t priority;        // 0=LOW 1=NORMAL 2=HIGH
    float   temperature;
    float   humidity;
    float   pressure;
    int16_t gasValue;
    uint8_t riskScore;
    uint8_t hopCount;
    int8_t  rssi;
    uint8_t battery;
    uint32_t timestampMs;
    uint8_t  route[MAX_HOPS];  // node IDs along the path, 0 = gateway / end
    uint8_t  routeLen;
};

// ── Command packet (gateway → node) ────────────────────────────────────────
struct CommandPacket {
    char    commandId[9];
    uint8_t targetNode;
    uint8_t commandType;   // see CommandType enum in commands.h
    float   param1;        // generic float parameter
    float   param2;
};

#define MAX_HOPS 4

void comm_init(uint8_t selfId, const uint8_t* gatewayMac);
bool comm_send_packet(const SensorPacket& pkt, const uint8_t* destMac);
void comm_register_receive_callback(void (*cb)(const SensorPacket&, int8_t rssi));
void comm_register_command_callback(void (*cb)(const CommandPacket&));
