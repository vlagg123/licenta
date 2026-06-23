#pragma once
#include <stdint.h>
#include <stdbool.h>

#define MAX_HOPS 4

// ── structura pachetului ESP-NOW ───────────────────────────────────────────
// trimis de nodurile senzoriale catre gateway (sau urmatorul hop)
struct SensorPacket {
    char    packetId[9];     // ID hex pe 8 caractere + terminator null
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
    uint8_t  route[MAX_HOPS];  // ID-urile nodurilor de pe traseul pachetului, 0 = gateway
    uint8_t  routeLen;
    uint8_t  tempSensorOk;     // 1 = senzor temperatura OK, 0 = defect/absent
};

// ── pachet de comanda (gateway → nod) ─────────────────────────────────────
struct CommandPacket {
    char    commandId[9];
    uint8_t targetNode;
    uint8_t commandType;   // valorile sunt definite in enum-ul CommandType din commands.h
    float   param1;        // parametri generici (la SET_THRESHOLDS: gaz normal, gaz critic,
    float   param2;        //                     temp warning, temp critic)
    float   param3;
    float   param4;
};

void comm_init(uint8_t selfId, const uint8_t* gatewayMac);
bool comm_send_packet(const SensorPacket& pkt, const uint8_t* destMac);
void comm_register_receive_callback(void (*cb)(const SensorPacket&, int8_t rssi));
void comm_register_command_callback(void (*cb)(const CommandPacket&));
