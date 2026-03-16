import logging
import sys
import time
import uuid

from flask import Flask, abort, g, jsonify, request
from flask_cors import CORS
from flask_migrate import Migrate
from loguru import logger

from config import Config
from models.database import db

logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{extra[request_id]}</cyan> | <level>{message}</level>",
    level="DEBUG",
    colorize=True,
)
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="DEBUG",
    colorize=True,
    filter=lambda record: "request_id" not in record["extra"],
)

logging.getLogger("werkzeug").setLevel(logging.WARNING)


def get_status_color(code):
    if 200 <= code < 300:
        return "\033[32m"
    elif 300 <= code < 400:
        return "\033[33m"
    elif 400 <= code < 500:
        return "\033[33m"
    else:
        return "\033[31m"


def get_method_color(method):
    colors = {
        "GET": "\033[36m",  # cyan
        "POST": "\033[32m",  # green
        "PUT": "\033[34m",  # blue
        "PATCH": "\033[35m",  # magenta
        "DELETE": "\033[31m",  # red
    }
    return colors.get(method.upper(), "\033[37m")


RESET = "\033[0m"


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
                logger.bind(request_id=g.request_id).debug("  Body: " + body[:500])
            elif request.form:
                logger.bind(request_id=g.request_id).debug(
                    "  Form: " + str(dict(request.form))
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
                + "{:.2f}ms".format(duration)
            )
            response.headers["X-Request-ID"] = g.get("request_id", "")
        except Exception:
            pass
        return response

    from routes.auth_routes import auth_bp
    from routes.esp32_devices_routes import esp32_devices_bp
    from routes.esp32_routes import esp32_bp
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
