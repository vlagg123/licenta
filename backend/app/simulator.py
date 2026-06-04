from __future__ import annotations
import asyncio
import random
import uuid
from collections import deque
from datetime import datetime
from typing import Optional

from app.config import NODES_CONFIG, SIMULATION_INTERVAL, NEIGHBOUR_TABLE
from app.models import NodeState, NodeStatus, SensorPacket, MessageType, Priority, GasThresholds
from app.risk_engine import compute_risk_score, classify_risk
from app.routing import route_to_gateway, estimate_latency

_forced_alert:    set[int]   = set()
_forced_offline:  set[int]   = set()
_maintenance_nodes: set[int] = set()
_alt_route_nodes: set[int]   = set()
_packet_loss_pct: float      = 0.0

# pragurile curente de gaz, actualizate din main cand utilizatorul le schimba
_current_thresholds: GasThresholds | None = None

_temp_history: dict[int, deque] = {nid: deque(maxlen=5) for nid in NODES_CONFIG if nid != 0}
_drift:        dict[int, float] = {nid: 0.0 for nid in NODES_CONFIG if nid != 0}
_battery:      dict[int, int]   = {nid: random.randint(70, 100) for nid in NODES_CONFIG if nid != 0}


def _base_values(node_id: int) -> dict:
    bases = {
        1: {"temp": 22, "hum": 55, "pres": 1013, "gas": 80},
        2: {"temp": 28, "hum": 45, "pres": 1012, "gas": 150},
        3: {"temp": 20, "hum": 60, "pres": 1014, "gas": 90},
        4: {"temp": 32, "hum": 40, "pres": 1012, "gas": 120},
    }
    return bases.get(node_id, {"temp": 24, "hum": 50, "pres": 1013, "gas": 80})


def _init_temp_history(node_id: int) -> None:
    base = _base_values(node_id)
    _temp_history[node_id].clear()
    for _ in range(5):
        _temp_history[node_id].append(float(base["temp"]))


# initializeaza istoricul la pornire
for _nid in list(_temp_history.keys()):
    _init_temp_history(_nid)


def set_gas_thresholds(t: GasThresholds) -> None:
    global _current_thresholds
    _current_thresholds = t


def trigger_alert(node_id: int) -> None:
    _forced_alert.add(node_id)
    _forced_offline.discard(node_id)
    _maintenance_nodes.discard(node_id)


def trigger_offline(node_id: int) -> None:
    _forced_offline.add(node_id)
    _forced_alert.discard(node_id)
    _maintenance_nodes.discard(node_id)


def set_maintenance(node_id: int) -> None:
    _maintenance_nodes.add(node_id)
    _forced_alert.discard(node_id)
    _forced_offline.discard(node_id)


def reset_all() -> None:
    _forced_alert.clear()
    _forced_offline.clear()
    _maintenance_nodes.clear()
    _alt_route_nodes.clear()
    global _packet_loss_pct
    _packet_loss_pct = 0.0
    for nid in list(_drift.keys()):
        _drift[nid] = 0.0
    for nid in list(_battery.keys()):
        _battery[nid] = random.randint(70, 100)
    for nid in list(_temp_history.keys()):
        _init_temp_history(nid)


def reset_node(node_id: int) -> None:
    _forced_alert.discard(node_id)
    _forced_offline.discard(node_id)
    _maintenance_nodes.discard(node_id)
    _alt_route_nodes.discard(node_id)
    if node_id in _drift:
        _drift[node_id] = 0.0
    if node_id in _battery:
        _battery[node_id] = random.randint(70, 100)
    if node_id in _temp_history:
        _init_temp_history(node_id)


def set_route_failure(node_id: int) -> None:
    _alt_route_nodes.add(node_id)


def set_packet_loss(pct: float) -> None:
    global _packet_loss_pct
    _packet_loss_pct = max(0.0, min(1.0, pct))


def restore_connection() -> None:
    global _packet_loss_pct
    _packet_loss_pct = 0.0
    _alt_route_nodes.clear()


