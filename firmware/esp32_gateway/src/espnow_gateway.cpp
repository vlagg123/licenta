#include "espnow_gateway.h"
#include "config.h"
#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <string.h>

static void (*_pkt_cb)(const SensorPacket&, int8_t) = nullptr;

static void _on_recv(const uint8_t* mac, const uint8_t* data, int len) {
    if (len == sizeof(SensorPacket)) {
        SensorPacket pkt;
        memcpy(&pkt, data, sizeof(pkt));
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

void espnow_register_packet_callback(void (*cb)(const SensorPacket&, int8_t rssi)) {
    _pkt_cb = cb;
}
