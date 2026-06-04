#include "routing.h"
#include "config.h"
#include <Arduino.h>
#include <string.h>
#include <math.h>

static NeighbourEntry neighbours[MAX_NODES];
static int            neighbour_count = 0;
static uint8_t        self_id = 0;

void routing_init(uint8_t selfId) {
    self_id = selfId;
    memset(neighbours, 0, sizeof(neighbours));
    neighbour_count = 0;
    Serial.printf("[ROUTING] nod %d initializat\n", self_id);
}

void routing_update_neighbour(uint8_t nodeId, const uint8_t* mac, int8_t rssi, uint8_t battery) {
    for (int i = 0; i < neighbour_count; i++) {
        if (neighbours[i].nodeId == nodeId) {
            neighbours[i].rssi       = rssi;
            neighbours[i].battery    = battery;
            neighbours[i].lastSeenMs = millis();
            neighbours[i].alive      = true;
            memcpy(neighbours[i].mac, mac, 6);
            return;
        }
    }
    if (neighbour_count < MAX_NODES) {
        neighbours[neighbour_count] = {nodeId, {0}, rssi, battery, (uint32_t)millis(), true};
        memcpy(neighbours[neighbour_count].mac, mac, 6);
        neighbour_count++;
        Serial.printf("[ROUTING] vecin nou: nod %d RSSI=%d\n", nodeId, rssi);
    }
}

void routing_mark_dead(uint8_t nodeId) {
    for (int i = 0; i < neighbour_count; i++) {
        if (neighbours[i].nodeId == nodeId) {
            neighbours[i].alive = false;
            Serial.printf("[ROUTING] nod %d marcat mort\n", nodeId);
        }
    }
}

void routing_check_timeouts() {
    uint32_t now = millis();
    for (int i = 0; i < neighbour_count; i++) {
        if (neighbours[i].alive && (now - neighbours[i].lastSeenMs) > OFFLINE_TIMEOUT_MS)
            routing_mark_dead(neighbours[i].nodeId);
    }
}

// formula cost: alpha*hop + beta*rssi_pen + gamma*batt_pen
// mod normal (battery-aware): alpha=0.30 beta=0.20 gamma=0.40
// mod alerta (latency-aware): alpha=0.50 beta=0.40 gamma=0.05
float routing_link_cost(int8_t rssi, uint8_t battery, bool alertMode) {
    const float alpha = alertMode ? 0.50f : 0.30f;
    const float beta  = alertMode ? 0.40f : 0.20f;
    const float gamma = alertMode ? 0.05f : 0.40f;

    // rssi ideal -40 dBm, range normalizare 60 dBm
    float rssi_pen = constrain((float)(-40 - rssi) / 60.0f, 0.0f, 1.0f);
    float batt_pen = (100.0f - battery) / 100.0f;

    return alpha * 1.0f + beta * rssi_pen + gamma * batt_pen;
}

// greedy: alege vecinul viu cu costul cel mai mic
RouteEntry routing_best_next_hop(uint8_t destination, bool alertMode) {
    RouteEntry best;
    best.valid    = false;
    best.cost     = 999.0f;
    best.hopCount = 99;

    for (int i = 0; i < neighbour_count; i++) {
        if (!neighbours[i].alive) continue;
        if (neighbours[i].nodeId == destination) {
            float c = routing_link_cost(neighbours[i].rssi, neighbours[i].battery, alertMode);
            if (c < best.cost) {
                best.destination = destination;
                best.nextHop     = destination;
                best.hopCount    = 1;
                best.cost        = c;
                best.valid       = true;
            }
        }
    }
    if (best.valid) return best;

    // destinatia nu e vecin direct - trimitem prin cel mai ieftin relay
    for (int i = 0; i < neighbour_count; i++) {
        if (!neighbours[i].alive) continue;
        float c = routing_link_cost(neighbours[i].rssi, neighbours[i].battery, alertMode) + 0.5f;
        if (c < best.cost) {
            best.destination = destination;
            best.nextHop     = neighbours[i].nodeId;
            best.hopCount    = 2;
            best.cost        = c;
            best.valid       = true;
        }
    }
    return best;
}

uint8_t routing_hop_count_to_gateway() {
    RouteEntry r = routing_best_next_hop(0, false);
    return r.valid ? r.hopCount : 99;
}
