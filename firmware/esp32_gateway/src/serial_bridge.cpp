#include "serial_bridge.h"
#include "config.h"
#include <Arduino.h>
#include <ArduinoJson.h>
#include <string.h>

static const char* STATUS_NAMES[] = {"NORMAL", "WARNING", "ALERT"};
static const char* PRIO_NAMES[]   = {"LOW", "NORMAL", "HIGH"};

void serial_bridge_init() {
    Serial.begin(SERIAL_BAUD);
    Serial.println("{\"type\":\"gateway_boot\",\"msg\":\"FireWSN Gateway pornit\"}");
}

void serial_bridge_send_packet(const SensorPacket& pkt, int8_t rssi) {
    StaticJsonDocument<512> doc;
    doc["type"]        = "sensor_data";
    doc["packet_id"]   = pkt.packetId;
    doc["node_id"]     = pkt.sourceId;
    doc["zone"]        = (pkt.sourceId < ZONE_COUNT) ? ZONE_NAMES[pkt.sourceId] : "Unknown";
    doc["temperature"] = serialized(String(pkt.temperature, 1));
    doc["humidity"]    = serialized(String(pkt.humidity, 1));
    doc["pressure"]    = serialized(String(pkt.pressure, 1));
    doc["gas_value"]   = pkt.gasValue;
    doc["risk_score"]  = pkt.riskScore;

    uint8_t st = min((uint8_t)2, pkt.messageType);
    doc["status"]       = STATUS_NAMES[st];
    doc["message_type"] = STATUS_NAMES[st];
    doc["priority"]     = PRIO_NAMES[min((uint8_t)2, pkt.priority)];

    JsonArray route = doc.createNestedArray("route");
    for (int i = 0; i < pkt.routeLen && i < MAX_HOPS; i++) route.add(pkt.route[i]);
    route.add(0);  // gateway e intotdeauna destinatia finala

    doc["hop_count"]     = pkt.hopCount;
    doc["rssi"]          = rssi;
    doc["battery"]       = pkt.battery;
    doc["latency_ms"]    = pkt.hopCount * 8 + 5;
    doc["temp_sensor_ok"] = (bool)pkt.tempSensorOk;

    // timestamp-ul e adaugat de Raspberry Pi la receptionare (serial_gateway.py)
    doc["timestamp"] = "2026-01-01T00:00:00";

    serializeJson(doc, Serial);
    Serial.println();
}

void serial_bridge_poll() {
    if (!Serial.available()) return;

    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.length() == 0) return;

    StaticJsonDocument<256> doc;
    DeserializationError err = deserializeJson(doc, line);
    if (err) {
        Serial.printf("{\"type\":\"error\",\"msg\":\"JSON parse error: %s\"}\n", err.c_str());
        return;
    }

    if (strcmp(doc["type"], "command") != 0) return;

    CommandPacket cmd = {};
    strncpy(cmd.commandId, doc["command_id"] | "cmd000", 8);
    cmd.targetNode = doc["target_node"] | 0;
    cmd.param1     = doc["payload"]["param1"] | 0.0f;
    cmd.param2     = doc["payload"]["param2"] | 0.0f;
    cmd.param3     = doc["payload"]["param3"] | 0.0f;
    cmd.param4     = doc["payload"]["param4"] | 0.0f;

    // mapeaza numele comenzii (string) la codul numeric asteptat de noduri
    const char* ct = doc["command_type"];
    if      (strcmp(ct, "MUTE_BUZZER")          == 0) cmd.commandType = 1;
    else if (strcmp(ct, "RESET_ALERT")          == 0) cmd.commandType = 2;
    else if (strcmp(ct, "TEST_ALARM")           == 0) cmd.commandType = 3;
    else if (strcmp(ct, "SET_THRESHOLDS")       == 0) cmd.commandType = 5;
    else if (strcmp(ct, "SET_MAINTENANCE_MODE") == 0) cmd.commandType = 6;

    // trimite catre nod folosind MAC-ul invatat din pachetele lui
    uint8_t target = cmd.targetNode;
    if (espnow_send_command_to_node(cmd, target)) {
        Serial.printf("{\"type\":\"ack\",\"command_id\":\"%s\",\"target\":%d}\n",
                      cmd.commandId, target);
    } else {
        Serial.printf("{\"type\":\"error\",\"msg\":\"nod %d necunoscut - nu a trimis inca date\"}\n", target);
    }
}
