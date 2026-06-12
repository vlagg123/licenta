from __future__ import annotations
import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Optional
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import SIMULATION_MODE, NODES_CONFIG, HOST, PORT, GAS_LEVEL_DEFAULTS
from app.models import (
    NodeState, NodeStatus, MessageType, Priority, SensorPacket, Event,
    NodeCommand, CommandResponse, CommandType, SystemStatus,
    GasThresholds, GasLevel, GAS_LEVEL_COLORS,
)
from app.database import (
    init_db, insert_event, insert_sensor_snapshot,
    get_events, get_events_today_count, log_command,
    get_setting, set_setting,
)
from app.risk_engine import classify_gas_level, gas_level_color, classify_status_direct
from app.websocket_manager import manager, _serial as _ws_serial
from app import simulator as sim
from app.routing import get_all_routes

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("main")

app = FastAPI(title="Fire Detection WSN", version="1.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

node_states: dict[int, NodeState] = {}
_gas_thresholds: GasThresholds    = GasThresholds()
_start_time = time.time()
_serial_gw  = None


@app.on_event("startup")
async def startup() -> None:
    init_db()
    _load_gas_thresholds()
    _init_node_states()

    if SIMULATION_MODE:
        log.info("mod simulare pornit")
        sim.set_gas_thresholds(_gas_thresholds)
        asyncio.create_task(sim.simulation_loop(node_states, _on_packet))
    else:
        log.info("mod hardware pornit pe portul serial")
        from app.serial_gateway import SerialGateway
        global _serial_gw
        _serial_gw = SerialGateway(packet_callback=_on_packet)
        asyncio.create_task(_serial_gw.run())

    asyncio.create_task(_offline_watchdog())


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
        initial_status = NodeStatus.OFFLINE if not SIMULATION_MODE else NodeStatus.NORMAL
        node_states[nid] = NodeState(node_id=nid, zone=cfg["zone"], x=cfg["x"], y=cfg["y"],
                                     status=initial_status)


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
                # nodurile in mentenanta nu sunt marcate offline
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

    prev_status   = ns.status
    prev_gas_level = ns.gas_level
    glevel = classify_gas_level(pkt.gas_value, _gas_thresholds)
    gcolor = gas_level_color(glevel)

    # daca backend-ul a marcat nodul in mentenanta (comanda SET_MAINTENANCE_MODE),
    # pastreaza MAINTENANCE indiferent de ce trimite hardware-ul pana la RESET_ALERT explicit
    # necesar in hardware mode unde firmware-ul nu trimite niciodata status=MAINTENANCE
    if prev_status == NodeStatus.MAINTENANCE:
        final_status = NodeStatus.MAINTENANCE
        final_msg    = MessageType.NORMAL
        final_prio   = Priority.NORMAL
    elif pkt.status not in (NodeStatus.MAINTENANCE, NodeStatus.OFFLINE):
        final_status, final_msg, final_prio = classify_status_direct(pkt.gas_value, pkt.temperature, _gas_thresholds)
    else:
        final_status = pkt.status
        final_msg    = pkt.message_type
        final_prio   = pkt.priority

    # actualizare stare in memorie - intotdeauna, indiferent de DB
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
    ns.last_seen       = pkt.timestamp
    ns.packet_count   += 1

    # scriere DB separata de broadcast - o eroare DB nu blocheaza UI-ul
    try:
        if (glevel == GasLevel.CRITICAL and prev_gas_level != GasLevel.CRITICAL
                and pkt.status != NodeStatus.MAINTENANCE):
            _record_event(pkt.node_id, "GAS_CRITICAL",
                          f"Nod {pkt.node_id} ({ns.zone}): gaz critic - {pkt.gas_value} ADC",
                          pkt.risk_score)
        if ns.packet_count % 10 == 0:
            insert_sensor_snapshot(pkt.node_id, pkt.temperature, pkt.humidity,
                                   pkt.pressure, pkt.gas_value, pkt.risk_score,
                                   final_status, pkt.timestamp)
        if final_status != prev_status:
            ps = prev_status.value  if hasattr(prev_status,  'value') else prev_status
            fs = final_status.value if hasattr(final_status, 'value') else final_status
            _record_event(pkt.node_id, final_status,
                          f"Nod {pkt.node_id} ({ns.zone}): {ps} -> {fs} | risc={pkt.risk_score} | t={pkt.temperature}C gaz={pkt.gas_value}",
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
        "timestamp":       pkt.timestamp,
        "buzzer_on_high":  _gas_thresholds.enable_buzzer_on_gas_high,
    })


def _record_event(node_id: int, event_type: str, description: str, risk_score: int) -> None:
    ns   = node_states.get(node_id)
    # node_id=0 e gateway-ul, nu e in node_states
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


@app.get("/api/nodes", tags=["Nodes"])
def get_nodes():
    return [ns.dict() for ns in node_states.values()]


