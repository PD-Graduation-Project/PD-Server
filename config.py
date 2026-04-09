import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-key-change-me"
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT settings
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET") or "jwt-secret-change-me"
    JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM") or "HS256"

    # File upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    UPLOAD_FOLDER = "uploads"
    ALLOWED_EXTENSIONS = {
        "audio": ["mp3", "wav", "m4a"],
        "image": ["png", "jpg", "jpeg", "gif"],
        "text": ["txt", "csv", "json"],
    }

    # IP Whitelisting for Cloudflare Tunnel
    ALLOWED_IPS = (
        [ip.strip() for ip in os.environ.get("ALLOWED_IPS", "").split(",")]
        if os.environ.get("ALLOWED_IPS")
        else []
    )

    # ESP32 Factory Key HMAC Secret
    FACTORY_SECRET = os.environ.get("FACTORY_SECRET") or "dev_factory_secret_change_me"

    # Redis settings for ESP32 event pub/sub
    REDIS_URL = os.environ.get("REDIS_URL") or "redis://localhost:6379/0"

    # MinIO / S3 settings
    MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "minio:9000")
    MINIO_ROOT_USER = os.environ.get("MINIO_ROOT_USER", "minioadmin")
    MINIO_ROOT_PASSWORD = os.environ.get("MINIO_ROOT_PASSWORD", "minioadmin")
    MINIO_BUCKET = os.environ.get("MINIO_BUCKET", "pd-server")
    MINIO_SECURE = os.environ.get("MINIO_SECURE", "false").lower() == "true"

    # Storage backend: "local" or "s3"
    STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "local")

    # Gunicorn workers (default 2 for small VMs)
    GUNICORN_WORKERS = int(os.environ.get("GUNICORN_WORKERS", "2"))

    # CORS allowed origins (comma-separated list, empty = deny all)
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "")

    @staticmethod
    def init_app(app):
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        # Connection pool settings - only for PostgreSQL/MySQL, not SQLite
        uri = app.config.get("SQLALCHEMY_DATABASE_URI") or ""
        if uri and not uri.startswith("sqlite"):
            app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
                "pool_size": 10,
                "max_overflow": 20,
                "pool_pre_ping": True,
            }
