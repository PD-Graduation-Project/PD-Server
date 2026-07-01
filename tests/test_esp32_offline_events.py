"""
Tests to ensure that creating a test when an ESP32 device is offline
does not raise an exception, still returns 201, and that the connection
manager handles missing connections gracefully.

Note: test_started event is now sent via POST /api/tests/<id>/start endpoint,
not automatically on create.
"""

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
        self, client, auth_headers, test_group, monkeypatch
    ):
        """POST /api/tests returns 201 even when device is offline."""
        monkeypatch.setattr(
            cm_module.connection_manager, "send_event", lambda *a, **kw: False
        )

        response = client.post(
            "/api/tests",
            json={"test_type": "tremor", "group_id": test_group},
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["test_type"] == "tremor"
        assert data["data"]["status"] == "pending"

    def test_create_tremor_test_persists_even_when_event_not_sent(
        self, app, client, auth_headers, test_user, test_group, monkeypatch
    ):
        """Test session is saved to DB when created."""
        monkeypatch.setattr(
            cm_module.connection_manager, "send_event", lambda *a, **kw: False
        )

        response = client.post(
            "/api/tests",
            json={"test_type": "tremor", "group_id": test_group},
            headers=auth_headers,
        )

        assert response.status_code == 201
        test_id = response.get_json()["data"]["id"]

        with app.app_context():
            session = db.session.get(TestSession, test_id)
            assert session is not None
            assert session.test_type == "tremor"
            assert session.status == "pending"

    def test_create_tremor_test_does_not_send_event(
        self, client, auth_headers, test_user, test_group, monkeypatch
    ):
        """send_event is NOT called when creating a tremor test (must use /start endpoint)."""
        calls = []

        def fake_send_event(user_id, event, data):
            calls.append({"user_id": user_id, "event": event, "data": data})
            return True

        monkeypatch.setattr(cm_module.connection_manager, "send_event", fake_send_event)

        response = client.post(
            "/api/tests",
            json={"test_type": "tremor", "group_id": test_group},
            headers=auth_headers,
        )

        assert response.status_code == 201
        assert (
            len(calls) == 0
        ), "send_event should not be called on create, use /start endpoint"

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
            # Each test_type needs its own group (can't reuse same group for both
            # since each type can only appear once per group)
            group_resp = client.post("/api/groups", headers=auth_headers)
            gid = group_resp.get_json()["data"]["id"]
            calls.clear()
            response = client.post(
                "/api/tests",
                json={"test_type": test_type, "group_id": gid},
                headers=auth_headers,
            )
            assert response.status_code == 201
            assert len(calls) == 0, f"send_event should not be called for {test_type}"


class TestStartTestEndpoint:
    """Integration tests for POST /api/tests/<id>/start endpoint."""

    def test_start_test_sends_event_success(
        self, client, auth_headers, test_user, test_group, monkeypatch
    ):
        """POST /api/tests/<id>/start sends test_started event to ESP32."""
        calls = []

        def fake_send_event(user_id, event, data):
            calls.append({"user_id": user_id, "event": event, "data": data})
            return True

        monkeypatch.setattr(cm_module.connection_manager, "send_event", fake_send_event)

        # First create a tremor test
        response = client.post(
            "/api/tests",
            json={"test_type": "tremor", "group_id": test_group},
            headers=auth_headers,
        )
        assert response.status_code == 201
        test_id = response.get_json()["data"]["id"]

        # Now start the test
        response = client.post(
            f"/api/tests/{test_id}/start",
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert len(calls) == 1
        assert calls[0]["user_id"] == test_user.id
        assert calls[0]["event"] == "test_started"
        assert calls[0]["data"]["test_type"] == "tremor"
        assert calls[0]["data"]["test_id"] == test_id

    def test_start_test_returns_503_when_device_offline(
        self, client, auth_headers, test_group, monkeypatch
    ):
        """POST /api/tests/<id>/start returns 503 when device is offline."""
        monkeypatch.setattr(
            cm_module.connection_manager, "send_event", lambda *a, **kw: False
        )

        # First create a tremor test
        response = client.post(
            "/api/tests",
            json={"test_type": "tremor", "group_id": test_group},
            headers=auth_headers,
        )
        test_id = response.get_json()["data"]["id"]

        # Now try to start the test
        response = client.post(
            f"/api/tests/{test_id}/start",
            headers=auth_headers,
        )

        assert response.status_code == 503
        assert "not connected" in response.get_json()["error"]

    def test_start_test_returns_400_for_non_tremor(
        self, client, auth_headers, test_group
    ):
        """POST /api/tests/<id>/start returns 400 for non-tremor tests."""
        # Create a drawing test
        response = client.post(
            "/api/tests",
            json={"test_type": "drawing", "group_id": test_group},
            headers=auth_headers,
        )
        test_id = response.get_json()["data"]["id"]

        # Try to start it
        response = client.post(
            f"/api/tests/{test_id}/start",
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "tremor" in response.get_json()["error"]

    def test_start_test_returns_400_for_mobile_device(
        self, client, auth_headers, test_group
    ):
        """POST /api/tests/<id>/start returns 400 for mobile device tests."""
        # Create a tremor test with mobile device
        response = client.post(
            "/api/tests",
            json={"test_type": "tremor", "group_id": test_group, "device": "mobile"},
            headers=auth_headers,
        )
        test_id = response.get_json()["data"]["id"]

        # Try to start it
        response = client.post(
            f"/api/tests/{test_id}/start",
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "ESP32" in response.get_json()["error"]


import queue
import threading
from unittest.mock import MagicMock, PropertyMock


class TestListenerSelfHeal:
    """Tests for the self-healing listener (resubscribe on failure)."""

    def test_resubscribe_on_pubsub_exception(self, app, monkeypatch):
        """When get_message() raises, _resubscribe() is called."""
        cm = cm_module.connection_manager
        msg_queue = queue.Queue()
        stop_event = threading.Event()

        pubsub = MagicMock()
        pubsub.get_message.side_effect = ConnectionError("Redis went away")
        type(pubsub).connection = PropertyMock(
            return_value=MagicMock(is_connected=True)
        )

        resubscribe_calls = []
        original_resubscribe = cm._resubscribe

        def tracking_resubscribe(uid, old_ps, lq, se):
            resubscribe_calls.append(True)
            return original_resubscribe(uid, old_ps, lq, se)

        monkeypatch.setattr(cm, "_resubscribe", tracking_resubscribe)

        cm._listen(pubsub, msg_queue, 99999, stop_event)

        assert len(resubscribe_calls) >= 1, (
            "_resubscribe should be called when get_message() raises"
        )

    def test_sentinel_when_resubscribe_exhausted(self, app, monkeypatch):
        """When _resubscribe returns None (all retries failed), __listener_died
        is pushed to the queue."""
        cm = cm_module.connection_manager
        msg_queue = queue.Queue()
        stop_event = threading.Event()

        pubsub = MagicMock()
        pubsub.get_message.side_effect = ConnectionError("Redis gone")
        type(pubsub).connection = PropertyMock(
            return_value=MagicMock(is_connected=True)
        )

        monkeypatch.setattr(
            cm, "_RESUBSCRIBE_DELAYS", [0.01]
        )

        cm._listen(pubsub, msg_queue, 99999, stop_event)

        assert not msg_queue.empty()
        msg = msg_queue.get_nowait()
        assert msg["event"] == "__listener_died"

    def test_resubscribe_skipped_on_clean_shutdown(self, app, monkeypatch):
        """When stop_event is set, _resubscribe is not called."""
        cm = cm_module.connection_manager
        msg_queue = queue.Queue()
        stop_event = threading.Event()
        stop_event.set()

        pubsub = MagicMock()
        pubsub.get_message.side_effect = RuntimeError("should not be called")

        resubscribe_calls = []
        original_resubscribe = cm._resubscribe

        def tracking_resubscribe(uid, old_ps, lq, se):
            resubscribe_calls.append(True)
            return original_resubscribe(uid, old_ps, lq, se)

        monkeypatch.setattr(cm, "_resubscribe", tracking_resubscribe)

        cm._listen(pubsub, msg_queue, 99999, stop_event)

        assert len(resubscribe_calls) == 0
        assert msg_queue.empty()

    def test_remove_guard_prevents_stale_cleanup(self, app):
        """remove() with a stale queue ref does not destroy the active connection."""
        cm = cm_module.connection_manager
        active_queue = queue.Queue()
        stale_queue = queue.Queue()

        cm._local_listeners[42] = {
            "device_id": "ESP42",
            "queue": active_queue,
            "pubsub": MagicMock(),
            "thread": MagicMock(is_alive=lambda: True),
            "stop_event": threading.Event(),
        }

        cm.remove(42, stale_queue)

        assert 42 in cm._local_listeners
        assert cm._local_listeners[42]["queue"] is active_queue

        cm.remove(42, active_queue)

        assert 42 not in cm._local_listeners

    def test_remove_noop_for_unknown_user(self, app):
        """remove() does nothing for a user with no connection."""
        cm = cm_module.connection_manager
        cm.remove(99999)

    def test_send_event_logs_dead_thread(self, app):
        """send_event logs a specific warning when the listener thread is dead."""
        cm = cm_module.connection_manager
        dead_thread = MagicMock()
        dead_thread.is_alive.return_value = False

        cm._local_listeners[42] = {
            "device_id": "ESP42",
            "queue": queue.Queue(),
            "pubsub": MagicMock(),
            "thread": dead_thread,
            "stop_event": threading.Event(),
        }

        result = cm.send_event(user_id=42, event="test", data={})

        assert result is False
