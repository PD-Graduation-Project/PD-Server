"""
Test configuration with testcontainers for isolated test environments.

This module provides fixtures that use testcontainers to spin up:
- PostgreSQL database
- Redis server

Each test session gets fresh containers, ensuring isolation.
"""

import os

os.environ["GEVENT_PATCH"] = "false"
os.environ["STORAGE_BACKEND"] = "local"
os.environ["RATE_LIMIT_ENABLED"] = "false"

import tempfile
from pathlib import Path

_test_upload_dir = Path(tempfile.mkdtemp(prefix="pd_test_uploads_"))
os.environ["UPLOAD_FOLDER"] = str(_test_upload_dir)

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

# Check if testcontainers is available
try:
    from testcontainers.postgres import PostgresContainer
    from testcontainers.redis import RedisContainer

    TESTCONTAINERS_AVAILABLE = True
except ImportError:
    TESTCONTAINERS_AVAILABLE = False

from app import create_app
from models.database import db
from models.test_models import ESP32Device, TestGroup, TestInput, TestSession
from models.user import RefreshToken, User


@pytest.fixture(scope="session", autouse=True)
def cleanup_connection_managers():
    yield
    import threading

    def safe_remove(manager, key, timeout=2.0):
        def _remove():
            try:
                manager.remove(key)
            except Exception:
                pass

        t = threading.Thread(target=_remove)
        t.start()
        t.join(timeout=timeout)

    try:
        from utils.mobile_connection_manager import mobile_connection_manager
        from utils.esp32_connection_manager import connection_manager

        for key in list(mobile_connection_manager._local_listeners.keys()):
            safe_remove(mobile_connection_manager, key)
        for key in list(connection_manager._local_listeners.keys()):
            safe_remove(connection_manager, key)
    except Exception:
        pass


@pytest.fixture(scope="session")
def containers():
    """
    Start testcontainers for the test session.
    Returns connection URLs for PostgreSQL and Redis.
    """
    if not TESTCONTAINERS_AVAILABLE:
        # Fall back to in-memory SQLite and mocked Redis
        yield {
            "database_url": "sqlite:///:memory:",
            "redis_url": "redis://localhost:6379/0",
            "use_real_redis": False,
        }
        return

    # Start PostgreSQL container
    postgres = PostgresContainer("postgres:15-alpine")
    postgres.start()

    # Start Redis container
    redis = RedisContainer("redis:7-alpine")
    redis.start()

    # RedisContainer uses get_connection_url() for host:port format
    redis_url = (
        f"redis://{redis.get_container_host_ip()}:{redis.get_exposed_port(6379)}/0"
    )

    yield {
        "database_url": postgres.get_connection_url(),
        "redis_url": redis_url,
        "use_real_redis": True,
        "postgres": postgres,
        "redis": redis,
    }

    # Cleanup with timeout
    import threading

    def stop_postgres():
        postgres.stop()

    def stop_redis():
        redis.stop()

    t1 = threading.Thread(target=stop_postgres)
    t2 = threading.Thread(target=stop_redis)
    t1.start()
    t2.start()
    t1.join(timeout=30)
    t2.join(timeout=30)


@pytest.fixture(scope="session")
def app(containers):
    """
    Create and configure a test Flask application instance.
    Uses testcontainers for PostgreSQL and Redis.
    """
    config = {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": containers["database_url"],
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "JWT_SECRET_KEY": "test-secret-key-do-not-use-in-production",
        "JWT_ALGORITHM": "HS256",
        "FACTORY_SECRET": "test_factory_secret",
        "REDIS_URL": containers["redis_url"],
        "STORAGE_BACKEND": "local",  # Use local storage for tests
    }

    app = create_app(config)

    with app.app_context():
        db.create_all()
        yield app
        # Cleanup with timeout
        import threading

        def drop_all():
            with app.app_context():
                db.drop_all()

        t = threading.Thread(target=drop_all)
        t.start()
        t.join(timeout=30)


