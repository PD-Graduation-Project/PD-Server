import requests
from loguru import logger

from config import Config


EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


def send_expo_push(push_tokens, title, body, data=None):
    """
    Send push notification via Expo Push API.

    Args:
        push_tokens: List of Expo push tokens (or single token as string)
        title: Notification title
        body: Notification body text
        data: Optional dict of custom data to include

    Returns:
        bool: True if all sends succeeded, False otherwise
    """
    if not push_tokens:
        logger.debug("No push tokens provided, skipping notification")
        return True

    if not Config.EXPO_ACCESS_TOKEN:
        logger.warning("EXPO_ACCESS_TOKEN not configured, skipping push notification")
        return False

    if isinstance(push_tokens, str):
        push_tokens = [push_tokens]

    if not push_tokens:
        return True

    messages = []
    for token in push_tokens:
        message = {
            "to": token,
            "title": title,
            "body": body,
            "data": data or {},
            "sound": "default",
        }
        messages.append(message)

    if len(messages) == 1:
        return _send_single_push(messages[0])
    else:
        return _send_batch_push(messages)


def _send_single_push(message):
    """Send a single push notification."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {Config.EXPO_ACCESS_TOKEN}",
    }

    try:
        response = requests.post(
            EXPO_PUSH_URL, json=message, headers=headers, timeout=10
        )
        response.raise_for_status()

        result = response.json()
        if result.get("errors"):
            for error in result["errors"]:
                logger.error(f"Expo push error: {error}")
            return False

        logger.info(f"Expo push sent successfully to {message['to']}")
        return True

    except requests.RequestException as e:
        logger.error(f"Expo push request failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending Expo push: {e}")
        return False


def _send_batch_push(messages):
    """Send multiple push notifications."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {Config.EXPO_ACCESS_TOKEN}",
    }

    batch_url = "https://exp.host/--/api/v2/push/send/batch"

    try:
        response = requests.post(
            batch_url, json={"queue": messages}, headers=headers, timeout=30
        )
        response.raise_for_status()

        result = response.json()
        if result.get("errors"):
            for error in result["errors"]:
                logger.error(f"Expo batch push error: {error}")
            return False

        logger.info(f"Expo batch push sent: {len(messages)} messages")
        return True

    except requests.RequestException as e:
        logger.error(f"Expo batch push request failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending Expo batch push: {e}")
        return False
