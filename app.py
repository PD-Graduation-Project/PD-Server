from flask import Flask, jsonify
from flask_cors import CORS
from config import Config
from models.database import db


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    CORS(app)

    # Import blueprints here to avoid circular imports
    from routes.auth import auth_bp
    from routes.tests import tests_bp

    # Create tables
    with app.app_context():
        db.create_all()

    # Register blueprints (routes)
    app.register_blueprint(auth_bp)
    app.register_blueprint(tests_bp)

    # Health check endpoint
    @app.route("/health", methods=["GET"])
    def health_check():
        return jsonify({"status": "healthy", "service": "pd-server"}), 200

    # Error handlers
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