@pytest.fixture(scope="function")
def client(app):
    """
    Create a test client for making requests.
    """
    return app.test_client()


@pytest.fixture(scope="function")
def runner(app):
    """
    Create a test CLI runner.
    """
    return app.test_cli_runner()


@pytest.fixture(scope="function")
def db_session(app):
    """
    Create a clean database session for each test.
    Automatically rolls back after each test.
    """
    with app.app_context():
        # Clean all tables
        TestInput.query.delete()
        TestSession.query.delete()
        TestGroup.query.delete()
        ESP32Device.query.delete()
        RefreshToken.query.delete()
        User.query.delete()
        db.session.commit()

        yield db.session

        # Cleanup after test
        db.session.rollback()
        TestInput.query.delete()
        TestSession.query.delete()
        TestGroup.query.delete()
        ESP32Device.query.delete()
        RefreshToken.query.delete()
        User.query.delete()
        db.session.commit()


@pytest.fixture(autouse=True)
def mock_ml_predictor():
    """
    Automatically mock all ML predictor functions for every test.
    Prevents tests from loading PyTorch models and running real inference.
    """
    mock_job = MagicMock()
    mock_job.id = "test-job-id"

    mock_queue = MagicMock()
    mock_queue.enqueue.return_value = mock_job

    with (
        patch("ml.predictor.predict_drawing", return_value=0.5) as mock_drawing,
        patch("ml.predictor.predict_tremor", return_value=0.5) as mock_tremor,
        patch("ml.predictor.predict_voice", return_value=0.5) as mock_voice,
        patch(
            "ml.predictor.predict_questionnaire", return_value=0.5
        ) as mock_questionnaire,
        patch("ml.overall_model.predict_overall", return_value=0.5) as mock_overall,
        patch("routes.upload_routes.get_ml_queue", return_value=mock_queue),
    ):
        yield {
            "predict_drawing": mock_drawing,
            "predict_tremor": mock_tremor,
            "predict_voice": mock_voice,
            "predict_questionnaire": mock_questionnaire,
            "predict_overall": mock_overall,
            "queue": mock_queue,
            "job": mock_job,
        }


@pytest.fixture
def test_user(db_session):
    """
    Create a test user in the database.
    """
    user = User(email="test@example.com")
    user.set_password("password123")
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def multiple_users(db_session):
    """
    Create multiple test users.
    """
    users = []
    for i in range(3):
        user = User(email=f"user{i}@example.com")
        user.set_password(f"password{i}")
        db_session.add(user)
        users.append(user)

    db_session.commit()
    return users


@pytest.fixture
def auth_tokens(client, test_user):
    """
    Get valid access and refresh tokens for test_user.
    """
    response = client.post(
        "/api/auth/login", json={"email": "test@example.com", "password": "password123"}
    )

    data = response.get_json()
    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "user": test_user,
    }


@pytest.fixture
def auth_headers(auth_tokens):
    """
    Get authorization headers with valid access token.
    """
    return {
        "Authorization": f"Bearer {auth_tokens['access_token']}",
        "Content-Type": "application/json",
    }


@pytest.fixture
def expired_access_token(app, test_user):
    """
    Generate an expired access token for testing.
    """
    from datetime import timezone

    import jwt

    with app.app_context():
        payload = {
            "user_id": test_user.id,
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        }

        token = jwt.encode(
            payload, app.config["JWT_SECRET_KEY"], algorithm=app.config["JWT_ALGORITHM"]
        )

        return token


@pytest.fixture
def expired_refresh_token(app, test_user, db_session):
    """
    Create an expired refresh token in database.
    """
    import secrets

    from werkzeug.security import generate_password_hash

    with app.app_context():
        token = secrets.token_urlsafe(64)
        token_hash = generate_password_hash(token)

        refresh_token = RefreshToken(
            user_id=test_user.id,
            token_hash=token_hash,
            expires_at=datetime.utcnow() - timedelta(days=1),
            device_info="Test Device",
            ip_address="127.0.0.1",
        )

        db_session.add(refresh_token)
        db_session.commit()

        return token


