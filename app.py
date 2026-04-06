from gevent import monkey

monkey.patch_all()

import logging
import os
import re
import sys
import threading
import time
import uuid

from flask import Flask, abort, g, jsonify, request
from flask_cors import CORS
from flask_migrate import Migrate
from loguru import logger

from config import Config
from models.database import db

# ── ANSI helpers ──────────────────────────────────────────────────────────────
ANSI_ESCAPE = re.compile(r"\033\[[0-9;]*m")

RESET = "\033[0m"
GREEN = "\033[32m"
CYAN = "\033[36m"
DIM = "\033[2m"
DIM_YELLOW = "\033[2;33m"  # body / form text

LEVEL_COLORS = {
    "TRACE": "\033[37m",
    "DEBUG": "\033[34m",
    "INFO": "\033[1m",
    "SUCCESS": "\033[32m",
    "WARNING": "\033[33m",
    "ERROR": "\033[31m",
    "CRITICAL": "\033[41m",
}

METHOD_COLORS = {
    "GET": "\033[36m",
    "POST": "\033[32m",
    "PUT": "\033[34m",
    "PATCH": "\033[35m",
    "DELETE": "\033[31m",
}


def strip_ansi(s: str) -> str:
    return ANSI_ESCAPE.sub("", s)


def get_method_color(method: str) -> str:
    return METHOD_COLORS.get(method.upper(), "\033[37m")


def get_status_color(code: int) -> str:
    if 200 <= code < 300:
        return "\033[32m"
    if 300 <= code < 500:
        return "\033[33m"
    return "\033[31m"


# ── Log record renderer ───────────────────────────────────────────────────────
def _build_record_str(record: dict, color: bool) -> str:
    request_id = record["extra"].get("request_id")
    level = record["level"].name
    ts = record["time"].strftime("%Y-%m-%d %H:%M:%S")
    msg = record["message"] if color else strip_ansi(record["message"])

    if color:
        level_c = LEVEL_COLORS.get(level, "")
        ts_str = GREEN + ts + RESET
        level_str = level_c + f"{level:<8}" + RESET
        if request_id:
            id_str = CYAN + request_id + RESET
            return f"{ts_str} | {level_str} | {id_str} | {msg}\n"
        loc = CYAN + f"{record['name']}:{record['function']}:{record['line']}" + RESET
        return f"{ts_str} | {level_str} | {loc} - {msg}\n"
    else:
        if request_id:
            return f"{ts} | {level:<8} | {request_id} | {msg}\n"
        return f"{ts} | {level:<8} | {record['name']}:{record['function']}:{record['line']} - {msg}\n"


# ── Sinks ─────────────────────────────────────────────────────────────────────
def console_sink(message) -> None:
    sys.stderr.write(_build_record_str(message.record, color=True))
    sys.stderr.flush()


_log_file = None
_log_file_date: str | None = None
_log_lock = threading.Lock()


def file_sink(message) -> None:
    global _log_file, _log_file_date
    from datetime import date

    today = date.today().isoformat()
    with _log_lock:
        if _log_file_date != today:
            if _log_file:
                _log_file.close()
            os.makedirs("logs", exist_ok=True)
            _log_file = open(f"logs/app_{today}.log", "a", encoding="utf-8")
            _log_file_date = today
        _log_file.write(_build_record_str(message.record, color=False))  # type: ignore[union-attr]
        _log_file.flush()  # type: ignore[union-attr]


# ── Logger init ───────────────────────────────────────────────────────────────
logger.remove()
logger.add(console_sink, level="DEBUG", format="{message}")
logger.add(file_sink, level="DEBUG", format="{message}")

# Keep werkzeug startup messages but suppress per-request access lines
_wz_logger = logging.getLogger("werkzeug")
_wz_logger.setLevel(logging.INFO)


class _SuppressAccessLogs(logging.Filter):
    """Drop werkzeug's '127.0.0.1 - - [date] "GET /" 200 -' lines."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not (record.levelno == logging.INFO and " - - [" in msg and '"' in msg)


_wz_logger.addFilter(_SuppressAccessLogs())


# ── App factory ───────────────────────────────────────────────────────────────
def create_app(config_override=None):
    app = Flask(__name__)
    app.config.from_object(Config)

    if config_override:
        app.config.update(config_override)

    Config.init_app(app)

    db.init_app(app)
    Migrate(app, db)

    CORS(app)

    @app.before_request
    def check_ip():
        if Config.ALLOWED_IPS and request.remote_addr not in Config.ALLOWED_IPS:
            abort(403)

    @app.before_request
    def log_request():
        try:
            g.start_time = time.time()
            g.request_id = str(uuid.uuid4())[:8]
            method_color = get_method_color(request.method)
            logger.bind(request_id=g.request_id).info(
                "→ " + method_color + request.method + RESET + " " + request.path
            )
            body = request.get_data(as_text=True)
            if body:
                logger.bind(request_id=g.request_id).debug(
                    "  Body: " + DIM_YELLOW + body[:500] + RESET
                )
            elif request.form:
                logger.bind(request_id=g.request_id).debug(
                    "  Form: " + DIM_YELLOW + str(dict(request.form)) + RESET
                )
        except Exception:
            pass

    @app.after_request
    def log_response(response):
        try:
            duration = (time.time() - g.get("start_time", time.time())) * 1000
            status_color = get_status_color(response.status_code)
            method_color = get_method_color(request.method)
            logger.bind(request_id=g.get("request_id", "N/A")).info(
                "← "
                + method_color
                + request.method
                + RESET
                + " "
                + request.path
                + " "
                + status_color
                + str(response.status_code)
                + RESET
                + " "
                + DIM
                + f"{duration:.2f}ms"
                + RESET
            )
            response.headers["X-Request-ID"] = g.get("request_id", "")
        except Exception:
            pass
        return response

    from routes.auth_routes import auth_bp
    from routes.esp32_devices_routes import esp32_devices_bp
    from routes.esp32_routes import esp32_bp
    from routes.file_routes import file_bp
    from routes.group_routes import group_bp
    from routes.questionnaire_routes import questionnaire_bp
    from routes.test_routes import test_bp
    from routes.upload_routes import upload_bp
    from routes.user_routes import user_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(questionnaire_bp)
    app.register_blueprint(group_bp)
    app.register_blueprint(test_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(esp32_bp)
    app.register_blueprint(esp32_devices_bp)
    app.register_blueprint(file_bp)

    @app.route("/health", methods=["GET"])
    def health_check():
        return jsonify({"status": "healthy"}), 200

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({"error": "Internal server error"}), 500

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=6969)
