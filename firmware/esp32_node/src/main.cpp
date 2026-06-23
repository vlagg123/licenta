#include <Arduino.h>
#include "config.h"
#include "sensors.h"
#include "routing.h"
#include "communication.h"
#include "commands.h"

static uint8_t  nodeId        = NODE_ID;
static uint32_t packetCounter = 0;
static bool     inAlertMode   = false;

static GasThresholds gasThresholds = {
    GAS_NORMAL_MAX, GAS_LOW_MAX, GAS_MEDIUM_MAX, GAS_HIGH_MAX, GAS_CRITICAL_MIN,
    (bool)BUZZER_ON_GAS_HIGH
};

// Istoricul ultimelor 5 temperaturi — folosit pentru detectia trendului termic
static float tempHistory[5] = {25.0f, 25.0f, 25.0f, 25.0f, 25.0f};
static int   histIdx        = 0;

// Scor de risc multi-factor (0-100): combina temperatura, gaz, trend, baterie si semnal.
// E doar o valoare informativa trimisa la dashboard; statusul care aprinde LED-ul si
// porneste buzzerul se decide separat, pe praguri directe, in classifyStatus().
static int computeRiskScore(float temp, int gas, int battery, int8_t rssi) {
    int score = 0;

    // componenta temperatura — proportionala pana la prag, maxima dupa
    if (temp < TEMP_WARNING)
        score += (int)((temp - 20.0f) / (TEMP_WARNING - 20.0f) * 10.0f);
    else if (temp < TEMP_ALERT)
        score += 10 + (int)((temp - TEMP_WARNING) / (TEMP_ALERT - TEMP_WARNING) * 15.0f);
    else
        score += 25;
    score = max(0, score);

    // componenta gaz — proportionala intre warning si alert
    if (gas < GAS_WARNING)       score += gas * 10 / GAS_WARNING;
    else if (gas < GAS_ALERT)    score += 10 + (gas - GAS_WARNING) * 20 / (GAS_ALERT - GAS_WARNING);
    else                         score += 30;

    // trend termic — crestere brusca in 5 masuratori consecutive sugereaza un incendiu
    float delta = tempHistory[histIdx] - tempHistory[(histIdx + 1) % 5];
    if      (delta >= 10.0f) score += 20;
    else if (delta >= 5.0f)  score += 12;
    else if (delta >= 2.0f)  score += 5;

    if (battery < 20) score += 5;
    if (rssi < -80)   score += 5;

    return min(100, max(0, score));
}

// Status local pe baza pragurilor directe — aceeasi logica ca backend-ul.
// Temperatura e indicator primar de incendiu: temp critica declanseaza ALERT
// independent de gaz, iar gazul critic la fel. Astfel nodul fizic (LED + buzzer)
// reactioneaza identic cu ce arata dashboard-ul, nu mai surd.
static uint8_t classifyStatus(float temp, int gas, GasLevel gasLevel) {
    bool critical = (gasLevel == GAS_CRITICAL) || (temp >= TEMP_ALERT);
    bool warning  = (gas > gasThresholds.normalMax) || (temp >= TEMP_WARNING);
    if (critical) return 2;  // ALERT
    if (warning)  return 1;  // WARNING
    return 0;                // NORMAL
}

static void updateIndicators(uint8_t status, GasLevel gasLevel) {
    // in mentenanta nodul nu mai semnalizeaza fizic — LED si buzzer raman stinse
    if (commands_is_maintenance()) {
        digitalWrite(PIN_LED, LOW);
        digitalWrite(PIN_BUZZER, LOW);
        return;
    }

    // buzzerul suna la orice ALERT (temp critica SAU gaz critic), daca nu e pe mute;
    // optional si la gaz HIGH cand buzzerOnHigh e activ
    bool buzzerActive = !commands_is_muted() &&
                        (status == 2 || shouldActivateBuzzer(gasLevel, gasThresholds));

    switch (status) {
        case 2:  digitalWrite(PIN_LED, HIGH);              break;
        case 1:  digitalWrite(PIN_LED, (millis()/500)%2); break;
        default: digitalWrite(PIN_LED, LOW);               break;
    }

    digitalWrite(PIN_BUZZER, buzzerActive ? HIGH : LOW);
}

static void onPacketReceived(const SensorPacket& pkt, int8_t rssi) {
    uint8_t mac[6] = {0};
    routing_update_neighbour(pkt.sourceId, mac, rssi, pkt.battery);

    // daca pachetul nu e pentru acest nod, il redirectioneaza catre destinatie
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
        // pragurile din dashboard se aplica aici, unde traieste gasThresholds:
        // param1 = normal max, param2 = critic min (pragul la care suna buzzerul)
        if (cmd.commandType == CMD_SET_THRESHOLDS) {
            if (cmd.param1 > 0) gasThresholds.normalMax   = (int)cmd.param1;
            if (cmd.param2 > 0) gasThresholds.criticalMin = (int)cmd.param2;
            Serial.printf("[CFG] praguri gaz actualizate: normal<=%d critic>=%d\n",
                          gasThresholds.normalMax, gasThresholds.criticalMin);
        }
    }
}

static void sendSensorPacket(const SensorData& sd) {
    // RSSI-ul peer-ului ESP-NOW nu e accesibil direct fara modul promiscuu activat
    int8_t rssi = -60;

    // istoricul de temperatura se actualizeaza doar cu citiri valide,
    // ca un senzor defect sa nu polueze detectia de trend
    if (sd.tempValid) {
        histIdx = (histIdx + 1) % 5;
        tempHistory[histIdx] = sd.temperature;
    }

    GasLevel gasLevel = classifyGasLevel(sd.gasValue, gasThresholds);
    int risk = computeRiskScore(sd.temperature, sd.gasValue, 85, rssi);

    uint8_t status = classifyStatus(sd.temperature, sd.gasValue, gasLevel);
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
    pkt.battery       = 85;  // hardcodat — citirea reala necesita divizor de tensiune pe ADC
    pkt.timestampMs   = millis();
    pkt.route[0]      = nodeId;
    pkt.routeLen      = 1;
    pkt.tempSensorOk  = sd.tempValid ? 1 : 0;

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
    // executa testul de alarma aici (in task-ul principal), nu in callback-ul ESP-NOW,
    // ca delay-urile lui sa nu blocheze stiva radio si sa reseteze nodul
    commands_run_pending();

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
