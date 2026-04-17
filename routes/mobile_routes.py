import json
import queue
from datetime import datetime

from flask import Blueprint, Response, g, jsonify, request, stream_with_context
from loguru import logger

from middleware.authenticate import authenticate
from models.database import db
from models.user import User
from utils.mobile_connection_manager import mobile_connection_manager

mobile_bp = Blueprint("mobile", __name__, url_prefix="/api")

SSE_HEARTBEAT_INTERVAL = 15


@mobile_bp.route("/stream", methods=["GET"])
@authenticate
def stream():
    """
    SSE endpoint for mobile app.
    Mobile connects and listens for real-time events.
    Connection stays open until client disconnects.
    """
    user_id = g.user_id

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    logger.info(f"Mobile SSE stream connected: user={user_id}")

    msg_queue = queue.Queue(maxsize=100)

    mobile_connection_manager.add(user_id, msg_queue)

    db.session.expire_all()

    def event_stream():
        try:
            yield format_sse(event="connected", data={"user_id": user_id})

            while True:
                try:
                    msg = msg_queue.get(timeout=SSE_HEARTBEAT_INTERVAL)
                    logger.info(
                        f"Mobile event forwarded: '{msg['event']}' to user={user_id}"
                    )
                    yield format_sse(event=msg["event"], data=msg["data"])
                except queue.Empty:
                    yield format_sse(
                        event="heartbeat",
                        data={"timestamp": datetime.utcnow().isoformat()},
                    )
        except GeneratorExit:
            pass
        finally:
            logger.info(f"Mobile SSE stream disconnected: user={user_id}")
            mobile_connection_manager.remove(user_id)

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )


@mobile_bp.route("/stream/heartbeat", methods=["POST"])
@authenticate
def heartbeat():
    """Refresh mobile SSE connection TTL."""
    mobile_connection_manager._heartbeat(g.user_id)
    return jsonify({"success": True}), 200


def format_sse(event, data):
    """Format data as SSE event string."""
    if isinstance(data, dict):
        data = json.dumps(data)
    return f"event: {event}\ndata: {data}\n\n"
