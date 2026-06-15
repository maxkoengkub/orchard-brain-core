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
        rainfall=0.0,
        sensor_mask=255,
        battery_pct=95,
        tx_reason=0,
        rssi_last_rx=-50
    )
    
    saved = await repo.save_sensor_reading(reading)
    
    assert saved.node_id == 10
    assert saved.temperature == 25.5
    assert saved.time.timestamp() == 1718000000

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
