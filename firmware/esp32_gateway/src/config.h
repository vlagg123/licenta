#pragma once

#define GATEWAY_ID      0
#define SERIAL_BAUD     115200
#define ESPNOW_CHANNEL  1

// Zone names indexed by node_id
static const char* ZONE_NAMES[] = {
    "Camera tehnica",   // 0 = gateway
    "Intrare",          // 1
    "Depozit",          // 2
    "Parcare",          // 3
    "Tablou electric",  // 4
};
#define ZONE_COUNT 5