@app.get("/api/nodes/{node_id}", tags=["Nodes"])
def get_node(node_id: int):
    ns = node_states.get(node_id)
    if not ns:
        raise HTTPException(404, f"nodul {node_id} nu exista")
    return ns.dict()


@app.get("/api/nodes/{node_id}/routes", tags=["Routing"])
def get_node_routes(node_id: int, alert_mode: bool = False):
    if node_id not in node_states:
        raise HTTPException(404)
    return get_all_routes(node_id, node_states, alert_mode)


@app.get("/api/events", tags=["Events"])
def get_events_endpoint(limit: int = Query(100, ge=1, le=1000), node_id: Optional[int] = Query(None)):
    return get_events(limit=limit, node_id=node_id)


@app.post("/api/commands", response_model=CommandResponse, tags=["Commands"])
async def send_command(cmd: NodeCommand):
    ns_check = node_states.get(cmd.target_node)
    if ns_check and ns_check.status == NodeStatus.OFFLINE:
        raise HTTPException(400, f"Nodul {cmd.target_node} este offline - comanda ignorata")

    log_command(cmd.command_id, cmd.target_node, cmd.command_type, cmd.payload, cmd.timestamp)
    _record_event(cmd.target_node, "COMMAND", f"Comanda {cmd.command_type} -> nod {cmd.target_node}", 0)

    if SIMULATION_MODE:
        if cmd.command_type == CommandType.RESET_ALERT:
            sim.reset_node(cmd.target_node)
        elif cmd.command_type == CommandType.FORCE_SIMULATED_ALERT:
            sim.trigger_alert(cmd.target_node)
        elif cmd.command_type == CommandType.SET_MAINTENANCE_MODE:
            # mentenanta nu e acelasi lucru cu offline - nodul ramane activ dar fara alarme
            sim.set_maintenance(cmd.target_node)
    else:
        if _serial_gw:
            sent = await _serial_gw.send_command({
                "type": "command", "command_id": cmd.command_id,
                "target_node": cmd.target_node, "command_type": cmd.command_type,
                "payload": cmd.payload, "timestamp": cmd.timestamp.isoformat(),
            })
            if not sent:
                raise HTTPException(503, "gateway serial deconectat - comanda nu a fost trimisa la nod")
            # reflecta imediat in starea backend comenzile care schimba statusul nodului,
            # fara sa asteptam urmatorul pachet serial (care poate veni cu delay)
            ns_hw = node_states.get(cmd.target_node)
            if ns_hw:
                if cmd.command_type == CommandType.SET_MAINTENANCE_MODE:
                    ns_hw.status       = NodeStatus.MAINTENANCE
                    ns_hw.message_type = MessageType.NORMAL
                    ns_hw.priority     = Priority.NORMAL
                elif cmd.command_type == CommandType.RESET_ALERT:
                    # iese din mentenanta si din orice alerta, urmatorul pachet confirma starea reala
                    ns_hw.status       = NodeStatus.NORMAL
                    ns_hw.message_type = MessageType.NORMAL
                    ns_hw.priority     = Priority.NORMAL

    await manager.broadcast({"type": "command_sent", "command_id": cmd.command_id,
                              "target_node": cmd.target_node, "command_type": cmd.command_type})
    return CommandResponse(success=True, message="Comanda trimisa", command_id=cmd.command_id)


@app.post("/api/simulation/alert/{node_id}", tags=["Simulation"])
async def sim_alert(node_id: int):
    if node_id not in node_states:
        raise HTTPException(404)
    sim.trigger_alert(node_id)
    _record_event(node_id, "SIM_ALERT", f"[SIM] Alerta fortata pe nod {node_id}", 85)
    return {"ok": True, "node_id": node_id, "action": "ALERT"}


@app.post("/api/simulation/offline/{node_id}", tags=["Simulation"])
async def sim_offline(node_id: int):
    if node_id not in node_states:
        raise HTTPException(404)
    sim.trigger_offline(node_id)
    ns = node_states[node_id]
    ns.status = NodeStatus.OFFLINE
    _record_event(node_id, "OFFLINE", f"[SIM] Nod {node_id} fortat offline", 0)
    await manager.broadcast({"type": "node_offline", "node_id": node_id})
    return {"ok": True, "node_id": node_id, "action": "OFFLINE"}


@app.post("/api/simulation/reset", tags=["Simulation"])
async def sim_reset():
    sim.reset_all()
    for ns in node_states.values():
        ns.message_type    = MessageType.NORMAL
        ns.priority        = Priority.NORMAL
        ns.risk_score      = 0
        ns.gas_level       = GasLevel.NORMAL
        ns.gas_level_color = "#22c55e"
        if not SIMULATION_MODE:
            ns.status      = NodeStatus.OFFLINE
            ns.last_seen   = None
        else:
            ns.status      = NodeStatus.NORMAL
    _record_event(0, "SIM_RESET", "[SIM] Sistem resetat la normal", 0)
    # trimite starea completa imediat ca UI-ul sa se actualizeze fara sa astepte pachetul urmator
    await manager.broadcast({
        "type":  "initial_state",
        "nodes": [ns.dict() for ns in node_states.values()],
        "mode":  "SIMULATION" if SIMULATION_MODE else "HARDWARE",
    })
    return {"ok": True}


