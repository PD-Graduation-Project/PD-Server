import logging

from flask import Flask, abort, jsonify, request
from flask_cors import CORS
from flask_migrate import Migrate

from config import Config
from models.database import db

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logging.getLogger("utils.esp32_connection_manager").setLevel(logging.INFO)
logging.getLogger("routes.test_routes").setLevel(logging.INFO)
logging.getLogger("routes.esp32_routes").setLevel(logging.INFO)


def create_app(config_override=None):
    app = Flask(__name__)
    app.config.from_object(Config)

    if config_override:
        app.config.update(config_override)

    # Apply Config.init_app (sets pool options, creates upload folder, etc.)
    Config.init_app(app)

    # Initialize extensions
    db.init_app(app)
    Migrate(app, db)

    CORS(app)

    @app.before_request
    def check_ip():
        if Config.ALLOWED_IPS and request.remote_addr not in Config.ALLOWED_IPS:
            abort(403)

    from routes.auth_routes import auth_bp
    from routes.esp32_devices_routes import esp32_devices_bp
    from routes.esp32_routes import esp32_bp
    from routes.questionnaire_routes import questionnaire_bp
    from routes.test_routes import test_bp
    from routes.upload_routes import upload_bp
    from routes.user_routes import user_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(questionnaire_bp)
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
