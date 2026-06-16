from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from database.models import TrustTier

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

class KnowledgeSourceBase(BaseModel):
    source_name: str
    source_version: str
    trust_tier: TrustTier
    is_active: bool = True
    metadata_json: Optional[Dict[str, Any]] = None

class KnowledgeSourceCreate(KnowledgeSourceBase):
    pass

class KnowledgeSourceUpdate(BaseModel):
    source_name: Optional[str] = None
    source_version: Optional[str] = None
    trust_tier: Optional[TrustTier] = None
    is_active: Optional[bool] = None
    metadata_json: Optional[Dict[str, Any]] = None

class KnowledgeSourceResponse(KnowledgeSourceBase, BaseResponse):
    id: int
    created_at: datetime
    updated_at: datetime

class EvidenceBase(BaseModel):
    source_id: int
    knowledge_epoch_id: Optional[int] = None
    rule_key: str
    rule_version: str
    confidence_weight: float
    context_json: Optional[Dict[str, Any]] = None

class RiskEvidenceResponse(EvidenceBase, BaseResponse):
    id: int
    risk_id: int
    created_at: datetime

class RecommendationEvidenceResponse(EvidenceBase, BaseResponse):
    id: int
    recommendation_id: int
    created_at: datetime

class DynamicThresholdResponse(BaseResponse):
    threshold_id: int
    parameter_name: str
    optimal_min: Optional[float] = None
    optimal_max: Optional[float] = None
    warn_min: Optional[float] = None
    warn_max: Optional[float] = None
    critical_min: Optional[float] = None
    critical_max: Optional[float] = None
    confidence_score: float
    source_id: int
    evidence_id: Optional[int] = None
    knowledge_epoch_id: Optional[int] = None
    created_at: datetime

class KnowledgeEpochCreate(BaseModel):
    name: str
    description: Optional[str] = None

class KnowledgeEpochResponse(BaseResponse):
    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime

class ActiveEpochUpdate(BaseModel):
    epoch_id: int
