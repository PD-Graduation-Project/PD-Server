import json
import queue
import threading
import time

import redis
from loguru import logger

from config import Config


class ESP32ConnectionManager:
    """
    Redis-backed manager for tracking active ESP32 SSE connections.
    Uses Redis pub/sub to deliver events to the correct device across multiple processes.
    Connection state is stored in Redis so it works across multiple workers.
    """

    CONNECTION_KEY_PREFIX = "esp32:conn:"
    CONNECTION_TTL = 60

    def __init__(self):
        self._redis_url = Config.REDIS_URL
        self._lock = threading.Lock()
        self._local_listeners = {}

    def _get_redis_client(self):
        """Get a new Redis client instance."""
        return redis.from_url(self._redis_url, decode_responses=True)

    def _conn_key(self, user_id):
        return f"{self.CONNECTION_KEY_PREFIX}{user_id}"

    def add(self, user_id, device_id, message_queue):
        """
        Register an ESP32 SSE connection for a user.
        Subscribes to a Redis channel for this user and starts a listener thread.

        If a connection already exists for this user, it will be replaced after
        proper cleanup of the old connection.
        """
        channel = f"esp32:user:{user_id}"

        try:
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
                self._local_listeners[user_id] = {
                    "device_id": device_id,
                    "redis_client": redis_client,
                    "pubsub": pubsub,
                    "thread": listener_thread,
                    "stop_event": stop_event,
                    "queue": message_queue,
                }

            redis_client.hset(
                self._conn_key(user_id),
                mapping={
                    "device_id": device_id,
                    "connected": "1",
                },
            )
            redis_client.expire(self._conn_key(user_id), self.CONNECTION_TTL)

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
            conn = self._local_listeners.pop(user_id, None)
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
                except Exception as e:
                    logger.error(f"ESP32 disconnect error for user={user_id}: {e}")
            else:
                logger.warning(
                    f"ESP32 disconnect: no local listener for user={user_id}"
                )

        try:
            redis_client = self._get_redis_client()
            redis_client.delete(self._conn_key(user_id))
            redis_client.close()
        except Exception as e:
            logger.error(f"ESP32 redis disconnect error for user={user_id}: {e}")

        logger.info(f"ESP32 disconnected: user={user_id}")

    def get(self, user_id):
        """Get connection info for a user's ESP32."""
        try:
            redis_client = self._get_redis_client()
            data = redis_client.hgetall(self._conn_key(user_id))
            redis_client.close()
            if data and data.get("connected") == "1":
                return {
                    "device_id": data.get("device_id"),
                    "connected": True,
                }
            return None
        except Exception as e:
            logger.error(f"ESP32 get connection failed for user={user_id}: {e}")
            return None

    def is_connected(self, user_id):
        """Check if user has an active ESP32 connection."""
        try:
            redis_client = self._get_redis_client()
            connected = redis_client.hget(self._conn_key(user_id), "connected")
            redis_client.close()
            return connected == "1"
        except Exception as e:
            logger.error(f"ESP32 is_connected failed for user={user_id}: {e}")
            return False

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
        if not self.is_connected(user_id):
            logger.warning(
                f"ESP32 send_event: no connection for user={user_id}, event='{event}' dropped"
            )
            return False

        channel = f"esp32:user:{user_id}"
        message = json.dumps({"event": event, "data": data})

        try:
            redis_client = self._get_redis_client()
            redis_client.publish(channel, message)
            redis_client.close()
            logger.info(f"ESP32 event sent: '{event}' to user={user_id}")
            return True
        except Exception as e:
            logger.error(f"ESP32 send_event failed for user={user_id}: {e}")
            return False

    def get_connected_devices(self):
        """Get list of all connected device user IDs."""
        try:
            redis_client = self._get_redis_client()
            keys = redis_client.keys(f"{self.CONNECTION_KEY_PREFIX}*")
            result = []
            for key in keys:
                try:
                    user_id = int(key.replace(self.CONNECTION_KEY_PREFIX, ""))
                except ValueError:
                    continue
                data = redis_client.hgetall(key)
                if data and data.get("connected") == "1":
                    result.append(
                        {
                            "user_id": user_id,
                            "device_id": data.get("device_id"),
                        }
                    )
            redis_client.close()
            return result
        except Exception as e:
            logger.error(f"ESP32 get_connected_devices failed: {e}")
            return []

    def _heartbeat(self, user_id):
        """Refresh connection TTL (called by heartbeat endpoint)."""
        try:
            redis_client = self._get_redis_client()
            redis_client.expire(self._conn_key(user_id), self.CONNECTION_TTL)
            redis_client.close()
        except Exception:
            pass


connection_manager = ESP32ConnectionManager()
