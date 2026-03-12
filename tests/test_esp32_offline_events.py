"""
Tests to ensure that creating a test when an ESP32 device is offline
does not raise an exception, still returns 201, and that the connection
manager handles missing connections gracefully.
"""

import pytest

from models.database import db
from models.test_models import TestSession
from utils import esp32_connection_manager as cm_module


class TestConnectionManagerOffline:
    """Unit tests for ESP32ConnectionManager when no device is connected."""

    def test_send_event_returns_false_when_no_connection(self, app):
        """send_event returns False (not raises) when device is offline."""
        with app.app_context():
            result = cm_module.connection_manager.send_event(
                user_id=99999,
                event="test_started",
                data={"test_id": 1, "test_type": "tremor", "config": {}},
            )
            assert result is False

    def test_is_connected_returns_false_for_unknown_user(self, app):
        """is_connected returns False for a user with no active stream."""
        with app.app_context():
            assert cm_module.connection_manager.is_connected(99999) is False

    def test_get_returns_none_for_unknown_user(self, app):
        """get returns None for a user with no active stream."""
        with app.app_context():
            assert cm_module.connection_manager.get(99999) is None

    def test_remove_does_not_raise_when_no_connection(self, app):
        """remove does not raise when there is no connection to remove."""
        with app.app_context():
            # Should log a warning but never raise
            cm_module.connection_manager.remove(99999)


class TestCreateTestOfflineDevice:
    """Integration tests for POST /api/tests when ESP32 device is offline."""

    def test_create_tremor_test_succeeds_when_device_offline(
        self, client, auth_headers, monkeypatch
    ):
        """POST /api/tests returns 201 even when device is offline and event is not sent."""
        monkeypatch.setattr(
            cm_module.connection_manager, "send_event", lambda *a, **kw: False
        )

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

    def test_create_tremor_test_persists_even_when_event_not_sent(
        self, app, client, auth_headers, test_user, monkeypatch
    ):
        """Test session is saved to DB regardless of whether the SSE event was delivered."""
        monkeypatch.setattr(
            cm_module.connection_manager, "send_event", lambda *a, **kw: False
        )

        response = client.post(
            "/api/tests",
            json={"test_type": "tremor"},
            headers=auth_headers,
        )

        assert response.status_code == 201
        test_id = response.get_json()["data"]["id"]

        with app.app_context():
            session = db.session.get(TestSession, test_id)
            assert session is not None
            assert session.test_type == "tremor"
            assert session.status == "pending"

    def test_send_event_is_called_with_correct_args(
        self, client, auth_headers, test_user, monkeypatch
    ):
        """send_event is called with correct args when a tremor test is created."""
        calls = []

        def fake_send_event(user_id, event, data):
            calls.append({"user_id": user_id, "event": event, "data": data})
            return False  # simulate offline

        monkeypatch.setattr(cm_module.connection_manager, "send_event", fake_send_event)

        response = client.post(
            "/api/tests",
            json={"test_type": "tremor"},
            headers=auth_headers,
        )

        assert response.status_code == 201
        assert len(calls) == 1
        assert calls[0]["user_id"] == test_user.id
        assert calls[0]["event"] == "test_started"
        assert calls[0]["data"]["test_type"] == "tremor"
        assert "test_id" in calls[0]["data"]

    def test_send_event_not_called_for_non_tremor_tests(
        self, client, auth_headers, monkeypatch
    ):
        """send_event is NOT called for drawing or voice tests (mobile-only)."""
        calls = []

        def fake_send_event(user_id, event, data):
            calls.append(event)
            return True

        monkeypatch.setattr(cm_module.connection_manager, "send_event", fake_send_event)

        for test_type in ("drawing", "voice"):
            calls.clear()
            response = client.post(
                "/api/tests",
                json={"test_type": test_type},
                headers=auth_headers,
            )
            assert response.status_code == 201
            assert len(calls) == 0, f"send_event should not be called for {test_type}"

    def test_create_tremor_test_succeeds_when_event_send_raises(
        self, client, auth_headers, monkeypatch
    ):
        """POST /api/tests returns 201 even if send_event raises an unexpected exception."""

        def exploding_send_event(*a, **kw):
            raise RuntimeError("Redis connection refused")

        monkeypatch.setattr(
            cm_module.connection_manager, "send_event", exploding_send_event
        )

        try:
            response = client.post(
                "/api/tests",
                json={"test_type": "tremor"},
                headers=auth_headers,
            )
            assert response.status_code == 201
        except RuntimeError:
            pytest.fail(
                "POST /api/tests raised an unhandled exception when send_event failed. "
                "Add a try/except around connection_manager.send_event() in test_routes.py."
            )

    def test_create_tremor_test_succeeds_when_device_online(
        self, client, auth_headers, test_user, monkeypatch
    ):
        """POST /api/tests returns 201 and send_event returns True when device is online."""
        calls = []

        def fake_send_event(user_id, event, data):
            calls.append(True)
            return True  # simulate online

        monkeypatch.setattr(cm_module.connection_manager, "send_event", fake_send_event)

        response = client.post(
            "/api/tests",
            json={"test_type": "tremor"},
            headers=auth_headers,
        )

        assert response.status_code == 201
        assert len(calls) == 1
