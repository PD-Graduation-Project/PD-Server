from models.user import RefreshToken


class TestLogout:
    """Test logout endpoint"""

    def test_logout_success(self, client, auth_tokens, db_session):
        """Test successful logout"""
        headers = {"Authorization": f"Bearer {auth_tokens['access_token']}"}
        response = client.post(
            "/api/auth/logout",
            json={"refresh_token": auth_tokens["refresh_token"]},
            headers=headers,
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "message" in data
        assert "Logged out successfully" in data["message"]

        # Verify token was revoked in database
        refresh_tokens = RefreshToken.query.filter_by(
            user_id=auth_tokens["user"].id, revoked=True
        ).all()
        assert len(refresh_tokens) == 1

    def test_logout_prevents_future_refresh(self, client, auth_tokens):
        """Test cannot refresh after logout"""
        headers = {"Authorization": f"Bearer {auth_tokens['access_token']}"}
        # Logout
        response = client.post(
            "/api/auth/logout",
            json={"refresh_token": auth_tokens["refresh_token"]},
            headers=headers,
        )
        assert response.status_code == 200

        # Try to refresh with revoked token
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": auth_tokens["refresh_token"]},
            headers=headers,
        )
        assert response.status_code == 401

    def test_logout_missing_token(self, client, auth_tokens):
        """Test logout fails without token"""
        headers = {"Authorization": f"Bearer {auth_tokens['access_token']}"}
        response = client.post("/api/auth/logout", json={}, headers=headers)

        assert response.status_code == 400

    def test_logout_invalid_token(self, client, auth_tokens):
        """Test logout with invalid token"""
        headers = {"Authorization": f"Bearer {auth_tokens['access_token']}"}
        response = client.post(
            "/api/auth/logout", json={"refresh_token": "invalid_token"}, headers=headers
        )

        assert response.status_code == 401

    def test_logout_only_affects_current_session(self, client, test_user):
        """Test logout only revokes specific session, not all sessions"""
        # Login twice to create 2 sessions
        response1 = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "password123"},
        )
        token1_data = response1.get_json()
        token1 = token1_data["refresh_token"]
        access_token1 = token1_data["access_token"]

        response2 = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "password123"},
        )
        token2_data = response2.get_json()
        token2 = token2_data["refresh_token"]
        access_token2 = token2_data["access_token"]

        # Logout from session 1
        headers1 = {"Authorization": f"Bearer {access_token1}"}
        client.post(
            "/api/auth/logout", json={"refresh_token": token1}, headers=headers1
        )

        # Session 1 should be invalid
        response = client.post(
            "/api/auth/refresh", json={"refresh_token": token1}, headers=headers1
        )
        assert response.status_code == 401

        # Session 2 should still work
        headers2 = {"Authorization": f"Bearer {access_token2}"}
        response = client.post(
            "/api/auth/refresh", json={"refresh_token": token2}, headers=headers2
        )
        assert response.status_code == 200
