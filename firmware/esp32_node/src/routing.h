#pragma once
#include <stdint.h>

#define MAX_NODES    5
#define MAX_HOPS     4

// intrare in tabela de vecini
struct NeighbourEntry {
    uint8_t  nodeId;
    uint8_t  mac[6];
    int8_t   rssi;          // RSSI-ul ultimului pachet primit (dBm)
    uint8_t  battery;       // nivelul bateriei la ultima receptie (%)
    uint32_t lastSeenMs;    // momentul ultimului pachet primit (millis)
    bool     alive;
};

// intrare in tabela de rutare: cel mai bun next-hop catre o destinatie
struct RouteEntry {
    uint8_t  destination;
    uint8_t  nextHop;
    uint8_t  hopCount;
    float    cost;
    bool     valid;
};

void     routing_init(uint8_t selfId);
void     routing_update_neighbour(uint8_t nodeId, const uint8_t* mac, int8_t rssi, uint8_t battery);
void     routing_mark_dead(uint8_t nodeId);
void     routing_check_timeouts();
RouteEntry routing_best_next_hop(uint8_t destination, bool alertMode);
uint8_t  routing_hop_count_to_gateway();
float    routing_link_cost(int8_t rssi, uint8_t battery, bool alertMode);
