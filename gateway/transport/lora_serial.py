from gateway.transport.interface import TransportInterface
from typing import Callable

class LoRaSerialTransport(TransportInterface):
    """
    Concrete implementation of UART transport for E220.
    Uses pyserial (mocked for skeleton).
    """
    def __init__(self, port: str, baudrate: int = 9600):
        self.port = port
        self.baudrate = baudrate
        self.callback = None
        # self.serial = serial.Serial(port, baudrate)

    def send_bytes(self, data: bytes) -> bool:
        # self.serial.write(data)
        return True

    def set_receive_callback(self, callback: Callable[[bytes, int], None]) -> None:
        self.callback = callback
        
    def _poll(self):
        # Background thread reading from self.serial
        pass
