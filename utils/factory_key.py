"""
Factory key generation and verification using HMAC-SHA256.

This module provides functions to generate and verify factory keys
for ESP32 device registration. Factory keys are derived from device_id
using HMAC with a shared secret.
"""

import hashlib
import hmac
import re

from config import Config


def get_factory_secret() -> str:
    """
    Get factory secret from configuration.

    Returns:
        The factory secret string.

    Raises:
        ValueError: If FACTORY_SECRET is not configured.
    """
    secret = Config.FACTORY_SECRET
    if not secret:
        raise ValueError("FACTORY_SECRET not configured")
    return secret


def generate_factory_key(device_id: str) -> str:
    """
    Generate expected factory_key for a device_id.

    Args:
        device_id: Device ID in format ESP32-XXXXXX

    Returns:
        factory_key in format fk_<32-hex-chars>
    """
    secret = get_factory_secret()
    h = hmac.new(secret.encode(), device_id.encode(), hashlib.sha256)
    return f"fk_{h.hexdigest()[:32]}"


def verify_factory_key(device_id: str, provided_key: str) -> bool:
    """
    Verify factory_key matches expected HMAC for device_id.

    Uses timing-safe comparison to prevent timing attacks.

    Args:
        device_id: Device ID in format ESP32-XXXXXX
        provided_key: Factory key provided by ESP32

    Returns:
        True if key is valid, False otherwise.
    """
    try:
        expected = generate_factory_key(device_id)
        return hmac.compare_digest(expected, provided_key)
    except ValueError:
        return False


def validate_device_id_format(device_id: str) -> bool:
    """
    Validate device_id format.

    Expected format: ESP32-XXXXXX (6 hex characters)

    Args:
        device_id: Device ID to validate

    Returns:
        True if format is valid, False otherwise.
    """
    return bool(re.match(r"^ESP32-[0-9A-F]{6}$", device_id.upper()))
