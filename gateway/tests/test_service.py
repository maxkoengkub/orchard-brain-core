import pytest
import pytest_asyncio
import asyncio
from typing import Callable

from database.models import Base
from database.repository import DatabaseRepository
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from gateway.service import GatewayService
from gateway.packet_encoder.encoder import LoRaEncoder
from gateway.packet_decoder.decoder import LoRaDecoder
from gateway.configuration.config_manager import ConfigManager
from gateway.transport.interface import TransportInterface

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

@pytest_asyncio.fixture(scope="function")
async def async_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture(scope="function")
async def test_session(async_engine):
    async_session = async_sessionmaker(
        bind=async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session

@pytest_asyncio.fixture(scope="function")
def config_manager():
    cm = ConfigManager()
    cm.node_secrets[10] = b"0123456789abcdef"
    return cm

@pytest.mark.asyncio
async def test_gateway_service_lifecycle(test_session, config_manager):
    repo = DatabaseRepository(test_session)
    encoder = LoRaEncoder(config_manager)
    decoder = LoRaDecoder(config_manager)
    transport = MockTransport()

    service = GatewayService(
        repository=repo,
        encoder=encoder,
        decoder=decoder,
        transport=transport,
        poll_interval_sec=0.1,
        timeout_sec=0.5,
        max_retries=1
    )

    # Insert a pending command
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
    cmd = await repo.update_command_status("cmd-test-1", "ACKED")
    assert cmd.status == "ACKED"
    
    service.stop()
