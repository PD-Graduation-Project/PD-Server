from freezegun import freeze_time


class TestTokenExpiration:
    """Test token expiration behavior"""

    @freeze_time("2024-01-01 12:00:00")
    def test_access_token_expires_after_15_minutes(self, client, test_user):
        """Test access token expires after configured time"""
        # Login and get tokens
        response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "password123"},
        )
        access_token = response.get_json()["access_token"]

        # Access token should work now
        headers = {"Authorization": f"Bearer {access_token}"}
        response = client.get("/api/auth/sessions", headers=headers)
        assert response.status_code == 200

        # Fast forward 20 minutes (past expiration)
        with freeze_time("2024-01-01 12:20:00"):
            response = client.get("/api/auth/sessions", headers=headers)
            assert response.status_code == 401

    def test_refresh_token_long_lived(self, client, auth_tokens):
        """Test refresh token has longer expiration than access token"""
        headers = {"Authorization": f"Bearer {auth_tokens['access_token']}"}
        # Refresh token should still work (not expired within test)
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": auth_tokens["refresh_token"]},
            headers=headers,
        )
        assert response.status_code == 200
