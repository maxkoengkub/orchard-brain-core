import asyncio
import time
from typing import Dict, Any, Callable
from sqlalchemy.ext.asyncio import async_sessionmaker
from datetime import datetime, timezone
import logging

from database.repository import DatabaseRepository
from gateway.packet_encoder.encoder import LoRaEncoder, PKT_TYPE_ACTUATION, PKT_TYPE_CONFIG_PUSH, PKT_TYPE_DATA_ACK, PKT_TYPE_CONFIG_ACK
from gateway.packet_encoder.packers import pack_actuation_command, pack_config_push
from gateway.packet_decoder.decoder import LoRaDecoder, PKT_TYPE_DATA_UPLINK
from gateway.transport.interface import TransportInterface
from shared.payloads.models import ActuationCommand, ConfigPush, ActuatorType, ActuatorAction
from src.orchard_brain.engine import OrchardBrain

logger = logging.getLogger(__name__)

class GatewayService:
    def __init__(
        self,
        session_factory: async_sessionmaker,
        encoder: LoRaEncoder,
        decoder: LoRaDecoder,
        transport: TransportInterface,
        brain: OrchardBrain,
        poll_interval_sec: float = 1.0,
        timeout_sec: float = 5.0,
        max_retries: int = 3
    ):
        self.session_factory = session_factory
        self.encoder = encoder
        self.decoder = decoder
        self.transport = transport
        self.brain = brain
        
        self.poll_interval_sec = poll_interval_sec
        self.timeout_sec = timeout_sec
        self.max_retries = max_retries
        
        # inflight state: target_node -> dict
        self.inflight: Dict[int, Dict[str, Any]] = {}
        
        self._reading_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        
        # Hook up the transport receive callback
        self.transport.set_receive_callback(self._on_receive)

    async def start(self):
        self._running = True
        logger.info("GatewayService started.")
        asyncio.create_task(self._poll_loop())
        asyncio.create_task(self._timeout_loop())
        asyncio.create_task(self._process_readings())

    def stop(self):
        self._running = False
        logger.info("GatewayService stopping.")

    def _on_receive(self, raw_bytes: bytes, rssi: int):
        try:
            pkt_type, payload = self.decoder.decode_frame(raw_bytes)
            
            # Extract SRC node ID directly from MAC header
            import struct
            if len(raw_bytes) >= 6:
                _, src, _, _ = struct.unpack("<HHBB", raw_bytes[:6])
                
                if pkt_type == PKT_TYPE_DATA_UPLINK:
                    # Enqueue reading
                    self._reading_queue.put_nowait((src, payload))
                
                # Check if this is an ACK and we have an inflight command to this node
                elif pkt_type in (PKT_TYPE_DATA_ACK, PKT_TYPE_CONFIG_ACK) and src in self.inflight:
                    inflight_record = self.inflight.pop(src)
                    
                    async def update_ack():
                        async with self.session_factory() as session:
                            repo = DatabaseRepository(session)
                            if inflight_record["type"] == "actuation":
                                await repo.update_command_status(inflight_record["id"], "ACKED")
                            elif inflight_record["type"] == "config":
                                await repo.update_configuration_status(inflight_record["id"], "ACKED")
                    
                    loop = asyncio.get_event_loop()
                    loop.create_task(update_ack())
                    logger.info(f"Received ACK from Node {src}. Status updated to ACKED.")
        except Exception as e:
            logger.error(f"Error handling received packet: {e}")

    async def _process_readings(self):
        while self._running:
            try:
                src, reading = await self._reading_queue.get()
                dt = datetime.now(timezone.utc)
                
                async with self.session_factory() as session:
                    repo = DatabaseRepository(session)
                    
                    # 1. Persist the sensor reading
                    reading.timestamp = int(dt.timestamp()) # Align timestamp if needed or leave raw
                    await repo.save_sensor_reading(reading)
                    
                    # 2. Evaluate using deterministic brain inside a thread pool
                    brain_result = await asyncio.to_thread(self.brain.evaluate, reading)
                    
                    # 3. Persist the evaluation
                    await repo.save_brain_result(src, dt, brain_result)
                    
                    logger.info(f"Processed reading and brain evaluation for Node {src}.")
            except Exception as e:
                logger.error(f"Error in _process_readings: {e}")

    async def _poll_loop(self):
        while self._running:
            try:
                async with self.session_factory() as session:
                    repo = DatabaseRepository(session)
                    
                    # 1. Poll Commands
                    pending_cmds = await repo.get_pending_commands(limit=10)
                    for cmd_model in pending_cmds:
                        target_node = cmd_model.node_id
                        
                        # Strict one-in-flight per node
                        if target_node in self.inflight:
                            continue
                            
                        # Pack payload
                        actuation = ActuationCommand(
                            command_id=cmd_model.command_id,
                            target_node=target_node,
                            actuator_type=ActuatorType(cmd_model.actuator_type),
                            action=ActuatorAction(cmd_model.action),
                            value=cmd_model.value,
                            duration_sec=cmd_model.duration_sec
                        )
                        payload_bytes = pack_actuation_command(actuation)
                        
                        # Encode frame
                        frame = self.encoder.encode_frame(
                            dest=target_node,
                            pkt_type=PKT_TYPE_ACTUATION,
                            payload=payload_bytes
                        )
                        
                        # Transmit
                        self.transport.send_bytes(frame)
                        
                        # Track Inflight
                        self.inflight[target_node] = {
                            "type": "actuation",
                            "id": cmd_model.command_id,
                            "frame": frame,
                            "retries": 0,
                            "sent_time": time.time()
                        }
                        
                        await repo.update_command_status(cmd_model.command_id, "SENT")
                        logger.info(f"Sent ActuationCommand {cmd_model.command_id} to Node {target_node}.")

                    # 2. Poll Configurations
                    pending_configs = await repo.get_pending_configurations(limit=10)
                    for config_event in pending_configs:
                        config_data = config_event.metadata_json
                        # If config push doesn't target a specific node, we might broadcast it.
                        # Assuming a target_node is provided, or we default to broadcast (0xFFFF).
                        target_node = config_data.get("target_node", 0xFFFF)
                        
                        if target_node != 0xFFFF and target_node in self.inflight:
                            continue
                            
                        config_push = ConfigPush(**config_data)
                        payload_bytes = pack_config_push(config_push)
                        
                        frame = self.encoder.encode_frame(
                            dest=target_node,
                            pkt_type=PKT_TYPE_CONFIG_PUSH,
                            payload=payload_bytes
                        )
                        
                        self.transport.send_bytes(frame)
                        
                        if target_node != 0xFFFF: # Track unicast
                            self.inflight[target_node] = {
                                "type": "config",
                                "id": config_event.id,
                                "frame": frame,
                                "retries": 0,
                                "sent_time": time.time()
                            }
                        
                        await repo.update_configuration_status(config_event.id, "SENT")
                        logger.info(f"Sent ConfigPush to Node {target_node}.")
                        
            except Exception as e:
                logger.error(f"Error in poll loop: {e}")
                
            await asyncio.sleep(self.poll_interval_sec)

    async def _timeout_loop(self):
        while self._running:
            try:
                now = time.time()
                for target_node, record in list(self.inflight.items()):
                    if now - record["sent_time"] > self.timeout_sec:
                        if record["retries"] < self.max_retries:
                            # Retry
                            record["retries"] += 1
                            record["sent_time"] = now
                            self.transport.send_bytes(record["frame"])
                            logger.info(f"Retry {record['retries']} for Node {target_node}.")
                        else:
                            # Failed
                            self.inflight.pop(target_node)
                            async def update_failed():
                                async with self.session_factory() as session:
                                    repo = DatabaseRepository(session)
                                    if record["type"] == "actuation":
                                        await repo.update_command_status(record["id"], "FAILED")
                                    elif record["type"] == "config":
                                        await repo.update_configuration_status(record["id"], "FAILED")
                            loop = asyncio.get_event_loop()
                            loop.create_task(update_failed())
                            logger.error(f"Timeout max retries reached for Node {target_node}. Marked FAILED.")
            except Exception as e:
                logger.error(f"Error in timeout loop: {e}")
                
            await asyncio.sleep(1.0)
