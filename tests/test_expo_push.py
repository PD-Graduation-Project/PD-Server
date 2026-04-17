import pytest
from unittest.mock import patch, MagicMock


class TestExpoPush:
    """Test suite for Expo push notification helper"""

    @patch("utils.expo_push.Config")
    def test_send_expo_push_no_token_returns_true(self, mock_config):
        """send_expo_push should return True when no tokens provided"""
        mock_config.EXPO_ACCESS_TOKEN = "test_token"
        from utils.expo_push import send_expo_push

        result = send_expo_push([], "Test", "Body")
        assert result is True

    @patch("utils.expo_push.Config")
    def test_send_expo_push_no_token_config_returns_false(self, mock_config):
        """send_expo_push should return False when no token configured"""
        mock_config.EXPO_ACCESS_TOKEN = None
        from utils.expo_push import send_expo_push

        result = send_expo_push(["token123"], "Test", "Body")
        assert result is False

    @patch("utils.expo_push.requests.post")
    def test_send_expo_push_single_token_success(self, mock_post):
        """send_expo_push should send to single token successfully"""
        from utils.expo_push import send_expo_push
        from config import Config

        Config.EXPO_ACCESS_TOKEN = "test_token"
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": {"id": "xxx"}}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = send_expo_push(["ExponentPushToken-abc"], "Test Title", "Test Body")

        assert result is True
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "https://exp.host/--/api/v2/push/send" in str(call_args)

    @patch("utils.expo_push.requests.post")
    def test_send_expo_push_multiple_tokens_uses_batch(self, mock_post):
        """send_expo_push should use batch API for multiple tokens"""
        from utils.expo_push import send_expo_push
        from config import Config

        Config.EXPO_ACCESS_TOKEN = "test_token"
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": [{"id": "xxx"}]}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        tokens = ["token1", "token2", "token3"]
        result = send_expo_push(tokens, "Test Title", "Test Body")

        assert result is True
        assert "batch" in str(mock_post.call_args)

    @patch("utils.expo_push.requests.post")
    def test_send_expo_push_string_token_converted_to_list(self, mock_post):
        """send_expo_push should convert string token to list"""
        from utils.expo_push import send_expo_push
        from config import Config

        Config.EXPO_ACCESS_TOKEN = "test_token"
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": {"id": "xxx"}}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = send_expo_push("ExponentPushToken-single", "Test", "Body")

        assert result is True

    @patch("utils.expo_push.requests.post")
    def test_send_expo_push_includes_data_payload(self, mock_post):
        """send_expo_push should include data payload"""
        from utils.expo_push import send_expo_push
        from config import Config

        Config.EXPO_ACCESS_TOKEN = "test_token"
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": {"id": "xxx"}}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        send_expo_push(
            ["token1"], "Title", "Body", {"test_id": 123, "test_type": "tremor"}
        )

        call_args = mock_post.call_args
        json_body = call_args.kwargs.get("json") or call_args[1].get("json")
        assert json_body["data"] == {"test_id": 123, "test_type": "tremor"}

    @patch("utils.expo_push.requests.post")
    def test_send_expo_push_network_error_returns_false(self, mock_post):
        """send_expo_push should return False on network error"""
        import requests
        from utils.expo_push import send_expo_push
        from config import Config

        Config.EXPO_ACCESS_TOKEN = "test_token"
        mock_post.side_effect = requests.RequestException("Connection error")

        result = send_expo_push(["token1"], "Test", "Body")
        assert result is False
