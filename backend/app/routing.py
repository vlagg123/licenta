from __future__ import annotations
import heapq
from app.config import NEIGHBOUR_TABLE, ROUTING_WEIGHTS_NORMAL, ROUTING_WEIGHTS_ALERT

# rssi ideal e -40 dBm, range de normalizare 60 dBm
RSSI_IDEAL = -40
RSSI_RANGE = 60


def _link_cost(rssi: int, battery: int, congestion: float, alert_mode: bool) -> float:
    w = ROUTING_WEIGHTS_ALERT if alert_mode else ROUTING_WEIGHTS_NORMAL

    rssi_pen = max(0.0, min(1.0, (RSSI_IDEAL - rssi) / RSSI_RANGE))
    batt_pen = (100 - battery) / 100.0
    cong_pen = max(0.0, min(1.0, congestion))

    return (
        w["alpha"] * 1.0
        + w["beta"]  * rssi_pen
        + w["gamma"] * batt_pen
        + w["delta"] * cong_pen
    )


def compute_route(
    source_id: int,
    destination_id: int,
    node_states: dict,
    alert_mode: bool = False,
) -> tuple[list[int], float]:
    INF  = float("inf")
    dist = {nid: INF for nid in NEIGHBOUR_TABLE}
    prev = {nid: None for nid in NEIGHBOUR_TABLE}
    dist[source_id] = 0.0
    pq = [(0.0, source_id)]

    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        for (v, base_rssi) in NEIGHBOUR_TABLE.get(u, []):
            ns = node_states.get(v)
            # nodul offline nu intra in calcul
            if ns and getattr(ns, "status", "NORMAL") == "OFFLINE":
                continue
            battery   = getattr(ns, "battery", 80) if ns else 80
            live_rssi = getattr(ns, "rssi", base_rssi) if ns else base_rssi
            cost = _link_cost(live_rssi, battery, 0.0, alert_mode)
            if dist[u] + cost < dist[v]:
                dist[v] = dist[u] + cost
                prev[v] = u
                heapq.heappush(pq, (dist[v], v))

    path = []
    cur  = destination_id
    while cur is not None:
        path.append(cur)
        cur = prev.get(cur)  # .get() previne KeyError daca topologia se schimba
    path.reverse()

    if not path or path[0] != source_id:
        return [source_id, destination_id], INF

    return path, dist[destination_id]


def get_all_routes(source_id: int, node_states: dict, alert_mode: bool = False) -> dict:
    routes = {}
    for dest in NEIGHBOUR_TABLE:
        if dest == source_id:
            continue
        path, cost = compute_route(source_id, dest, node_states, alert_mode)
        routes[dest] = {"path": path, "cost": round(cost, 3)}
    return routes


def route_to_gateway(source_id: int, node_states: dict, alert_mode: bool = False) -> list[int]:
    path, _ = compute_route(source_id, 0, node_states, alert_mode)
    return path


def estimate_latency(route: list[int]) -> int:
    hops = max(0, len(route) - 1)
    return 5 + hops * 8
