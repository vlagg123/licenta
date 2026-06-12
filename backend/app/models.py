from __future__ import annotations
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class NodeStatus(str, Enum):
    NORMAL      = "NORMAL"
    WARNING     = "WARNING"
    ALERT       = "ALERT"
    OFFLINE     = "OFFLINE"
    MAINTENANCE = "MAINTENANCE"

class MessageType(str, Enum):
    NORMAL  = "NORMAL"
    WARNING = "WARNING"
    ALERT   = "ALERT"

class Priority(str, Enum):
    LOW    = "LOW"
    NORMAL = "NORMAL"
    HIGH   = "HIGH"

class GasLevel(str, Enum):
    NORMAL   = "GAS_NORMAL"
    LOW      = "GAS_LOW"
    MEDIUM   = "GAS_MEDIUM"
    HIGH     = "GAS_HIGH"
    CRITICAL = "GAS_CRITICAL"

GAS_LEVEL_COLORS: dict = {
    "GAS_NORMAL":   "#22c55e",
    "GAS_LOW":      "#86efac",
    "GAS_MEDIUM":   "#f59e0b",
    "GAS_HIGH":     "#f97316",
    "GAS_CRITICAL": "#ef4444",
}

GAS_LEVEL_LABELS: dict = {
    "GAS_NORMAL":   "Normal",
    "GAS_LOW":      "Scazut",
    "GAS_MEDIUM":   "Mediu",
    "GAS_HIGH":     "Ridicat",
    "GAS_CRITICAL": "Critic",
}


class GasThresholds(BaseModel):
    normal_max:                int   = 300
    low_max:                   int   = 450
    medium_max:                int   = 600
    high_max:                  int   = 750
    critical_min:              int   = 751
    enable_buzzer_on_gas_high: bool  = False
    temp_warning:              float = 45.0
    temp_critical:             float = 65.0


class CommandType(str, Enum):
    MUTE_BUZZER           = "MUTE_BUZZER"
    RESET_ALERT           = "RESET_ALERT"
    TEST_ALARM            = "TEST_ALARM"
    CALIBRATE_SENSOR      = "CALIBRATE_SENSOR"
    SET_THRESHOLDS        = "SET_THRESHOLDS"
    SET_MAINTENANCE_MODE  = "SET_MAINTENANCE_MODE"
    REQUEST_STATUS        = "REQUEST_STATUS"
    FORCE_SIMULATED_ALERT = "FORCE_SIMULATED_ALERT"


class SensorPacket(BaseModel):
    packet_id:    str
    node_id:      int
    zone:         str
    temperature:  float
    humidity:     float
    pressure:     float
    gas_value:    int
    risk_score:   int
    status:       NodeStatus
    message_type: MessageType
    priority:     Priority
    route:        List[int]
    hop_count:    int
    rssi:         int
    battery:      int
    latency_ms:   int
    timestamp:    datetime

    class Config:
        use_enum_values = True


class NodeState(BaseModel):
    node_id:         int
    zone:            str
    x:               int
    y:               int
    temperature:     float      = 25.0
    humidity:        float      = 50.0
    pressure:        float      = 1013.0
    gas_value:       int        = 0
    gas_level:       GasLevel   = GasLevel.NORMAL
    gas_level_color: str        = "#22c55e"
    risk_score:      int        = 0
    status:          NodeStatus = NodeStatus.NORMAL
    message_type:    MessageType = MessageType.NORMAL
    priority:        Priority    = Priority.NORMAL
    route:           List[int]   = Field(default_factory=list)
    hop_count:       int  = 1
    rssi:            int  = -60
    battery:         int  = 100
    latency_ms:      int  = 10
    last_seen:       Optional[datetime] = None
    packet_count:    int  = 0

    class Config:
        use_enum_values = True


class Event(BaseModel):
    id:           Optional[int] = None
    node_id:      int
    zone:         str
    event_type:   str
    description:  str
    risk_score:   int
    timestamp:    datetime
    acknowledged: bool = False


class NodeCommand(BaseModel):
    command_id:   str
    target_node:  int
    command_type: CommandType
    payload:      dict = Field(default_factory=dict)
    timestamp:    datetime = Field(default_factory=datetime.utcnow)

    class Config:
        use_enum_values = True


class CommandResponse(BaseModel):
    success:    bool
    message:    str
    command_id: str


class SystemStatus(BaseModel):
    mode:          str  # SIMULATION sau HARDWARE
    total_nodes:   int
    online_nodes:  int
    alert_nodes:   int
    warning_nodes: int
    uptime_s:      float
    events_today:  int
