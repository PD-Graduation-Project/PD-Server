from models.database import db
from models.test_models import ESP32Device


class TestPairDevice:
    def test_pair_success(self, client, auth_headers, esp32_device_unpaired):
        """User pairs device with device_id."""
        response = client.post(
            "/api/esp32-devices/pair",
            json={"device_id": "ESP32-005678", "name": "My Sensor"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        result = response.get_json()
        assert result["success"] is True
        assert result["data"]["device_id"] == "ESP32-005678"
        assert result["data"]["name"] == "My Sensor"

    def test_pair_default_name(self, client, auth_headers, esp32_device_unpaired):
        """If no name provided, default to device_id."""
        response = client.post(
            "/api/esp32-devices/pair",
            json={"device_id": "ESP32-005678"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        result = response.get_json()
        assert result["data"]["name"] == "ESP32-005678"

    def test_pair_missing_device_id(self, client, auth_headers):
        """Missing device_id returns 400."""
        response = client.post(
            "/api/esp32-devices/pair",
            json={},
            headers=auth_headers,
        )
        assert response.status_code == 400

    def test_pair_device_not_found(self, client, auth_headers):
        """Unknown device_id returns 404."""
        response = client.post(
            "/api/esp32-devices/pair",
            json={"device_id": "ESP32-NONEXISTENT"},
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_pair_already_paired_same_user(self, client, auth_headers, esp32_device):
        """Re-pairing to same user returns 200 with message."""
        response = client.post(
            "/api/esp32-devices/pair",
            json={"device_id": "ESP32-001234"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        result = response.get_json()
        assert "already paired" in result.get("message", "")

    def test_pair_already_paired_other_user(
        self, app, client, auth_headers, db_session
    ):
        """Device paired to another user returns 409."""
        from models.user import User

        with app.app_context():
            other_user = User(email="other@example.com")
            other_user.set_password("password123")
            db_session.add(other_user)
            db_session.flush()

            device = ESP32Device(
                device_id="ESP32-OTHER",
                factory_api_key="factory_other_key",
                api_key="sk_live_other_key",
                user_id=other_user.id,
            )
            db_session.add(device)
            db_session.commit()

            response = client.post(
                "/api/esp32-devices/pair",
                json={"device_id": "ESP32-OTHER"},
                headers=auth_headers,
            )
            assert response.status_code == 409

    def test_pair_unauthorized(self, client, esp32_device_unpaired):
        """No auth returns 401."""
        response = client.post(
            "/api/esp32-devices/pair",
            json={"device_id": "ESP32-005678"},
        )
        assert response.status_code == 401


class TestListDevices:
    def test_list_devices_success(self, client, auth_headers, esp32_device):
        """List user's paired devices."""
        response = client.get(
            "/api/esp32-devices",
            headers=auth_headers,
        )
        assert response.status_code == 200
        result = response.get_json()
        assert result["success"] is True
        assert len(result["data"]) == 1
        assert result["data"][0]["device_id"] == "ESP32-001234"

    def test_list_devices_empty(self, client, auth_headers):
        """User with no devices gets empty list."""
        response = client.get(
            "/api/esp32-devices",
            headers=auth_headers,
        )
        assert response.status_code == 200
        result = response.get_json()
        assert result["data"] == []

    def test_list_devices_unauthorized(self, client):
        """No auth returns 401."""
        response = client.get("/api/esp32-devices")
        assert response.status_code == 401


class TestUnpairDevice:
    def test_unpair_success(self, app, client, auth_headers, esp32_device):
        """Unpair device removes user_id."""
        response = client.delete(
            f"/api/esp32-devices/{esp32_device.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        result = response.get_json()
        assert result["success"] is True

        with app.app_context():
            device = db.session.get(ESP32Device, esp32_device.id)
            assert device.user_id is None
            assert device.name is None

    def test_unpair_not_found(self, client, auth_headers):
        """Unpair nonexistent device returns 404."""
        response = client.delete(
            "/api/esp32-devices/9999",
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_unpair_other_users_device(
        self, app, client, auth_headers, db_session, esp32_device_unpaired
    ):
        """Cannot unpair another user's device."""
        from models.user import User

        with app.app_context():
            other_user = User(email="other2@example.com")
            other_user.set_password("password123")
            db_session.add(other_user)
            db_session.flush()

            esp32_device_unpaired.user_id = other_user.id
            db_session.commit()

            response = client.delete(
                f"/api/esp32-devices/{esp32_device_unpaired.id}",
                headers=auth_headers,
            )
            assert response.status_code == 404

    def test_unpair_unauthorized(self, client, esp32_device):
        """No auth returns 401."""
        response = client.delete(f"/api/esp32-devices/{esp32_device.id}")
        assert response.status_code == 401
