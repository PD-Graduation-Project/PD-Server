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


@pytest.fixture(scope="function")
def in_progress_drawing_session(app, test_user, clean_test_data):
    """Create an in-progress drawing session with one upload."""
    with app.app_context():
        session = TestSession(
            user_id=test_user.id,
            test_type="drawing",
            status="in_progress",
            device_source="mobile",
        )
        db.session.add(session)
        db.session.flush()

        test_input = TestInput(
            test_session_id=session.id,
            input_type="drawing_spiral",
            file_path="/uploads/drawing/1/spiral_left.png",
            original_filename="left.png",
            mime_type="image/png",
            file_size=1024,
        )
        db.session.add(test_input)
        db.session.commit()
        yield session


@pytest.fixture(scope="function")
def in_progress_drawing_complete_session(app, test_user, clean_test_data):
    """Create an in-progress drawing session with both uploads."""
    with app.app_context():
        session = TestSession(
            user_id=test_user.id,
            test_type="drawing",
            status="in_progress",
            device_source="mobile",
        )
        db.session.add(session)
        db.session.flush()

        test_input1 = TestInput(
            test_session_id=session.id,
            input_type="drawing_spiral",
            file_path="/uploads/drawing/1/spiral_left.png",
            original_filename="left.png",
            mime_type="image/png",
            file_size=1024,
        )
        test_input2 = TestInput(
            test_session_id=session.id,
            input_type="drawing_spiral",
            file_path="/uploads/drawing/1/spiral_right.png",
            original_filename="right.png",
            mime_type="image/png",
            file_size=1024,
        )
        db.session.add(test_input1)
        db.session.add(test_input2)
        db.session.commit()
        yield session


@pytest.fixture(scope="function")
def empty_config_tremor_session(app, test_user, clean_test_data):
    """Create a tremor session with empty config (no subtests enabled)."""
    with app.app_context():
        session = TestSession(
            user_id=test_user.id,
            test_type="tremor",
            status="in_progress",
            device_source="esp32",
            config={},
        )
        db.session.add(session)
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
        self, app, client, auth_headers, in_progress_voice_session
    ):
        response = client.post(
            f"/api/tests/{in_progress_voice_session.id}/complete",
            headers=auth_headers,
        )
        assert response.status_code == 200
        result = response.get_json()
        assert result["success"] is True
        assert result["data"]["status"] == "completed"
        assert "ml_score" in result["data"]
        assert result["data"]["ml_score"] is not None
        assert 0.0 <= result["data"]["ml_score"] <= 1.0

        with app.app_context():
            from models.test_models import TestSession

            session = db.session.get(TestSession, in_progress_voice_session.id)
            assert session.ml_score is not None

    def test_complete_test_already_completed(
        self, app, client, auth_headers, test_user, clean_test_data
    ):
        with app.app_context():
            session = TestSession(
                user_id=test_user.id,
                test_type="voice",
                status="completed",
                device_source="mobile",
                ml_score=0.5,
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

    # Test 1: Drawing partial upload (only 1 image) → 400
    def test_complete_drawing_partial_upload_fails(
        self, client, auth_headers, in_progress_drawing_session
    ):
        """Test that completing drawing test with only 1 image fails."""
        response = client.post(
            f"/api/tests/{in_progress_drawing_session.id}/complete",
            headers=auth_headers,
        )
        assert response.status_code == 400
        result = response.get_json()
        assert result["error"] == "Missing required subtest uploads"
        assert "missing" in result
        assert "spiral drawings incomplete" in result["missing"]

    # Test 2: Voice without audio → 400
    def test_complete_voice_no_upload_fails(
        self, app, client, auth_headers, voice_session
    ):
        """Test that completing voice test without audio upload fails."""
        # Set status to in_progress manually (since we need at least one upload first)
        with app.app_context():
            voice_session.status = "in_progress"
            db.session.commit()

        response = client.post(
            f"/api/tests/{voice_session.id}/complete",
            headers=auth_headers,
        )
        assert response.status_code == 400
        result = response.get_json()
        assert result["error"] == "Missing required subtest uploads"
        assert "missing" in result
        assert "voice recording" in result["missing"]

    # Test 3: Complete another user's test → 403
    def test_complete_other_user_test_fails(
        self, app, client, multiple_users, clean_test_data
    ):
        """Test that completing another user's test returns 403."""
        # multiple_users fixture creates:
        # users[0]: user0@example.com with password0 (session owner)
        # users[1]: user1@example.com with password1 (attacker)
        user0 = multiple_users[0]  # user0@example.com

        with app.app_context():
            # Create session for user0
            session = TestSession(
                user_id=user0.id,
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
            session_id = session.id

        # Login as user1 (different user)
        response = client.post(
            "/api/auth/login",
            json={"email": "user1@example.com", "password": "password1"},
        )
        assert response.status_code == 200
        tokens = response.get_json()
        user1_headers = {
            "Authorization": f"Bearer {tokens['access_token']}",
            "Content-Type": "application/json",
        }

        # Try to complete user0's session as user1
        response = client.post(
            f"/api/tests/{session_id}/complete",
            headers=user1_headers,
        )
        assert response.status_code == 403

    # Test 4: Tremor with empty config (no subtests enabled)
    def test_complete_tremor_empty_config_succeeds(
        self, client, auth_headers, empty_config_tremor_session
    ):
        """Test completing tremor test with no enabled subtests."""
        # Since no subtests are enabled, expected_count should be 0
        # So missing list should be empty, allowing completion
        response = client.post(
            f"/api/tests/{empty_config_tremor_session.id}/complete",
            headers=auth_headers,
        )
        # This depends on implementation - currently it will complete since no files are required
        assert response.status_code == 200
        result = response.get_json()
        assert result["data"]["status"] == "completed"
        # ML model still runs and returns a score even with no data
        assert "ml_score" in result["data"]

    # Test 5: ML model exception handling - currently returns 500 (no graceful handling)
    def test_complete_test_ml_exception_returns_500(
        self, app, client, auth_headers, in_progress_drawing_complete_session
    ):
        """Test that ML model exceptions cause 500 error (documents current behavior)."""
        # Mock the predict_drawing function to raise an exception
        from unittest.mock import patch

        import pytest

        with patch("ml.drawing_model.predict_drawing") as mock_predict:
            mock_predict.side_effect = Exception("ML model failed")

            # Currently the exception propagates and returns 500
            # In the future, this could be improved to return 500 with a user-friendly error
            with pytest.raises(Exception, match="ML model failed"):
                client.post(
                    f"/api/tests/{in_progress_drawing_complete_session.id}/complete",
                    headers=auth_headers,
                )
            # Note: When Flask's test client raises an exception, pytest catches it
            # In production, this would be a 500 error
