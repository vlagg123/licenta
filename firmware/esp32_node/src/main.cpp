#include <Arduino.h>
#include "config.h"
#include "sensors.h"
#include "routing.h"
#include "communication.h"
#include "commands.h"

static uint8_t  nodeId        = NODE_ID;
static uint32_t packetCounter = 0;
static bool     inAlertMode   = false;
static bool     forceAlert    = false;

static GasThresholds gasThresholds = {
    GAS_NORMAL_MAX, GAS_LOW_MAX, GAS_MEDIUM_MAX, GAS_HIGH_MAX,
    (bool)BUZZER_ON_GAS_HIGH
};

// ultimele 5 temperaturi pt detectia trendului
static float tempHistory[5] = {25.0f, 25.0f, 25.0f, 25.0f, 25.0f};
static int   histIdx = 0;

static int computeRiskScore(float temp, int gas, int battery, int8_t rssi) {
    int score = 0;

    if (temp < TEMP_WARNING)      score += (int)((temp - 20.0f) / (TEMP_WARNING - 20.0f) * 10.0f);
    else if (temp < TEMP_ALERT)   score += 10 + (int)((temp - TEMP_WARNING) / (TEMP_ALERT - TEMP_WARNING) * 15.0f);
    else                          score += 25;
    score = max(0, score);

    if (gas < GAS_WARNING)        score += gas * 10 / GAS_WARNING;
    else if (gas < GAS_ALERT)     score += 10 + (gas - GAS_WARNING) * 20 / (GAS_ALERT - GAS_WARNING);
    else                          score += 30;

    // trend temperatura - daca urca mai mult de 5 grade in 5 masuratori e suspect
    float oldest = tempHistory[(histIdx + 1) % 5];
    float newest = tempHistory[histIdx];
    float delta  = newest - oldest;
    if (delta >= 10.0f)      score += 20;
    else if (delta >= 5.0f)  score += 12;
    else if (delta >= 2.0f)  score += 5;

    if (battery < 20) score += 5;
    if (rssi < -80)   score += 5;

    return min(100, max(0, score));
}

static uint8_t classifyStatus(int risk) {
    if (risk >= RISK_ALERT)   return 2;
    if (risk >= RISK_WARNING) return 1;
    return 0;
}

static void updateIndicators(uint8_t status, GasLevel gasLevel) {
    bool buzzerActive = !commands_is_muted() &&
                        shouldActivateBuzzer(gasLevel, gasThresholds);

    switch (status) {
        case 2:
            digitalWrite(PIN_LED, HIGH);
            break;
        case 1:
            digitalWrite(PIN_LED, (millis() / 500) % 2);
            break;
        default:
            digitalWrite(PIN_LED, LOW);
            break;
    }
    Serial.printf("[BUZZ] gasLvl=%d buzzerActive=%d\n", (int)gasLevel, (int)buzzerActive);
    if (buzzerActive) digitalWrite(PIN_BUZZER, HIGH);
    else              digitalWrite(PIN_BUZZER, LOW);
}

static void onPacketReceived(const SensorPacket& pkt, int8_t rssi) {
    uint8_t mac[6] = {0};
    routing_update_neighbour(pkt.sourceId, mac, rssi, pkt.battery);

    if (pkt.sourceId != nodeId && pkt.destinationId != nodeId) {
        RouteEntry route = routing_best_next_hop(pkt.destinationId, pkt.messageType == 2);
        if (route.valid) {
            SensorPacket fwd = pkt;
            fwd.hopCount++;
            if (fwd.routeLen < MAX_HOPS) fwd.route[fwd.routeLen++] = nodeId;
            comm_send_packet(fwd, GATEWAY_MAC);
        }
    }
}

static void onCommandReceived(const CommandPacket& cmd) {
    if (cmd.targetNode == nodeId || cmd.targetNode == 0xFF) {
        commands_handle(cmd);
        if (cmd.commandType == CMD_FORCE_ALERT) forceAlert = true;
        if (cmd.commandType == CMD_RESET_ALERT)  forceAlert = false;
    }
}

