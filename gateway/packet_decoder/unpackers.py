import struct
from typing import Any, Tuple

from shared.payloads.models import SensorReading

# Format: < = Little Endian
# H = uint16 (node_id)
# I = uint32 (timestamp)
# I = uint32 (sequence_number)
# h = int16  (temperature)
# H = uint16 (humidity)
# H = uint16 (soil_moisture)
# H = uint16 (ec)
# H = uint16 (ph)
# H = uint16 (rainfall)
# B = uint8  (sensor_mask)
# B = uint8  (battery_pct)
# B = uint8  (tx_reason)
# b = int8   (rssi_last_rx)
# 4s = char[4] (hmac_truncated)
SENSOR_READING_FMT = "<HIIhHHHHHBBBb4s"
SENSOR_READING_SIZE = 30

def unpack_sensor_reading(payload_bytes: bytes) -> SensorReading:
    if len(payload_bytes) != SENSOR_READING_SIZE:
        raise ValueError(f"Expected {SENSOR_READING_SIZE} bytes for SensorReading, got {len(payload_bytes)}")

    unpacked = struct.unpack(SENSOR_READING_FMT, payload_bytes)
    
    return SensorReading(
        node_id=unpacked[0],
        timestamp=unpacked[1],
        sequence_number=unpacked[2],
        temperature=unpacked[3] / 100.0,
        humidity=unpacked[4] / 100.0,
        soil_moisture=unpacked[5] / 100.0,
        ec=unpacked[6] / 10.0,
        ph=unpacked[7] / 100.0,
        rainfall=unpacked[8] / 10.0,
        sensor_mask=unpacked[9],
        battery_pct=unpacked[10],
        tx_reason=unpacked[11],
        rssi_last_rx=unpacked[12]
        # hmac_truncated is unpacked[13], checked at MAC layer
    )
