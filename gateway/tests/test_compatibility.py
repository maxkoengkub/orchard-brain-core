import pytest
from src.orchard_brain.orchard_memory import SensorSnapshot
from shared.payloads.models import SensorReading

class LegacyReading:
    def __init__(self, t, h, e, p):
        self.temperature = t
        self.humidity = h
        self.ec = e
        self.ph = p

def test_sensor_snapshot_legacy_compatibility():
    # Test with legacy reading object (no soil_moisture, no rainfall)
    legacy = LegacyReading(28.5, 60.0, 1.2, 6.5)
    snapshot = SensorSnapshot.from_reading(legacy)
    
    assert snapshot.temperature == 28.5
    assert snapshot.humidity == 60.0
    # Fallback to humidity
    assert snapshot.soil_moisture == 60.0
    assert snapshot.ec == 1.2
    assert snapshot.ph == 6.5
    # Default rainfall
    assert snapshot.rainfall == 0.0

def test_sensor_snapshot_pydantic_compatibility():
    # Test with Phase 1A SensorReading pydantic model
    reading = SensorReading(
        node_id=1,
        timestamp=1000000,
        sequence_number=1,
        temperature=29.0,
        humidity=55.0,
        soil_moisture=45.0,
        ec=1.5,
        ph=6.8,
        rainfall=5.2,
        sensor_mask=0xFF,
        battery_pct=100,
        tx_reason=0,
        rssi_last_rx=-50
    )
    
    snapshot = SensorSnapshot.from_reading(reading)
    
    assert snapshot.temperature == 29.0
    assert snapshot.humidity == 55.0
    # Should pick up actual soil moisture
    assert snapshot.soil_moisture == 45.0
    assert snapshot.ec == 1.5
    assert snapshot.ph == 6.8
    # Should pick up actual rainfall
    assert snapshot.rainfall == 5.2
