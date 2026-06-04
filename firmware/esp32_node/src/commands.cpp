#include "commands.h"
#include "config.h"
#include <Arduino.h>

static uint8_t _led_pin    = PIN_LED;
static uint8_t _buzzer_pin = PIN_BUZZER;
static bool    _muted      = false;
static bool    _maintenance = false;

static float _temp_warn  = TEMP_WARNING;
static float _temp_alert = TEMP_ALERT;
static int   _gas_warn   = GAS_WARNING;
static int   _gas_alert  = GAS_ALERT;

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
        digitalWrite(_buzzer_pin, HIGH);
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
            _beep(3, 200, 100);
            _blink(3, 200, 100);
            Serial.println("[CMD] test alarma executat");
            break;

        case CMD_CALIBRATE_SENSOR:
            // placeholder - ar actualiza baseline-ul ADC
            Serial.println("[CMD] calibrare senzor");
            break;

        case CMD_SET_THRESHOLDS:
            _temp_warn = cmd.param1;
            _gas_alert = (int)cmd.param2;
            Serial.printf("[CMD] praguri noi: T_warn=%.1f Gas_alert=%d\n", _temp_warn, _gas_alert);
            break;

        case CMD_SET_MAINTENANCE_MODE:
            _maintenance = (bool)(int)cmd.param1;
            Serial.printf("[CMD] mentenanta: %s\n", _maintenance ? "ON" : "OFF");
            break;

        case CMD_REQUEST_STATUS:
            // loop-ul principal trimite un pachet de status la urmatorul ciclu
            Serial.println("[CMD] status solicitat");
            break;

        case CMD_FORCE_ALERT:
            Serial.println("[CMD] alerta fortata");
            break;

        default:
            Serial.printf("[CMD] comanda necunoscuta: %d\n", cmd.commandType);
    }
}

bool commands_is_muted()       { return _muted; }
bool commands_is_maintenance() { return _maintenance; }
