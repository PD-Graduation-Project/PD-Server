"""
End-to-End Test: Multi-User Isolation

Tests that users cannot access each other's devices and tests:
1. User A pairs a device
2. User B cannot pair the same device
3. User A creates a test
4. User B cannot access User A's test
5. User A can access their own test
"""

import secrets


class TestMultiUserIsolation:
    """
    E2E Test: Multi-user isolation.

    Tests:
    1. User A pairs a device - User B cannot pair same device
    2. User A creates a test - User B cannot access it
    3. User A's devices are not visible to User B
    """

    def test_device_pairing_isolation(
        self,
        e2e_client,
        e2e_app,
    ):
        """
        Test that User B cannot pair a device already paired to User A.
        """
        email_a = f"usera_{secrets.token_hex(8)}@example.com"
        email_b = f"userb_{secrets.token_hex(8)}@example.com"

        # ===== Create User A =====
        with e2e_app.app_context():
            from models.database import db
            from models.user import User

            user_a = User(email=email_a)
            user_a.set_password("password123")
            db.session.add(user_a)
            db.session.commit()

        # ===== Create User B =====
        with e2e_app.app_context():
            from models.database import db
            from models.user import User

            user_b = User(email=email_b)
            user_b.set_password("password123")
            db.session.add(user_b)
            db.session.commit()

        # ===== Create ESP32 Device =====
        with e2e_app.app_context():
            from models.database import db
            from models.test_models import ESP32Device

            esp32 = ESP32Device(
                device_id=f"ESP32-ISO-{secrets.token_hex(4).upper()}",
                factory_api_key=f"factory_iso_{secrets.token_hex(8)}",
                api_key=f"sk_live_iso_{secrets.token_hex(16)}",
                is_connected=False,
            )
            db.session.add(esp32)
            db.session.commit()
            device_id = esp32.device_id

        # ===== User A Logs In =====
        login_a_response = e2e_client.post(
            "/api/auth/login",
            json={"email": email_a, "password": "password123"},
        )
        assert login_a_response.status_code == 200
        token_a = login_a_response.get_json()["access_token"]
        headers_a = {
            "Authorization": f"Bearer {token_a}",
            "Content-Type": "application/json",
        }

        # ===== User B Logs In =====
        login_b_response = e2e_client.post(
            "/api/auth/login",
            json={"email": email_b, "password": "password123"},
        )
        assert login_b_response.status_code == 200
        token_b = login_b_response.get_json()["access_token"]
        headers_b = {
            "Authorization": f"Bearer {token_b}",
            "Content-Type": "application/json",
        }

        # ===== User A Pairs Device =====
        pair_a_response = e2e_client.post(
            "/api/esp32-devices/pair",
            json={"device_id": device_id, "name": "User A's Device"},
            headers=headers_a,
        )
        assert pair_a_response.status_code == 200
        assert pair_a_response.get_json()["data"]["name"] == "User A's Device"

        # ===== User B Cannot Pair Same Device =====
        pair_b_response = e2e_client.post(
            "/api/esp32-devices/pair",
            json={"device_id": device_id, "name": "User B's Device"},
            headers=headers_b,
        )
        assert pair_b_response.status_code == 409  # Conflict

    def test_test_access_isolation(
        self,
        e2e_client,
        e2e_app,
    ):
        """
        Test that User B cannot access User A's test.
        """
        email_a = f"usera_test_{secrets.token_hex(8)}@example.com"
        email_b = f"userb_test_{secrets.token_hex(8)}@example.com"

        # ===== Create User A =====
        with e2e_app.app_context():
            from models.database import db
            from models.user import User

            user_a = User(email=email_a)
            user_a.set_password("password123")
            db.session.add(user_a)
            db.session.commit()

        # ===== Create User B =====
        with e2e_app.app_context():
            from models.database import db
            from models.user import User

            user_b = User(email=email_b)
            user_b.set_password("password123")
            db.session.add(user_b)
            db.session.commit()

        # ===== User A Logs In =====
        login_a_response = e2e_client.post(
            "/api/auth/login",
            json={"email": email_a, "password": "password123"},
        )
        assert login_a_response.status_code == 200
        token_a = login_a_response.get_json()["access_token"]
        headers_a = {
            "Authorization": f"Bearer {token_a}",
            "Content-Type": "application/json",
        }

        # ===== User B Logs In =====
        login_b_response = e2e_client.post(
            "/api/auth/login",
            json={"email": email_b, "password": "password123"},
        )
        assert login_b_response.status_code == 200
        token_b = login_b_response.get_json()["access_token"]
        headers_b = {
            "Authorization": f"Bearer {token_b}",
            "Content-Type": "application/json",
        }

        # ===== User A Creates Group + Test =====
        group_response = e2e_client.post("/api/groups", headers=headers_a)
        assert group_response.status_code == 201
        group_id = group_response.get_json()["data"]["id"]

        create_response = e2e_client.post(
            "/api/tests",
            json={"test_type": "tremor", "config": {"0": True}, "group_id": group_id},
            headers=headers_a,
        )
        assert create_response.status_code == 201
        test_id = create_response.get_json()["data"]["id"]

        # ===== User B Cannot Access User A's Test =====
        get_b_response = e2e_client.get(f"/api/tests/{test_id}", headers=headers_b)
        assert get_b_response.status_code in [403, 404]  # Forbidden or Not Found

        # ===== User A Can Access Their Own Test =====
        get_a_response = e2e_client.get(f"/api/tests/{test_id}", headers=headers_a)
        assert get_a_response.status_code == 200
        assert get_a_response.get_json()["data"]["id"] == test_id

    def test_device_list_isolation(
        self,
        e2e_client,
        e2e_app,
    ):
        """
        Test that User A's devices are not visible to User B.
        """
        email_a = f"usera_list_{secrets.token_hex(8)}@example.com"
        email_b = f"userb_list_{secrets.token_hex(8)}@example.com"

        # ===== Create User A =====
        with e2e_app.app_context():
            from models.database import db
            from models.user import User

            user_a = User(email=email_a)
            user_a.set_password("password123")
            db.session.add(user_a)
            db.session.commit()
            user_a_id = user_a.id

        # ===== Create User B =====
        with e2e_app.app_context():
            from models.database import db
            from models.test_models import ESP32Device
            from models.user import User

            user_b = User(email=email_b)
            user_b.set_password("password123")
            db.session.add(user_b)
            db.session.commit()

            # Create device for User A
            esp32 = ESP32Device(
                device_id=f"ESP32-LIST-{secrets.token_hex(4).upper()}",
                user_id=user_a_id,
                factory_api_key=f"factory_list_{secrets.token_hex(8)}",
                api_key=f"sk_live_list_{secrets.token_hex(16)}",
                name="User A's Private Device",
                is_connected=False,
            )
            db.session.add(esp32)
            db.session.commit()

        # ===== User B Logs In =====
        login_b_response = e2e_client.post(
            "/api/auth/login",
            json={"email": email_b, "password": "password123"},
        )
        assert login_b_response.status_code == 200
        token_b = login_b_response.get_json()["access_token"]
        headers_b = {
            "Authorization": f"Bearer {token_b}",
            "Content-Type": "application/json",
        }

        # ===== User B's Device List Should Be Empty =====
        list_response = e2e_client.get("/api/esp32-devices", headers=headers_b)
        assert list_response.status_code == 200
        devices = list_response.get_json()["data"]

        # User B should NOT see User A's device
        device_ids = [d["device_id"] for d in devices]
        assert "ESP32-LIST-" not in str(device_ids)