@pytest.fixture
def revoked_refresh_token(app, test_user, db_session):
    """
    Create a revoked refresh token in database.
    """
    import secrets

    from werkzeug.security import generate_password_hash

    with app.app_context():
        token = secrets.token_urlsafe(64)
        token_hash = generate_password_hash(token)

        refresh_token = RefreshToken(
            user_id=test_user.id,
            token_hash=token_hash,
            expires_at=datetime.utcnow() + timedelta(days=30),
            revoked=True,
            device_info="Test Device",
            ip_address="127.0.0.1",
        )

        db_session.add(refresh_token)
        db_session.commit()

        return token


@pytest.fixture
def multiple_sessions(app, test_user, db_session):
    """
    Create multiple active sessions for test_user.
    """
    import secrets

    from werkzeug.security import generate_password_hash

    with app.app_context():
        tokens = []
        devices = ["iPhone 14", "MacBook Pro", "iPad Air"]

        for device in devices:
            token = secrets.token_urlsafe(64)
            token_hash = generate_password_hash(token)

            refresh_token = RefreshToken(
                user_id=test_user.id,
                token_hash=token_hash,
                expires_at=datetime.utcnow() + timedelta(days=30),
                device_info=device,
                ip_address="127.0.0.1",
            )

            db_session.add(refresh_token)
            db_session.flush()

            tokens.append(
                {
                    "token": token,
                    "device": device,
                    "db_record": refresh_token,
                    "id": refresh_token.id,
                }
            )

        db_session.commit()
        return tokens


@pytest.fixture
def test_group(client, auth_headers):
    """
    Create a test group via the API and return the group_id.
    """
    response = client.post("/api/groups", headers=auth_headers)
    assert response.status_code == 201, f"Failed to create group: {response.get_json()}"
    return response.get_json()["data"]["id"]


@pytest.fixture
def esp32_device(db_session, test_user):
    """
    Create a registered and paired ESP32 device with production API key.
    """
    from utils.factory_key import generate_factory_key

    device_id = "ESP32-001234"
    factory_key = generate_factory_key(device_id)

    device = ESP32Device(
        device_id=device_id,
        user_id=test_user.id,
        factory_api_key=factory_key,
        api_key="sk_live_test_production_key_xyz789",
        name="Test Sensor",
        is_connected=False,
    )
    db_session.add(device)
    db_session.commit()
    return device


@pytest.fixture
def esp32_device_unpaired(db_session):
    """
    Create a registered but unpaired ESP32 device (no user_id).
    """
    from utils.factory_key import generate_factory_key

    device_id = "ESP32-005678"
    factory_key = generate_factory_key(device_id)

    device = ESP32Device(
        device_id=device_id,
        factory_api_key=factory_key,
        api_key="sk_live_unpaired_key_abc123",
        is_connected=False,
    )
    db_session.add(device)
    db_session.commit()
    return device


@pytest.fixture
def esp32_device_unregistered():
    """
    Return device_id and factory_key for an unregistered device.
    """
    from dataclasses import dataclass

    from utils.factory_key import generate_factory_key

    device_id = "ESP32-009999"
    factory_key = generate_factory_key(device_id)

    @dataclass
    class UnregisteredDevice:
        device_id: str
        factory_api_key: str

    return UnregisteredDevice(device_id=device_id, factory_api_key=factory_key)


@pytest.fixture
def esp32_api_key_headers(esp32_device):
    """
    Headers for ESP32 production API key authentication.
    """
    return {
        "X-Device-API-Key": esp32_device.api_key,
    }


@pytest.fixture
def esp32_factory_key_headers(esp32_device_unregistered):
    """
    Headers for ESP32 factory API key authentication.
    """
    return {
        "X-Device-API-Key": esp32_device_unregistered.factory_api_key,
    }
