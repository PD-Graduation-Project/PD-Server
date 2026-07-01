import json
import queue
import threading
import time

from loguru import logger
from redis import Redis

from config import Config


class ESP32ConnectionManager:
    """
    Redis-backed manager for tracking active ESP32 SSE connections.
    Uses Redis pub/sub to deliver events to the correct device across multiple processes.
    Connection state is stored in Redis so it works across multiple workers.

    The _listen thread self-heals: if the pub/sub connection drops (exception)
    or looks stale (health check), it recreates the subscription transparently.
    Only after all retries are exhausted does it signal the SSE stream to close.
    """

    CONNECTION_KEY_PREFIX = "esp32:conn:"
    CONNECTION_TTL = 90

    _RESUBSCRIBE_DELAYS = [0.5, 1, 2, 4, 8]
    _HEALTH_CHECK_INTERVAL = 30

    def __init__(self):
        self._lock = threading.Lock()
        self._local_listeners: dict = {}

    def _redis(self) -> Redis:
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
            mapping={"device_id": device_id, "connected": "1"},
        )
        r.expire(self._conn_key(user_id), self.CONNECTION_TTL)

        logger.info(f"ESP32 connected: device={device_id} user={user_id}")

    def _listen(self, pubsub, local_queue, user_id, stop_event):
        last_activity = time.monotonic()

        while not stop_event.is_set():
            # Periodic health check — catches silent connection death
            if time.monotonic() - last_activity >= self._HEALTH_CHECK_INTERVAL:
                if not self._connection_healthy(pubsub):
                    pubsub = self._resubscribe(
                        user_id, pubsub, local_queue, stop_event
                    )
                    if pubsub is None:
                        break
                    last_activity = time.monotonic()
                    continue
                last_activity = time.monotonic()

            # Read next message
            try:
                message = pubsub.get_message(timeout=1.0)
            except Exception as e:
                if stop_event.is_set():
                    break
                logger.warning(
                    f"ESP32 listener: pub/sub error for user={user_id}: {e}"
                )
                pubsub = self._resubscribe(
                    user_id, pubsub, local_queue, stop_event
                )
                if pubsub is None:
                    break
                last_activity = time.monotonic()
                continue

            if not message:
                continue

            last_activity = time.monotonic()

            try:
                data = json.loads(message["data"])
                local_queue.put_nowait(
                    {"event": data["event"], "data": json.dumps(data["data"])}
                )
            except queue.Full:
                logger.warning(
                    f"ESP32 queue full for user={user_id}, dropping message"
                )
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"ESP32 bad message for user={user_id}: {e}")

    def _connection_healthy(self, pubsub) -> bool:
        try:
            conn = getattr(pubsub, "connection", None)
            if conn is None:
                return False
            return conn.is_connected
        except Exception:
            return False

    def _resubscribe(self, user_id, old_pubsub, local_queue, stop_event):
        """Try to recreate the pub/sub subscription with bounded backoff.
        Returns the new pubsub on success, None if all retries failed (in which
        case a __listener_died sentinel is pushed to the queue)."""
        for attempt, delay in enumerate(self._RESUBSCRIBE_DELAYS):
            if stop_event.is_set():
                return None
            time.sleep(delay)
            try:
                r = self._redis()
                new_pubsub = r.pubsub(ignore_subscribe_messages=True)
                new_pubsub.subscribe(f"esp32:user:{user_id}")

                with self._lock:
                    conn = self._local_listeners.get(user_id)
                    if conn and conn.get("queue") is local_queue:
                        old_pubsub.unsubscribe()
                        old_pubsub.close()
                        conn["pubsub"] = new_pubsub

                logger.info(
                    f"ESP32 listener resubscribed for user={user_id} "
                    f"(attempt {attempt + 1}/{len(self._RESUBSCRIBE_DELAYS)})"
                )
                return new_pubsub
            except Exception as e:
                logger.warning(
                    f"ESP32 resubscribe attempt {attempt + 1} failed for "
                    f"user={user_id}: {e}"
                )

        logger.error(
            f"ESP32 listener: all resubscribe attempts exhausted for "
            f"user={user_id}, giving up"
        )
        try:
            local_queue.put_nowait({"event": "__listener_died", "data": "{}"})
        except queue.Full:
            pass
        return None

    def _cleanup_local(self, user_id):
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

    def remove(self, user_id, message_queue=None):
        """
        Remove an ESP32 SSE connection.

        If message_queue is provided, only removes the connection if the stored
        queue matches — this prevents an old SSE stream's finally block from
        destroying a newer stream's connection (race condition on reconnect).
        """
        with self._lock:
            conn = self._local_listeners.get(user_id)
            if not conn:
                return
            if message_queue is not None and conn.get("queue") is not message_queue:
                return
            conn = self._local_listeners.pop(user_id)
            device_id = conn.get("device_id")

            conn["stop_event"].set()
            try:
                conn["pubsub"].unsubscribe()
                conn["pubsub"].close()
            except Exception:
                pass

        r = self._redis()
        r.delete(self._conn_key(user_id))

        logger.info(
            f"ESP32 disconnected: device={device_id or 'unknown'} user={user_id}"
        )

    def get(self, user_id):
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
        try:
            r = self._redis()
            return r.hget(self._conn_key(user_id), "connected") == "1"
        except Exception:
            return False

    def send_event(self, user_id, event, data) -> bool:
        channel = f"esp32:user:{user_id}"
        message = json.dumps({"event": event, "data": data})

        try:
            r = self._redis()
            receivers = r.publish(channel, message)
            if receivers == 0:
                with self._lock:
                    conn = self._local_listeners.get(user_id)
                if conn and not conn["thread"].is_alive():
                    logger.warning(
                        f"ESP32 event '{event}' for user={user_id} — "
                        f"listener thread is dead"
                    )
                else:
                    logger.warning(
                        f"ESP32 event '{event}' for user={user_id} — "
                        f"no listeners"
                    )
                return False
            logger.info(f"ESP32 event sent: '{event}' to user={user_id}")
            return True
        except Exception as e:
            logger.error(f"ESP32 send_event failed for user={user_id}: {e}")
            return False

    def get_connected_devices(self) -> list:
        try:
            r = self._redis()
            result = []
            for key in r.scan_iter(f"{self.CONNECTION_KEY_PREFIX}*"):
                data = r.hgetall(key)
                if data.get("connected") == "1":
                    try:
                        user_id = int(
                            key.replace(self.CONNECTION_KEY_PREFIX, "")
                        )
                        result.append(
                            {
                                "user_id": user_id,
                                "device_id": data.get("device_id"),
                            }
                        )
                    except ValueError:
                        pass
            return result
        except Exception as e:
            logger.error(f"ESP32 get_connected_devices failed: {e}")
            return []

    def heartbeat(self, user_id):
        try:
            r = self._redis()
            r.expire(self._conn_key(user_id), self.CONNECTION_TTL)
        except Exception:
            pass


connection_manager = ESP32ConnectionManager()
