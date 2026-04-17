import json
import queue
import threading

import redis
from loguru import logger

from config import Config


class MobileConnectionManager:
    """
    Redis-backed manager for tracking active mobile SSE connections.
    Uses Redis pub/sub to deliver events to the correct user across multiple processes.
    Connection state is stored in Redis so it works across multiple workers.
    """

    CONNECTION_KEY_PREFIX = "mobile:conn:"
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

    def add(self, user_id, message_queue):
        """
        Register a mobile SSE connection for a user.
        Subscribes to a Redis channel for this user and starts a listener thread.
        """
        channel = f"mobile:user:{user_id}"

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
                    "redis_client": redis_client,
                    "pubsub": pubsub,
                    "thread": listener_thread,
                    "stop_event": stop_event,
                    "queue": message_queue,
                }

            redis_client.hset(
                self._conn_key(user_id),
                mapping={
                    "connected": "1",
                },
            )
            redis_client.expire(self._conn_key(user_id), self.CONNECTION_TTL)

            logger.info(f"Mobile SSE connected: user={user_id}")

        except Exception as e:
            logger.error(f"Mobile SSE connect failed for user={user_id}: {e}")
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
                                f"Mobile event queued: '{event}' for user={user_id}"
                            )
                        except queue.Full:
                            logger.warning(
                                f"Mobile event queue full for user={user_id}, dropping message"
                            )
                        except json.JSONDecodeError:
                            logger.error(
                                f"Mobile invalid JSON in Redis message for user={user_id}"
                            )
                except Exception as e:
                    if not stop_event.is_set():
                        logger.debug(f"Mobile pubsub error for user={user_id}: {e}")
                    continue
        except Exception as e:
            logger.error(f"Mobile Redis listener crashed for user={user_id}: {e}")

    def remove(self, user_id):
        """Remove a mobile SSE connection and unsubscribe from Redis channel."""
        channel = f"mobile:user:{user_id}"

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
                    logger.error(f"Mobile disconnect error for user={user_id}: {e}")
            else:
                logger.warning(
                    f"Mobile disconnect: no local listener for user={user_id}"
                )

        try:
            redis_client = self._get_redis_client()
            redis_client.delete(self._conn_key(user_id))
            redis_client.close()
        except Exception as e:
            logger.error(f"Mobile redis disconnect error for user={user_id}: {e}")

        logger.info(f"Mobile SSE disconnected: user={user_id}")

    def is_connected(self, user_id):
        """Check if user has an active mobile SSE connection."""
        try:
            redis_client = self._get_redis_client()
            connected = redis_client.hget(self._conn_key(user_id), "connected")
            redis_client.close()
            return connected == "1"
        except Exception as e:
            logger.error(f"Mobile is_connected failed for user={user_id}: {e}")
            return False

    def send_event(self, user_id, event, data):
        """
        Send an SSE event to a user's connected mobile app via Redis pub/sub.

        Args:
            user_id: The user whose mobile app should receive the event
            event: SSE event name (e.g., "next_subtest", "device_connected")
            data: Dict to be JSON-serialized as event data

        Returns:
            True if event was published, False if no connection or Redis error
        """
        if not self.is_connected(user_id):
            logger.warning(
                f"Mobile send_event: no connection for user={user_id}, event='{event}' dropped"
            )
            return False

        channel = f"mobile:user:{user_id}"
        message = json.dumps({"event": event, "data": data})

        try:
            redis_client = self._get_redis_client()
            redis_client.publish(channel, message)
            redis_client.close()
            logger.info(f"Mobile event sent: '{event}' to user={user_id}")
            return True
        except Exception as e:
            logger.error(f"Mobile send_event failed for user={user_id}: {e}")
            return False

    def _heartbeat(self, user_id):
        """Refresh connection TTL (called by heartbeat endpoint)."""
        try:
            redis_client = self._get_redis_client()
            redis_client.expire(self._conn_key(user_id), self.CONNECTION_TTL)
            redis_client.close()
        except Exception:
            pass


mobile_connection_manager = MobileConnectionManager()
