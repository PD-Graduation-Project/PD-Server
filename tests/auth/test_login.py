from models.user import RefreshToken


class TestLogin:
    """Test user login endpoint"""

    def test_login_success(self, client, test_user):
        """Test successful login"""
        response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "password123"},
        )

        assert response.status_code == 200
        data = response.get_json()

        # Check response structure
        assert data["message"] == "Success"
        assert "access_token" in data
        assert "refresh_token" in data
        assert "user" in data
        assert data["user"]["email"] == "test@example.com"

    def test_login_invalid_email(self, client):
        """Test login fails with non-existent email"""
        response = client.post(
            "/api/auth/login",
            json={"email": "nonexistent@example.com", "password": "password123"},
        )

        assert response.status_code == 401
        data = response.get_json()
        assert "error" in data
        assert "Invalid credentials" in data["error"]

    def test_login_invalid_password(self, client, test_user):
        """Test login fails with wrong password"""
        response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "wrongpassword"},
        )

        assert response.status_code == 401
        data = response.get_json()
        assert "Invalid credentials" in data["error"]

    def test_login_missing_credentials(self, client):
        """Test login fails without credentials"""
        response = client.post("/api/auth/login", json={})

        assert response.status_code == 400

    def test_login_creates_refresh_token(self, client, test_user, db_session):
        """Test login creates refresh token in database"""
        # Count tokens before login
        tokens_before = RefreshToken.query.filter_by(user_id=test_user.id).count()

        response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "password123"},
        )

        assert response.status_code == 200

        # Check token was created
        tokens_after = RefreshToken.query.filter_by(user_id=test_user.id).count()
        assert tokens_after == tokens_before + 1

    def test_login_multiple_times_creates_multiple_tokens(
        self, client, test_user, db_session
    ):
        """Test logging in multiple times creates multiple sessions"""
        # Login 3 times
        for _ in range(3):
            response = client.post(
                "/api/auth/login",
                json={"email": "test@example.com", "password": "password123"},
            )
            assert response.status_code == 200

        # Should have 3 active tokens
        active_tokens = RefreshToken.query.filter_by(
            user_id=test_user.id, revoked=False
        ).count()
        assert active_tokens == 3
