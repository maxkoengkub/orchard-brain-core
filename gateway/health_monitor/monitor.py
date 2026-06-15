import logging
import time

logger = logging.getLogger(__name__)

class HealthMonitor:
    def __init__(self):
        self.node_states = {}

    def process_heartbeat(self, model: dict):
        # We assume heartbeat model is unpacked into a dict
        node_id = model.get("node_id")
        if node_id is not None:
            self.node_states[node_id] = {
                "last_seen": time.time(),
                "battery_pct": model.get("battery_pct", 0),
                "uptime_sec": model.get("uptime_sec", 0),
                "sensor_mask": model.get("sensor_mask", 0),
                "fw_version": model.get("fw_version", 0)
            }
            logger.info(f"Heartbeat received from node {node_id}")
            
    def get_node_health(self, node_id: int):
        return self.node_states.get(node_id)
