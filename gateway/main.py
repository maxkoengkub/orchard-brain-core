import asyncio
import logging
import sys

from database.config import AsyncSessionLocal
from database.repository import DatabaseRepository
from gateway.configuration.config_manager import ConfigManager
from gateway.packet_encoder.encoder import LoRaEncoder
from gateway.packet_decoder.decoder import LoRaDecoder
from gateway.transport.lora_serial import LoraSerial
from gateway.service import GatewayService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

async def async_main():
    # In a real environment, you might load these from a config file
    config_manager = ConfigManager()
    
    # Example config overrides for local execution
    # config_manager.set_network_id(1)
    
    encoder = LoRaEncoder(config_manager, gateway_id=0x0000)
    decoder = LoRaDecoder(config_manager)
    
    # Example transport initialization. For production it would be a real COM/ttyS port.
    try:
        transport = LoraSerial(port="COM3", baudrate=9600)
        transport.connect()
    except Exception as e:
        logger.warning(f"Could not open LoraSerial: {e}")
        logger.warning("Gateway will start but transport may be broken.")
        transport = None # Ideally fall back to a MockTransport, or exit
        sys.exit(1)

    async with AsyncSessionLocal() as session:
        repo = DatabaseRepository(session)
        service = GatewayService(
            repository=repo,
            encoder=encoder,
            decoder=decoder,
            transport=transport
        )
        
        await service.start()
        
        try:
            # Keep the main thread alive indefinitely
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            pass
        finally:
            service.stop()
            if transport:
                transport.disconnect()

def main():
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("Gateway service stopped by user.")

if __name__ == "__main__":
    main()
