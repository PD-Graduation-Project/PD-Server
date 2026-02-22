"""
End-to-End Test: ESP32 Device Lifecycle

Tests the complete ESP32 device lifecycle:
1. Unregistered device registers and gets production key
2. Device connects to SSE stream
3. Device sends heartbeat
4. User pairs device
5. Device receives test_started events
6. Device is unpaired
"""

import secrets


class TestESP32Lifecycle:
    """
    E2E Test: Complete ESP32 device lifecycle.

    Lifecycle:
    1. Unregistered device registers (gets production key)
    2. Device connects to SSE stream
    3. Device sends heartbeat
    4. User pairs device
    5. Device receives test_started events
    6. Device is unpaired
    """

    def test_esp32_registration_flow(
        self,
        e2e_client,
        e2e_esp32_unregistered,
    ):
        """
        Test ESP32 registration: first boot → register → get production key.
        """
        # 1. Device Registration
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

        register_data = register_response.get_json()
        assert register_data["success"] is True
        assert register_data["data"]["device_id"] == e2e_esp32_unregistered.device_id
        assert register_data["data"]["api_key"].startswith("sk_live_")

        # Verify the API key was saved to database
        with e2e_client.application.app_context():
            from models.test_models import ESP32Device

            device = ESP32Device.query.filter_by(
                device_id=e2e_esp32_unregistered.device_id
            ).first()

            assert device is not None
            assert device.api_key == register_data["data"]["api_key"]
            assert device.user_id is None  # Not yet paired

    def test_esp32_registration_repeated(
        self,
        e2e_client,
        e2e_esp32_paired,
    ):
        """
        Test that registering an already registered device returns existing key.
        """
        # Device is already registered (has production key)
        register_response = e2e_client.post(
            "/api/esp32/register",
            json={"device_id": e2e_esp32_paired.device_id},
            headers={
                "X-Device-API-Key": e2e_esp32_paired.factory_api_key,
                "Content-Type": "application/json",
            },
        )

        assert register_response.status_code == 200
        register_data = register_response.get_json()

        # Should return the SAME key, not generate a new one
        assert register_data["data"]["api_key"] == e2e_esp32_paired.api_key

    def test_esp32_invalid_registration(
        self,
        e2e_client,
    ):
        """
        Test that registration fails with invalid factory key.
        """
        register_response = e2e_client.post(
            "/api/esp32/register",
            json={"device_id": "INVALID-DEVICE"},
            headers={
                "X-Device-API-Key": "invalid_factory_key",
                "Content-Type": "application/json",
            },
        )

        assert register_response.status_code == 401

    def test_esp32_heartbeat_flow(
        self,
        e2e_client,
        e2e_esp32_paired,
    ):
        """
        Test ESP32 heartbeat: updates is_connected and last_seen_at.
        """
        # 1. Send Heartbeat
        heartbeat_response = e2e_client.post(
            "/api/esp32/heartbeat",
            headers={
                "X-Device-API-Key": e2e_esp32_paired.api_key,
                "Content-Type": "application/json",
            },
        )

        assert heartbeat_response.status_code == 200
        heartbeat_data = heartbeat_response.get_json()
        assert heartbeat_data["success"] is True
        assert heartbeat_data["message"] == "Heartbeat received"

        # 2. Verify Database Updated
        with e2e_client.application.app_context():
            from models.test_models import ESP32Device

            device = ESP32Device.query.get(e2e_esp32_paired.id)
            assert device.is_connected is True
            assert device.last_seen_at is not None

    def test_esp32_heartbeat_unregistered(
        self,
        e2e_client,
        e2e_esp32_unregistered,
    ):
        """
        Test that unregistered device (no production key) cannot send heartbeat.
        """
        heartbeat_response = e2e_client.post(
            "/api/esp32/heartbeat",
            headers={
                "X-Device-API-Key": e2e_esp32_unregistered.api_key or "no_key",
                "Content-Type": "application/json",
            },
        )

        # Should fail - device has no production API key
        assert heartbeat_response.status_code in [401, 403]

    def test_esp32_sse_connection_flow(
        self,
        e2e_client,
        e2e_esp32_paired,
    ):
        """
        Test ESP32 SSE connection: connects and receives events.
        """
        # Note: Full SSE testing requires streaming test client
        # This test verifies the endpoint accepts the connection

        sse_response = e2e_client.get(
            "/api/esp32/stream",
            headers={
                "X-Device-API-Key": e2e_esp32_paired.api_key,
                "Accept": "text/event-stream",
            },
        )

        # Should return 200 with event-stream content type
        assert sse_response.status_code == 200
        assert "text/event-stream" in sse_response.content_type

    def test_esp32_complete_lifecycle(
        self,
        e2e_client,
        e2e_app,
        e2e_user,
    ):
        """
        Test complete ESP32 lifecycle:
        1. Unregistered device registers
        2. Device pairs to user
        3. Device receives test
        4. Device is unpaired
        """
        # ===== STEP 1: Generate Device ID and Factory Key =====
        from utils.factory_key import generate_factory_key

        device_id = f"ESP32-{secrets.token_hex(3).upper()}"
        factory_key = generate_factory_key(device_id)

        # ===== STEP 2: Device Registration =====
        register_response = e2e_client.post(
            "/api/esp32/register",
            json={"device_id": device_id},
            headers={
                "X-Device-API-Key": factory_key,
                "Content-Type": "application/json",
            },
        )
        assert (
            register_response.status_code == 200
        ), f"Registration failed: {register_response.get_json()}"
        production_key = register_response.get_json()["data"]["api_key"]

        # ===== STEP 3: User Login =====
        login_response = e2e_client.post(
            "/api/auth/login",
            json={"email": e2e_user.email, "password": "testpassword123"},
        )
        assert login_response.status_code == 200
        tokens = login_response.get_json()
        auth_headers = {
            "Authorization": f"Bearer {tokens['access_token']}",
            "Content-Type": "application/json",
        }

        # ===== STEP 4: User Pairs Device =====
        pair_response = e2e_client.post(
            "/api/esp32-devices/pair",
            json={"device_id": device_id, "name": "Lifecycle Test Device"},
            headers=auth_headers,
        )
        assert pair_response.status_code == 200
        pair_data = pair_response.get_json()["data"]
        assert pair_data["is_connected"] is False

        # ===== STEP 5: Device Sends Heartbeat =====
        heartbeat_response = e2e_client.post(
            "/api/esp32/heartbeat", headers={"X-Device-API-Key": production_key}
        )
        assert heartbeat_response.status_code == 200

        # ===== STEP 6: Verify Device Status =====
        with e2e_app.app_context():
            from models.test_models import ESP32Device

            device = ESP32Device.query.filter_by(device_id=device_id).first()
            assert device.is_connected is True
            assert device.user_id == e2e_user.id
            assert device.name == "Lifecycle Test Device"

        # ===== STEP 7: Device is Unpaired =====
        unpair_response = e2e_client.delete(
            f"/api/esp32-devices/{pair_data['id']}", headers=auth_headers
        )
        assert unpair_response.status_code == 200

        # ===== STEP 8: Verify Device Unpaired =====
        with e2e_app.app_context():
            from models.test_models import ESP32Device

            device = ESP32Device.query.filter_by(device_id=device_id).first()
            assert device.user_id is None
            assert device.name is None


# Import required modules
