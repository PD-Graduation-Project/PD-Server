class TestRefresh:
    """Test token refresh endpoint"""

    def test_refresh_success(self, client, auth_tokens):
        """Test successfully refreshing access token"""
        headers = {"Authorization": f"Bearer {auth_tokens['access_token']}"}
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": auth_tokens["refresh_token"]},
            headers=headers,
        )

        assert response.status_code == 200
        data = response.get_json()

        # Check response
        assert "access_token" in data
        assert "token_type" in data
        assert "expires_in" in data
        assert data["token_type"] == "Bearer"

        # New access token should be different from old one
        assert data["access_token"] != auth_tokens["access_token"]

    def test_refresh_missing_token(self, client, auth_tokens):
        """Test refresh fails without token"""
        headers = {"Authorization": f"Bearer {auth_tokens['access_token']}"}
        response = client.post("/api/auth/refresh", json={}, headers=headers)

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "Refresh token required" in data["error"]

    def test_refresh_invalid_token(self, client, auth_tokens):
        """Test refresh fails with invalid token"""
        headers = {"Authorization": f"Bearer {auth_tokens['access_token']}"}
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": "invalid_token_12345"},
            headers=headers,
        )

        assert response.status_code == 401
        data = response.get_json()
        assert "Invalid or expired refresh token" in data["error"]

    def test_refresh_expired_token(self, client, auth_tokens, expired_refresh_token):
        """Test refresh fails with expired token"""
        headers = {"Authorization": f"Bearer {auth_tokens['access_token']}"}
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": expired_refresh_token},
            headers=headers,
        )

        assert response.status_code == 401
        data = response.get_json()
        assert "Invalid or expired refresh token" in data["error"]

    def test_refresh_revoked_token(self, client, auth_tokens, revoked_refresh_token):
        """Test refresh fails with revoked token"""
        headers = {"Authorization": f"Bearer {auth_tokens['access_token']}"}
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": revoked_refresh_token},
            headers=headers,
        )

        assert response.status_code == 401

    def test_refresh_multiple_times(self, client, auth_tokens):
        """Test can refresh multiple times with same token"""
        headers = {"Authorization": f"Bearer {auth_tokens['access_token']}"}
        # Refresh 3 times
        tokens = []
        for _ in range(3):
            response = client.post(
                "/api/auth/refresh",
                json={"refresh_token": auth_tokens["refresh_token"]},
                headers=headers,
            )
            assert response.status_code == 200
            data = response.get_json()
            tokens.append(data["access_token"])
            headers = {"Authorization": f"Bearer {data['access_token']}"}

        # All access tokens should be different
        assert len(tokens) == len(set(tokens))
