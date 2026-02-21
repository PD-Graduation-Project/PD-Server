from models.user import User


class TestQuestionnaireRoutes:
    """Test suite for questionnaire routes"""

    def test_get_questionnaire_without_auth_returns_401(self, client):
        """GET /api/questionnaire should return 401 without authentication"""
        response = client.get("/api/questionnaire/")
        assert response.status_code == 401

    def test_get_questionnaire_returns_all_questions(
        self, client, auth_headers, test_user
    ):
        """GET /api/questionnaire should return all 28 questionnaire responses"""
        response = client.get("/api/questionnaire/", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "data" in data
        assert len(data["data"]) == 28

    def test_get_questionnaire_includes_all_question_ids(
        self, client, auth_headers, test_user
    ):
        """GET /api/questionnaire should include all question IDs from Q01 to Q28"""
        response = client.get("/api/questionnaire/", headers=auth_headers)
        data = response.get_json()
        for i in range(1, 29):
            qid = f"Q{i:02d}"
            assert qid in data["data"]

    def test_get_questionnaire_with_existing_responses(
        self, client, auth_headers, test_user, db_session
    ):
        """GET /api/questionnaire should return existing responses"""
        test_user.Q01 = True
        test_user.Q02 = False
        test_user.Q15 = True
        db_session.commit()

        response = client.get("/api/questionnaire/", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["data"]["Q01"] is True
        assert data["data"]["Q02"] is False
        assert data["data"]["Q15"] is True

    def test_patch_questionnaire_without_auth_returns_401(self, client):
        """PATCH /api/questionnaire should return 401 without authentication"""
        response = client.patch("/api/questionnaire/", json={"Q01": True})
        assert response.status_code == 401

    def test_patch_questionnaire_with_single_question(
        self, client, auth_headers, test_user, db_session
    ):
        """PATCH /api/questionnaire should update a single question"""
        response = client.patch(
            "/api/questionnaire/",
            headers=auth_headers,
            json={"Q01": True},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "Q01" in data["updated"]

        updated_user = db_session.get(User, test_user.id)
        assert updated_user.Q01 is True

    def test_patch_questionnaire_with_multiple_questions(
        self, client, auth_headers, test_user, db_session
    ):
        """PATCH /api/questionnaire should update multiple questions"""
        response = client.patch(
            "/api/questionnaire/",
            headers=auth_headers,
            json={"Q01": True, "Q05": False, "Q10": True},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert len(data["updated"]) == 3

        updated_user = db_session.get(User, test_user.id)
        assert updated_user.Q01 is True
        assert updated_user.Q05 is False
        assert updated_user.Q10 is True

    def test_patch_questionnaire_with_empty_body_returns_400(
        self, client, auth_headers, test_user
    ):
        """PATCH /api/questionnaire should return 400 for empty body"""
        response = client.patch("/api/questionnaire/", headers=auth_headers, json={})
        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert "No valid fields provided" in data["error"]

    def test_patch_questionnaire_with_no_valid_fields_returns_400(
        self, client, auth_headers, test_user
    ):
        """PATCH /api/questionnaire should return 400 for invalid fields"""
        response = client.patch(
            "/api/questionnaire/",
            headers=auth_headers,
            json={"invalid_field": True},
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert "No valid fields provided" in data["error"]

    def test_patch_questionnaire_with_invalid_type_returns_400(
        self, client, auth_headers, test_user
    ):
        """PATCH /api/questionnaire should return 400 for non-boolean values"""
        response = client.patch(
            "/api/questionnaire/",
            headers=auth_headers,
            json={"Q01": "yes"},
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert "must be boolean" in data["error"]

    def test_patch_questionnaire_allows_none_values(
        self, client, auth_headers, test_user, db_session
    ):
        """PATCH /api/questionnaire should allow setting values to None"""
        test_user.Q01 = True
        db_session.commit()

        response = client.patch(
            "/api/questionnaire/",
            headers=auth_headers,
            json={"Q01": None},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

        updated_user = db_session.get(User, test_user.id)
        assert updated_user.Q01 is None

    def test_patch_questionnaire_only_updates_valid_question_ids(
        self, client, auth_headers, test_user, db_session
    ):
        """PATCH /api/questionnaire should ignore invalid question IDs"""
        response = client.patch(
            "/api/questionnaire/",
            headers=auth_headers,
            json={"Q01": True, "Q29": True, "invalid": True},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert len(data["updated"]) == 1
        assert "Q01" in data["updated"]

        updated_user = db_session.get(User, test_user.id)
        assert updated_user.Q01 is True

    def test_get_questionnaire_persists_across_requests(
        self, client, auth_headers, test_user, db_session
    ):
        """Questionnaire responses should persist across multiple requests"""
        client.patch(
            "/api/questionnaire/",
            headers=auth_headers,
            json={"Q01": True, "Q02": False},
        )

        response = client.get("/api/questionnaire/", headers=auth_headers)
        data = response.get_json()
        assert data["data"]["Q01"] is True
        assert data["data"]["Q02"] is False

    def test_questionnaire_handles_all_questions(
        self, client, auth_headers, test_user, db_session
    ):
        """Questionnaire should handle all 28 questions correctly"""
        all_responses = {f"Q{i:02d}": i % 2 == 0 for i in range(1, 29)}

        response = client.patch(
            "/api/questionnaire/",
            headers=auth_headers,
            json=all_responses,
        )
        assert response.status_code == 200

        response = client.get("/api/questionnaire/", headers=auth_headers)
        data = response.get_json()

        for i in range(1, 29):
            qid = f"Q{i:02d}"
            assert data["data"][qid] == (i % 2 == 0)
