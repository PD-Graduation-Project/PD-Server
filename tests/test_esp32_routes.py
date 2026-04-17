import pytest
from unittest.mock import patch, MagicMock

from models.database import db
from models.test_models import ESP32Device


@pytest.fixture
def mock_esp32_connection_manager():
    """Mock the ESP32 connection manager for SSE tests."""
    with patch("routes.esp32_routes.connection_manager") as mock:
        mock.add = MagicMock()
        mock.remove = MagicMock()
        mock.is_connected = MagicMock(return_value=True)
        mock.send_event = MagicMock(return_value=True)
        yield mock


class TestESP32Register:
    def test_register_success(self, app, client, esp32_device_unregistered):
        """ESP32 registers with HMAC factory key and gets production key."""
        headers = {"X-Device-API-Key": esp32_device_unregistered.factory_api_key}
        response = client.post(
            "/api/esp32/register",
            json={"device_id": esp32_device_unregistered.device_id},
            headers=headers,
        )
        assert response.status_code == 200
        result = response.get_json()
        assert result["success"] is True
        assert result["data"]["device_id"] == "ESP32-009999"
        assert result["data"]["api_key"].startswith("sk_live_")

        # Verify device was created in DB
        with app.app_context():
            device = ESP32Device.query.filter_by(device_id="ESP32-009999").first()
            assert device is not None
            assert device.api_key.startswith("sk_live_")
            assert device.factory_api_key == esp32_device_unregistered.factory_api_key

    def test_register_already_registered(self, client, esp32_device):
        """ESP32 already has production key, returns existing key."""
        headers = {"X-Device-API-Key": esp32_device.factory_api_key}
        response = client.post(
            "/api/esp32/register",
            json={"device_id": esp32_device.device_id},
            headers=headers,
        )
        assert response.status_code == 200
        result = response.get_json()
        assert result["data"]["api_key"] == esp32_device.api_key

    def test_register_invalid_factory_key_format(self, client):
        """Invalid factory key format (not starting with fk_) returns 401."""
        headers = {"X-Device-API-Key": "invalid_factory_key"}
        response = client.post(
            "/api/esp32/register",
            json={"device_id": "ESP32-000000"},
            headers=headers,
        )
        assert response.status_code == 401
        assert "Invalid factory key format" in response.get_json()["error"]

    def test_register_invalid_hmac(self, client):
        """Factory key with correct format but wrong HMAC returns 401."""
        headers = {"X-Device-API-Key": "fk_00000000000000000000000000000000"}
        response = client.post(
            "/api/esp32/register",
            json={"device_id": "ESP32-AABBCC"},
            headers=headers,
        )
        assert response.status_code == 401
        assert "Invalid factory key" in response.get_json()["error"]

    def test_register_missing_api_key_header(self, client):
        """Missing X-Device-API-Key header returns 401."""
        response = client.post(
            "/api/esp32/register",
            json={"device_id": "ESP32-000000"},
        )
        assert response.status_code == 401

    def test_register_missing_device_id(self, client, esp32_device_unregistered):
        """Missing device_id in body returns 400."""
        headers = {"X-Device-API-Key": esp32_device_unregistered.factory_api_key}
        response = client.post(
            "/api/esp32/register",
            json={},
            headers=headers,
        )
        assert response.status_code == 400
        assert "device_id is required" in response.get_json()["error"]

    def test_register_invalid_device_id_format(self, client):
        """Invalid device_id format returns 400."""

        # Generate a valid factory key for an invalid device_id
        # This tests the format validation
        headers = {"X-Device-API-Key": "fk_00000000000000000000000000000000"}
        response = client.post(
            "/api/esp32/register",
            json={"device_id": "INVALID-FORMAT"},
            headers=headers,
        )
        assert response.status_code == 400
        assert "Invalid device_id format" in response.get_json()["error"]

    def test_register_creates_device_on_first_registration(self, app, client):
        """First registration creates device in DB."""
        from utils.factory_key import generate_factory_key

        device_id = "ESP32-AABBCC"
        factory_key = generate_factory_key(device_id)

        headers = {"X-Device-API-Key": factory_key}
        response = client.post(
            "/api/esp32/register",
            json={"device_id": device_id},
            headers=headers,
        )
        assert response.status_code == 200

        # Verify device created in DB
        with app.app_context():
            device = ESP32Device.query.filter_by(device_id=device_id).first()
            assert device is not None
            assert device.factory_api_key == factory_key
            assert device.api_key.startswith("sk_live_")
            assert device.user_id is None  # Not paired yet

    def test_register_lowercase_device_id_normalized(self, app, client):
        """Device ID is normalized to uppercase."""
        from utils.factory_key import generate_factory_key

        device_id = "ESP32-DDEEFF"
        factory_key = generate_factory_key(device_id)

        headers = {"X-Device-API-Key": factory_key}
        response = client.post(
            "/api/esp32/register",
            json={"device_id": "esp32-ddeeff"},  # lowercase
            headers=headers,
        )
        assert response.status_code == 200
        assert response.get_json()["data"]["device_id"] == "ESP32-DDEEFF"


class TestESP32Heartbeat:
    def test_heartbeat_success(self, client, esp32_api_key_headers, esp32_device):
        """Heartbeat updates device status."""
        response = client.post(
            "/api/esp32/heartbeat",
            headers=esp32_api_key_headers,
        )
        assert response.status_code == 200
        result = response.get_json()
        assert result["success"] is True
        assert result["message"] == "Heartbeat received"

    def test_heartbeat_updates_device(
        self, app, client, esp32_api_key_headers, esp32_device
    ):
        """Heartbeat sets is_connected and last_seen_at."""
        client.post("/api/esp32/heartbeat", headers=esp32_api_key_headers)

        with app.app_context():
            device = db.session.get(ESP32Device, esp32_device.id)
            assert device.is_connected is True
            assert device.last_seen_at is not None

    def test_heartbeat_invalid_key(self, client):
        """Invalid production key returns 401."""
        headers = {"X-Device-API-Key": "invalid_key"}
        response = client.post("/api/esp32/heartbeat", headers=headers)
        assert response.status_code == 401

    def test_heartbeat_unpaired_device(self, client, esp32_device_unpaired):
        """Unpaired device (no user_id) returns 403."""
        headers = {"X-Device-API-Key": esp32_device_unpaired.api_key}
        response = client.post("/api/esp32/heartbeat", headers=headers)
        assert response.status_code == 403

    def test_heartbeat_no_header(self, client):
        """Missing header returns 401."""
        response = client.post("/api/esp32/heartbeat")
        assert response.status_code == 401


class TestESP32Stream:
    def test_stream_returns_sse_content_type(
        self, client, esp32_api_key_headers, mock_esp32_connection_manager
    ):
        """Stream returns text/event-stream content type."""
        response = client.get(
            "/api/esp32/stream",
            headers=esp32_api_key_headers,
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.content_type
        response.close()

    def test_stream_unauthorized(self, client):
        """Stream without auth returns 401."""
        response = client.get("/api/esp32/stream")
        assert response.status_code == 401

    def test_stream_invalid_key(self, client):
        """Stream with invalid key returns 401."""
        headers = {"X-Device-API-Key": "invalid_key"}
        response = client.get("/api/esp32/stream", headers=headers)
        assert response.status_code == 401

    def test_stream_unpaired_device(self, client, esp32_device_unpaired):
        """Unpaired device cannot connect to stream."""
        headers = {"X-Device-API-Key": esp32_device_unpaired.api_key}
        response = client.get("/api/esp32/stream", headers=headers)
        assert response.status_code == 403
