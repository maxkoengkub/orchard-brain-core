import struct
import hmac
import hashlib
from gateway.packet_encoder.encoder import LoRaEncoder, PKT_TYPE_ACTUATION
from gateway.packet_encoder.packers import pack_actuation_command
from shared.payloads.models import ActuationCommand, ActuatorType, ActuatorAction

def test_encode_actuation_command(config_manager):
    encoder = LoRaEncoder(config_manager, gateway_id=0x0000)
    
    cmd = ActuationCommand(
        command_id="cmd-1234",
        target_node=42,
        actuator_type=ActuatorType.VALVE,
        action=ActuatorAction.OPEN
    )
    
    payload = pack_actuation_command(cmd)
    frame = encoder.encode_frame(dest=42, pkt_type=PKT_TYPE_ACTUATION, payload=payload)
    
    # Validate MAC Header: <HHBB
    dest, src, net, hdr = struct.unpack("<HHBB", frame[:6])
    assert dest == 42
    assert src == 0x0000
    assert net == 1
    assert (hdr >> 4) == PKT_TYPE_ACTUATION
    
    # Validate HMAC length and calculation
    assert len(frame) == 6 + len(payload) + 4
    
    expected_hmac = hmac.new(
        b'supersecretkey12',
        frame[:-4],
        hashlib.sha256
    ).digest()[:4]
    
    assert frame[-4:] == expected_hmac
