from gevent import monkey

monkey.patch_all()

import logging
import os
import re
import sys
import threading
import time
import uuid
from datetime import datetime, timezone

from flask import Flask, abort, g, jsonify, request
from flask_cors import CORS
from flask_migrate import Migrate
from loguru import logger
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

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


def use_color_logs() -> bool:
    return os.environ.get("LOG_FORMAT", "pretty") != "json"


def should_log_request_path(path: str) -> bool:
    silent_paths = {
        p.strip()
        for p in os.environ.get("LOG_SILENT_PATHS", "/metrics").split(",")
        if p.strip()
    }
    return path not in silent_paths


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
    use_color = use_color_logs()
    sys.stderr.write(_build_record_str(message.record, color=use_color))
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

        log_format = os.environ.get("LOG_FORMAT", "pretty")

        if log_format == "json":
            import json
            from datetime import datetime

            log_record = {
                "timestamp": datetime.utcnow().isoformat(),
                "level": message.record["level"].name,
                "message": strip_ansi(message.record["message"]),
                "request_id": message.record["extra"].get("request_id"),
            }
            _log_file.write(json.dumps(log_record) + "\n")
        else:
            _log_file.write(_build_record_str(message.record, color=False))
        _log_file.flush()


# ── Logger init ───────────────────────────────────────────────────────────────
logger.remove()

log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
log_format = os.environ.get("LOG_FORMAT", "pretty")

logger.add(console_sink, level=log_level, format="{message}")
logger.add(file_sink, level=log_level, format="{message}")

# Keep werkzeug startup messages but suppress per-request access lines
_wz_logger = logging.getLogger("werkzeug")
_wz_logger.setLevel(logging.INFO)


