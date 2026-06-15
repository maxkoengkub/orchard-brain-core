class ConfigManager:
    def __init__(self, network_id: int = 1):
        self.network_id = network_id
        # In a real system, these would be loaded from a DB/NVS
        # Mocking node 1 with a known secret for testing
        self.node_secrets = {
            1: b'\x00' * 16, # 16 byte dummy secret
            42: b'supersecretkey12'
        }

    def get_network_id(self) -> int:
        return self.network_id

    def get_node_secret(self, node_id: int) -> bytes:
        return self.node_secrets.get(node_id)
