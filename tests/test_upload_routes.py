import pytest

from models.database import db
from models.test_models import TestInput, TestSession


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
def tremor_session(app, test_user, clean_test_data):
    """Create a tremor test session."""
    with app.app_context():
        session = TestSession(
            user_id=test_user.id,
            test_type="tremor",
            status="pending",
            device_source="esp32",
            config={"step_0": True, "step_1": True, "step_2": False},
        )
        db.session.add(session)
        db.session.commit()
        yield session


@pytest.fixture(scope="function")
def drawing_session(app, test_user, clean_test_data):
    """Create a drawing test session."""
    with app.app_context():
        session = TestSession(
            user_id=test_user.id,
            test_type="drawing",
            status="pending",
            device_source="mobile",
        )
        db.session.add(session)
        db.session.commit()
        yield session


@pytest.fixture(scope="function")
def voice_session(app, test_user, clean_test_data):
    """Create a voice test session."""
    with app.app_context():
        session = TestSession(
            user_id=test_user.id,
            test_type="voice",
            status="pending",
            device_source="mobile",
        )
        db.session.add(session)
        db.session.commit()
        yield session


@pytest.fixture(scope="function")
def in_progress_voice_session(app, test_user, clean_test_data):
    """Create an in-progress voice session with an upload."""
    with app.app_context():
        session = TestSession(
            user_id=test_user.id,
            test_type="voice",
            status="in_progress",
            device_source="mobile",
        )
        db.session.add(session)
        db.session.flush()

        test_input = TestInput(
            test_session_id=session.id,
            input_type="voice_recording",
            file_path="/uploads/voice/1/recording.wav",
            original_filename="test.wav",
            mime_type="audio/wav",
            file_size=1024,
        )
        db.session.add(test_input)
        db.session.commit()
        yield session


class TestUploadTremor:
    def test_upload_tremor_success(self, client, auth_headers, tremor_session):
        import io

        data = {
            "file": (io.BytesIO(b"gyro data here"), "test.txt"),
            "subtest": "0",
            "hand": "l",
        }
        response = client.post(
            f"/api/tests/{tremor_session.id}/tremor",
            data=data,
            headers=auth_headers,
            content_type="multipart/form-data",
        )
        assert response.status_code == 200
        result = response.get_json()
        assert result["success"] is True
        assert result["data"]["subtest"] == "0"
        assert result["data"]["hand"] == "l"
        assert result["data"]["input_type"] == "tremor_gyro"

    def test_upload_tremor_updates_status(self, client, auth_headers, tremor_session):
        import io

        data = {
            "file": (io.BytesIO(b"gyro data"), "test.txt"),
            "subtest": "0",
            "hand": "l",
        }
        response = client.post(
            f"/api/tests/{tremor_session.id}/tremor",
            data=data,
            headers=auth_headers,
            content_type="multipart/form-data",
        )
        assert response.status_code == 200

        get_response = client.get(
            f"/api/tests/{tremor_session.id}", headers=auth_headers
        )
        assert get_response.get_json()["data"]["status"] == "in_progress"

    def test_upload_tremor_invalid_subtest(self, client, auth_headers, tremor_session):
        import io

        data = {
            "file": (io.BytesIO(b"data"), "test.txt"),
            "subtest": "invalid",
            "hand": "l",
        }
        response = client.post(
            f"/api/tests/{tremor_session.id}/tremor",
            data=data,
            headers=auth_headers,
            content_type="multipart/form-data",
        )
        assert response.status_code == 400

    def test_upload_tremor_invalid_hand(self, client, auth_headers, tremor_session):
        import io

        data = {
            "file": (io.BytesIO(b"data"), "test.txt"),
            "subtest": "0",
            "hand": "x",
        }
        response = client.post(
            f"/api/tests/{tremor_session.id}/tremor",
            data=data,
            headers=auth_headers,
            content_type="multipart/form-data",
        )
        assert response.status_code == 400

    def test_upload_tremor_missing_file(self, client, auth_headers, tremor_session):
        data = {
            "subtest": "0",
            "hand": "l",
        }
        response = client.post(
            f"/api/tests/{tremor_session.id}/tremor",
            data=data,
            headers=auth_headers,
            content_type="multipart/form-data",
        )
        assert response.status_code == 400

    def test_upload_tremor_wrong_test_type(
        self, app, client, auth_headers, test_user, clean_test_data
    ):
        import io

        with app.app_context():
            session = TestSession(
                user_id=test_user.id,
                test_type="drawing",
                status="pending",
                device_source="mobile",
            )
            db.session.add(session)
            db.session.commit()

            data = {
                "file": (io.BytesIO(b"data"), "test.txt"),
                "subtest": "0",
                "hand": "l",
            }
            response = client.post(
                f"/api/tests/{session.id}/tremor",
                data=data,
                headers=auth_headers,
                content_type="multipart/form-data",
            )
            assert response.status_code == 400

    def test_upload_tremor_unauthorized(self, client, tremor_session):
        import io

        data = {
            "file": (io.BytesIO(b"data"), "test.txt"),
            "subtest": "0",
            "hand": "l",
        }
        response = client.post(
            f"/api/tests/{tremor_session.id}/tremor",
            data=data,
            content_type="multipart/form-data",
        )
        assert response.status_code == 401


