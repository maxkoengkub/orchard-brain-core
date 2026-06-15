import struct
import hmac
import hashlib
from typing import Tuple, Any

from gateway.packet_decoder.unpackers import unpack_sensor_reading

# LoRa MAC Header Format: DEST (H), SRC (H), NET (B), HDR (B)
MAC_HEADER_FMT = "<HHBB"
MAC_HEADER_SIZE = 6

# Packet Types
PKT_TYPE_DATA_UPLINK = 0x1
PKT_TYPE_HEARTBEAT = 0x4
PKT_TYPE_ALERT_UPLINK = 0xC

class PacketDecodeError(Exception):
    pass

class LoRaDecoder:
    def __init__(self, config_manager):
        self.config_manager = config_manager

    def decode_frame(self, raw_bytes: bytes) -> Tuple[int, Any]:
        """
        Decodes a raw LoRa frame.
        Returns a tuple of (packet_type, decoded_model_or_dict)
        """
        if len(raw_bytes) < MAC_HEADER_SIZE + 4: # Min header + HMAC
            raise PacketDecodeError("Frame too short")

        mac_header = raw_bytes[:MAC_HEADER_SIZE]
        dest, src, net, hdr = struct.unpack(MAC_HEADER_FMT, mac_header)

        if net != self.config_manager.get_network_id():
            raise PacketDecodeError("Network ID mismatch")

        node_secret = self.config_manager.get_node_secret(src)
        if not node_secret:
            raise PacketDecodeError("Unknown SRC node")

        # Extract HMAC from end
        expected_hmac_truncated = raw_bytes[-4:]
        payload_and_header = raw_bytes[:-4]

        # Verify HMAC
        calculated_hmac = hmac.new(
            node_secret,
            payload_and_header,
            hashlib.sha256
        ).digest()[:4]

        if not hmac.compare_digest(calculated_hmac, expected_hmac_truncated):
            raise PacketDecodeError("HMAC validation failed")

        pkt_type = (hdr >> 4) & 0x0F
        flags = hdr & 0x0F

        payload_bytes = raw_bytes[MAC_HEADER_SIZE:]

        if pkt_type == PKT_TYPE_DATA_UPLINK:
            # Reconstruct the 30-byte format which INCLUDES the HMAC at the end
            # We already have payload_bytes + expected_hmac_truncated
            sensor_bytes = payload_bytes
            model = unpack_sensor_reading(sensor_bytes)
            return (pkt_type, model)
        else:
            # Handle other packet types as dicts or models
            return (pkt_type, {"raw": payload_bytes})
