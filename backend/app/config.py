import os

# Portul serial al gateway-ului ESP32 conectat prin USB la Raspberry Pi
# verifica portul cu: ls /dev/tty* inainte si dupa conectare
# de obicei /dev/ttyUSB0 sau /dev/ttyACM0
SERIAL_PORT: str     = os.getenv("SERIAL_PORT", "/dev/ttyUSB0")
SERIAL_BAUDRATE: int = int(os.getenv("SERIAL_BAUDRATE", "115200"))

HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8000"))

DATABASE_PATH: str = os.getenv("DATABASE_PATH", "fire_detection.db")

# Configuratia nodurilor: ID -> zona + coordonate (x, y) pe harta 2D din frontend
NODES_CONFIG: dict = {
    1: {"zone": "Intrare",         "x": 90,  "y": 180},
    2: {"zone": "Depozit",         "x": 310, "y": 180},
    3: {"zone": "Parcare",         "x": 310, "y": 340},
    4: {"zone": "Tablou electric", "x": 90,  "y": 340},
    0: {"zone": "Camera tehnica",  "x": 510, "y": 260},
}

THRESHOLDS: dict = {
    "temperature_warning": 45.0,
    "temperature_alert":   65.0,
    "offline_timeout_s":   15,   # secunde fara date pana cand nodul e marcat offline (3 pachete ratate)
}