class TestUploadDrawings:
    def test_upload_drawings_success(self, client, auth_headers, drawing_session):
        import io

        data = {
            "spiral_left": (io.BytesIO(b"fake png data"), "left.png"),
            "spiral_right": (io.BytesIO(b"fake png data"), "right.png"),
        }
        response = client.post(
            f"/api/tests/{drawing_session.id}/drawings",
            data=data,
            headers=auth_headers,
            content_type="multipart/form-data",
        )
        assert response.status_code == 200
        result = response.get_json()
        assert result["success"] is True
        assert len(result["data"]["inputs"]) == 2

    def test_upload_drawings_missing_file(self, client, auth_headers, drawing_session):
        import io

        data = {
            "spiral_left": (io.BytesIO(b"fake png data"), "left.png"),
        }
        response = client.post(
            f"/api/tests/{drawing_session.id}/drawings",
            data=data,
            headers=auth_headers,
            content_type="multipart/form-data",
        )
        assert response.status_code == 400

    def test_upload_drawings_wrong_test_type(
        self, client, auth_headers, tremor_session
    ):
        import io

        data = {
            "spiral_left": (io.BytesIO(b"data"), "left.png"),
            "spiral_right": (io.BytesIO(b"data"), "right.png"),
        }
        response = client.post(
            f"/api/tests/{tremor_session.id}/drawings",
            data=data,
            headers=auth_headers,
            content_type="multipart/form-data",
        )
        assert response.status_code == 400


class TestUploadVoice:
    def test_upload_voice_success(self, client, auth_headers, voice_session):
        import io

        data = {
            "audio": (io.BytesIO(b"fake audio data"), "recording.wav"),
        }
        response = client.post(
            f"/api/tests/{voice_session.id}/voice",
            data=data,
            headers=auth_headers,
            content_type="multipart/form-data",
        )
        assert response.status_code == 200
        result = response.get_json()
        assert result["success"] is True
        assert result["data"]["input_type"] == "voice_recording"

    def test_upload_voice_missing_file(self, client, auth_headers, voice_session):
        response = client.post(
            f"/api/tests/{voice_session.id}/voice",
            data={},
            headers=auth_headers,
            content_type="multipart/form-data",
        )
        assert response.status_code == 400

    def test_upload_voice_wrong_test_type(self, client, auth_headers, tremor_session):
        import io

        data = {
            "audio": (io.BytesIO(b"data"), "recording.wav"),
        }
        response = client.post(
            f"/api/tests/{tremor_session.id}/voice",
            data=data,
            headers=auth_headers,
            content_type="multipart/form-data",
        )
        assert response.status_code == 400


class TestCompleteTest:
    def test_complete_test_success(
        self, client, auth_headers, in_progress_voice_session
    ):
        response = client.post(
            f"/api/tests/{in_progress_voice_session.id}/complete",
            headers=auth_headers,
        )
        assert response.status_code == 200
        result = response.get_json()
        assert result["success"] is True
        assert result["data"]["status"] == "completed"

    def test_complete_test_already_completed(
        self, app, client, auth_headers, test_user, clean_test_data
    ):
        with app.app_context():
            session = TestSession(
                user_id=test_user.id,
                test_type="voice",
                status="completed",
                device_source="mobile",
            )
            db.session.add(session)
            db.session.commit()

            response = client.post(
                f"/api/tests/{session.id}/complete",
                headers=auth_headers,
            )
            assert response.status_code == 400

    def test_complete_test_pending(self, client, auth_headers, tremor_session):
        response = client.post(
            f"/api/tests/{tremor_session.id}/complete",
            headers=auth_headers,
        )
        assert response.status_code == 400

    def test_complete_test_unauthorized(self, client, in_progress_voice_session):
        response = client.post(
            f"/api/tests/{in_progress_voice_session.id}/complete",
        )
        assert response.status_code == 401
