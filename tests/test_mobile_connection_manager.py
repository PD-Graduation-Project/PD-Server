import pytest
from unittest.mock import MagicMock, patch, PropertyMock


class TestMobileConnectionManager:
    """Test suite for MobileConnectionManager - unit tests without threads."""

    def test_is_connected_returns_true_when_connected(self, app):
        """is_connected() should return True when user has active connection"""
        from utils.mobile_connection_manager import MobileConnectionManager

        with app.app_context():
            manager = MobileConnectionManager()
            mock_redis = MagicMock()
            mock_redis.hget.return_value = "1"
            manager._get_redis_client = MagicMock(return_value=mock_redis)

            result = manager.is_connected(user_id=1)
            assert result is True
            mock_redis.close.assert_called()

    def test_is_connected_returns_false_when_not_connected(self, app):
        """is_connected() should return False when user has no connection"""
        from utils.mobile_connection_manager import MobileConnectionManager

        with app.app_context():
            manager = MobileConnectionManager()
            mock_redis = MagicMock()
            mock_redis.hget.return_value = None
            manager._get_redis_client = MagicMock(return_value=mock_redis)

            result = manager.is_connected(user_id=1)
            assert result is False
            mock_redis.close.assert_called()

    def test_send_event_when_connected(self, app):
        """send_event() should publish to Redis when user is connected"""
        from utils.mobile_connection_manager import MobileConnectionManager

        with app.app_context():
            manager = MobileConnectionManager()
            mock_redis = MagicMock()
            mock_redis.hget.return_value = "1"
            manager._get_redis_client = MagicMock(return_value=mock_redis)

            result = manager.send_event(
                user_id=1, event="next_subtest", data={"test_id": 123}
            )

            assert result is True
            mock_redis.publish.assert_called()
            mock_redis.close.assert_called()

    def test_send_event_when_not_connected(self, app):
        """send_event() should return False when user is not connected"""
        from utils.mobile_connection_manager import MobileConnectionManager

        with app.app_context():
            manager = MobileConnectionManager()
            mock_redis = MagicMock()
            mock_redis.hget.return_value = None
            manager._get_redis_client = MagicMock(return_value=mock_redis)

            result = manager.send_event(
                user_id=1, event="next_subtest", data={"test_id": 123}
            )

            assert result is False
            mock_redis.publish.assert_not_called()
            mock_redis.close.assert_called()


class TestMobileConnectionManagerWithMockedThread:
    """Tests that mock the thread creation to avoid memory leaks."""

    @patch("utils.mobile_connection_manager.threading.Thread")
    @patch("utils.mobile_connection_manager.threading.Event")
    def test_add_registers_connection(self, mock_event_cls, mock_thread_cls, app):
        """add() should register a connection in Redis and start a thread"""
        from utils.mobile_connection_manager import MobileConnectionManager

        mock_event = MagicMock()
        mock_event_cls.return_value = mock_event

        mock_thread = MagicMock()
        mock_thread_cls.return_value = mock_thread

        with app.app_context():
            manager = MobileConnectionManager()

            mock_redis = MagicMock()
            mock_pubsub = MagicMock()
            mock_redis.pubsub.return_value = mock_pubsub
            manager._get_redis_client = MagicMock(return_value=mock_redis)

            import queue

            msg_queue = queue.Queue()
            manager.add(user_id=1, message_queue=msg_queue)

            mock_redis.hset.assert_called()
            mock_redis.expire.assert_called()
            mock_thread.start.assert_called_once()
            mock_redis.close.assert_not_called()

    @patch("utils.mobile_connection_manager.threading.Thread")
    @patch("utils.mobile_connection_manager.threading.Event")
    def test_remove_clears_connection(self, mock_event_cls, mock_thread_cls, app):
        """remove() should delete connection from Redis"""
        from utils.mobile_connection_manager import MobileConnectionManager

        mock_event = MagicMock()
        mock_event.is_set.return_value = True
        mock_event_cls.return_value = mock_event

        mock_thread = MagicMock()
        mock_thread_cls.return_value = mock_thread

        with app.app_context():
            manager = MobileConnectionManager()
            mock_redis = MagicMock()
            mock_pubsub = MagicMock()
            manager._get_redis_client = MagicMock(return_value=mock_redis)

            import queue

            manager._local_listeners[1] = {
                "redis_client": mock_redis,
                "pubsub": mock_pubsub,
                "thread": mock_thread,
                "stop_event": mock_event,
                "queue": queue.Queue(),
            }

            manager.remove(user_id=1)

            mock_event.set.assert_called()
            mock_redis.delete.assert_called()


