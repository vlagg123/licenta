from __future__ import annotations
from app.config import THRESHOLDS
from app.models import NodeStatus, MessageType, Priority, GasLevel, GAS_LEVEL_COLORS, GasThresholds


def classify_gas_level(gas: int, thresholds: GasThresholds | None = None) -> GasLevel:
    t = thresholds or GasThresholds()
    # critical_min e primul check - are prioritate fata de high_max
    if gas >= t.critical_min: return GasLevel.CRITICAL
    if gas <= t.normal_max:   return GasLevel.NORMAL
    if gas <= t.low_max:      return GasLevel.LOW
    if gas <= t.medium_max:   return GasLevel.MEDIUM
    if gas <= t.high_max:     return GasLevel.HIGH
    # intre high_max si critical_min - tot HIGH
    return GasLevel.HIGH


def gas_level_color(level: GasLevel) -> str:
    return GAS_LEVEL_COLORS.get(level.value, "#22c55e")


def _temperature_score(temp: float) -> int:
    t_warn  = THRESHOLDS["temperature_warning"]
    t_alert = THRESHOLDS["temperature_alert"]
    if temp < t_warn:
        return int(min(15, max(0, (temp - 20) / (t_warn - 20) * 10)))
    elif temp < t_alert:
        return int(10 + (temp - t_warn) / (t_alert - t_warn) * 15)
    return 25


# scorul gazului depinde de nivelul clasificat, nu direct de valoare bruta
def _gas_score(gas: int, thresholds: GasThresholds | None = None) -> int:
    scores = {
        GasLevel.NORMAL:   0,
        GasLevel.LOW:      8,
        GasLevel.MEDIUM:   15,
        GasLevel.HIGH:     22,
        GasLevel.CRITICAL: 30,
    }
    return scores[classify_gas_level(gas, thresholds)]


def _trend_score(temp_history: list[float]) -> int:
    # cat de repede creste temperatura - daca urca 10 grade in 5 citiri e suspect
    if len(temp_history) < 2:
        return 0
    delta = temp_history[-1] - temp_history[0]
    if delta < 2:   return 0
    if delta < 5:   return 5
    if delta < 10:  return 12
    return 20


def _neighbour_score(neighbour_alerts: int) -> int:
    # daca si vecinii raporteaza probleme e mai credibil
    if neighbour_alerts == 0: return 0
    if neighbour_alerts == 1: return 7
    return 15


def _comm_score(battery: int, rssi: int) -> int:
    score = 0
    if battery < THRESHOLDS["battery_low"]: score += 5
    if rssi < -80:                          score += 5
    return score


def compute_risk_score(
    temperature: float,
    gas_value: int,
    temp_history: list[float],
    neighbour_alerts: int,
    battery: int,
    rssi: int,
    gas_thresholds: GasThresholds | None = None,
) -> int:
    # scor total 0-100, combinatie din mai multi parametri
    score = (
        _temperature_score(temperature)
        + _gas_score(gas_value, gas_thresholds)
        + _trend_score(temp_history)
        + _neighbour_score(neighbour_alerts)
        + _comm_score(battery, rssi)
    )
    return min(100, max(0, score))


def classify_risk(risk_score: int) -> tuple[NodeStatus, MessageType, Priority]:
    if risk_score >= 70:
        return NodeStatus.ALERT, MessageType.ALERT, Priority.HIGH
    if risk_score >= 40:
        return NodeStatus.WARNING, MessageType.WARNING, Priority.NORMAL
    return NodeStatus.NORMAL, MessageType.NORMAL, Priority.NORMAL
