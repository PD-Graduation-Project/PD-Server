import pytest

from models.database import db
from models.test_models import TestInput, TestSession
from models.user import User


@pytest.fixture(scope="function")
def clean_test_data(app):
    """Clean up test data before and after each test."""
    with app.app_context():
        TestInput.query.delete()
        TestSession.query.delete()
        db.session.commit()
        yield
        TestInput.query.delete()
        TestSession.query.delete()
        db.session.commit()


@pytest.fixture(scope="function")
def test_session_fixture(app, test_user, clean_test_data):
    """Create a single test session."""
    with app.app_context():
        session = TestSession(
            user_id=test_user.id,
            test_type="tremor",
            status="pending",
            device_source="esp32",
        )
        db.session.add(session)
        db.session.commit()
        yield session


@pytest.fixture(scope="function")
def multiple_sessions_fixture(app, test_user, clean_test_data):
    """Create multiple test sessions."""
    with app.app_context():
        sessions = []
        test_types = ["tremor", "drawing", "voice"]
        statuses = ["pending", "in_progress", "completed"]

        for i, test_type in enumerate(test_types):
            for j, status in enumerate(statuses[: i + 1]):
                session = TestSession(
                    user_id=test_user.id,
                    test_type=test_type,
                    status=status,
                    device_source="mobile" if test_type != "tremor" else "esp32",
                )
                db.session.add(session)
                sessions.append(session)

        db.session.commit()
        yield sessions


class TestCreateTest:
    def test_create_tremor_test(self, client, auth_headers):
        response = client.post(
            "/api/tests",
            json={"test_type": "tremor"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["test_type"] == "tremor"
        assert data["data"]["status"] == "pending"
        assert data["data"]["device_source"] == "esp32"

    def test_create_drawing_test(self, client, auth_headers):
        response = client.post(
            "/api/tests",
            json={"test_type": "drawing"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["test_type"] == "drawing"
        assert data["data"]["device_source"] == "mobile"

    def test_create_voice_test(self, client, auth_headers):
        response = client.post(
            "/api/tests",
            json={"test_type": "voice"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["test_type"] == "voice"
        assert data["data"]["device_source"] == "mobile"

    def test_create_test_with_config(self, client, auth_headers):
        response = client.post(
            "/api/tests",
            json={
                "test_type": "tremor",
                "config": {"step_0": True, "step_2": False, "step_10": True},
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["success"] is True

    def test_create_test_empty_config(self, client, auth_headers):
        response = client.post(
            "/api/tests",
            json={"test_type": "drawing"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["success"] is True

    def test_create_test_with_device_override(self, client, auth_headers):
        response = client.post(
            "/api/tests",
            json={
                "test_type": "tremor",
                "device": "esp32",
                "config": {"step_0": True},
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["device_source"] == "esp32"

    def test_create_test_mobile_override(self, client, auth_headers):
        response = client.post(
            "/api/tests",
            json={
                "test_type": "tremor",
                "device": "mobile",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["device_source"] == "mobile"

    def test_create_test_invalid_device(self, client, auth_headers):
        response = client.post(
            "/api/tests",
            json={
                "test_type": "tremor",
                "device": "invalid",
            },
            headers=auth_headers,
        )
        assert response.status_code == 400

    def test_create_test_invalid_type(self, client, auth_headers):
        response = client.post(
            "/api/tests",
            json={"test_type": "invalid"},
            headers=auth_headers,
        )
        assert response.status_code == 400

    def test_create_test_unauthorized(self, client):
        response = client.post(
            "/api/tests",
            json={"test_type": "tremor"},
        )
        assert response.status_code == 401


class TestListTests:
    def test_list_tests_empty(self, client, auth_headers):
        response = client.get("/api/tests", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["tests"] == []
        assert data["data"]["total"] == 0
        assert data["data"]["page"] == 1

    def test_list_tests_with_sessions(
        self, client, auth_headers, multiple_sessions_fixture
    ):
        response = client.get("/api/tests", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["total"] == 6

    def test_list_tests_filter_by_type(
        self, client, auth_headers, multiple_sessions_fixture
    ):
        response = client.get("/api/tests?test_type=tremor", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        for test in data["data"]["tests"]:
            assert test["test_type"] == "tremor"

    def test_list_tests_filter_by_status(
        self, client, auth_headers, multiple_sessions_fixture
    ):
        response = client.get("/api/tests?status=completed", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        for test in data["data"]["tests"]:
            assert test["status"] == "completed"

    def test_list_tests_pagination(
        self, client, auth_headers, multiple_sessions_fixture
    ):
        response = client.get("/api/tests?page=1&per_page=2", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert len(data["data"]["tests"]) == 2
        assert data["data"]["total"] == 6
        assert data["data"]["pages"] == 3

    def test_list_tests_unauthorized(self, client):
        response = client.get("/api/tests")
        assert response.status_code == 401


class TestGetTest:
    def test_get_test_success(self, client, auth_headers, test_session_fixture):
        response = client.get(
            f"/api/tests/{test_session_fixture.id}", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["id"] == test_session_fixture.id
        assert data["data"]["test_type"] == "tremor"

    def test_get_test_not_found(self, client, auth_headers):
        response = client.get("/api/tests/9999", headers=auth_headers)
        assert response.status_code == 404

    def test_get_test_forbidden(self, app, client, auth_headers):
        with app.app_context():
            other_user = User(email="other@example.com")
            other_user.set_password("password123")
            db.session.add(other_user)
            db.session.commit()

            other_session = TestSession(
                user_id=other_user.id,
                test_type="tremor",
                status="pending",
                device_source="esp32",
            )
            db.session.add(other_session)
            db.session.commit()

            response = client.get(
                f"/api/tests/{other_session.id}", headers=auth_headers
            )
            assert response.status_code == 403

            TestSession.query.filter_by(id=other_session.id).delete()
            User.query.filter_by(email="other@example.com").delete()
            db.session.commit()

    def test_get_test_unauthorized(self, client, test_session_fixture):
        response = client.get(f"/api/tests/{test_session_fixture.id}")
        assert response.status_code == 401
