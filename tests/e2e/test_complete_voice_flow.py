"""
End-to-End Test: Complete Voice Test Flow

Tests the complete self-administered voice test workflow:
1. User registration/login
2. Create voice test
3. Upload voice recording
4. Complete test
5. Verify ML score
"""

import io

from tests.e2e.conftest import E2ETestDataGenerator


class TestCompleteVoiceFlow:
    """
    E2E Test: Complete voice test flow.

    Flow:
    1. User logs in
    2. User creates voice test
    3. User uploads voice recording
    4. User completes test
    5. Verify ML score is calculated
    """

    def test_complete_voice_flow(
        self,
        e2e_client,
        e2e_user,
    ):
        """
        Execute the complete voice test flow.
        """
        # ===== STEP 1: User Login =====
        login_response = e2e_client.post(
            "/api/auth/login",
            json={"email": e2e_user.email, "password": "testpassword123"},
        )
        assert (
            login_response.status_code == 200
        ), f"Login failed: {login_response.get_json()}"

        tokens = login_response.get_json()
        auth_headers = {
            "Authorization": f"Bearer {tokens['access_token']}",
            "Content-Type": "application/json",
        }

        # ===== STEP 2: Create Group + Voice Test =====
        group_response = e2e_client.post("/api/groups", headers=auth_headers)
        assert group_response.status_code == 201
        group_id = group_response.get_json()["data"]["id"]

        create_response = e2e_client.post(
            "/api/tests",
            json={"test_type": "voice", "group_id": group_id},
            headers=auth_headers,
        )
        assert create_response.status_code == 201
        test_data = create_response.get_json()["data"]
        test_id = test_data["id"]
        assert test_data["status"] == "pending"

        # ===== STEP 3: Generate Voice Sample =====
        data_generator = E2ETestDataGenerator()
        voice_sample = data_generator.generate_voice_sample(
            duration_ms=3000, sample_rate=44100, frequency=440.0, format="WAV"
        )

        # ===== STEP 4: Upload Voice Recording =====
        upload_response = e2e_client.post(
            f"/api/tests/{test_id}/voice",
            data={
                "audio": (io.BytesIO(voice_sample), "voice_recording.wav"),
            },
            headers={
                "Authorization": f"Bearer {tokens['access_token']}",
                "Content-Type": "multipart/form-data",
            },
        )
        assert (
            upload_response.status_code == 200
        ), f"Upload failed: {upload_response.get_json()}"

        upload_data = upload_response.get_json()["data"]
        assert upload_data["input_type"] == "voice_recording"

        # Verify status changed to in_progress
        status_response = e2e_client.get(f"/api/tests/{test_id}", headers=auth_headers)
        assert status_response.status_code == 200
        assert status_response.get_json()["data"]["status"] == "in_progress"

        # ===== STEP 5: Complete Test =====
        complete_response = e2e_client.post(
            f"/api/tests/{test_id}/complete", headers=auth_headers
        )
        assert (
            complete_response.status_code == 200
        ), f"Complete failed: {complete_response.get_json()}"

        complete_data = complete_response.get_json()["data"]
        assert complete_data["status"] == "completed"
        assert "ml_score" in complete_data
        assert complete_data["ml_score"] is not None
        assert 0.0 <= complete_data["ml_score"] <= 1.0

        # ===== STEP 6: Verify Results =====
        get_response = e2e_client.get(f"/api/tests/{test_id}", headers=auth_headers)
        assert get_response.status_code == 200

        final_data = get_response.get_json()["data"]
        assert final_data["status"] == "completed"
        assert final_data["ml_score"] == complete_data["ml_score"]

    def test_voice_flow_multiple_recordings(
        self,
        e2e_client,
        e2e_user,
    ):
        """
        Test that uploading multiple voice recordings works.
        """
        # Login
        login_response = e2e_client.post(
            "/api/auth/login",
            json={"email": e2e_user.email, "password": "testpassword123"},
        )
        assert login_response.status_code == 200
        tokens = login_response.get_json()

        voice_auth = {
            "Authorization": f"Bearer {tokens['access_token']}",
            "Content-Type": "application/json",
        }

        # Create group then test
        group_response = e2e_client.post("/api/groups", headers=voice_auth)
        assert group_response.status_code == 201
        group_id = group_response.get_json()["data"]["id"]

        create_response = e2e_client.post(
            "/api/tests",
            json={"test_type": "voice", "group_id": group_id},
            headers=voice_auth,
        )
        assert create_response.status_code == 201
        test_id = create_response.get_json()["data"]["id"]

        # Generate and upload multiple voice samples
        data_generator = E2ETestDataGenerator()

        for i in range(3):
            voice_sample = data_generator.generate_voice_sample(
                duration_ms=1000 + (i * 500), format="WAV"
            )

            upload_response = e2e_client.post(
                f"/api/tests/{test_id}/voice",
                data={
                    "audio": (io.BytesIO(voice_sample), f"recording_{i}.wav"),
                },
                headers={
                    "Authorization": f"Bearer {tokens['access_token']}",
                    "Content-Type": "multipart/form-data",
                },
            )
            assert upload_response.status_code == 200

        # Complete test
        complete_response = e2e_client.post(
            f"/api/tests/{test_id}/complete",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert complete_response.status_code == 200
        assert complete_response.get_json()["data"]["ml_score"] is not None
