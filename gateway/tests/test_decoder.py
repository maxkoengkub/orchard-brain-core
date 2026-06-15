import struct
import hmac
import hashlib
from gateway.packet_decoder.decoder import LoRaDecoder, PKT_TYPE_DATA_UPLINK
from gateway.packet_decoder.unpackers import SENSOR_READING_SIZE

def test_decode_sensor_reading(config_manager):
    decoder = LoRaDecoder(config_manager)
    
    # Construct a fake frame
    dest = 0x0000
    src = 42
    net = 1
    hdr = (PKT_TYPE_DATA_UPLINK << 4) | 0
    mac_header = struct.pack("<HHBB", dest, src, net, hdr)
    
    # 30-byte payload for SENSOR_READING
    # Format: <HIIhHHHHHBBBb4s
    payload_fmt = "<HIIhHHHHHBBBb"
    payload = struct.pack(
        payload_fmt,
        42, # node_id
        1000, # timestamp
        1, # seq
        2500, # temp
        5000, # hum
        2000, # soil
        1500, # ec
        650, # ph
        10, # rain
        0xFF, # mask
        100, # batt
        0, # tx_reason
        -50 # rssi
    )
    
    # Dummy 4s for unpacking logic (HMAC sits at end)
    # The payload unpacker expects exactly 30 bytes including HMAC space
    frame_without_hmac = mac_header + payload
    
    calculated_hmac = hmac.new(
        config_manager.get_node_secret(src),
        frame_without_hmac,
        hashlib.sha256
    ).digest()[:4]
    
    full_frame = frame_without_hmac + calculated_hmac
    
    # Decode
    pkt_type, model = decoder.decode_frame(full_frame)
    
    assert pkt_type == PKT_TYPE_DATA_UPLINK
    assert model.node_id == 42
    assert model.temperature == 25.0
    assert model.humidity == 50.0
