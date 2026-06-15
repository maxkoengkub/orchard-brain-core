import struct
from shared.payloads.models import ActuationCommand, ConfigPush, ActuatorType, ActuatorAction

# Formats
DATA_ACK_FMT = "<I"
DATA_NACK_FMT = "<IB"
CONFIG_PUSH_FMT = "<IBbI"
ACTUATION_COMMAND_FMT = "<16sHBBfI"

def pack_data_ack(seq_num: int) -> bytes:
    return struct.pack(DATA_ACK_FMT, seq_num)

def pack_data_nack(seq_num: int, reason: int) -> bytes:
    return struct.pack(DATA_NACK_FMT, seq_num, reason)

def pack_config_push(model: ConfigPush) -> bytes:
    return struct.pack(
        CONFIG_PUSH_FMT,
        model.config_hash,
        model.lora_channel or 0,
        model.tx_power_dbm or 0,
        model.sample_rate_sec or 0
    )

def pack_actuation_command(model: ActuationCommand) -> bytes:
    actuator_map = {
        ActuatorType.VALVE: 0,
        ActuatorType.PUMP: 1,
        ActuatorType.FERTIGATOR: 2
    }
    action_map = {
        ActuatorAction.OPEN: 0,
        ActuatorAction.CLOSE: 1,
        ActuatorAction.SET: 2
    }
    
    cmd_id_bytes = model.command_id.encode('utf-8')[:16].ljust(16, b'\x00')
    
    return struct.pack(
        ACTUATION_COMMAND_FMT,
        cmd_id_bytes,
        model.target_node,
        actuator_map[model.actuator_type],
        action_map[model.action],
        model.value if model.value is not None else 0.0,
        model.duration_sec if model.duration_sec is not None else 0
    )
