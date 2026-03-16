import json
import queue
import threading

import redis
from loguru import logger

from config import Config


class ESP32ConnectionManager:
    """
    Redis-backed manager for tracking active ESP32 SSE connections.
    Uses Redis pub/sub to deliver events to the correct device across multiple processes.
    """

    def __init__(self):
        self._redis_url = Config.REDIS_URL
        self._connections = {}
        self._lock = threading.Lock()

    def _get_redis_client(self):
        """Get a new Redis client instance."""
        return redis.from_url(self._redis_url, decode_responses=True)

    def add(self, user_id, device_id, message_queue):
        """
        Register an ESP32 SSE connection for a user.
        Subscribes to a Redis channel for this user and starts a listener thread.
        """
        channel = f"esp32:user:{user_id}"

        try:
            # IMPORTANT: Keep redis_client alive - if it goes out of scope,
            # the connection is closed and pubsub stops working
            redis_client = self._get_redis_client()
            pubsub = redis_client.pubsub()
            pubsub.subscribe(channel)

            stop_event = threading.Event()
            listener_thread = threading.Thread(
                target=self._listen_to_redis,
                args=(pubsub, message_queue, user_id, stop_event),
                daemon=True,
            )
            listener_thread.start()

            with self._lock:
                self._connections[user_id] = {
                    "device_id": device_id,
                    "redis_client": redis_client,  # Keep reference to prevent GC
                    "pubsub": pubsub,
                    "thread": listener_thread,
                    "stop_event": stop_event,
                    "queue": message_queue,
                }

            logger.info(f"ESP32 connected: device={device_id} user={user_id}")

        except Exception as e:
            logger.error(f"ESP32 connect failed for user={user_id}: {e}")
            raise

    def _listen_to_redis(self, pubsub, local_queue, user_id, stop_event):
        """Background thread that listens to Redis pub/sub and forwards to local queue."""
        try:
            while not stop_event.is_set():
                try:
                    message = pubsub.get_message(timeout=1.0)
                    if message and message["type"] == "message":
                        try:
                            data = json.loads(message["data"])
                            event = data.get("event")
                            event_data = data.get("data")
                            local_queue.put_nowait(
                                {"event": event, "data": json.dumps(event_data)}
                            )
                            logger.debug(
                                f"ESP32 event queued: '{event}' for user={user_id}"
                            )
                        except queue.Full:
                            logger.warning(
                                f"ESP32 event queue full for user={user_id}, dropping message"
                            )
                        except json.JSONDecodeError:
                            logger.error(
                                f"ESP32 invalid JSON in Redis message for user={user_id}"
                            )
                except Exception as e:
                    if not stop_event.is_set():
                        logger.debug(f"ESP32 pubsub error for user={user_id}: {e}")
                    continue
        except Exception as e:
            logger.error(f"ESP32 Redis listener crashed for user={user_id}: {e}")

    def remove(self, user_id):
        """Remove an ESP32 SSE connection and unsubscribe from Redis channel."""
        channel = f"esp32:user:{user_id}"

        with self._lock:
            conn = self._connections.pop(user_id, None)
            if conn:
                stop_event = conn.get("stop_event")
                if stop_event:
                    stop_event.set()
                try:
                    conn["pubsub"].unsubscribe(channel)
                    conn["pubsub"].close()
                    redis_client = conn.get("redis_client")
                    if redis_client:
                        redis_client.close()
                    logger.info(f"ESP32 disconnected: user={user_id}")
                except Exception as e:
                    logger.error(f"ESP32 disconnect error for user={user_id}: {e}")
            else:
                logger.warning(
                    f"ESP32 disconnect: no connection found for user={user_id}"
                )

    def get(self, user_id):
        """Get connection info for a user's ESP32."""
        with self._lock:
            conn = self._connections.get(user_id)
            if conn:
                stop_event = conn.get("stop_event")
                is_running = stop_event is not None and not stop_event.is_set()
                return {
                    "device_id": conn["device_id"],
                    "connected": is_running,
                }
            return None

    def is_connected(self, user_id):
        """Check if user has an active ESP32 connection."""
        with self._lock:
            conn = self._connections.get(user_id)
            if conn is None:
                return False
            stop_event = conn.get("stop_event")
            return stop_event is not None and not stop_event.is_set()

    def send_event(self, user_id, event, data):
        """
        Send an SSE event to a user's connected ESP32 device via Redis pub/sub.

        Args:
            user_id: The user whose ESP32 should receive the event
            event: SSE event name (e.g., "test_started")
            data: Dict to be JSON-serialized as event data

        Returns:
            True if event was published, False if no connection or Redis error
        """
        channel = f"esp32:user:{user_id}"
        message = json.dumps({"event": event, "data": data})

        with self._lock:
            conn = self._connections.get(user_id)
            if not conn:
                logger.warning(
                    f"ESP32 send_event: no connection for user={user_id}, event='{event}' dropped"
                )
                return False

        try:
            redis_client = self._get_redis_client()
            redis_client.publish(channel, message)
            logger.info(f"ESP32 event sent: '{event}' to user={user_id}")
            return True
        except Exception as e:
            logger.error(f"ESP32 send_event failed for user={user_id}: {e}")
            return False

    def get_connected_devices(self):
        """Get list of all connected device user IDs."""
        with self._lock:
            result = []
            for uid, info in self._connections.items():
                stop_event = info.get("stop_event")
                if stop_event and not stop_event.is_set():
                    result.append({"user_id": uid, "device_id": info["device_id"]})
            return result


connection_manager = ESP32ConnectionManager()