static void sendSensorPacket(const SensorData& sd) {
    // DE MODIFICAT PENTRU PARTEA HARDWARE:
    // rssi-ul real al peer-ului nu e accesibil direct fara modul promiscuu activat
    // o alternativa e sa folosesti WiFi.RSSI() dupa un esp_wifi_sta_get_ap_info()
    // sau sa trimiti rssi-ul primit in pachetele de la vecini si sa il stochezi in routing table
    int8_t rssi = -60;

    histIdx = (histIdx + 1) % 5;
    tempHistory[histIdx] = sd.temperature;

    GasLevel gasLevel = classifyGasLevel(sd.gasValue, gasThresholds);
    int risk = computeRiskScore(sd.temperature, sd.gasValue, 85, rssi);
    if (forceAlert) risk = max(risk, 75);

    uint8_t status = classifyStatus(risk);
    inAlertMode = (status == 2);

    SensorPacket pkt;
    snprintf(pkt.packetId, sizeof(pkt.packetId), "%08lX", packetCounter++);
    pkt.sourceId      = nodeId;
    pkt.destinationId = 0;
    pkt.messageType   = status;
    pkt.priority      = (status == 2) ? 2 : (status == 1 ? 1 : 0);
    pkt.temperature   = sd.temperature;
    pkt.humidity      = sd.humidity;
    pkt.pressure      = sd.pressure;
    pkt.gasValue      = (int16_t)sd.gasValue;
    pkt.riskScore     = (uint8_t)risk;
    pkt.hopCount      = 1;
    pkt.rssi          = rssi;

    // DE MODIFICAT PENTRU PARTEA HARDWARE:
    // bateria e hardcodata la 85% - trebuie citita din ADC printr-un divizor de tensiune
    // schema tipica: baterie → R1(100k) → ADC_PIN → R2(100k) → GND
    // formula: battery_pct = (analogRead(PIN_BATT) / 4095.0f * 2.0f * 3.3f / 4.2f) * 100
    // ajusteaza valorile R1/R2 si tensiunile dupa tipul bateriei (LiPo = 3.0V min, 4.2V max)
    pkt.battery       = 85;

    pkt.timestampMs   = millis();
    pkt.route[0]      = nodeId;
    pkt.routeLen      = 1;

    RouteEntry bestRoute = routing_best_next_hop(0, inAlertMode);
    uint8_t nextHopMac[6];
    memcpy(nextHopMac, GATEWAY_MAC, 6);

    bool sent = comm_send_packet(pkt, nextHopMac);
    Serial.printf("[TX] N%d T=%.1f Gas=%d GasLvl=%d Risk=%d Status=%d Sent=%d\n",
                  nodeId, sd.temperature, sd.gasValue, (int)gasLevel, risk, status, sent);

    updateIndicators(status, gasLevel);
}

void setup() {
    pinMode(PIN_BUZZER, OUTPUT);
    digitalWrite(PIN_BUZZER, LOW);
    Serial.begin(115200);
    delay(500);
    Serial.printf("\n=== FireWSN Node %d pornit ===\n", nodeId);

    commands_init(PIN_LED, PIN_BUZZER);
    sensors_init();
    routing_init(nodeId);
    comm_init(nodeId, GATEWAY_MAC);
    comm_register_receive_callback(onPacketReceived);
    comm_register_command_callback(onCommandReceived);

    Serial.println("[BOOT] gata");
}

void loop() {
    routing_check_timeouts();

    SensorData sd = sensors_read();
    if (!sd.valid) {
        Serial.println("[LOOP] citire senzor invalida, skip");
    } else {
        sendSensorPacket(sd);
    }

    uint32_t interval = inAlertMode ? INTERVAL_ALERT_MS : INTERVAL_NORMAL_MS;
    delay(interval);
}
