from models.user import RefreshToken, User


class TestRegister:
    """Test user registration endpoint"""

    def test_register_success(self, client, db_session):
        """Test successful user registration"""
        response = client.post(
            "/api/auth/register",
            json={"email": "newuser@example.com", "password": "securepass123"},
        )

        assert response.status_code == 201
        data = response.get_json()

        # Check response structure
        assert "message" in data
        assert data["message"] == "Success"
        assert "access_token" in data
        assert "refresh_token" in data
        assert "token_type" in data
        assert data["token_type"] == "Bearer"
        assert "expires_in" in data
        assert "user" in data

        # Check user data
        assert data["user"]["email"] == "newuser@example.com"
        assert "password" not in data["user"]
        assert "password_hash" not in data["user"]

        # Verify user was created in database
        user = User.query.filter_by(email="newuser@example.com").first()
        assert user is not None
        assert user.check_password("securepass123")

        # Verify refresh token was created in database
        refresh_tokens = RefreshToken.query.filter_by(user_id=user.id).all()
        assert len(refresh_tokens) == 1

    def test_register_missing_email(self, client):
        """Test registration fails without email"""
        response = client.post("/api/auth/register", json={"password": "securepass123"})

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "'email': ['Missing data for required field.']" in str(data["error"])

    def test_register_missing_password(self, client):
        """Test registration fails without password"""
        response = client.post("/api/auth/register", json={"email": "test@example.com"})

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_register_duplicate_email(self, client, test_user):
        """Test registration fails with duplicate email"""
        response = client.post(
            "/api/auth/register",
            json={
                "email": "test@example.com",  # Already exists from fixture
                "password": "newpassword",
            },
        )

        assert response.status_code == 409
        data = response.get_json()
        assert "error" in data
        assert "Email already registered" in data["error"]

    def test_register_empty_json(self, client):
        """Test registration fails with empty JSON"""
        response = client.post("/api/auth/register", json={})

        assert response.status_code == 400

    def test_register_invalid_json(self, client):
        """Test registration fails with invalid JSON"""
        response = client.post(
            "/api/auth/register", data="invalid json", content_type="application/json"
        )

        assert response.status_code in [400, 415]
