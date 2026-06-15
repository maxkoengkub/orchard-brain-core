import logging
from gateway.packet_decoder.decoder import LoRaDecoder, PKT_TYPE_DATA_UPLINK, PKT_TYPE_HEARTBEAT
from gateway.packet_encoder.encoder import LoRaEncoder, PKT_TYPE_DATA_ACK
from gateway.packet_encoder.packers import pack_data_ack
from shared.payloads.models import SensorReading

logger = logging.getLogger(__name__)

class GatewayRouter:
    def __init__(self, decoder: LoRaDecoder, encoder: LoRaEncoder, transport, orchard_brain, health_monitor):
        self.decoder = decoder
        self.encoder = encoder
        self.transport = transport
        self.orchard_brain = orchard_brain
        self.health_monitor = health_monitor
        self.transport.set_receive_callback(self.handle_rx_bytes)

    def handle_rx_bytes(self, raw_bytes: bytes, rssi: int):
        try:
            pkt_type, model = self.decoder.decode_frame(raw_bytes)
            
            if pkt_type == PKT_TYPE_DATA_UPLINK and isinstance(model, SensorReading):
                self._handle_sensor_reading(model)
            elif pkt_type == PKT_TYPE_HEARTBEAT:
                self.health_monitor.process_heartbeat(model)
            else:
                logger.warning(f"Unhandled packet type {pkt_type}")
                
        except Exception as e:
            logger.error(f"Failed to decode frame: {e}")

    def _handle_sensor_reading(self, reading: SensorReading):
        # 1. Send ACK back to node
        ack_payload = pack_data_ack(reading.sequence_number)
        ack_frame = self.encoder.encode_frame(reading.node_id, PKT_TYPE_DATA_ACK, ack_payload)
        self.transport.send_bytes(ack_frame)
        
        # 2. Route to Intelligence Core
        try:
            # Pass the Pydantic model directly to OrchardBrain
            orch_result = self.orchard_brain.evaluate_orchestrated(reading)
            logger.info(f"Brain evaluation complete for node {reading.node_id}")
        except Exception as e:
            logger.error(f"Brain evaluation failed: {e}")
