from datetime import datetime, timedelta

from models.user import RefreshToken


class TestSessions:
    """Test get sessions endpoint"""

    def test_get_sessions_success(
        self, client, auth_headers, multiple_sessions, test_user
    ):
        """Test getting list of active sessions"""
        response = client.get("/api/auth/sessions", headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()

        assert "sessions" in data
        assert len(data["sessions"]) >= 3  # From multiple_sessions fixture

        # Check session structure
        session = data["sessions"][0]
        assert "id" in session
        assert "device_info" in session
        assert "ip_address" in session
        assert "created_at" in session
        assert "expires_at" in session

    def test_get_sessions_requires_authentication(self, client):
        """Test sessions endpoint requires authentication"""
        response = client.get("/api/auth/sessions")

        assert response.status_code == 401

    def test_get_sessions_excludes_revoked(
        self, client, auth_headers, multiple_sessions, db_session
    ):
        """Test sessions endpoint only returns active sessions"""
        # Get the ID of the session to revoke
        revoked_id = multiple_sessions[0]["id"]

        # Revoke the session using a query (avoids detached object issues)
        db_session.query(RefreshToken).filter_by(id=revoked_id).update(
            {"revoked": True}
        )
        db_session.commit()

        response = client.get("/api/auth/sessions", headers=auth_headers)
        data = response.get_json()

        # Should not include revoked session
        session_ids = [s["id"] for s in data["sessions"]]
        assert revoked_id not in session_ids

    def test_get_sessions_excludes_expired(
        self, client, auth_headers, test_user, db_session
    ):
        """Test sessions endpoint excludes expired sessions"""
        import secrets

        from werkzeug.security import generate_password_hash

        # Create expired session
        token = secrets.token_urlsafe(64)
        expired_session = RefreshToken(
            user_id=test_user.id,
            token_hash=generate_password_hash(token),
            expires_at=datetime.utcnow() - timedelta(days=1),
            device_info="Expired Device",
        )
        db_session.add(expired_session)
        db_session.commit()

        response = client.get("/api/auth/sessions", headers=auth_headers)
        data = response.get_json()

        # Should not include expired session
        session_ids = [s["id"] for s in data["sessions"]]
        assert expired_session.id not in session_ids
