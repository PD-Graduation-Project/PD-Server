import json
import queue
import threading
from datetime import datetime

from loguru import logger
from redis import Redis

from config import Config


class ESP32ConnectionManager:
    """
    Redis-backed manager for tracking active ESP32 SSE connections.
    Uses Redis pub/sub to deliver events to the correct device across multiple processes.
    Connection state is stored in Redis so it works across multiple workers.
    """

    CONNECTION_KEY_PREFIX = "esp32:conn:"
    CONNECTION_TTL = 90  # longer than heartbeat interval (60s) to avoid flapping

    def __init__(self):
        self._lock = threading.Lock()
        self._local_listeners: dict = {}

    def _redis(self) -> Redis:
        """Get a client from the shared pool - no new connection each time."""
        return Redis(connection_pool=Config.redis_pool())

    def _conn_key(self, user_id):
        return f"{self.CONNECTION_KEY_PREFIX}{user_id}"

    def add(self, user_id, device_id, message_queue):
        """
        Register an ESP32 SSE connection for a user.
        Subscribes to a Redis channel for this user and starts a listener thread.

        If a connection already exists for this user, it will be replaced after
        proper cleanup of the old connection.
        """
        # Clean up any existing connection for this user first
        self._cleanup_local(user_id)

        channel = f"esp32:user:{user_id}"
        r = self._redis()
        pubsub = r.pubsub(ignore_subscribe_messages=True)
        pubsub.subscribe(channel)

        stop_event = threading.Event()
        thread = threading.Thread(
            target=self._listen,
            args=(pubsub, message_queue, user_id, stop_event),
            daemon=True,
            name=f"esp32-listener-{user_id}",
        )
        thread.start()

        with self._lock:
            self._local_listeners[user_id] = {
                "device_id": device_id,
                "pubsub": pubsub,
                "thread": thread,
                "stop_event": stop_event,
                "queue": message_queue,
            }

        r.hset(
            self._conn_key(user_id),
            mapping={
                "device_id": device_id,
                "connected": "1",
            },
        )
        r.expire(self._conn_key(user_id), self.CONNECTION_TTL)

        logger.info(f"ESP32 connected: device={device_id} user={user_id}")

    def _listen(self, pubsub, local_queue, user_id, stop_event):
        """Background thread that listens to Redis pub/sub and forwards to local queue."""
        try:
            while not stop_event.is_set():
                message = pubsub.get_message(timeout=1.0)
                if not message:
                    continue

                try:
                    data = json.loads(message["data"])
                    local_queue.put_nowait(
                        {"event": data["event"], "data": json.dumps(data["data"])}
                    )
                except queue.Full:
                    logger.warning(f"ESP32 queue full for user={user_id}, dropping message")
                except (json.JSONDecodeError, KeyError) as e:
                    logger.error(f"ESP32 bad message for user={user_id}: {e}")
        except Exception as e:
            if not stop_event.is_set():
                logger.error(f"ESP32 listener crashed for user={user_id}: {e}")

    def _cleanup_local(self, user_id):
        """Stop listener thread and pubsub for a user, if any."""
        with self._lock:
            conn = self._local_listeners.pop(user_id, None)
            if not conn:
                return

            conn["stop_event"].set()
            try:
                conn["pubsub"].unsubscribe()
                conn["pubsub"].close()
            except Exception:
                pass

    def remove(self, user_id):
        """Remove an ESP32 SSE connection and unsubscribe from Redis channel."""
        # Get device_id before cleanup for logging
        with self._lock:
            conn = self._local_listeners.get(user_id)
            device_id = conn.get("device_id") if conn else None

        self._cleanup_local(user_id)

        r = self._redis()
        r.delete(self._conn_key(user_id))

        logger.info(f"ESP32 disconnected: device={device_id or 'unknown'} user={user_id}")

    def get(self, user_id):
        """Get connection info for a user's ESP32."""
        try:
            r = self._redis()
            data = r.hgetall(self._conn_key(user_id))
            if data and data.get("connected") == "1":
                return {
                    "device_id": data.get("device_id"),
                    "connected": True,
                }
            return None
        except Exception as e:
            logger.error(f"ESP32 get connection failed for user={user_id}: {e}")
            return None

    def is_connected(self, user_id) -> bool:
        """Check if user has an active ESP32 connection."""
        try:
            r = self._redis()
            return r.hget(self._conn_key(user_id), "connected") == "1"
        except Exception:
            return False

    def send_event(self, user_id, event, data) -> bool:
        """
        Send an SSE event to a user's connected ESP32 device via Redis pub/sub.

        Args:
            user_id: The user whose ESP32 should receive the event
            event: SSE event name (e.g., "test_started")
            data: Dict to be JSON-serialized as event data

        Returns:
            True if event was published and had listeners, False otherwise
        """
        channel = f"esp32:user:{user_id}"
        message = json.dumps({"event": event, "data": data})

        try:
            r = self._redis()
            receivers = r.publish(channel, message)
            if receivers == 0:
                logger.warning(
                    f"ESP32 event '{event}' for user={user_id} - no listeners"
                )
                return False
            logger.info(f"ESP32 event sent: '{event}' to user={user_id}")
            return True
        except Exception as e:
            logger.error(f"ESP32 send_event failed for user={user_id}: {e}")
            return False

    def get_connected_devices(self) -> list:
        """Get list of all connected device user IDs."""
        try:
            r = self._redis()
            keys = r.keys(f"{self.CONNECTION_KEY_PREFIX}*")
            result = []
            for key in keys:
                data = r.hgetall(key)
                if data.get("connected") == "1":
                    try:
                        user_id = int(key.replace(self.CONNECTION_KEY_PREFIX, ""))
                        result.append(
                            {"user_id": user_id, "device_id": data.get("device_id")}
                        )
                    except ValueError:
                        pass
            return result
        except Exception as e:
            logger.error(f"ESP32 get_connected_devices failed: {e}")
            return []

    def heartbeat(self, user_id):
        """Refresh connection TTL (called by heartbeat endpoint)."""
        try:
            r = self._redis()
            r.expire(self._conn_key(user_id), self.CONNECTION_TTL)
        except Exception:
            pass


connection_manager = ESP32ConnectionManager()
