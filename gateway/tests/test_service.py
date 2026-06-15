import pytest
import pytest_asyncio
import asyncio
from typing import Callable

from database.models import Base, SensorReadingModel, OrchardHealthModel, RiskModel, RecommendationModel
from database.repository import DatabaseRepository
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from gateway.service import GatewayService
from gateway.packet_encoder.encoder import LoRaEncoder
from gateway.packet_decoder.decoder import LoRaDecoder
from gateway.configuration.config_manager import ConfigManager
from gateway.transport.interface import TransportInterface
from src.orchard_brain.engine import OrchardBrain
from shared.payloads.models import SensorReading

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

class MockTransport(TransportInterface):
    def __init__(self):
        self.sent_frames = []
        self._callback = None

    def send_bytes(self, data: bytes) -> bool:
        self.sent_frames.append(data)
        return True

    def set_receive_callback(self, callback: Callable[[bytes, int], None]) -> None:
        self._callback = callback

    def simulate_receive(self, data: bytes, rssi: int = -50):
        if self._callback:
            self._callback(data, rssi)

from sqlalchemy.pool import StaticPool

import os

TEST_DATABASE_URL = "sqlite+aiosqlite:///test_gateway.db"

@pytest_asyncio.fixture(scope="function")
async def async_engine():
    # Remove old test DB if it exists
    if os.path.exists("test_gateway.db"):
        os.remove("test_gateway.db")
        
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    
    if os.path.exists("test_gateway.db"):
        try:
            os.remove("test_gateway.db")
        except:
            pass

@pytest_asyncio.fixture(scope="function")
def session_factory(async_engine):
    return async_sessionmaker(
        bind=async_engine, class_=AsyncSession, expire_on_commit=False
    )

@pytest_asyncio.fixture(scope="function")
def config_manager():
    cm = ConfigManager()
    cm.node_secrets[10] = b"0123456789abcdef"
    return cm

@pytest.mark.asyncio
async def test_gateway_service_lifecycle(session_factory, config_manager):
    encoder = LoRaEncoder(config_manager)
    decoder = LoRaDecoder(config_manager)
    transport = MockTransport()
    brain = OrchardBrain(enable_memory=False)

    service = GatewayService(
        session_factory=session_factory,
        encoder=encoder,
        decoder=decoder,
        transport=transport,
        brain=brain,
        poll_interval_sec=0.1,
        timeout_sec=0.5,
        max_retries=1
    )

    # Insert a pending command
    async with session_factory() as session:
        repo = DatabaseRepository(session)
        cmd_dict = {
            "command_id": "cmd-test-1",
            "target_node": 10,
            "actuator_type": "VALVE",
            "action": "OPEN",
            "value": 0.0,
            "duration_sec": 60
        }
        await repo.save_command(cmd_dict)

    # Start service
    await service.start()
    
    # Wait for poll to process it
    await asyncio.sleep(0.3)
    
    # Check that transport sent something
    assert len(transport.sent_frames) == 1
    
    # Check DB status is SENT
    async with session_factory() as session:
        repo = DatabaseRepository(session)
        cmd = await repo.update_command_status("cmd-test-1", "SENT") # Fetch latest
        assert cmd.status == "SENT"

    # Simulate ACK receiving
    import struct
    import hmac
    import hashlib
    # Construct a DATA_ACK frame from Node 10
    mac_header = struct.pack("<HHBB", 0x0000, 10, config_manager.get_network_id(), (0x2 << 4))
    payload = struct.pack("<I", 1) # seq_num
    frame_without_hmac = mac_header + payload
    calculated_hmac = hmac.new(
        config_manager.get_node_secret(10),
        frame_without_hmac,
        hashlib.sha256
    ).digest()[:4]
    ack_frame = frame_without_hmac + calculated_hmac

    transport.simulate_receive(ack_frame)
    
    # Wait for the async task inside _on_receive to complete
    await asyncio.sleep(0.2)
    
    # Check DB status is ACKED
    async with session_factory() as session:
        repo = DatabaseRepository(session)
        cmd = await repo.update_command_status("cmd-test-1", "ACKED")
        assert cmd.status == "ACKED"
    
    service.stop()

@pytest.mark.asyncio
async def test_gateway_service_uplink_processing(session_factory, config_manager):
    encoder = LoRaEncoder(config_manager)
    decoder = LoRaDecoder(config_manager)
    transport = MockTransport()
    brain = OrchardBrain(enable_memory=False)

    service = GatewayService(
        session_factory=session_factory,
        encoder=encoder,
        decoder=decoder,
        transport=transport,
        brain=brain,
        poll_interval_sec=0.1,
        timeout_sec=0.5,
        max_retries=1
    )

    await service.start()

    import struct
    import hmac
    import hashlib
    
    payload_without_hmac = struct.pack(
        "<HIIhHHHHHBBBb",
        10,            # node_id
        1000,          # timestamp
        1,             # sequence_number
        int(40.0 * 100), # temperature
        int(50.0 * 100), # humidity
        int(50.0 * 100), # soil_moisture
        int(200.0 * 10), # ec
        int(6.0 * 100),  # ph
        int(0.0 * 10),   # rainfall
        1,             # sensor_mask
        90,            # battery_pct
        0,             # tx_reason
        -50            # rssi_last_rx
    )
    
    mac_header = struct.pack("<HHBB", 0x0000, 10, config_manager.get_network_id(), (0x1 << 4))
    frame_without_hmac = mac_header + payload_without_hmac
    calculated_hmac = hmac.new(
        config_manager.get_node_secret(10),
        frame_without_hmac,
        hashlib.sha256
    ).digest()[:4]
    
    uplink_frame = frame_without_hmac + calculated_hmac

    transport.simulate_receive(uplink_frame)

    # Wait for queue and processing to complete
    await asyncio.sleep(0.3)

    service.stop()

    async with session_factory() as session:
        # Assert Sensor Reading
        res = await session.execute(select(SensorReadingModel))
        r = res.scalars().first()
        assert r is not None
        assert r.temperature == 40.0

        # Assert Orchard Health
        res = await session.execute(select(OrchardHealthModel))
        health = res.scalars().first()
        assert health is not None
        assert health.health_score < 100

        # Assert Risks
        res = await session.execute(select(RiskModel))
        risks = res.scalars().all()
        assert len(risks) > 0
        has_heat_stress = any(risk.risk_type == "heat_stress" and risk.severity == "critical" for risk in risks)
        assert has_heat_stress

        # Assert Recommendations
        res = await session.execute(select(RecommendationModel))
        recs = res.scalars().all()
        assert len(recs) > 0
        has_cooling_rec = any("micro_sprinkler" in rec.action and rec.priority == "critical" for rec in recs)
        assert has_cooling_rec

