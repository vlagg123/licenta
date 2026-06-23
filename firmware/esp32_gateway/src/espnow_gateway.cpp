#include "espnow_gateway.h"
#include "config.h"
#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <string.h>

static void (*_pkt_cb)(const SensorPacket&, int8_t) = nullptr;

// tabela de MAC-uri invatate din pachetele primite, indexata dupa node_id;
// asa gateway-ul stie unde sa trimita comenzile fara MAC-uri hardcodate
#define GW_MAX_NODES 8
static uint8_t _node_mac[GW_MAX_NODES][6];
static bool    _node_known[GW_MAX_NODES] = { false };

static void _on_recv(const uint8_t* mac, const uint8_t* data, int len) {
    if (len == sizeof(SensorPacket)) {
        SensorPacket pkt;
        memcpy(&pkt, data, sizeof(pkt));
        // invatam MAC-ul real al nodului din pachet, ca sa-i putem trimite comenzi inapoi
        if (pkt.sourceId < GW_MAX_NODES) {
            memcpy(_node_mac[pkt.sourceId], mac, 6);
            _node_known[pkt.sourceId] = true;
        }
        // RSSI real al peer-ului necesita modul promiscuu; folosim -60 ca aproximatie
        int8_t rssi = -60;
        Serial.printf("[GW-RX] Nod=%d Risk=%d Temp=%.1f Gas=%d\n",
                      pkt.sourceId, pkt.riskScore, pkt.temperature, pkt.gasValue);
        if (_pkt_cb) _pkt_cb(pkt, rssi);
    }
}

static void _on_sent(const uint8_t* mac, esp_now_send_status_t status) {
    Serial.printf("[GW-TX] %s\n", status == ESP_NOW_SEND_SUCCESS ? "OK" : "FAIL");
}

void espnow_init() {
    WiFi.mode(WIFI_STA);
    WiFi.disconnect();

    // MAC-ul afisat aici trebuie copiat in GATEWAY_MAC din config.h al fiecarui nod
    Serial.print("[GW] MAC: ");
    Serial.println(WiFi.macAddress());

    if (esp_now_init() != ESP_OK) {
        Serial.println("[GW] ESP-NOW init esuat!");
        return;
    }
    esp_now_register_recv_cb(_on_recv);
    esp_now_register_send_cb(_on_sent);
    Serial.println("[GW] ESP-NOW gata");
}

bool espnow_send_command(const CommandPacket& cmd, const uint8_t* destMac) {
    if (!esp_now_is_peer_exist(destMac)) {
        esp_now_peer_info_t peer = {};
        memcpy(peer.peer_addr, destMac, 6);
        peer.channel = ESPNOW_CHANNEL;
        peer.encrypt = false;
        esp_now_add_peer(&peer);
    }
    return esp_now_send(destMac, (uint8_t*)&cmd, sizeof(cmd)) == ESP_OK;
}

bool espnow_send_command_to_node(const CommandPacket& cmd, uint8_t nodeId) {
    // foloseste MAC-ul invatat din pachete; daca nodul nu a trimis inca date, nu stim unde sa-i trimitem
    if (nodeId >= GW_MAX_NODES || !_node_known[nodeId]) return false;
    return espnow_send_command(cmd, _node_mac[nodeId]);
}

void espnow_register_packet_callback(void (*cb)(const SensorPacket&, int8_t rssi)) {
    _pkt_cb = cb;
}
