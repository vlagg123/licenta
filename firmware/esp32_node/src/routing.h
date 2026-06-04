#pragma once
#include <stdint.h>

#define MAX_NODES    5
#define MAX_HOPS     4

// Neighbour table entry
struct NeighbourEntry {
    uint8_t  nodeId;
    uint8_t  mac[6];
    int8_t   rssi;          // last known RSSI (dBm)
    uint8_t  battery;       // last known battery %
    uint32_t lastSeenMs;    // millis() of last received packet
    bool     alive;
};

// Routing table entry: best next-hop towards a destination
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
