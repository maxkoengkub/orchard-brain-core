from typing import Protocol, Callable

class TransportInterface(Protocol):
    def send_bytes(self, data: bytes) -> bool:
        ...

    def set_receive_callback(self, callback: Callable[[bytes, int], None]) -> None:
        ...
