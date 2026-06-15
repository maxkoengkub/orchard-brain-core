from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import Integer, Float, String, DateTime, ForeignKeyConstraint, Boolean, JSON
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional

class Base(DeclarativeBase):
    pass

class SensorReadingModel(Base):
    __tablename__ = 'sensor_readings'
    
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    node_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    sequence_number: Mapped[int] = mapped_column(Integer)
    temperature: Mapped[float] = mapped_column(Float)
    humidity: Mapped[float] = mapped_column(Float)
    soil_moisture: Mapped[float] = mapped_column(Float)
    ec: Mapped[float] = mapped_column(Float)
    ph: Mapped[float] = mapped_column(Float)
    rainfall: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    leaf_wetness: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    solar_radiation: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    wind_speed: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    wind_direction: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    sensor_mask: Mapped[int] = mapped_column(Integer)
    battery_pct: Mapped[int] = mapped_column(Integer)
    tx_reason: Mapped[int] = mapped_column(Integer)
    rssi_last_rx: Mapped[int] = mapped_column(Integer)
    
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

class InfrastructureReadingModel(Base):
    __tablename__ = 'infrastructure_metrics'
    
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    node_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    flow_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tank_level: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fertilizer_tank_level: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pump_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

class OrchardHealthModel(Base):
    __tablename__ = 'orchard_health'
    
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    node_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    health_score: Mapped[int] = mapped_column(Integer)
    water_stress: Mapped[int] = mapped_column(Integer)
    nutrient_stress: Mapped[int] = mapped_column(Integer)
    
    risks: Mapped[list["RiskModel"]] = relationship(back_populates="health")
    recommendations: Mapped[list["RecommendationModel"]] = relationship(back_populates="health")

class RiskModel(Base):
    __tablename__ = 'risks'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    node_id: Mapped[int] = mapped_column(Integer)
    
    risk_type: Mapped[str] = mapped_column(String(50))
    severity: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(String(512))
    
    __table_args__ = (
        ForeignKeyConstraint(
            ['time', 'node_id'],
            ['orchard_health.time', 'orchard_health.node_id'],
            ondelete="CASCADE"
        ),
    )
    
    health: Mapped["OrchardHealthModel"] = relationship(back_populates="risks")

class RecommendationModel(Base):
    __tablename__ = 'recommendations'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    node_id: Mapped[int] = mapped_column(Integer)
    
    action: Mapped[str] = mapped_column(String(100))
    priority: Mapped[str] = mapped_column(String(50))
    reason: Mapped[str] = mapped_column(String(1024))
    confidence: Mapped[float] = mapped_column(Float)
    
    __table_args__ = (
        ForeignKeyConstraint(
            ['time', 'node_id'],
            ['orchard_health.time', 'orchard_health.node_id'],
            ondelete="CASCADE"
        ),
    )
    
    health: Mapped["OrchardHealthModel"] = relationship(back_populates="recommendations")

class NodeStatusModel(Base):
    __tablename__ = 'node_status'
    
    node_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    battery_pct: Mapped[int] = mapped_column(Integer)
    uptime_sec: Mapped[int] = mapped_column(Integer)
    fw_version: Mapped[int] = mapped_column(Integer)
    sensor_mask: Mapped[int] = mapped_column(Integer)

class CommandHistoryModel(Base):
    __tablename__ = 'command_history'
    
    command_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    node_id: Mapped[int] = mapped_column(Integer)
    actuator_type: Mapped[int] = mapped_column(Integer)
    action: Mapped[int] = mapped_column(Integer)
    value: Mapped[float] = mapped_column(Float)
    duration_sec: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(50), default="PENDING")

class SystemEventModel(Base):
    __tablename__ = 'system_events'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    event_type: Mapped[str] = mapped_column(String(100))
    message: Mapped[str] = mapped_column(String(1024))
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=True)
