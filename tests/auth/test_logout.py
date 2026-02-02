from models.user import RefreshToken


class TestLogout:
    """Test logout endpoint"""

    def test_logout_success(self, client, auth_tokens, db_session):
        """Test successful logout"""
        response = client.post(
            "/api/auth/logout", json={"refresh_token": auth_tokens["refresh_token"]}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "message" in data
        assert "Logged out successfully" in data["message"]

        # Verify token was revoked in database
        refresh_tokens = RefreshToken.query.filter_by(
            user_id=auth_tokens["user"].id, revoked=False
        ).all()
        assert len(refresh_tokens) == 0

    def test_logout_prevents_future_refresh(self, client, auth_tokens):
        """Test cannot refresh after logout"""
        # Logout
        response = client.post(
            "/api/auth/logout", json={"refresh_token": auth_tokens["refresh_token"]}
        )
        assert response.status_code == 200

        # Try to refresh with revoked token
        response = client.post(
            "/api/auth/refresh", json={"refresh_token": auth_tokens["refresh_token"]}
        )
        assert response.status_code == 401

    def test_logout_missing_token(self, client):
        """Test logout fails without token"""
        response = client.post("/api/auth/logout", json={})

        assert response.status_code == 400

    def test_logout_invalid_token(self, client):
        """Test logout with invalid token"""
        response = client.post(
            "/api/auth/logout", json={"refresh_token": "invalid_token"}
        )

        assert response.status_code == 401

    def test_logout_only_affects_current_session(self, client, test_user):
        """Test logout only revokes specific session, not all sessions"""
        # Login twice to create 2 sessions
        response1 = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "password123"},
        )
        token1 = response1.get_json()["refresh_token"]

        response2 = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "password123"},
        )
        token2 = response2.get_json()["refresh_token"]

        # Logout from session 1
        client.post("/api/auth/logout", json={"refresh_token": token1})

        # Session 1 should be invalid
        response = client.post("/api/auth/refresh", json={"refresh_token": token1})
        assert response.status_code == 401

        # Session 2 should still work
        response = client.post("/api/auth/refresh", json={"refresh_token": token2})
        assert response.status_code == 200
