import json
import logging
import queue
import threading
from functools import wraps

import redis

from config import Config

logger = logging.getLogger(__name__)


def debug_log(func):
    """Decorator to add debug logging to connection manager methods."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        logger.debug(
            f"[DEBUG] {func.__name__} called with args={args[1:]}, kwargs={kwargs}"
        )
        return result

    return wrapper


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
        logger.info(f"[ESP32 CONNECT] User {user_id} device {device_id} connecting...")
        logger.debug(f"[ESP32 CONNECT] Subscribing to Redis channel: {channel}")

        try:
            # IMPORTANT: Keep redis_client alive - if it goes out of scope,
            # the connection is closed and pubsub stops working
            redis_client = self._get_redis_client()
            pubsub = redis_client.pubsub()
            pubsub.subscribe(channel)
            logger.info(
                f"[ESP32 CONNECTED] Subscribed to Redis channel: {channel} for device_id={device_id}"
            )

            # Use threading.Event for proper stop signal
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

            logger.info(
                f"[ESP32 CONNECT] Active connections: {list(self._connections.keys())}"
            )

        except Exception as e:
            logger.error(
                f"[ESP32 CONNECT ERROR] Failed to subscribe to Redis channel {channel}: {e}"
            )
            raise

    def _listen_to_redis(self, pubsub, local_queue, user_id, stop_event):
        """Background thread that listens to Redis pub/sub and forwards to local queue."""
        logger.debug(f"[REDIS LISTENER] Starting listener for user {user_id}")
        try:
            while not stop_event.is_set():
                try:
                    message = pubsub.get_message(timeout=1.0)
                    if message and message["type"] == "message":
                        logger.debug(f"[REDIS RECEIVED] Raw message: {message['data']}")
                        try:
                            data = json.loads(message["data"])
                            event = data.get("event")
                            event_data = data.get("data")
                            logger.info(
                                f"[EVENT RECEIVED] User {user_id} received event: '{event}' with data: {event_data}"
                            )
                            local_queue.put_nowait(
                                {"event": event, "data": json.dumps(event_data)}
                            )
                            logger.debug(
                                f"[EVENT QUEUED] Event '{event}' queued for user {user_id}"
                            )
                        except queue.Full:
                            logger.warning(
                                f"[EVENT QUEUE FULL] Local queue full for user {user_id}, dropping message"
                            )
                        except json.JSONDecodeError:
                            logger.error(
                                f"[EVENT PARSE ERROR] Invalid JSON in Redis message: {message['data']}"
                            )
                except Exception as e:
                    if not stop_event.is_set():
                        logger.debug(f"[REDIS LISTENER] PubSub get_message error: {e}")
                    continue
            logger.debug(f"[REDIS LISTENER] Listener stopped for user {user_id}")
        except Exception as e:
            logger.error(
                f"[REDIS LISTENER ERROR] Error in Redis listener thread for user {user_id}: {e}"
            )

    def remove(self, user_id):
        """Remove an ESP32 SSE connection and unsubscribe from Redis channel."""
        channel = f"esp32:user:{user_id}"
        logger.info(f"[ESP32 DISCONNECT] User {user_id} disconnecting...")

        with self._lock:
            conn = self._connections.pop(user_id, None)
            if conn:
                # Signal the listener thread to stop
                stop_event = conn.get("stop_event")
                if stop_event:
                    stop_event.set()
                    logger.debug(
                        f"[ESP32 DISCONNECT] Stop event set for user {user_id}"
                    )
                try:
                    conn["pubsub"].unsubscribe(channel)
                    conn["pubsub"].close()
                    # Close the redis client connection
                    redis_client = conn.get("redis_client")
                    if redis_client:
                        redis_client.close()
                    logger.info(
                        f"[ESP32 DISCONNECTED] Unsubscribed from Redis channel: {channel}"
                    )
                except Exception as e:
                    logger.error(
                        f"[ESP32 DISCONNECT ERROR] Error unsubscribing from {channel}: {e}"
                    )
            else:
                logger.warning(
                    f"[ESP32 DISCONNECT] No connection found for user {user_id}"
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

        logger.info(
            f"[EVENT SEND] Attempting to send event '{event}' to user {user_id}"
        )
        logger.debug(f"[EVENT SEND] Channel: {channel}, message: {message}")

        with self._lock:
            conn = self._connections.get(user_id)

            if not conn:
                logger.warning(
                    f"[EVENT SEND FAILED] No active connection for user {user_id}, event '{event}' not sent"
                )
                return False
            logger.debug(
                f"[EVENT SEND] Found active connection for user {user_id}: {conn['device_id']}"
            )

        try:
            redis_client = self._get_redis_client()
            subscribers = redis_client.publish(channel, message)
            logger.info(
                f"[EVENT PUBLISHED] Event '{event}' published to channel {channel} (subscribers: {subscribers})"
            )
            return True
        except Exception as e:
            logger.error(
                f"[EVENT SEND ERROR] Failed to publish event to {channel}: {e}"
            )
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
