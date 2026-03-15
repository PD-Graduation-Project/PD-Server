"""
End-to-End Test: Complete Tremor Test Flow

Tests the complete tremor test workflow:
1. User registration/login
2. Device pairing
3. Create tremor test
4. ESP32 registration
5. ESP32 uploads tremor data
6. ESP32 completes test
7. Mobile polls and verifies ML score
"""

import io
import secrets

from tests.e2e.conftest import E2ETestDataGenerator


class TestCompleteTremorFlow:
    """
    E2E Test: Complete tremor test flow from device pairing to ML score.

    Flow:
    1. User logs in
    2. User pairs ESP32 device
    3. User creates tremor test
    4. ESP32 receives test_started event (simulated)
    5. ESP32 uploads gyro data for all enabled subtests
    6. ESP32 completes test
    7. Mobile polls and verifies ML score
    """

    def test_complete_tremor_flow(
        self,
        e2e_client,
        e2e_app,
        e2e_user,
        e2e_esp32_unregistered,
    ):
        """
        Execute the complete tremor test flow.
        """
        # 1. User Login
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

        # 2. ESP32 Registration (must happen before pairing)
        register_response = e2e_client.post(
            "/api/esp32/register",
            json={"device_id": e2e_esp32_unregistered.device_id},
            headers={
                "X-Device-API-Key": e2e_esp32_unregistered.factory_api_key,
                "Content-Type": "application/json",
            },
        )
        assert (
            register_response.status_code == 200
        ), f"Registration failed: {register_response.get_json()}"
        production_key = register_response.get_json()["data"]["api_key"]

        # 3. Pair Device
        pair_response = e2e_client.post(
            "/api/esp32-devices/pair",
            json={
                "device_id": e2e_esp32_unregistered.device_id,
                "name": "E2E Test Sensor",
            },
            headers=auth_headers,
        )
        assert (
            pair_response.status_code == 200
        ), f"Pairing failed: {pair_response.get_json()}"

        pair_data = pair_response.get_json()
        assert pair_data["data"]["is_connected"] is False

        # 4. Create Group + Tremor Test
        group_response = e2e_client.post("/api/groups", headers=auth_headers)
        assert group_response.status_code == 201
        group_id = group_response.get_json()["data"]["id"]

        create_response = e2e_client.post(
            "/api/tests",
            json={
                "test_type": "tremor",
                "group_id": group_id,
                "config": {
                    "0": True,
                    "1": True,
                    "2": False,
                    "3": True,
                },
            },
            headers=auth_headers,
        )
        assert create_response.status_code == 201
        test_data = create_response.get_json()["data"]
        test_id = test_data["id"]
        assert test_data["status"] == "pending"

        esp32_headers = {
            "X-Device-API-Key": production_key,
            "Content-Type": "application/json",
        }

        # 5. Simulate ESP32 Data Upload
        data_generator = E2ETestDataGenerator()

        # Upload step 0, left hand
        gyro_data = data_generator.generate_gyro_data(subtest=0, hand="l", samples=1000)
        upload_response = e2e_client.post(
            f"/api/tests/{test_id}/tremor",
            data={
                "file": (io.BytesIO(gyro_data), "step_0_left.txt"),
                "subtest": "0",
                "hand": "l",
            },
            headers={
                **esp32_headers,
                "Content-Type": "multipart/form-data",
            },
        )
        assert (
            upload_response.status_code == 200
        ), f"Upload failed: {upload_response.get_json()}"

        # Upload step 0, right hand
        gyro_data = data_generator.generate_gyro_data(subtest=0, hand="r", samples=1000)
        upload_response = e2e_client.post(
            f"/api/tests/{test_id}/tremor",
            data={
                "file": (io.BytesIO(gyro_data), "step_0_right.txt"),
                "subtest": "0",
                "hand": "r",
            },
            headers={
                **esp32_headers,
                "Content-Type": "multipart/form-data",
            },
        )
        assert upload_response.status_code == 200

        # Upload step 1, left hand
        gyro_data = data_generator.generate_gyro_data(subtest=1, hand="l", samples=1000)
        upload_response = e2e_client.post(
            f"/api/tests/{test_id}/tremor",
            data={
                "file": (io.BytesIO(gyro_data), "step_1_left.txt"),
                "subtest": "1",
                "hand": "l",
            },
            headers={
                **esp32_headers,
                "Content-Type": "multipart/form-data",
            },
        )
        assert upload_response.status_code == 200

        # Upload step 1, right hand
        gyro_data = data_generator.generate_gyro_data(subtest=1, hand="r", samples=1000)
        upload_response = e2e_client.post(
            f"/api/tests/{test_id}/tremor",
            data={
                "file": (io.BytesIO(gyro_data), "step_1_right.txt"),
                "subtest": "1",
                "hand": "r",
            },
            headers={
                **esp32_headers,
                "Content-Type": "multipart/form-data",
            },
        )
        assert upload_response.status_code == 200

        # Upload step 3, left hand (step_2 is disabled)
        gyro_data = data_generator.generate_gyro_data(subtest=3, hand="l", samples=1000)
        upload_response = e2e_client.post(
            f"/api/tests/{test_id}/tremor",
            data={
                "file": (io.BytesIO(gyro_data), "step_3_left.txt"),
                "subtest": "3",
                "hand": "l",
            },
            headers={
                **esp32_headers,
                "Content-Type": "multipart/form-data",
            },
        )
        assert upload_response.status_code == 200

        # Upload step 3, right hand
        gyro_data = data_generator.generate_gyro_data(subtest=3, hand="r", samples=1000)
        upload_response = e2e_client.post(
            f"/api/tests/{test_id}/tremor",
            data={
                "file": (io.BytesIO(gyro_data), "step_3_right.txt"),
                "subtest": "3",
                "hand": "r",
            },
            headers={
                **esp32_headers,
                "Content-Type": "multipart/form-data",
            },
        )
        assert upload_response.status_code == 200

        # Verify status changed to in_progress
        status_response = e2e_client.get(f"/api/tests/{test_id}", headers=auth_headers)
        assert status_response.status_code == 200
        assert status_response.get_json()["data"]["status"] == "in_progress"

        # 6. Complete Test
        complete_response = e2e_client.post(
            f"/api/tests/{test_id}/complete", headers=esp32_headers
        )
        assert (
            complete_response.status_code == 200
        ), f"Complete failed: {complete_response.get_json()}"

        complete_data = complete_response.get_json()["data"]
        assert complete_data["status"] == "completed"
        assert "ml_score" in complete_data
        assert complete_data["ml_score"] is not None
        assert 0.0 <= complete_data["ml_score"] <= 1.0

        # 7. Mobile Verifies Results
        get_response = e2e_client.get(f"/api/tests/{test_id}", headers=auth_headers)
        assert get_response.status_code == 200

        final_data = get_response.get_json()["data"]
        assert final_data["status"] == "completed"
        assert final_data["ml_score"] == complete_data["ml_score"]

        # Verify test appears in list
        list_response = e2e_client.get("/api/tests", headers=auth_headers)
        assert list_response.status_code == 200

        test_ids = [t["id"] for t in list_response.get_json()["data"]["tests"]]
        assert test_id in test_ids

    def test_tremor_flow_with_single_subtest(
        self,
        e2e_client,
        e2e_app,
        e2e_user,
    ):
        """
        Test tremor flow with only one subtest enabled.
        """
        # Login
        login_response = e2e_client.post(
            "/api/auth/login",
            json={"email": e2e_user.email, "password": "testpassword123"},
        )
        assert login_response.status_code == 200
        tokens = login_response.get_json()

        # Create paired ESP32
        with e2e_app.app_context():
            from models.database import db
            from models.test_models import ESP32Device

            esp32 = ESP32Device(
                device_id=f"ESP32-SINGLE-{secrets.token_hex(4).upper()}",
                user_id=e2e_user.id,
                factory_api_key=f"factory_single_{secrets.token_hex(8)}",
                api_key=f"sk_live_single_{secrets.token_hex(16)}",
                name="Single Subtest Test",
                is_connected=False,
            )
            db.session.add(esp32)
            db.session.commit()
            esp32_api_key = esp32.api_key

        auth_headers_single = {
            "Authorization": f"Bearer {tokens['access_token']}",
            "Content-Type": "application/json",
        }

        # Create group then test with only step 0
        group_resp = e2e_client.post("/api/groups", headers=auth_headers_single)
        assert group_resp.status_code == 201
        group_id = group_resp.get_json()["data"]["id"]

        create_response = e2e_client.post(
            "/api/tests",
            json={"test_type": "tremor", "group_id": group_id, "config": {"0": True}},
            headers=auth_headers_single,
        )
        assert create_response.status_code == 201
        test_id = create_response.get_json()["data"]["id"]

        # Upload both hands for step 0
        data_generator = E2ETestDataGenerator()

        # Left hand
        gyro_data = data_generator.generate_gyro_data(subtest=0, hand="l", samples=10)
        upload_response = e2e_client.post(
            f"/api/tests/{test_id}/tremor",
            data={
                "file": (io.BytesIO(gyro_data), "step_0_left.txt"),
                "subtest": "0",
                "hand": "l",
            },
            headers={
                "X-Device-API-Key": esp32_api_key,
                "Content-Type": "multipart/form-data",
            },
        )
        assert upload_response.status_code == 200

        # Right hand
        gyro_data = data_generator.generate_gyro_data(subtest=0, hand="r", samples=10)
        upload_response = e2e_client.post(
            f"/api/tests/{test_id}/tremor",
            data={
                "file": (io.BytesIO(gyro_data), "step_0_right.txt"),
                "subtest": "0",
                "hand": "r",
            },
            headers={
                "X-Device-API-Key": esp32_api_key,
                "Content-Type": "multipart/form-data",
            },
        )
        assert upload_response.status_code == 200

        # Complete test
        complete_response = e2e_client.post(
            f"/api/tests/{test_id}/complete",
            headers={"X-Device-API-Key": esp32_api_key},
        )
        assert complete_response.status_code == 200

        complete_data = complete_response.get_json()["data"]
        assert complete_data["status"] == "completed"
        assert complete_data["ml_score"] is not None

    def test_tremor_flow_partial_upload_then_complete(
        self,
        e2e_client,
        e2e_app,
        e2e_user,
    ):
        """
        Test that completing with partial uploads still works.
        """
        # Login
        login_response = e2e_client.post(
            "/api/auth/login",
            json={"email": e2e_user.email, "password": "testpassword123"},
        )
        assert login_response.status_code == 200
        tokens = login_response.get_json()

        # Create paired ESP32
        with e2e_app.app_context():
            from models.database import db
            from models.test_models import ESP32Device

            esp32 = ESP32Device(
                device_id=f"ESP32-PARTIAL-{secrets.token_hex(4).upper()}",
                user_id=e2e_user.id,
                factory_api_key=f"factory_partial_{secrets.token_hex(8)}",
                api_key=f"sk_live_partial_{secrets.token_hex(16)}",
                name="Partial Upload Test",
                is_connected=False,
            )
            db.session.add(esp32)
            db.session.commit()
            esp32_api_key = esp32.api_key

        partial_auth_headers = {
            "Authorization": f"Bearer {tokens['access_token']}",
            "Content-Type": "application/json",
        }

        # Create group then test with 3 subtests
        group_resp = e2e_client.post("/api/groups", headers=partial_auth_headers)
        assert group_resp.status_code == 201
        group_id = group_resp.get_json()["data"]["id"]

        create_response = e2e_client.post(
            "/api/tests",
            json={
                "test_type": "tremor",
                "group_id": group_id,
                "config": {"0": True, "1": True, "2": True},
            },
            headers=partial_auth_headers,
        )
        assert create_response.status_code == 201
        test_id = create_response.get_json()["data"]["id"]

        # Upload only ONE subtest
        data_generator = E2ETestDataGenerator()
        gyro_data = data_generator.generate_gyro_data(subtest=0, hand="l", samples=50)

        upload_response = e2e_client.post(
            f"/api/tests/{test_id}/tremor",
            data={
                "file": (io.BytesIO(gyro_data), "step_0.txt"),
                "subtest": "0",
                "hand": "l",
            },
            headers={
                "X-Device-API-Key": esp32_api_key,
                "Content-Type": "multipart/form-data",
            },
        )
        assert upload_response.status_code == 200

        # Complete test (should fail - missing subtests)
        complete_response = e2e_client.post(
            f"/api/tests/{test_id}/complete",
            headers={"X-Device-API-Key": esp32_api_key},
        )
        assert complete_response.status_code == 400

        complete_data = complete_response.get_json()
        assert "missing" in complete_data
        assert "1_l" in complete_data["missing"]
        assert "1_r" in complete_data["missing"]
