from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime

class BaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class SensorHistoryResponse(BaseResponse):
    time: datetime
    node_id: int
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    soil_moisture: Optional[float] = None
    ec: Optional[float] = None
    ph: Optional[float] = None
    rainfall: Optional[float] = None
    leaf_wetness: Optional[float] = None
    solar_radiation: Optional[float] = None
    wind_speed: Optional[float] = None
    wind_direction: Optional[int] = None
    battery_pct: int

class RecommendationResponse(BaseResponse):
    id: int
    time: datetime
    node_id: int
    action: str
    priority: str
    reason: str
    confidence: float

class RiskSummaryResponse(BaseResponse):
    id: int
    time: datetime
    node_id: int
    risk_type: str
    severity: str
    description: str

class NodeStatusResponse(BaseResponse):
    node_id: int
    last_seen: datetime
    battery_pct: int
    uptime_sec: int
    fw_version: int
    sensor_mask: int

class CommandRequest(BaseModel):
    command_id: str
    target_node: int
    actuator_type: int
    action: int
    value: Optional[float] = 0.0
    duration_sec: Optional[int] = 0

class ConfigurationRequest(BaseModel):
    config_hash: int
    lora_channel: Optional[int] = None
    tx_power_dbm: Optional[int] = None
    sample_rate_sec: Optional[int] = None
