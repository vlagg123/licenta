#include "commands.h"
#include "config.h"
#include <Arduino.h>

static uint8_t _led_pin    = PIN_LED;
static uint8_t _buzzer_pin = PIN_BUZZER;
static bool    _muted      = false;
static bool    _maintenance = false;
static bool    _test_pending = false;

void commands_init(uint8_t ledPin, uint8_t buzzerPin) {
    _led_pin    = ledPin;
    _buzzer_pin = buzzerPin;
    pinMode(_led_pin,    OUTPUT);
    pinMode(_buzzer_pin, OUTPUT);
    digitalWrite(_led_pin,    LOW);
    digitalWrite(_buzzer_pin, LOW);
}

static void _beep(int times, int onMs, int offMs) {
    if (_muted) return;
    for (int i = 0; i < times; i++) {
        digitalWrite(_buzzer_pin, HIGH);  // HIGH = buzzerul suna
        delay(onMs);
        digitalWrite(_buzzer_pin, LOW);
        delay(offMs);
    }
}

static void _blink(int times, int onMs, int offMs) {
    for (int i = 0; i < times; i++) {
        digitalWrite(_led_pin, HIGH);
        delay(onMs);
        digitalWrite(_led_pin, LOW);
        delay(offMs);
    }
}

void commands_handle(const CommandPacket& cmd) {
    Serial.printf("[CMD] tip=%d\n", cmd.commandType);
    switch ((CommandType)cmd.commandType) {
        case CMD_MUTE_BUZZER:
            _muted = true;
            digitalWrite(_buzzer_pin, LOW);
            Serial.println("[CMD] buzzer mut");
            break;

        case CMD_RESET_ALERT:
            _muted = false;
            _maintenance = false;
            Serial.println("[CMD] alerta resetata");
            break;

        case CMD_TEST_ALARM:
            // nu sunam aici — comanda vine din callback-ul ESP-NOW, iar delay-urile
            // ar bloca stiva radio; marcam si executam in loop() prin commands_run_pending()
            _test_pending = true;
            Serial.println("[CMD] test alarma programat");
            break;

        case CMD_SET_THRESHOLDS:
            // pragurile efective se aplica in main.cpp, unde traieste gasThresholds
            Serial.printf("[CMD] praguri gaz: normal<=%.0f critic>=%.0f\n", cmd.param1, cmd.param2);
            break;

        case CMD_SET_MAINTENANCE_MODE:
            _maintenance = (bool)(int)cmd.param1;
            Serial.printf("[CMD] mentenanta: %s\n", _maintenance ? "ON" : "OFF");
            break;

        default:
            Serial.printf("[CMD] comanda necunoscuta: %d\n", cmd.commandType);
    }
}

void commands_run_pending() {
    if (!_test_pending) return;
    _test_pending = false;
    _beep(3, 200, 100);
    _blink(3, 200, 100);
    Serial.println("[CMD] test alarma executat");
}

bool commands_is_muted()       { return _muted; }
bool commands_is_maintenance() { return _maintenance; }
