from flask import Flask, jsonify
from flask_cors import CORS
from flask_migrate import Migrate

from config import Config
from models.database import db


def create_app(config_override=None):
    app = Flask(__name__)
    app.config.from_object(Config)

    if config_override:
        app.config.update(config_override)

    # Initialize extensions
    db.init_app(app)
    Migrate(app, db)

    CORS(app)

    from routes.auth_routes import auth_bp
    from routes.questionnaire_routes import questionnaire_bp
    from routes.tests import tests_bp
    from routes.user_routes import user_bp

    with app.app_context():
        db.create_all()

    app.register_blueprint(auth_bp)
    app.register_blueprint(tests_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(questionnaire_bp)

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
    app.run(debug=True, host="0.0.0.0", port=5000)
