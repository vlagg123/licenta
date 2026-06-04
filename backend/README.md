# Fire Detection WSN – Backend

## Pornire rapidă (Simulation Mode – fără hardware)

```bash
# 1. Creează virtual environment
cd fire-detection-wsn/backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Instalează dependențe
pip install -r requirements.txt

# 3. Pornește serverul în Simulation Mode
SIMULATION_MODE=true uvicorn app.main:app --host 0.0.0.0 --port 8000

# 4. Deschide dashboardul:
#    http://localhost:8000          (laptop)
#    http://IP_RASPBERRY_PI:8000   (telefon pe aceeași rețea)
```

## Variabile de configurare

| Variabilă | Default | Descriere |
|---|---|---|
| `SIMULATION_MODE` | `true` | `true` = date simulate, `false` = serial real |
| `SERIAL_PORT` | `/dev/ttyUSB0` | Port USB pentru ESP32 gateway |
| `SERIAL_BAUDRATE` | `115200` | Viteză serial |
| `PORT` | `8000` | Port HTTP |
| `SIMULATION_INTERVAL` | `3.0` | Secundă între pachete simulate |

## Rulare pe Raspberry Pi 4

```bash
# Instalare completă pe Raspberry Pi
sudo apt update && sudo apt install -y python3 python3-pip python3-venv git

git clone <repo_url> fire-detection-wsn
cd fire-detection-wsn/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Simulation Mode (fără ESP32):
SIMULATION_MODE=true uvicorn app.main:app --host 0.0.0.0 --port 8000

# Hardware Mode (cu ESP32 gateway pe USB):
SIMULATION_MODE=false SERIAL_PORT=/dev/ttyUSB0 uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Pornire automată la boot (systemd)

```bash
sudo nano /etc/systemd/system/firewsn.service
```

```ini
[Unit]
Description=Fire Detection WSN Backend
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/fire-detection-wsn/backend
Environment=SIMULATION_MODE=true
ExecStart=/home/pi/fire-detection-wsn/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable firewsn
sudo systemctl start firewsn
sudo systemctl status firewsn
```

## API Endpoints

| Method | URL | Descriere |
|---|---|---|
| GET | `/api/nodes` | Toate nodurile cu starea curentă |
| GET | `/api/nodes/{id}` | Detalii nod specific |
| GET | `/api/nodes/{id}/routes` | Rute disponibile de la nod |
| GET | `/api/events` | Jurnal evenimente (SQLite) |
| POST | `/api/commands` | Trimite comandă la nod |
| POST | `/api/simulation/alert/{id}` | Forțează alertă pe nod |
| POST | `/api/simulation/offline/{id}` | Forțează nod offline |
| POST | `/api/simulation/reset` | Reset total sistem |
| POST | `/api/simulation/route-failure?node_id=X` | Simulează rută alternativă |
| POST | `/api/simulation/packet-loss?pct=0.4` | Simulează 40% pierdere pachete |
| POST | `/api/simulation/restore` | Restaurează conexiunile |
| GET | `/api/system/status` | Status general sistem |
| WS  | `/ws` | WebSocket live updates |

## Trecere din Simulation Mode în Hardware Mode

1. Flashează firmware-ul pe ESP32 gateway (vezi `firmware/esp32_gateway/`)
2. Conectează ESP32 gateway la Raspberry Pi prin USB
3. Identifică portul serial: `ls /dev/ttyUSB*` sau `ls /dev/ttyACM*`
4. Pornește backend-ul cu:
   ```bash
   SIMULATION_MODE=false SERIAL_PORT=/dev/ttyUSB0 uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
5. Asigură-te că utilizatorul `pi` are drepturi la portul serial:
   ```bash
   sudo usermod -a -G dialout pi
   # logout + login again
   ```

## Acces de pe telefon

1. Conectează telefonul la aceeași rețea Wi-Fi ca Raspberry Pi
2. Află IP-ul Raspberry Pi: `hostname -I`
3. Deschide în browser: `http://192.168.X.X:8000`
