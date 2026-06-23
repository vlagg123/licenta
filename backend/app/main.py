from __future__ import annotations
import asyncio
import json
import logging
import time
import os
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, WebSocket, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import NODES_CONFIG, HOST, PORT
from app.models import (
    NodeState, NodeStatus, MessageType, Priority, SensorPacket, Event,
    NodeCommand, CommandResponse, CommandType, SystemStatus,
    GasThresholds, GasLevel,
)
from app.database import (
    init_db, insert_event, insert_sensor_snapshot,
    get_events, get_events_today_count, log_command,
    get_setting, set_setting,
)
from app.risk_engine import classify_gas_level, gas_level_color, classify_status_direct
from app.websocket_manager import manager, _serial as _ws_serial
from app.serial_gateway import SerialGateway

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("main")

app = FastAPI(title="Fire Detection WSN", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

node_states: dict[int, NodeState] = {}
_gas_thresholds: GasThresholds    = GasThresholds()
_start_time = time.time()
_serial_gw: SerialGateway | None  = None


@app.on_event("startup")
async def startup() -> None:
    init_db()
    _load_gas_thresholds()
    _init_node_states()

    global _serial_gw
    _serial_gw = SerialGateway(packet_callback=_on_packet)
    asyncio.create_task(_serial_gw.run())
    asyncio.create_task(_offline_watchdog())
    log.info("server pornit in mod hardware")


def _load_gas_thresholds() -> None:
    global _gas_thresholds
    raw = get_setting("gas_thresholds")
    if raw:
        try:
            _gas_thresholds = GasThresholds(**json.loads(raw))
        except Exception as e:
            log.warning("nu am putut incarca pragurile din db: %s", e)


def _init_node_states() -> None:
    for nid, cfg in NODES_CONFIG.items():
        if nid == 0:
            continue
        node_states[nid] = NodeState(
            node_id=nid, zone=cfg["zone"], x=cfg["x"], y=cfg["y"],
            status=NodeStatus.OFFLINE,
        )


async def _offline_watchdog() -> None:
    from app.config import THRESHOLDS
    timeout = THRESHOLDS["offline_timeout_s"]
    while True:
        await asyncio.sleep(5)
        try:
            now = datetime.utcnow()
            for nid, ns in list(node_states.items()):
                if ns.last_seen is None:
                    continue
                if ns.status == NodeStatus.MAINTENANCE:
                    continue
                delta = (now - ns.last_seen).total_seconds()
                if delta > timeout and ns.status != NodeStatus.OFFLINE:
                    ns.status = NodeStatus.OFFLINE
                    _record_event(nid, "OFFLINE", f"Nod {nid} ({ns.zone}) offline - {delta:.0f}s fara date", 0)
                    await manager.broadcast({"type": "node_offline", "node_id": nid})
        except Exception as exc:
            log.error("eroare watchdog offline: %s", exc, exc_info=True)


async def _on_packet(pkt: SensorPacket) -> None:
    ns = node_states.get(pkt.node_id)
    if not ns:
        return

    prev_status    = ns.status
    prev_gas_level = ns.gas_level
    prev_temp_ok   = ns.temp_sensor_ok
    glevel = classify_gas_level(pkt.gas_value, _gas_thresholds)
    gcolor = gas_level_color(glevel)

    # daca nodul e in mentenanta, pastreaza statusul pana la RESET_ALERT explicit
    # firmware-ul nu trimite niciodata status=MAINTENANCE, asa ca backend-ul il tine manual
    if prev_status == NodeStatus.MAINTENANCE:
        final_status = NodeStatus.MAINTENANCE
        final_msg    = MessageType.NORMAL
        final_prio   = Priority.NORMAL
    else:
        final_status, final_msg, final_prio = classify_status_direct(
            pkt.gas_value, pkt.temperature, _gas_thresholds
        )

    ns.temperature     = pkt.temperature
    ns.humidity        = pkt.humidity
    ns.pressure        = pkt.pressure
    ns.gas_value       = pkt.gas_value
    ns.gas_level       = glevel
    ns.gas_level_color = gcolor
    ns.risk_score      = pkt.risk_score
    ns.status          = final_status
    ns.message_type    = final_msg
    ns.priority        = final_prio
    ns.route           = pkt.route
    ns.hop_count       = pkt.hop_count
    ns.rssi            = pkt.rssi
    ns.battery         = pkt.battery
    ns.latency_ms      = pkt.latency_ms
    ns.temp_sensor_ok  = pkt.temp_sensor_ok
    ns.last_seen       = pkt.timestamp
    ns.packet_count   += 1

    # un nod care tocmai a revenit online (sau a pornit) foloseste pragurile compilate;
    # ii retrimitem pragurile din dashboard ca buzzerul sa reactioneze la valorile curente
    if prev_status == NodeStatus.OFFLINE:
        asyncio.create_task(_push_thresholds_to_node(pkt.node_id))

    # scrierile in DB sunt separate de broadcast — o eroare DB nu blocheaza UI-ul
    try:
        if glevel == GasLevel.CRITICAL and prev_gas_level != GasLevel.CRITICAL:
            _record_event(pkt.node_id, "GAS_CRITICAL",
                          f"Nod {pkt.node_id} ({ns.zone}): gaz critic - {pkt.gas_value} ADC",
                          pkt.risk_score)
        if prev_temp_ok and not pkt.temp_sensor_ok:
            _record_event(pkt.node_id, "SENSOR_FAULT",
                          f"Nod {pkt.node_id} ({ns.zone}): senzor temperatura defect - monitorizez doar gazul",
                          pkt.risk_score)
        if ns.packet_count % 10 == 0:
            insert_sensor_snapshot(pkt.node_id, pkt.temperature, pkt.humidity,
                                   pkt.pressure, pkt.gas_value, pkt.risk_score,
                                   final_status, pkt.timestamp)
        if final_status != prev_status:
            ps = prev_status.value  if hasattr(prev_status,  "value") else prev_status
            fs = final_status.value if hasattr(final_status, "value") else final_status
            _record_event(pkt.node_id, final_status,
                          f"Nod {pkt.node_id} ({ns.zone}): {ps} -> {fs} | t={pkt.temperature}C gaz={pkt.gas_value}",
                          pkt.risk_score)
    except Exception as exc:
        log.error("eroare DB on_packet nod %s: %s", pkt.node_id, exc)

    await manager.broadcast({
        "type":            "sensor_update",
        "node_id":         pkt.node_id,
        "zone":            pkt.zone,
        "temperature":     pkt.temperature,
        "humidity":        pkt.humidity,
        "pressure":        pkt.pressure,
        "gas_value":       pkt.gas_value,
        "gas_level":       glevel.value,
        "gas_level_color": gcolor,
        "risk_score":      pkt.risk_score,
        "status":          final_status,
        "message_type":    final_msg,
        "priority":        final_prio,
        "route":           pkt.route,
        "hop_count":       pkt.hop_count,
        "rssi":            pkt.rssi,
        "battery":         pkt.battery,
        "latency_ms":      pkt.latency_ms,
        "temp_sensor_ok":  pkt.temp_sensor_ok,
        "timestamp":       pkt.timestamp,
        "buzzer_on_high":  _gas_thresholds.enable_buzzer_on_gas_high,
    })


def _record_event(node_id: int, event_type: str, description: str, risk_score: int) -> None:
    ns   = node_states.get(node_id)
    zone = ns.zone if ns else ("Gateway" if node_id == 0 else "Unknown")
    ev   = Event(node_id=node_id, zone=zone, event_type=event_type,
                 description=description, risk_score=risk_score, timestamp=datetime.utcnow())
    ev.id = insert_event(ev)
    payload = {"type": "event", "node_id": node_id, "zone": zone,
               "event_type": event_type, "description": description,
               "risk_score": risk_score, "timestamp": ev.timestamp}
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(manager.broadcast(payload))
    except RuntimeError:
        pass


async def _push_thresholds_to_node(node_id: int) -> None:
    # trimite pragurile curente catre nod prin SET_THRESHOLDS, ca buzzerul/LED-ul sa
    # urmeze valorile din dashboard: param1 = gaz normal max, param2 = gaz critic min,
    # param3 = temp warning, param4 = temp critic
    if not _serial_gw:
        return
    await _serial_gw.send_command({
        "type":         "command",
        "command_id":   f"thr-{node_id}-{int(time.time())}",
        "target_node":  node_id,
        "command_type": CommandType.SET_THRESHOLDS.value,
        "payload":      {"param1": float(_gas_thresholds.normal_max),
                         "param2": float(_gas_thresholds.critical_min),
                         "param3": float(_gas_thresholds.temp_warning),
                         "param4": float(_gas_thresholds.temp_critical)},
        "timestamp":    datetime.utcnow().isoformat(),
    })


@app.get("/api/nodes", tags=["Nodes"])
def get_nodes():
    return [ns.dict() for ns in node_states.values()]


@app.get("/api/nodes/{node_id}", tags=["Nodes"])
def get_node(node_id: int):
    ns = node_states.get(node_id)
    if not ns:
        raise HTTPException(404, f"nodul {node_id} nu exista")
    return ns.dict()


@app.get("/api/events", tags=["Events"])
def get_events_endpoint(limit: int = Query(100, ge=1, le=1000), node_id: Optional[int] = Query(None)):
    return get_events(limit=limit, node_id=node_id)


@app.post("/api/commands", response_model=CommandResponse, tags=["Commands"])
async def send_command(cmd: NodeCommand):
    ns = node_states.get(cmd.target_node)
    if ns and ns.status == NodeStatus.OFFLINE:
        raise HTTPException(400, f"Nodul {cmd.target_node} este offline - comanda ignorata")

    log_command(cmd.command_id, cmd.target_node, cmd.command_type, cmd.payload, cmd.timestamp)
    _record_event(cmd.target_node, "COMMAND", f"Comanda {cmd.command_type} -> nod {cmd.target_node}", 0)

    if not _serial_gw:
        raise HTTPException(503, "gateway serial neinitializat")

    # butonul Mentenanta inseamna "intra in mentenanta" -> nodul citeste param1=1;
    # iesirea se face cu Reset (RESET_ALERT). fara param1, nodul primea 0 si nu activa modul.
    payload = dict(cmd.payload)
    if cmd.command_type == CommandType.SET_MAINTENANCE_MODE:
        payload["param1"] = 1.0

    sent = await _serial_gw.send_command({
        "type":         "command",
        "command_id":   cmd.command_id,
        "target_node":  cmd.target_node,
        "command_type": cmd.command_type,
        "payload":      payload,
        "timestamp":    cmd.timestamp.isoformat(),
    })
    if not sent:
        raise HTTPException(503, "gateway serial deconectat - comanda nu a fost trimisa la nod")

    # reflecta imediat comenzile de stare in backend,
    # fara sa asteptam urmatorul pachet serial
    if ns:
        if cmd.command_type == CommandType.SET_MAINTENANCE_MODE:
            ns.status       = NodeStatus.MAINTENANCE
            ns.message_type = MessageType.NORMAL
            ns.priority     = Priority.NORMAL
        elif cmd.command_type == CommandType.RESET_ALERT:
            ns.status       = NodeStatus.NORMAL
            ns.message_type = MessageType.NORMAL
            ns.priority     = Priority.NORMAL

    await manager.broadcast({
        "type":         "command_sent",
        "command_id":   cmd.command_id,
        "target_node":  cmd.target_node,
        "command_type": cmd.command_type,
    })
    return CommandResponse(success=True, message="Comanda trimisa", command_id=cmd.command_id)


@app.get("/api/settings/gas-thresholds", response_model=GasThresholds, tags=["Settings"])
@app.get("/api/settings/alarm-thresholds", response_model=GasThresholds, tags=["Settings"])
def get_gas_thresholds():
    return _gas_thresholds


@app.post("/api/settings/gas-thresholds", response_model=GasThresholds, tags=["Settings"])
@app.post("/api/settings/alarm-thresholds", response_model=GasThresholds, tags=["Settings"])
async def update_gas_thresholds(thresholds: GasThresholds):
    if not (thresholds.normal_max < thresholds.low_max < thresholds.medium_max
            < thresholds.high_max < thresholds.critical_min):
        raise HTTPException(400, "pragurile trebuie sa fie in ordine: normal < low < medium < high < critical")

    global _gas_thresholds
    _gas_thresholds = thresholds
    set_setting("gas_thresholds", json.dumps(thresholds.dict()))
    await manager.broadcast({"type": "thresholds_updated", "thresholds": thresholds.dict()})

    # propaga noile praguri la noduri ca buzzerul lor sa foloseasca valorile setate aici
    for nid in node_states:
        await _push_thresholds_to_node(nid)

    return _gas_thresholds


@app.get("/api/system/status", response_model=SystemStatus, tags=["System"])
def system_status():
    statuses = [ns.status for ns in node_states.values()]
    return SystemStatus(
        mode          = "HARDWARE",
        total_nodes   = len(node_states),
        online_nodes  = sum(1 for s in statuses if s != NodeStatus.OFFLINE),
        alert_nodes   = sum(1 for s in statuses if s == NodeStatus.ALERT),
        warning_nodes = sum(1 for s in statuses if s == NodeStatus.WARNING),
        uptime_s      = round(time.time() - _start_time, 1),
        events_today  = get_events_today_count(),
    )


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        initial = {
            "type":  "initial_state",
            "nodes": [ns.dict() for ns in node_states.values()],
            "mode":  "HARDWARE",
        }
        await ws.send_text(json.dumps(initial, default=_ws_serial))
        while True:
            await ws.receive_text()
    except Exception:
        # prinde WebSocketDisconnect si orice alta exceptie de retea
        manager.disconnect(ws)


frontend_path = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
if os.path.isdir(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

    @app.get("/", include_in_schema=False)
    def serve_index():
        return FileResponse(os.path.join(frontend_path, "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False)
