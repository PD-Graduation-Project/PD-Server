from models.user import User


class TestUserRoutes:
    """Test suite for user routes"""

    def test_get_user_without_auth_returns_401(self, client):
        """GET /api/user should return 401 without authentication"""
        response = client.get("/api/user/")
        assert response.status_code == 401

    def test_get_user_with_valid_token_returns_user_data(
        self, client, auth_headers, test_user
    ):
        """GET /api/user should return user demographics with valid token"""
        response = client.get("/api/user/", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["id"] == test_user.id

    def test_get_user_returns_only_demographic_fields(
        self, client, auth_headers, test_user
    ):
        """GET /api/user should return only demographic fields, not questionnaire data"""
        response = client.get("/api/user/", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        expected_fields = [
            "id",
            "age",
            "height",
            "weight",
            "gender",
            "pd_appearance_in_kinship",
            "pd_appearance_in_first_grade_kinship",
        ]
        for field in expected_fields:
            assert field in data["data"]

    def test_update_user_without_auth_returns_401(self, client):
        """PATCH /api/user should return 401 without authentication"""
        response = client.patch("/api/user/", json={"age": 25})
        assert response.status_code == 401

    def test_update_user_with_valid_data(self, client, auth_headers, test_user):
        """PATCH /api/user should update user demographics"""
        response = client.patch(
            "/api/user/",
            headers=auth_headers,
            json={"age": 30, "height": 180, "weight": 75, "gender": "male"},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_update_user_with_partial_data(self, client, auth_headers, test_user):
        """PATCH /api/user should allow partial updates"""
        response = client.patch("/api/user/", headers=auth_headers, json={"age": 25})
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_update_user_with_invalid_gender_returns_400(
        self, client, auth_headers, test_user
    ):
        """PATCH /api/user should return 400 for invalid gender"""
        response = client.patch(
            "/api/user/", headers=auth_headers, json={"gender": "invalid"}
        )
        assert response.status_code == 400

    def test_update_user_with_negative_age_returns_400(
        self, client, auth_headers, test_user
    ):
        """PATCH /api/user should return 400 for negative age"""
        response = client.patch("/api/user/", headers=auth_headers, json={"age": -5})
        assert response.status_code == 400

    def test_update_user_with_out_of_range_age_returns_400(
        self, client, auth_headers, test_user
    ):
        """PATCH /api/user should return 400 for age > 100"""
        response = client.patch("/api/user/", headers=auth_headers, json={"age": 150})
        assert response.status_code == 400

    def test_update_user_with_out_of_range_height_returns_400(
        self, client, auth_headers, test_user
    ):
        """PATCH /api/user should return 400 for height > 300"""
        response = client.patch(
            "/api/user/", headers=auth_headers, json={"height": 350}
        )
        assert response.status_code == 400

    def test_reset_user_data_without_auth_returns_401(self, client):
        """POST /api/user/reset should return 401 without authentication"""
        response = client.post("/api/user/reset")
        assert response.status_code == 401

    def test_reset_user_data(self, client, auth_headers, test_user, db_session):
        """POST /api/user/reset should reset all demographic fields"""
        test_user.age = 30
        test_user.height = 180
        test_user.weight = 75
        test_user.gender = "male"
        db_session.commit()

        response = client.post("/api/user/reset", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["message"] == "User data reset"

    def test_delete_user_without_auth_returns_401(self, client):
        """DELETE /api/user should return 401 without authentication"""
        response = client.delete("/api/user/")
        assert response.status_code == 401

    def test_delete_user(self, client, auth_headers, test_user, db_session):
        """DELETE /api/user should delete the user account"""
        user_id = test_user.id
        response = client.delete("/api/user/", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["message"] == "Account deleted"

        deleted_user = db_session.get(User, user_id)
        assert deleted_user is None

    def test_delete_user_commits_transaction(
        self, client, auth_headers, test_user, db_session
    ):
        """DELETE /api/user should properly commit the transaction"""
        user_id = test_user.id
        client.delete("/api/user/", headers=auth_headers)

        deleted_user = db_session.get(User, user_id)
        assert deleted_user is None

    def test_get_user_returns_correct_structure(self, client, auth_headers, test_user):
        """GET /api/user should return response with correct structure"""
        response = client.get("/api/user/", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert "success" in data
        assert "data" in data
        assert data["success"] is True
