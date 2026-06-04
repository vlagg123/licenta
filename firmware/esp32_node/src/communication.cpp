#include "communication.h"
#include "config.h"
#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <string.h>

static uint8_t self_id   = 0;
static uint8_t gw_mac[6] = {0};
static void (*rx_cb)(const SensorPacket&, int8_t) = nullptr;
static void (*cmd_cb)(const CommandPacket&)        = nullptr;

static void _on_data_recv(const uint8_t* mac, const uint8_t* data, int len) {
    if (len == sizeof(SensorPacket)) {
        SensorPacket pkt;
        memcpy(&pkt, data, sizeof(pkt));
        // DE MODIFICAT PENTRU PARTEA HARDWARE:
        // WiFi.RSSI() returneaza semnalul catre AP (access point), nu catre peer-ul ESP-NOW
        // pentru RSSI real al peer-ului ai nevoie de modul promiscuu activat si un callback
        // esp_wifi_set_promiscuous(true) + esp_wifi_set_promiscuous_rx_cb(sniffer_cb)
        // in sniffer_cb parsezi header-ul 802.11 si extragi rssi din wifi_pkt_rx_ctrl_t
        int8_t rssi = WiFi.RSSI();
        if (rx_cb) rx_cb(pkt, rssi);
    } else if (len == sizeof(CommandPacket)) {
        CommandPacket cmd;
        memcpy(&cmd, data, sizeof(cmd));
        if (cmd_cb) cmd_cb(cmd);
    } else {
        Serial.printf("[COMM] pachet necunoscut, size=%d\n", len);
    }
}

static void _on_data_sent(const uint8_t* mac, esp_now_send_status_t status) {
    if (status != ESP_NOW_SEND_SUCCESS)
        Serial.println("[COMM] trimitere esuata");
}

void comm_init(uint8_t selfId, const uint8_t* gatewayMac) {
    self_id = selfId;
    memcpy(gw_mac, gatewayMac, 6);

    WiFi.mode(WIFI_STA);
    WiFi.disconnect();

    if (esp_now_init() != ESP_OK) {
        Serial.println("[COMM] ESP-NOW init esuat!");
        return;
    }

    esp_now_register_recv_cb(_on_data_recv);
    esp_now_register_send_cb(_on_data_sent);

    // DE MODIFICAT PENTRU PARTEA HARDWARE:
    // GATEWAY_MAC din config.h trebuie sa fie MAC-ul real al gateway-ului
    // vezi comentariul din config.h despre cum sa citesti MAC-ul
    esp_now_peer_info_t peer = {};
    memcpy(peer.peer_addr, gw_mac, 6);
    peer.channel = ESPNOW_CHANNEL;
    peer.encrypt = false;
    if (esp_now_add_peer(&peer) != ESP_OK)
        Serial.println("[COMM] peer gateway nu s-a putut adauga");

    Serial.printf("[COMM] ESP-NOW pornit. Nod %d\n", self_id);
}

bool comm_send_packet(const SensorPacket& pkt, const uint8_t* destMac) {
    return esp_now_send(destMac, (uint8_t*)&pkt, sizeof(pkt)) == ESP_OK;
}

void comm_register_receive_callback(void (*cb)(const SensorPacket&, int8_t rssi)) {
    rx_cb = cb;
}

void comm_register_command_callback(void (*cb)(const CommandPacket&)) {
    cmd_cb = cb;
}