@app.post("/api/simulation/reset/{node_id}", tags=["Simulation"])
async def sim_reset_node(node_id: int):
    if node_id not in node_states:
        raise HTTPException(404)
    sim.reset_node(node_id)
    ns = node_states[node_id]
    ns.message_type    = MessageType.NORMAL
    ns.priority        = Priority.NORMAL
    ns.risk_score      = 0
    ns.gas_level       = GasLevel.NORMAL
    ns.gas_level_color = "#22c55e"
    if not SIMULATION_MODE:
        ns.status      = NodeStatus.OFFLINE
        ns.last_seen   = None
    else:
        ns.status      = NodeStatus.NORMAL
    # broadcast imediat sa nu ramana date vechi in UI pana la pachetul urmator
    await manager.broadcast({
        "type":            "sensor_update",
        "node_id":         node_id,
        "zone":            ns.zone,
        "temperature":     ns.temperature,
        "humidity":        ns.humidity,
        "pressure":        ns.pressure,
        "gas_value":       ns.gas_value,
        "gas_level":       ns.gas_level,
        "gas_level_color": ns.gas_level_color,
        "risk_score":      ns.risk_score,
        "status":          ns.status,
        "message_type":    ns.message_type,
        "priority":        ns.priority,
        "route":           ns.route,
        "hop_count":       ns.hop_count,
        "rssi":            ns.rssi,
        "battery":         ns.battery,
        "latency_ms":      ns.latency_ms,
        "timestamp":       ns.last_seen or datetime.utcnow(),
        "buzzer_on_high":  _gas_thresholds.enable_buzzer_on_gas_high,
    })
    return {"ok": True, "node_id": node_id}


@app.post("/api/simulation/route-failure", tags=["Simulation"])
async def sim_route_failure(node_id: int = Query(...)):
    if node_id not in node_states:
        raise HTTPException(404)
    sim.set_route_failure(node_id)
    _record_event(node_id, "ROUTE_FAILURE", f"[SIM] Ruta primara cazuta la nod {node_id}", 20)
    return {"ok": True, "node_id": node_id}


@app.post("/api/simulation/packet-loss", tags=["Simulation"])
def sim_packet_loss(pct: float = Query(0.3, ge=0.0, le=1.0)):
    sim.set_packet_loss(pct)
    return {"ok": True, "packet_loss_pct": pct}


@app.post("/api/simulation/restore", tags=["Simulation"])
def sim_restore():
    sim.restore_connection()
    return {"ok": True}


@app.get("/api/settings/gas-thresholds", response_model=GasThresholds, tags=["Settings"])
@app.get("/api/settings/alarm-thresholds", response_model=GasThresholds, tags=["Settings"])
def get_gas_thresholds():
    return _gas_thresholds


@app.post("/api/settings/gas-thresholds", response_model=GasThresholds, tags=["Settings"])
@app.post("/api/settings/alarm-thresholds", response_model=GasThresholds, tags=["Settings"])
async def update_gas_thresholds(thresholds: GasThresholds):
    # validare completa - toate pragurile trebuie in ordine crescatoare
    if not (thresholds.normal_max < thresholds.low_max < thresholds.medium_max
            < thresholds.high_max < thresholds.critical_min):
        raise HTTPException(400, "pragurile trebuie sa fie in ordine: normal < low < medium < high < critical")

    global _gas_thresholds
    _gas_thresholds = thresholds
    set_setting("gas_thresholds", json.dumps(thresholds.dict()))

    # actualizeaza si simulatorul ca sa foloseasca noile praguri la calcul risc
    if SIMULATION_MODE:
        sim.set_gas_thresholds(_gas_thresholds)

    await manager.broadcast({"type": "thresholds_updated", "thresholds": thresholds.dict()})
    return _gas_thresholds


@app.get("/api/system/status", response_model=SystemStatus, tags=["System"])
def system_status():
    statuses = [ns.status for ns in node_states.values()]
    return SystemStatus(
        mode          = "SIMULATION" if SIMULATION_MODE else "HARDWARE",
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
            "mode":  "SIMULATION" if SIMULATION_MODE else "HARDWARE",
        }
        await ws.send_text(json.dumps(initial, default=_ws_serial))
        while True:
            await ws.receive_text()
    except Exception:
        # prinde si WebSocketDisconnect si orice alta exceptie de retea
        # fara asta, socket-ul mort ramane in active si toate broadcast-urile
        # incearca sa trimita la el pana la primul esec
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
