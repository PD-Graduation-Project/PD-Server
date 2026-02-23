#!/usr/bin/env python3
"""
Manufacturing script to generate factory_key from device MAC address.
Run this during device provisioning.

Usage:
    python scripts/generate_factory_key.py <mac_address>

Example:
    python scripts/generate_factory_key.py AA:BB:CC:DD:EE:FF

Output:
    device_id: ESP32-DDEEFF
    factory_key: fk_a1b2c3d4e5f6...

Environment:
    FACTORY_SECRET - Required. The shared secret for HMAC generation.
"""

import hashlib
import hmac
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv


def generate_device_id(mac_address: str) -> str:
    """
    Generate device_id from MAC address.

    Uses last 6 characters of MAC address (3 bytes = 6 hex chars).

    Args:
        mac_address: MAC address in format AA:BB:CC:DD:EE:FF or AABBCCDDEEFF

    Returns:
        device_id in format ESP32-XXXXXX
    """
    clean_mac = mac_address.replace(":", "").replace("-", "").upper()

    if len(clean_mac) != 12 or not re.match(r"^[0-9A-F]{12}$", clean_mac):
        raise ValueError(f"Invalid MAC address format: {mac_address}")

    return f"ESP32-{clean_mac[-6:]}"


def generate_factory_key(device_id: str, secret: str) -> str:
    """
    Generate factory_key using HMAC-SHA256.

    Args:
        device_id: Device ID in format ESP32-XXXXXX
        secret: Factory secret for HMAC

    Returns:
        factory_key in format fk_<32-hex-chars>
    """
    h = hmac.new(secret.encode(), device_id.encode(), hashlib.sha256)
    return f"fk_{h.hexdigest()[:32]}"


def main():
    if len(sys.argv) != 2:
        print("Usage: python generate_factory_key.py <mac_address>")
        print("Example: python generate_factory_key.py AA:BB:CC:DD:EE:FF")
        sys.exit(1)

        # Load .env from parent directory
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path)
    secret = os.environ.get("FACTORY_SECRET")
    if not secret:
        print("Error: FACTORY_SECRET environment variable not set")
        sys.exit(1)

    mac_address = sys.argv[1]

    try:
        device_id = generate_device_id(mac_address)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    factory_key = generate_factory_key(device_id, secret)

    print(f"device_id: {device_id}")
    print(f"factory_key: {factory_key}")
    print()
    print("Flash these values to ESP32:")
    print(f'  #define DEVICE_ID "{device_id}"')
    print(f'  #define FACTORY_KEY "{factory_key}"')


if __name__ == "__main__":
    main()
