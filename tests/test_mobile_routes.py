import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_mobile_connection_manager():
    """Mock the mobile connection manager for SSE tests."""
    with patch("routes.mobile_routes.mobile_connection_manager") as mock:
        mock.add = MagicMock()
        mock.remove = MagicMock()
        mock.is_connected = MagicMock(return_value=True)
        mock.send_event = MagicMock(return_value=True)
        yield mock


class TestMobileRoutes:
    """Test suite for mobile SSE routes"""

    def test_stream_without_auth_returns_401(self, client):
        """GET /api/stream should return 401 without authentication"""
        response = client.get("/api/stream")
        assert response.status_code == 401

    def test_stream_returns_sse_content_type(
        self, client, auth_headers, mock_mobile_connection_manager
    ):
        """GET /api/stream should return text/event-stream content type"""
        response = client.get("/api/stream", headers=auth_headers)
        assert response.status_code == 200
        assert "text/event-stream" in response.content_type
        response.close()

    def test_stream_includes_cache_control_headers(
        self, client, auth_headers, mock_mobile_connection_manager
    ):
        """GET /api/stream should include cache control headers"""
        response = client.get("/api/stream", headers=auth_headers)
        assert response.status_code == 200
        assert response.headers.get("Cache-Control") == "no-cache, no-transform"
        assert response.headers.get("Connection") == "keep-alive"
        response.close()

    def test_stream_yields_connected_event(
        self, client, auth_headers, mock_mobile_connection_manager
    ):
        """GET /api/stream should yield a connected event first"""
        import json

        response = client.get("/api/stream", headers=auth_headers)
        assert response.status_code == 200

        chunks = []
        for chunk in response.response:
            chunks.append(chunk)
            if len(chunks) >= 1:
                break

        response.close()

        assert len(chunks) > 0

        first_chunk = chunks[0].decode("utf-8")
        assert "event: connected" in first_chunk
        assert "data:" in first_chunk


class TestMobileHeartbeat:
    """Test suite for mobile heartbeat endpoint"""

    def test_heartbeat_without_auth_returns_401(self, client):
        """POST /api/stream/heartbeat should return 401 without authentication"""
        response = client.post("/api/stream/heartbeat")
        assert response.status_code == 401

    def test_heartbeat_with_auth_returns_200(self, client, auth_headers):
        """POST /api/stream/heartbeat should return 200 with valid auth"""
        response = client.post("/api/stream/heartbeat", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
