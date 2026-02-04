import pytest


@pytest.mark.integration
class TestAuthenticationFlow:
    """Integration tests for complete authentication flows"""

    def test_complete_auth_flow(self, client, db_session):
        """Test complete registration -> login -> refresh -> logout flow"""
        # 1. Register
        response = client.post(
            "/api/auth/register",
            json={"email": "flow@example.com", "password": "testpass123"},
        )
        assert response.status_code == 201
        response_data = response.get_json()
        refresh_token = response_data["refresh_token"]
        access_token = response_data["access_token"]

        # 2. Refresh token
        headers = {"Authorization": f"Bearer {access_token}"}
        response = client.post(
            "/api/auth/refresh", json={"refresh_token": refresh_token}, headers=headers
        )
        assert response.status_code == 200
        new_access_token = response.get_json()["access_token"]

        # 3. Use new access token
        headers = {"Authorization": f"Bearer {new_access_token}"}
        response = client.get("/api/auth/sessions", headers=headers)
        assert response.status_code == 200

        # 4. Logout
        response = client.post(
            "/api/auth/logout", json={"refresh_token": refresh_token}, headers=headers
        )
        assert response.status_code == 200

        # 5. Cannot refresh after logout
        response = client.post(
            "/api/auth/refresh", json={"refresh_token": refresh_token}, headers=headers
        )
        assert response.status_code == 401

    def test_multi_device_scenario(self, client, test_user):
        """Test user logged in on multiple devices"""
        devices = ["iPhone", "MacBook", "iPad"]
        tokens = []

        # Login from 3 devices
        for device in devices:
            response = client.post(
                "/api/auth/login",
                json={"email": "test@example.com", "password": "password123"},
                headers={"User-Agent": device},
            )
            assert response.status_code == 200
            tokens.append(response.get_json())

        # All tokens should work
        for token_data in tokens:
            headers = {"Authorization": f"Bearer {token_data['access_token']}"}
            response = client.post(
                "/api/auth/refresh",
                json={"refresh_token": token_data["refresh_token"]},
                headers=headers,
            )
            assert response.status_code == 200

        # Logout from one device
        headers = {"Authorization": f"Bearer {tokens[0]['access_token']}"}
        client.post(
            "/api/auth/logout",
            json={"refresh_token": tokens[0]["refresh_token"]},
            headers=headers,
        )

        # First token should fail
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": tokens[0]["refresh_token"]},
            headers=headers,
        )
        assert response.status_code == 401

        # Other tokens should still work
        for token_data in tokens[1:]:
            headers = {"Authorization": f"Bearer {token_data['access_token']}"}
            response = client.post(
                "/api/auth/refresh",
                json={"refresh_token": token_data["refresh_token"]},
                headers=headers,
            )
            assert response.status_code == 200
