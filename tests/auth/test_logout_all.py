from models.user import RefreshToken


class TestLogoutAll:
    """Test logout from all devices endpoint"""

    def test_logout_all_success(
        self, client, auth_headers, multiple_sessions, test_user, db_session
    ):
        """Test logging out from all devices"""
        # Verify multiple sessions exist
        active_before = RefreshToken.query.filter_by(
            user_id=test_user.id, revoked=False
        ).count()
        assert active_before > 0

        # Logout from all devices
        response = client.post("/api/auth/logout-all", headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert "Logged out from all devices" in data["message"]

        # Verify all tokens were revoked
        active_after = RefreshToken.query.filter_by(
            user_id=test_user.id, revoked=False
        ).count()
        assert active_after == 0

    def test_logout_all_requires_access_token(self, client):
        """Test logout-all requires authentication"""
        response = client.post("/api/auth/logout-all")

        assert response.status_code == 401

    def test_logout_all_invalid_access_token(self, client):
        """Test logout-all fails with invalid token"""
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.post("/api/auth/logout-all", headers=headers)

        assert response.status_code == 401

    def test_logout_all_expired_access_token(self, client, expired_access_token):
        """Test logout-all fails with expired access token"""
        headers = {"Authorization": f"Bearer {expired_access_token}"}
        response = client.post("/api/auth/logout-all", headers=headers)

        assert response.status_code == 401
