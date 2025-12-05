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

    @staticmethod
    def init_app(app):
        # Create upload folder if it doesn't exist
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