class _SuppressAccessLogs(logging.Filter):
    """Drop werkzeug's '127.0.0.1 - - [date] "GET /" 200 -' lines."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not (record.levelno == logging.INFO and " - - [" in msg and '"' in msg)


_wz_logger.addFilter(_SuppressAccessLogs())

# ── Metrics ───────────────────────────────────────────────────────────────────
HTTP_REQUESTS_TOTAL = Counter(
    "pd_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "pd_http_request_duration_seconds",
    "HTTP request duration seconds",
    ["method", "endpoint"],
)
HTTP_ERRORS_TOTAL = Counter(
    "pd_http_errors_total",
    "HTTP error responses",
    ["status_class"],
)

ML_QUEUE_DEPTH = Gauge("pd_ml_queue_depth", "Current ML queue depth")
ML_QUEUE_OLDEST_SECONDS = Gauge(
    "pd_ml_queue_oldest_seconds", "Age in seconds of oldest queued ML job"
)
DB_CONNECTIONS = Gauge("pd_db_connections", "Active Postgres connections")
ML_COMPLETED_TOTAL = Gauge("pd_ml_completed_total", "Completed ML jobs total")
ML_FAILED_TOTAL = Gauge("pd_ml_failed_total", "Failed ML jobs total")
ML_AVG_DURATION_SECONDS = Gauge(
    "pd_ml_avg_duration_seconds", "Average ML inference duration in seconds"
)
DEPLOY_UNIX_TIME = Gauge("pd_deploy_unix_time", "Current deployment unix timestamp")
DEPLOY_UNIX_TIME.set(time.time())


def _collect_runtime_metrics() -> None:
    try:
        db_res = db.session.execute(
            db.text(
                "SELECT numbackends FROM pg_stat_database WHERE datname = current_database()"
            )
        ).scalar()
        DB_CONNECTIONS.set(float(db_res or 0))
    except Exception:
        pass

    try:
        from redis import Redis

        r = Redis.from_url(Config.REDIS_URL)

        queue_depth = int(r.llen("rq:queue:ml"))
        ML_QUEUE_DEPTH.set(queue_depth)

        oldest_seconds = 0.0
        if queue_depth > 0:
            oldest_job_id = r.lindex("rq:queue:ml", -1)
            if oldest_job_id:
                if isinstance(oldest_job_id, bytes):
                    oldest_job_id = oldest_job_id.decode("utf-8")
                enqueued_at = r.hget(f"rq:job:{oldest_job_id}", "enqueued_at")
                if enqueued_at:
                    if isinstance(enqueued_at, bytes):
                        enqueued_at = enqueued_at.decode("utf-8")
                    try:
                        enqueued_dt = datetime.fromisoformat(
                            enqueued_at.replace("Z", "+00:00")
                        )
                        now = datetime.now(timezone.utc)
                        oldest_seconds = max(
                            0.0,
                            (
                                now - enqueued_dt.astimezone(timezone.utc)
                            ).total_seconds(),
                        )
                    except Exception:
                        oldest_seconds = 0.0
        ML_QUEUE_OLDEST_SECONDS.set(oldest_seconds)

        completed = float(r.get("pd:ml:completed_total") or 0)
        failed = float(r.get("pd:ml:failed_total") or 0)
        duration_sum = float(r.get("pd:ml:duration_sum_seconds") or 0)
        duration_count = float(r.get("pd:ml:duration_count") or 0)

        ML_COMPLETED_TOTAL.set(completed)
        ML_FAILED_TOTAL.set(failed)
        ML_AVG_DURATION_SECONDS.set(
            duration_sum / duration_count if duration_count > 0 else 0
        )

        r.close()
    except Exception:
        pass


# ── App factory ───────────────────────────────────────────────────────────────
def create_app(config_override=None):
    app = Flask(__name__)
    app.config.from_object(Config)

    if config_override:
        app.config.update(config_override)

    Config.init_app(app)

    db.init_app(app)
    Migrate(app, db)

    # CORS - configurable via CORS_ORIGINS env var
    # Empty = deny all, comma-separated list = allowed origins
    cors_origins = Config.CORS_ORIGINS.strip() if Config.CORS_ORIGINS else ""
    if cors_origins:
        origins = [o.strip() for o in cors_origins.split(",") if o.strip()]
        CORS(app, origins=origins)
    else:
        # No origins configured = only same-origin requests allowed
        CORS(app, origins=[])

    @app.before_request
    def check_ip():
        if Config.ALLOWED_IPS and request.remote_addr not in Config.ALLOWED_IPS:
            abort(403)

    @app.before_request
    def log_request():
        try:
            g.start_time = time.time()
            g.request_id = str(uuid.uuid4())[:8]
            g.skip_access_log = not should_log_request_path(request.path)

            if g.skip_access_log:
                return

            colored = use_color_logs()
            method_token = (
                get_method_color(request.method) + request.method + RESET
                if colored
                else request.method
            )
            logger.bind(request_id=g.request_id).info(
                "→ " + method_token + " " + request.path
            )
            # Only log body in development, never in production
            if os.environ.get("FLASK_ENV", "production") == "development":
                body = request.get_data(as_text=True)
                if body:
                    logger.bind(request_id=g.request_id).debug(
                        "  Body: "
                        + ((DIM_YELLOW + body[:500] + RESET) if colored else body[:500])
                    )
                elif request.form:
                    logger.bind(request_id=g.request_id).debug(
                        "  Form: "
                        + (
                            (DIM_YELLOW + str(dict(request.form)) + RESET)
                            if colored
                            else str(dict(request.form))
                        )
                    )
        except Exception:
            pass

    @app.after_request
    def log_response(response):
        try:
            duration = (time.time() - g.get("start_time", time.time())) * 1000
            if not g.get("skip_access_log", False):
                colored = use_color_logs()
                method_token = (
                    get_method_color(request.method) + request.method + RESET
                    if colored
                    else request.method
                )
                status_token = (
                    get_status_color(response.status_code)
                    + str(response.status_code)
                    + RESET
                    if colored
                    else str(response.status_code)
                )
                duration_token = (
                    DIM + f"{duration:.2f}ms" + RESET
                    if colored
                    else f"{duration:.2f}ms"
                )
                logger.bind(request_id=g.get("request_id", "N/A")).info(
                    "← "
                    + method_token
                    + " "
                    + request.path
                    + " "
                    + status_token
                    + " "
                    + duration_token
                )

            endpoint = request.url_rule.rule if request.url_rule else request.path
            HTTP_REQUESTS_TOTAL.labels(
                method=request.method,
                endpoint=endpoint,
                status=str(response.status_code),
            ).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=request.method, endpoint=endpoint
            ).observe(duration / 1000)
            if response.status_code >= 400:
                HTTP_ERRORS_TOTAL.labels(
                    status_class=f"{response.status_code // 100}xx"
                ).inc()

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

    @app.route("/metrics", methods=["GET"])
    def metrics():
        _collect_runtime_metrics()
        return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}

    @app.route("/ready", methods=["GET"])
    def readiness_check():
        """Readiness check - verifies all dependencies are available."""
        issues = []

        # Check database
        try:
            db.session.execute(db.text("SELECT 1"))
        except Exception as e:
            issues.append(f"database: {e}")

        # Check Redis
        try:
            from redis import Redis

            r = Redis.from_url(Config.REDIS_URL)
            r.ping()
            r.close()
        except Exception as e:
            issues.append(f"redis: {e}")

        # Check storage (S3 or local)
        try:
            if Config.STORAGE_BACKEND == "s3":
                from utils.s3_storage import get_storage

                storage = get_storage()
                storage.file_exists("healthcheck")  # Just verify client works
            else:
                from pathlib import Path

                upload_dir = Path(Config.UPLOAD_FOLDER)
                if not upload_dir.exists():
                    raise Exception("upload directory does not exist")
        except Exception as e:
            issues.append(f"storage: {e}")

        if issues:
            return jsonify({"status": "not ready", "issues": issues}), 503

        return jsonify({"status": "ready"}), 200

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        request_id = g.get("request_id", "unknown")
        logger.error(f"Internal error (request_id={request_id}): {error}")
        return (
            jsonify({"error": "Internal server error", "request_id": request_id}),
            500,
        )

    @app.errorhandler(Exception)
    def handle_exception(error):
        """Global exception handler - catches all unhandled exceptions."""
        request_id = g.get("request_id", "unknown")
        logger.exception(f"Unhandled exception (request_id={request_id}): {error}")
        return (
            jsonify({"error": "Internal server error", "request_id": request_id}),
            500,
        )

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=6969)
