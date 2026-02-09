from datetime import datetime, timedelta

import pytest

from app import create_app  # Adjust import based on your app structure
from models.database import db
from models.test_models import TestInput, TestSession
from models.user import RefreshToken, User


@pytest.fixture(scope="session")
def app():
    """
    Create and configure a test Flask application instance
    Session-scoped: created once per test session
    """
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",  # In-memory database
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "JWT_SECRET_KEY": "test-secret-key-do-not-use-in-production",
            "JWT_ALGORITHM": "HS256",
        }
    )

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture(scope="function")
def client(app):
    """
    Create a test client for making requests
    Function-scoped: fresh client for each test
    """
    return app.test_client()


@pytest.fixture(scope="function")
def runner(app):
    """
    Create a test CLI runner
    """
    return app.test_cli_runner()


@pytest.fixture(scope="function")
def db_session(app):
    """
    Create a clean database session for each test
    Automatically rolls back after each test
    """
    with app.app_context():
        TestInput.query.delete()
        TestSession.query.delete()
        RefreshToken.query.delete()
        User.query.delete()
        db.session.commit()

        yield db.session

        db.session.rollback()
        TestInput.query.delete()
        TestSession.query.delete()
        RefreshToken.query.delete()
        User.query.delete()
        db.session.commit()


@pytest.fixture
def test_user(db_session):
    """
    Create a test user in the database
    """
    user = User(email="test@example.com")
    user.set_password("password123")
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def multiple_users(db_session):
    """
    Create multiple test users
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
    Get valid access and refresh tokens for test_user
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
    Get authorization headers with valid access token
    """
    return {
        "Authorization": f"Bearer {auth_tokens['access_token']}",
        "Content-Type": "application/json",
    }


@pytest.fixture
def expired_access_token(app, test_user):
    """
    Generate an expired access token for testing
    """
    from datetime import timezone

    import jwt

    with app.app_context():
        # Create token that's already expired
        payload = {
            "user_id": test_user.id,
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),  # 1 hour ago
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        }

        token = jwt.encode(
            payload, app.config["JWT_SECRET_KEY"], algorithm=app.config["JWT_ALGORITHM"]
        )

        return token


@pytest.fixture
def expired_refresh_token(app, test_user, db_session):
    """
    Create an expired refresh token in database
    """
    import secrets

    from werkzeug.security import generate_password_hash

    with app.app_context():
        token = secrets.token_urlsafe(64)
        token_hash = generate_password_hash(token)

        refresh_token = RefreshToken(
            user_id=test_user.id,
            token_hash=token_hash,
            expires_at=datetime.utcnow() - timedelta(days=1),  # Expired yesterday
            device_info="Test Device",
            ip_address="127.0.0.1",
        )

        db_session.add(refresh_token)
        db_session.commit()

        return token


@pytest.fixture
def revoked_refresh_token(app, test_user, db_session):
    """
    Create a revoked refresh token in database
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
            revoked=True,  # Already revoked
            device_info="Test Device",
            ip_address="127.0.0.1",
        )

        db_session.add(refresh_token)
        db_session.commit()

        return token


@pytest.fixture
def multiple_sessions(app, test_user, db_session):
    """
    Create multiple active sessions for test_user
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
