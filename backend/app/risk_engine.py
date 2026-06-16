from __future__ import annotations
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


# Scorul de risc e calculat pe nod (computeRiskScore in firmware) si trimis gata
# in pachet. Backend-ul nu il recalculeaza — clasifica direct statusul dupa praguri,
# pentru un comportament predictibil si usor de explicat.
def classify_status_direct(
    gas_value: int,
    temperature: float,
    thresholds: GasThresholds,
) -> tuple[NodeStatus, MessageType, Priority]:
    gas_critical  = gas_value >= thresholds.critical_min
    temp_critical = temperature >= thresholds.temp_critical
    gas_warning   = gas_value > thresholds.normal_max
    temp_warning  = temperature >= thresholds.temp_warning

    if gas_critical or temp_critical:
        return NodeStatus.ALERT, MessageType.ALERT, Priority.HIGH
    if gas_warning or temp_warning:
        return NodeStatus.WARNING, MessageType.WARNING, Priority.NORMAL
    return NodeStatus.NORMAL, MessageType.NORMAL, Priority.NORMAL
