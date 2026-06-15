from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc
from datetime import datetime, timezone
import json

from database.models import (
    SensorReadingModel,
    OrchardHealthModel,
    RiskModel,
    RecommendationModel,
    NodeStatusModel,
    CommandHistoryModel,
    SystemEventModel,
    InfrastructureReadingModel
)
from shared.payloads.models import SensorReading

class DatabaseRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_sensor_reading(self, reading: SensorReading):
        # Convert timestamp (assuming seconds or ms) to UTC datetime
        # Assuming reading.timestamp is Unix time in seconds for now
        dt = datetime.fromtimestamp(reading.timestamp, tz=timezone.utc)
        
        db_reading = SensorReadingModel(
            time=dt,
            node_id=reading.node_id,
            sequence_number=reading.sequence_number,
            temperature=reading.temperature,
            humidity=reading.humidity,
            soil_moisture=reading.soil_moisture,
            ec=reading.ec,
            ph=reading.ph,
            rainfall=getattr(reading, "rainfall", None),
            leaf_wetness=getattr(reading, "leaf_wetness", None),
            solar_radiation=getattr(reading, "solar_radiation", None),
            wind_speed=getattr(reading, "wind_speed", None),
            wind_direction=getattr(reading, "wind_direction", None),
            sensor_mask=reading.sensor_mask,
            battery_pct=reading.battery_pct,
            tx_reason=reading.tx_reason,
            rssi_last_rx=reading.rssi_last_rx,
            metadata_json=getattr(reading, "metadata_json", None)
        )
        self.session.add(db_reading)
        await self.session.commit()
        return db_reading

    async def save_infrastructure_reading(self, node_id: int, timestamp: int, data: dict):
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        db_reading = InfrastructureReadingModel(
            time=dt,
            node_id=node_id,
            flow_rate=data.get("flow_rate"),
            tank_level=data.get("tank_level"),
            fertilizer_tank_level=data.get("fertilizer_tank_level"),
            pump_status=data.get("pump_status"),
            metadata_json=data.get("metadata_json")
        )
        self.session.add(db_reading)
        await self.session.commit()
        return db_reading

    async def save_orchestrator_result(self, node_id: int, dt: datetime, result: dict):
        health = OrchardHealthModel(
            time=dt,
            node_id=node_id,
            health_score=result["health_score"],
            water_stress=result["water_stress"],
            nutrient_stress=result["nutrient_stress"]
        )
        self.session.add(health)
        
        for risk in result.get("risks", []):
            risk_model = RiskModel(
                time=dt,
                node_id=node_id,
                risk_type=risk["type"],
                severity=risk["severity"],
                description=risk["description"]
            )
            self.session.add(risk_model)
            
        for rec in result.get("recommendations", []):
            rec_model = RecommendationModel(
                time=dt,
                node_id=node_id,
                action=rec["action"],
                priority=rec["priority"],
                reason=rec["reason"],
                confidence=rec["confidence"]
            )
            self.session.add(rec_model)
            
        await self.session.commit()
        return health

    async def update_node_status(self, status: dict):
        node_id = status["node_id"]
        stmt = select(NodeStatusModel).where(NodeStatusModel.node_id == node_id)
        result = await self.session.execute(stmt)
        node = result.scalar_one_or_none()
        
        if not node:
            node = NodeStatusModel(node_id=node_id)
            self.session.add(node)
            
        node.last_seen = datetime.now(timezone.utc)
        node.battery_pct = status.get("battery_pct", node.battery_pct)
        node.uptime_sec = status.get("uptime_sec", node.uptime_sec)
        node.fw_version = status.get("fw_version", node.fw_version)
        node.sensor_mask = status.get("sensor_mask", node.sensor_mask)
        
        await self.session.commit()
        return node
        
    async def log_system_event(self, event_type: str, message: str, metadata: dict = None):
        event = SystemEventModel(
            time=datetime.now(timezone.utc),
            event_type=event_type,
            message=message,
            metadata_json=metadata
        )
        self.session.add(event)
        await self.session.commit()
        return event

    # --- Read Operations ---

    async def get_sensor_history(self, node_id: int = None, limit: int = 100):
        stmt = select(SensorReadingModel).order_by(desc(SensorReadingModel.time)).limit(limit)
        if node_id is not None:
            stmt = stmt.where(SensorReadingModel.node_id == node_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_recommendations(self, node_id: int = None, limit: int = 50):
        stmt = select(RecommendationModel).order_by(desc(RecommendationModel.time)).limit(limit)
        if node_id is not None:
            stmt = stmt.where(RecommendationModel.node_id == node_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_risk_summary(self, node_id: int = None, limit: int = 50):
        stmt = select(RiskModel).order_by(desc(RiskModel.time)).limit(limit)
        if node_id is not None:
            stmt = stmt.where(RiskModel.node_id == node_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_nodes(self):
        stmt = select(NodeStatusModel)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    # --- Command & Config Queue Operations ---

    async def save_command(self, cmd: dict):
        db_cmd = CommandHistoryModel(
            command_id=cmd["command_id"],
            time=datetime.now(timezone.utc),
            node_id=cmd["target_node"],
            actuator_type=cmd["actuator_type"],
            action=cmd["action"],
            value=cmd.get("value", 0.0),
            duration_sec=cmd.get("duration_sec", 0),
            status="PENDING"
        )
        self.session.add(db_cmd)
        await self.session.commit()
        return db_cmd

    async def save_configuration(self, config: dict):
        # We model config pushes as system events for simplicity, 
        # or Gateway will poll PENDING system_events of type CONFIG_PUSH
        event = SystemEventModel(
            time=datetime.now(timezone.utc),
            event_type="CONFIG_PUSH",
            message=f"Configuration push staged for hash {config['config_hash']}",
            metadata_json=config
        )
        self.session.add(event)
        await self.session.commit()
        return event