def _generate_reading(node_id: int, node_states: dict[int, NodeState]) -> Optional[SensorPacket]:
    if random.random() < _packet_loss_pct:
        return None
    if node_id in _forced_offline:
        return None

    cfg  = NODES_CONFIG[node_id]
    base = _base_values(node_id)

    _drift[node_id] += random.uniform(-0.3, 0.4)
    _drift[node_id]  = max(-5, min(5, _drift[node_id]))

    if node_id in _forced_alert:
        temp     = base["temp"] + 30 + random.uniform(-2, 5) + abs(_drift[node_id])
        gas      = base["gas"] + 550 + random.randint(-30, 80)
        humidity = max(10, base["hum"] - 15 + random.uniform(-3, 3))
    else:
        temp     = base["temp"] + _drift[node_id] + random.uniform(-0.5, 0.5)
        gas      = base["gas"] + random.randint(-20, 20)
        humidity = base["hum"] + random.uniform(-2, 2)

    pressure = round(base["pres"] + random.uniform(-0.5, 0.5), 1)
    temp     = round(temp, 1)
    gas      = max(0, int(gas))
    humidity = round(max(5, min(95, humidity)), 1)

    _temp_history[node_id].append(temp)

    # vecini reali din topologie, nu calculati manual
    real_neighbours = [v for (v, _) in NEIGHBOUR_TABLE.get(node_id, [])]
    neighbour_alerts = sum(
        1 for nbr_id in real_neighbours
        if node_states.get(nbr_id) and node_states[nbr_id].status in (NodeStatus.ALERT, NodeStatus.WARNING)
    )

    _battery[node_id] = max(5, _battery[node_id] - random.choice([0, 0, 0, 1]))
    battery = _battery[node_id]
    rssi    = random.randint(-75, -45)

    risk_score = compute_risk_score(
        temperature      = temp,
        gas_value        = gas,
        temp_history     = list(_temp_history[node_id]),
        neighbour_alerts = neighbour_alerts,
        battery          = battery,
        rssi             = rssi,
        gas_thresholds   = _current_thresholds,
    )

    if node_id in _forced_alert:
        risk_score = max(risk_score, 75)

    status, msg_type, priority = classify_risk(risk_score)

    # mentenanta - nodul ramane online dar nu emite alarme
    if node_id in _maintenance_nodes:
        status     = NodeStatus.MAINTENANCE
        msg_type   = MessageType.NORMAL
        priority   = Priority.NORMAL
        risk_score = min(risk_score, 5)

    route = route_to_gateway(node_id, node_states, alert_mode=(status == NodeStatus.ALERT))

    if node_id in _alt_route_nodes:
        # ruta alternativa: sare peste hop-ul primar si ia un detour prin alt vecin
        primary_next = route[1] if len(route) > 1 else None
        alt_options  = [v for (v, _) in NEIGHBOUR_TABLE.get(node_id, []) if v != 0 and v != primary_next]
        if alt_options:
            detour = random.choice(alt_options)
            route  = [node_id, detour, 0]

    latency_ms = max(5, estimate_latency(route) + random.randint(-3, 8))

    return SensorPacket(
        packet_id    = str(uuid.uuid4())[:8],
        node_id      = node_id,
        zone         = cfg["zone"],
        temperature  = temp,
        humidity     = humidity,
        pressure     = pressure,
        gas_value    = gas,
        risk_score   = risk_score,
        status       = status,
        message_type = msg_type,
        priority     = priority,
        route        = route,
        hop_count    = len(route) - 1,
        rssi         = rssi,
        battery      = battery,
        latency_ms   = latency_ms,
        timestamp    = datetime.utcnow(),
    )


async def simulation_loop(node_states: dict[int, NodeState], packet_callback) -> None:
    import logging
    _log = logging.getLogger("simulator")
    sensor_nodes = [nid for nid in NODES_CONFIG if nid != 0]
    while True:
        for node_id in sensor_nodes:
            try:
                pkt = _generate_reading(node_id, node_states)
                if pkt:
                    await packet_callback(pkt)
            except Exception as exc:
                # eroarea unui singur nod nu trebuie sa opreasca intregul loop
                _log.error("eroare pachet nod %s: %s", node_id, exc, exc_info=True)
        await asyncio.sleep(SIMULATION_INTERVAL)
