import json
import queue
import threading
from datetime import datetime


class ESP32ConnectionManager:
    """
    In-memory manager for tracking active ESP32 SSE connections.
    Maps user_id -> connection info so we can send events to the right device.
    """

    def __init__(self):
        self._connections = {}
        self._lock = threading.Lock()

    def add(self, user_id, device_id, message_queue):
        """Register an ESP32 SSE connection for a user."""
        with self._lock:
            self._connections[user_id] = {
                "device_id": device_id,
                "queue": message_queue,
                "connected_at": datetime.utcnow(),
            }

    def remove(self, user_id):
        """Remove an ESP32 SSE connection."""
        with self._lock:
            self._connections.pop(user_id, None)

    def get(self, user_id):
        """Get connection info for a user's ESP32."""
        with self._lock:
            return self._connections.get(user_id)

    def is_connected(self, user_id):
        """Check if user has an active ESP32 connection."""
        with self._lock:
            return user_id in self._connections

    def send_event(self, user_id, event, data):
        """
        Send an SSE event to a user's connected ESP32 device.

        Args:
            user_id: The user whose ESP32 should receive the event
            event: SSE event name (e.g., "test_started")
            data: Dict to be JSON-serialized as event data

        Returns:
            True if event was queued, False if no connection found
        """
        with self._lock:
            conn = self._connections.get(user_id)
            if not conn:
                return False

            try:
                conn["queue"].put_nowait(
                    {
                        "event": event,
                        "data": json.dumps(data),
                    }
                )
                return True
            except queue.Full:
                return False

    def get_connected_devices(self):
        """Get list of all connected device_ids."""
        with self._lock:
            return [
                {"user_id": uid, "device_id": info["device_id"]}
                for uid, info in self._connections.items()
            ]


# Singleton instance
connection_manager = ESP32ConnectionManager()
