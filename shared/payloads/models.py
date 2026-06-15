from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field


class ActuatorType(str, Enum):
    VALVE = "VALVE"
    PUMP = "PUMP"
    FERTIGATOR = "FERTIGATOR"


class ActuatorAction(str, Enum):
    OPEN = "OPEN"
    CLOSE = "CLOSE"
    SET = "SET"


class SensorReading(BaseModel):
    node_id: int
    timestamp: int
    sequence_number: int
    temperature: float
    humidity: float
    soil_moisture: float
    ec: float
    ph: float
    rainfall: Optional[float] = None
    
    leaf_wetness: Optional[float] = None
    solar_radiation: Optional[float] = None
    wind_speed: Optional[float] = None
    wind_direction: Optional[int] = None
    
    sensor_mask: int
    battery_pct: int = Field(ge=0, le=100)
    tx_reason: int
    rssi_last_rx: int
    
    metadata_json: Optional[dict] = None


class ActuationCommand(BaseModel):
    command_id: str
    target_node: int
    actuator_type: ActuatorType
    action: ActuatorAction
    value: Optional[float] = None
    duration_sec: Optional[int] = None


class ConfigPush(BaseModel):
    config_hash: int
    lora_channel: Optional[int] = None
    tx_power_dbm: Optional[int] = None
    sample_rate_sec: Optional[int] = None
