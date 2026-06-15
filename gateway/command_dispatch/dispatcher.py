import logging
from gateway.packet_encoder.encoder import LoRaEncoder, PKT_TYPE_ACTUATION
from gateway.packet_encoder.packers import pack_actuation_command
from shared.payloads.models import ActuationCommand

logger = logging.getLogger(__name__)

class CommandDispatcher:
    def __init__(self, encoder: LoRaEncoder, transport):
        self.encoder = encoder
        self.transport = transport
        self.pending_commands = {}

    def dispatch(self, command: ActuationCommand) -> bool:
        """
        Dispatches an actuation command to a node.
        Returns True if queued/sent successfully.
        """
        try:
            payload = pack_actuation_command(command)
            frame = self.encoder.encode_frame(command.target_node, PKT_TYPE_ACTUATION, payload)
            
            # Record as pending until ACK'd
            self.pending_commands[command.command_id] = {
                "command": command,
                "retries": 0
            }
            
            self.transport.send_bytes(frame)
            logger.info(f"Dispatched command {command.command_id} to node {command.target_node}")
            return True
        except Exception as e:
            logger.error(f"Failed to dispatch command: {e}")
            return False
            
    def handle_ack(self, command_id: str):
        if command_id in self.pending_commands:
            del self.pending_commands[command_id]
            logger.info(f"Command {command_id} acknowledged")
