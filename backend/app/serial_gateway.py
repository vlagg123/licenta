from __future__ import annotations
import asyncio
import json
import logging
from datetime import datetime
from typing import Callable, Optional

# DE MODIFICAT PENTRU PARTEA HARDWARE:
# SERIAL_PORT si SERIAL_BAUDRATE vin din config.py (sau din variabile de environment)
# pe Raspberry Pi ruleaza: ls /dev/tty* inainte si dupa conectarea gateway-ului USB
# ca sa identifici portul corect; de obicei /dev/ttyUSB0 sau /dev/ttyACM0
from app.config import SERIAL_PORT, SERIAL_BAUDRATE
from app.models import SensorPacket, NodeStatus, MessageType, Priority

log = logging.getLogger("serial_gateway")

try:
    import serial_asyncio
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    log.warning("serial_asyncio nu e instalat, hardware mode nu merge")


def _safe_enum(cls, value, default):
    """Intoarce default in loc sa arunce ValueError cand firmware-ul trimite o valoare neasteptata."""
    try:
        return cls(value)
    except (ValueError, KeyError):
        log.warning("valoare necunoscuta '%s' pentru %s - folosesc %s", value, cls.__name__, default)
        return default


def _parse_packet(raw: dict) -> Optional[SensorPacket]:
    try:
        node_id = int(raw["node_id"])
        # route: daca lipseste sau nu e lista, construim fallback minim valid
        raw_route = raw.get("route")
        if isinstance(raw_route, list) and all(isinstance(x, int) for x in raw_route):
            route = raw_route
        else:
            route = [node_id, 0]

        return SensorPacket(
            packet_id    = raw.get("packet_id", "hw000"),
            node_id      = node_id,
            zone         = raw.get("zone", "Unknown"),
            temperature  = float(raw.get("temperature", 0)),
            humidity     = float(raw.get("humidity", 0)),
            pressure     = float(raw.get("pressure", 1013)),
            gas_value    = int(raw.get("gas_value", 0)),
            risk_score   = int(raw.get("risk_score", 0)),
            # enum-uri cu fallback explicit - un string necunoscut nu mai arunca tot pachetul
            status       = _safe_enum(NodeStatus,    raw.get("status",       "NORMAL"), NodeStatus.NORMAL),
            message_type = _safe_enum(MessageType,   raw.get("message_type", "NORMAL"), MessageType.NORMAL),
            priority     = _safe_enum(Priority,      raw.get("priority",     "NORMAL"), Priority.NORMAL),
            route        = route,
            hop_count    = int(raw.get("hop_count", 1)),
            rssi         = int(raw.get("rssi", -60)),
            battery      = int(raw.get("battery", 100)),
            latency_ms   = int(raw.get("latency_ms", 20)),
            # DE MODIFICAT PENTRU PARTEA HARDWARE:
            # daca gateway-ul nu are RTC/NTP, timestamp-ul din pachet e "2026-01-01T00:00:00" (fals)
            # in acel caz backend-ul foloseste datetime.utcnow() ca fallback - suficient pt demo
            # pentru productie: fie adaugi NTP pe gateway (WiFi), fie folosesti un modul RTC (DS3231)
            timestamp    = datetime.utcnow(),
        )
    except Exception as exc:
        log.error("eroare parsare pachet: %s - %s", raw, exc)
        return None


class SerialGateway:
    def __init__(self, packet_callback: Callable):
        self._callback  = packet_callback
        self._writer    = None
        self._connected = False

    async def run(self) -> None:
        if not SERIAL_AVAILABLE:
            log.error("serial_asyncio lipsa, nu pot porni hardware mode")
            return
        while True:
            try:
                reader, writer = await serial_asyncio.open_serial_connection(
                    url=SERIAL_PORT, baudrate=SERIAL_BAUDRATE, limit=2**20
                )
                self._writer    = writer
                self._connected = True
                log.info("port serial %s deschis", SERIAL_PORT)
                await asyncio.sleep(2)  # asteapta sa treaca mesajele de boot ESP32
                await self._read_loop(reader)
            except Exception as exc:
                self._connected = False
                # inchide writer-ul explicit la reconectare ca sa eliberam resursa seriala
                if self._writer is not None:
                    try:
                        self._writer.close()
                    except Exception:
                        pass
                    self._writer = None
                log.warning("eroare serial: %s - reincerc in 5s", exc)
                await asyncio.sleep(5)

    async def _read_loop(self, reader) -> None:
        while True:
            line = await reader.readline()
            text = line.decode("utf-8", errors="replace").strip()
            if not text:
                continue
            try:
                raw = json.loads(text)
                if raw.get("type") == "sensor_data":
                    pkt = _parse_packet(raw)
                    if pkt:
                        await self._callback(pkt)
            except json.JSONDecodeError:
                log.debug("linie non-json pe serial: %s", text)
            except Exception as exc:
                # eroare in callback nu trebuie sa inchida conexiunea seriala
                # fara asta, orice exceptie in _on_packet ar cauza 5s de date pierdute
                log.error("eroare procesare pachet serial: %s", exc, exc_info=True)

    async def send_command(self, command: dict) -> bool:
        if not self._connected or self._writer is None:
            return False
        try:
            self._writer.write((json.dumps(command) + "\n").encode())
            await self._writer.drain()
            return True
        except Exception as exc:
            log.error("eroare trimitere comanda: %s", exc)
            return False

    @property
    def connected(self) -> bool:
        return self._connected
