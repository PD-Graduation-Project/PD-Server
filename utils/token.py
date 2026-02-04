import datetime
import uuid

import jwt

from config import Config


def generate_access_token(user_id):
    """Generate a short-lived access token"""
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "user_id": user_id,
        "type": "access",
        "exp": now + datetime.timedelta(minutes=15),
        "iat": now,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm=Config.JWT_ALGORITHM)


def verify_access_token(token):
    """Verify and decode access token"""
    try:
        payload = jwt.decode(
            token, Config.JWT_SECRET_KEY, algorithms=[Config.JWT_ALGORITHM]
        )

        # Ensure it's an access token
        if payload.get("type") != "access":
            return None

        return payload["user_id"]
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
