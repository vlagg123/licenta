import os

SIMULATION_MODE: bool = os.getenv("SIMULATION_MODE", "false").lower() == "true"

# DE MODIFICAT PENTRU PARTEA HARDWARE:
# SERIAL_PORT depinde de sistemul de operare si de portul USB folosit
# Linux/Raspberry Pi: de obicei /dev/ttyUSB0 sau /dev/ttyACM0 (verifica cu: ls /dev/tty*)
# macOS: /dev/cu.usbserial-XXXX sau /dev/cu.SLAB_USBtoUART
# Windows: COM3, COM4 etc. (verifica in Device Manager)
# SERIAL_BAUDRATE trebuie sa coincida cu SERIAL_BAUD din firmware-ul gateway-ului (config.h)
SERIAL_PORT: str     = os.getenv("SERIAL_PORT", "/dev/ttyUSB0")
SERIAL_BAUDRATE: int = int(os.getenv("SERIAL_BAUDRATE", "115200"))

HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8000"))

DATABASE_PATH: str = os.getenv("DATABASE_PATH", "fire_detection.db")

SIMULATION_INTERVAL: float = float(os.getenv("SIMULATION_INTERVAL", "3.0"))

# coordonatele x,y sunt in pixeli pe canvas-ul 2D din frontend
# DE MODIFICAT PENTRU PARTEA HARDWARE:
# daca zona fizica e diferita de ce s-a simulat, actualizeaza si numele zonelor si
# coordonatele x,y ca sa reflecte planul real al cladirii (vezi drawFloorplan in app.js)
NODES_CONFIG: dict = {
    1: {"zone": "Intrare",         "x": 90,  "y": 180},
    2: {"zone": "Depozit",         "x": 310, "y": 180},
    3: {"zone": "Parcare",         "x": 310, "y": 340},
    4: {"zone": "Tablou electric", "x": 90,  "y": 340},
    0: {"zone": "Camera tehnica",  "x": 510, "y": 260},
}

# DE MODIFICAT PENTRU PARTEA HARDWARE:
# NEIGHBOUR_TABLE trebuie sa reflecte topologia reala a retelei
# valorile rssi de baza sunt estimari - masoara rssi real intre noduri dupa montare
# si actualizeaza tuplurile (vecin_id, rssi_dBm)
# un nod care nu apare ca vecin al altui nod nu va fi niciodata ales ca relay
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
    "gas_warning":         400,
    "gas_alert":           700,
    "battery_low":         20,
    "offline_timeout_s":   30,
}

GAS_LEVEL_DEFAULTS: dict = {
    "normal_max":                300,
    "low_max":                   450,
    "medium_max":                600,
    "high_max":                  750,
    "critical_min":              751,
    "enable_buzzer_on_gas_high": False,
}

# formula cost rutare: cost = alpha*hop + beta*rssi_pen + gamma*batt_pen + delta*cong_pen
# mod normal => prioritate baterie, mod alerta => prioritate latenta
# DE MODIFICAT PENTRU PARTEA HARDWARE:
# dupa testare reala poti ajusta coeficientii in functie de comportamentul observat
# ex: daca bateria se descarca prea repede in retea, mareste gamma in mod normal
ROUTING_WEIGHTS_NORMAL: dict = {"alpha": 0.30, "beta": 0.20, "gamma": 0.40, "delta": 0.10}
ROUTING_WEIGHTS_ALERT:  dict = {"alpha": 0.50, "beta": 0.40, "gamma": 0.05, "delta": 0.05}
