#pragma once
#include "communication.h"

enum CommandType : uint8_t {
    CMD_MUTE_BUZZER          = 1,
    CMD_RESET_ALERT          = 2,
    CMD_TEST_ALARM           = 3,
    CMD_SET_THRESHOLDS       = 5,
    CMD_SET_MAINTENANCE_MODE = 6,
};

void commands_init(uint8_t ledPin, uint8_t buzzerPin);
void commands_handle(const CommandPacket& cmd);
// executa testul de alarma daca a fost cerut — se apeleaza din loop(), nu din
// callback-ul ESP-NOW, fiindca foloseste delay-uri blocante
void commands_run_pending();
bool commands_is_muted();
bool commands_is_maintenance();
