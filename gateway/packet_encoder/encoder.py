import struct
import hmac
import hashlib

# Packet Types
PKT_TYPE_DATA_ACK = 0x2
PKT_TYPE_DATA_NACK = 0x3
PKT_TYPE_CONFIG_PUSH = 0x6
PKT_TYPE_CONFIG_ACK = 0x7
PKT_TYPE_ACTUATION = 0xD # Using one of the reserved

MAC_HEADER_FMT = "<HHBB"

class LoRaEncoder:
    def __init__(self, config_manager, gateway_id=0x0000):
        self.config_manager = config_manager
        self.gateway_id = gateway_id

    def encode_frame(self, dest: int, pkt_type: int, payload: bytes, flags: int = 0) -> bytes:
        net = self.config_manager.get_network_id()
        node_secret = self.config_manager.get_node_secret(dest)
        
        if not node_secret:
            raise ValueError("Unknown DEST node secret")
            
        hdr = (pkt_type << 4) | (flags & 0x0F)
        mac_header = struct.pack(MAC_HEADER_FMT, dest, self.gateway_id, net, hdr)
        
        frame_without_hmac = mac_header + payload
        
        calculated_hmac = hmac.new(
            node_secret,
            frame_without_hmac,
            hashlib.sha256
        ).digest()[:4]
        
        return frame_without_hmac + calculated_hmac
