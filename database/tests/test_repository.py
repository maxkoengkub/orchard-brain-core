import pytest
from datetime import datetime, timezone
from database.repository import DatabaseRepository
from shared.payloads.models import SensorReading

@pytest.mark.asyncio
async def test_save_sensor_reading(db_session):
    repo = DatabaseRepository(db_session)
    
    reading = SensorReading(
        node_id=10,
        timestamp=1718000000,
        sequence_number=1,
        temperature=25.5,
        humidity=60.0,
        soil_moisture=45.0,
        ec=1.2,
        ph=6.5,
        rainfall=None,
        leaf_wetness=0.0,
        solar_radiation=1200.0,
        wind_speed=None,
        wind_direction=None,
        sensor_mask=255,
        battery_pct=95,
        tx_reason=0,
        rssi_last_rx=-50,
        metadata_json={"calibration_status": "ok"}
    )
    
    saved = await repo.save_sensor_reading(reading)
    
    assert saved.node_id == 10
    assert saved.temperature == 25.5
    assert saved.time.timestamp() == 1718000000
    assert saved.rainfall is None
    assert saved.solar_radiation == 1200.0
    assert saved.metadata_json == {"calibration_status": "ok"}

@pytest.mark.asyncio
async def test_save_infrastructure_reading(db_session):
    repo = DatabaseRepository(db_session)
    
    data = {
        "flow_rate": 50.5,
        "tank_level": 85.0,
        "fertilizer_tank_level": 40.0,
        "pump_status": 1,
        "metadata_json": {"pump_temp": 35.2}
    }
    
    saved = await repo.save_infrastructure_reading(11, 1718000500, data)
    assert saved.node_id == 11
    assert saved.flow_rate == 50.5
    assert saved.pump_status == 1
    assert saved.metadata_json["pump_temp"] == 35.2

@pytest.mark.asyncio
async def test_save_orchestrator_result(db_session):
    repo = DatabaseRepository(db_session)
    
    result = {
        "health_score": 85,
        "water_stress": 10,
        "nutrient_stress": 5,
        "risks": [
            {"type": "HEAT", "severity": "MEDIUM", "description": "Hot day"}
        ],
        "recommendations": [
            {"action": "turn_on_water", "priority": "high", "reason": "Dry", "confidence": 0.9}
        ]
    }
    
    dt = datetime.now(timezone.utc)
    health = await repo.save_orchestrator_result(42, dt, result)
    
    assert health.node_id == 42
    assert health.health_score == 85

@pytest.mark.asyncio
async def test_update_node_status(db_session):
    repo = DatabaseRepository(db_session)
    status = {"node_id": 99, "battery_pct": 80, "uptime_sec": 3600, "fw_version": 2, "sensor_mask": 0xFF}
    
    node = await repo.update_node_status(status)
    assert node.node_id == 99
    assert node.battery_pct == 80
    
    # Update
    status2 = {"node_id": 99, "battery_pct": 79}
    node2 = await repo.update_node_status(status2)
    assert node2.battery_pct == 79
    assert node2.uptime_sec == 3600 # Unchanged
