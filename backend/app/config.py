import os

# Modul de rulare: SIMULATION=true pentru demo fara hardware, false pentru hardware real
SIMULATION_MODE: bool = os.getenv("SIMULATION_MODE", "false").lower() == "true"

# Portul serial al gateway-ului ESP32 conectat prin USB
# Linux/Raspberry Pi: /dev/ttyUSB0 sau /dev/ttyACM0 (verifica cu: ls /dev/tty*)
# macOS: /dev/cu.usbserial-XXXX
SERIAL_PORT: str     = os.getenv("SERIAL_PORT", "/dev/ttyUSB0")
SERIAL_BAUDRATE: int = int(os.getenv("SERIAL_BAUDRATE", "115200"))

HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8000"))

DATABASE_PATH: str = os.getenv("DATABASE_PATH", "fire_detection.db")

SIMULATION_INTERVAL: float = float(os.getenv("SIMULATION_INTERVAL", "3.0"))

# Configuratia nodurilor: ID -> zona + coordonate (x, y) pe harta 2D din frontend
NODES_CONFIG: dict = {
    1: {"zone": "Intrare",         "x": 90,  "y": 180},
    2: {"zone": "Depozit",         "x": 310, "y": 180},
    3: {"zone": "Parcare",         "x": 310, "y": 340},
    4: {"zone": "Tablou electric", "x": 90,  "y": 340},
    0: {"zone": "Camera tehnica",  "x": 510, "y": 260},
}

# Topologia retelei: fiecare nod stie catre cine poate trimite direct si cu ce RSSI estimat
# Folosita de algoritmul de rutare pentru a calcula cel mai bun urmator hop
NEIGHBOUR_TABLE: dict = {
    1: [(2, -55), (4, -68)],
    2: [(1, -55), (3, -62), (0, -50)],
    3: [(2, -62), (4, -65)],
    4: [(1, -68), (3, -65)],
    0: [(2, -50)],
}

THRESHOLDS: dict = {
    "temperature_warning": 45.0,
    "temperature_alert":   65.0,
    "offline_timeout_s":   30,
}

# Coeficientii functiei de cost pentru rutare: cost = alpha*hop + beta*rssi_pen + gamma*batt_pen + delta*cong_pen
# Mod normal — prioritizeaza durata de viata a bateriei (gamma mare)
# Mod alerta — prioritizeaza latenta minima (alpha si beta mai mari, gamma mic)
ROUTING_WEIGHTS_NORMAL: dict = {"alpha": 0.30, "beta": 0.20, "gamma": 0.40, "delta": 0.10}
ROUTING_WEIGHTS_ALERT:  dict = {"alpha": 0.50, "beta": 0.40, "gamma": 0.05, "delta": 0.05}