class TestNextSubtestEvent:
    """Test suite for next_subtest event trigger on tremor upload"""

    @patch("routes.upload_routes.mobile_connection_manager")
    def test_upload_tremor_json_sends_next_subtest_event(
        self, mock_manager, client, auth_headers, test_user, db_session
    ):
        """Uploading tremor JSON should trigger next_subtest SSE event"""
        from models.test_models import TestGroup, TestSession

        group = TestGroup(user_id=test_user.id, status="in_progress")
        db_session.add(group)
        db_session.commit()

        test_session = TestSession(
            user_id=test_user.id,
            group_id=group.id,
            test_type="tremor",
            status="pending",
            config={"0": True, "1": True},
        )
        db_session.add(test_session)
        db_session.commit()

        mock_manager.send_event.return_value = True

        imu_data = {
            "ax": [1.0] * 100,
            "ay": [1.0] * 100,
            "az": [1.0] * 100,
            "gx": [1.0] * 100,
            "gy": [1.0] * 100,
            "gz": [1.0] * 100,
        }

        response = client.post(
            f"/api/tests/{test_session.id}/tremor",
            headers=auth_headers,
            json={
                "subtest": "0",
                "hand": "left",
                "imu_data": imu_data,
            },
        )

        assert response.status_code == 200
        mock_manager.send_event.assert_called_once()

        call_args = mock_manager.send_event.call_args
        assert call_args[0][1] == "next_subtest"
        assert call_args[0][2]["test_id"] == test_session.id
        assert call_args[0][2]["uploaded_subtest"] == "0"


class TestDeviceConnectedEvent:
    """Test suite for device_connected event from ESP32"""

    @patch("utils.esp32_connection_manager.threading.Thread")
    @patch("utils.esp32_connection_manager.threading.Event")
    def test_esp32_connect_sends_device_connected_event(
        self, mock_event_cls, mock_thread_cls, app
    ):
        """ESP32 connecting should publish device_connected to mobile channel"""
        from utils.esp32_connection_manager import ESP32ConnectionManager

        mock_event = MagicMock()
        mock_event_cls.return_value = mock_event

        mock_thread = MagicMock()
        mock_thread_cls.return_value = mock_thread

        with app.app_context():
            manager = ESP32ConnectionManager()

            mock_redis = MagicMock()
            mock_pubsub = MagicMock()
            mock_redis.pubsub.return_value = mock_pubsub
            manager._get_redis_client = MagicMock(return_value=mock_redis)

            import queue

            msg_queue = queue.Queue()

            manager.add(user_id=1, device_id="ESP32-TEST123", message_queue=msg_queue)

            calls = mock_redis.publish.call_args_list
            mobile_calls = [c for c in calls if "mobile:user:" in str(c)]

            assert len(mobile_calls) >= 1
            first_mobile_call = mobile_calls[0]
            assert "device_connected" in str(first_mobile_call)


class TestDeviceDisconnectedEvent:
    """Test suite for device_disconnected event from ESP32"""

    @patch("utils.esp32_connection_manager.threading.Thread")
    @patch("utils.esp32_connection_manager.threading.Event")
    def test_esp32_disconnect_sends_device_disconnected_event(
        self, mock_event_cls, mock_thread_cls, app
    ):
        """ESP32 disconnecting should publish device_disconnected to mobile channel"""
        from utils.esp32_connection_manager import ESP32ConnectionManager

        mock_event = MagicMock()
        mock_event.is_set.return_value = True
        mock_event_cls.return_value = mock_event

        mock_thread = MagicMock()
        mock_thread_cls.return_value = mock_thread

        with app.app_context():
            manager = ESP32ConnectionManager()

            mock_redis = MagicMock()
            mock_pubsub = MagicMock()
            manager._get_redis_client = MagicMock(return_value=mock_redis)

            import queue

            manager._local_listeners[1] = {
                "device_id": "ESP32-TEST123",
                "redis_client": mock_redis,
                "pubsub": mock_pubsub,
                "thread": mock_thread,
                "stop_event": mock_event,
                "queue": queue.Queue(),
            }

            manager.remove(user_id=1)

            calls = mock_redis.publish.call_args_list
            mobile_calls = [c for c in calls if "mobile:user:" in str(c)]

            assert len(mobile_calls) >= 1
            assert "device_disconnected" in str(mobile_calls[-1])
