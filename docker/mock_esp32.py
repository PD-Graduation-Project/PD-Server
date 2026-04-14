#!/usr/bin/env python3
"""
Mock ESP32 Device for Testing

Simulates ESP32 device behavior:
- Registration with factory key
- Heartbeat sending
- SSE stream connection
- Test event handling

Usage:
    python mock_esp32.py --device-id ESP32-AABBCC --server http://app:5000

Environment Variables:
    MOCK_DEVICE_ID: Device ID (default: ESP32-MOCK01)
    MOCK_SERVER_URL: Server URL (default: http://app:5000)
    MOCK_FACTORY_SECRET: Factory secret for key generation
    MOCK_HEARTBEAT_INTERVAL: Heartbeat interval in seconds (default: 30)
    MOCK_TEST_MODE: Test mode - 'register', 'heartbeat', 'stream', or 'full' (default: 'full')
"""

import argparse
import hashlib
import hmac
import json
import os
import random
import signal
import sys
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import requests


class TestMode(Enum):
    REGISTER = "register"
    HEARTBEAT = "heartbeat"
    STREAM = "stream"
    FULL = "full"


@dataclass
class MockESP32Config:
    device_id: str
    server_url: str
    factory_secret: str
    heartbeat_interval: int
    test_mode: TestMode
    auto_complete_tests: bool = True
    tremor_data_points: int = 100


class MockESP32:
    def __init__(self, config: MockESP32Config):
        self.config = config
        self.api_key: Optional[str] = None
        self.is_connected = False
        self.sse_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.heartbeat_thread: Optional[threading.Thread] = None
        self.test_events_received: list = []
        self._factory_key_cache: Optional[str] = None
        self._current_event: Optional[str] = None
        self._current_test_data: Optional[dict] = None

    def generate_mock_imu_data(self) -> dict:
        points = self.config.tremor_data_points
        return {
            "ax": [round(random.uniform(-0.5, 0.5), 4) for _ in range(points)],
            "ay": [round(random.uniform(-0.5, 0.5), 4) for _ in range(points)],
            "az": [round(random.uniform(9.5, 10.5), 4) for _ in range(points)],
            "gx": [round(random.uniform(-0.05, 0.05), 6) for _ in range(points)],
            "gy": [round(random.uniform(-0.05, 0.05), 6) for _ in range(points)],
            "gz": [round(random.uniform(-0.05, 0.05), 6) for _ in range(points)],
        }

    def upload_tremor_subtest(self, test_id: int, subtest_id: str, hand: str) -> bool:
        if not self.api_key:
            print(f"[{self.config.device_id}] Cannot upload: not registered")
            return False
        imu_data = self.generate_mock_imu_data()
        try:
            response = requests.post(
                f"{self.config.server_url}/api/tests/{test_id}/tremor",
                json={
                    "subtest_id": subtest_id,
                    "hand": hand,
                    "imu_data": imu_data,
                },
                headers={
                    "X-Device-API-Key": self.api_key,
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
            if response.status_code == 200:
                data = response.json()
                print(
                    f"[{self.config.device_id}] Uploaded tremor: test={test_id} subtest={subtest_id} hand={hand}"
                )
                return True
            else:
                print(
                    f"[{self.config.device_id}] Upload failed: {response.status_code} - {response.text}"
                )
                return False
        except Exception as e:
            print(f"[{self.config.device_id}] Upload error: {e}")
            return False

    def complete_test(self, test_id: int) -> bool:
        if not self.api_key:
            print(f"[{self.config.device_id}] Cannot complete: not registered")
            return False
        try:
            response = requests.post(
                f"{self.config.server_url}/api/tests/{test_id}/complete",
                headers={"X-Device-API-Key": self.api_key},
                timeout=30,
            )
            if response.status_code in [200, 202]:
                print(f"[{self.config.device_id}] Test {test_id} marked as complete")
                return True
            else:
                print(
                    f"[{self.config.device_id}] Complete failed: {response.status_code} - {response.text}"
                )
                return False
        except Exception as e:
            print(f"[{self.config.device_id}] Complete error: {e}")
            return False

    def handle_test_started(self, test_data: dict):
        test_id = test_data.get("test_id")
        config = test_data.get("config", {})
        if not test_id:
            print(
                f"[{self.config.device_id}] Invalid test_started event: missing test_id"
            )
            return
        print(
            f"[{self.config.device_id}] Handling test_started: test_id={test_id} config={config}"
        )
        enabled_steps = [k for k, v in config.items() if v is True]
        if not enabled_steps:
            print(f"[{self.config.device_id}] No enabled subtests in config")
            return
        print(
            f"[{self.config.device_id}] Will upload {len(enabled_steps)} subtests for both hands"
        )
        for step in enabled_steps:
            for hand in ["left", "right"]:
                time.sleep(0.5)
                if self.stop_event.is_set():
                    return
                self.upload_tremor_subtest(test_id, step, hand)
        print(f"[{self.config.device_id}] All subtests uploaded, completing test...")
        self.complete_test(test_id)

    def generate_factory_key(self) -> str:
        if self._factory_key_cache:
            return self._factory_key_cache
        h = hmac.new(
            self.config.factory_secret.encode(),
            self.config.device_id.encode(),
            hashlib.sha256,
        )
        self._factory_key_cache = f"fk_{h.hexdigest()[:32]}"
        return self._factory_key_cache

    def register(self) -> bool:
        factory_key = self.generate_factory_key()
        try:
            response = requests.post(
                f"{self.config.server_url}/api/esp32/register",
                json={"device_id": self.config.device_id},
                headers={
                    "X-Device-API-Key": factory_key,
                    "Content-Type": "application/json",
                },
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                self.api_key = data.get("data", {}).get("api_key")
                if self.api_key:
                    print(f"[{self.config.device_id}] Registered successfully")
                    print(f"[{self.config.device_id}] API Key: {self.api_key[:20]}...")
                else:
                    print(
                        f"[{self.config.device_id}] Registration response missing api_key"
                    )
                    return False
                return True
            else:
                print(
                    f"[{self.config.device_id}] Registration failed: {response.status_code}"
                )
                print(f"[{self.config.device_id}] Response: {response.text}")
                return False
        except Exception as e:
            print(f"[{self.config.device_id}] Registration error: {e}")
            return False

    def send_heartbeat(self) -> bool:
        if not self.api_key:
            print(f"[{self.config.device_id}] Cannot send heartbeat: not registered")
            return False
        try:
            response = requests.post(
                f"{self.config.server_url}/api/esp32/heartbeat",
                headers={"X-Device-API-Key": self.api_key},
                timeout=10,
            )
            if response.status_code == 200:
                print(f"[{self.config.device_id}] Heartbeat sent")
                return True
            else:
                print(
                    f"[{self.config.device_id}] Heartbeat failed: {response.status_code}"
                )
                return False
        except Exception as e:
            print(f"[{self.config.device_id}] Heartbeat error: {e}")
            return False

    def heartbeat_loop(self):
        while not self.stop_event.is_set():
            self.stop_event.wait(self.config.heartbeat_interval)
            if not self.stop_event.is_set():
                self.send_heartbeat()

    def connect_stream(self):
        if not self.api_key:
            print(f"[{self.config.device_id}] Cannot connect stream: not registered")
            return
        print(f"[{self.config.device_id}] Connecting to SSE stream...")
        try:
            response = requests.get(
                f"{self.config.server_url}/api/esp32/stream",
                headers={
                    "X-Device-API-Key": self.api_key,
                    "Accept": "text/event-stream",
                    "Cache-Control": "no-cache",
                },
                stream=True,
                timeout=None,
            )
            if response.status_code != 200:
                print(
                    f"[{self.config.device_id}] Stream connection failed: {response.status_code}"
                )
                return
            print(f"[{self.config.device_id}] SSE stream connected")
            self.is_connected = True
            for line in response.iter_lines(decode_unicode=True):
                if self.stop_event.is_set():
                    break
                if line:
                    self._handle_sse_line(line)
        except Exception as e:
            if not self.stop_event.is_set():
                print(f"[{self.config.device_id}] Stream error: {e}")
        finally:
            self.is_connected = False
            print(f"[{self.config.device_id}] SSE stream disconnected")

    def _handle_sse_line(self, line: str):
        if line.startswith("event:"):
            self._current_event = line[6:].strip()
        elif line.startswith("data:"):
            data_str = line[5:].strip()
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                data = {"raw": data_str}
            event_type = self._current_event or "unknown"
            print(f"[{self.config.device_id}] Received event: {event_type}")
            if event_type == "test_started":
                self.test_events_received.append(
                    {"event": event_type, "data": data, "timestamp": time.time()}
                )
                print(f"[{self.config.device_id}] Test started event: {data}")
                if self.config.auto_complete_tests:
                    threading.Thread(
                        target=self.handle_test_started, args=(data,), daemon=True
                    ).start()
            elif event_type == "connected":
                print(f"[{self.config.device_id}] SSE connected confirmation")
            elif event_type == "heartbeat":
                pass
            else:
                print(f"[{self.config.device_id}] Unknown event: {event_type} - {data}")

    def start(self):
        print("=" * 60)
        print(f"MOCK ESP32 DEVICE")
        print(f"Device ID: {self.config.device_id}")
        print(f"Mode: {self.config.test_mode.value}")
        print("=" * 60)
        if self.config.test_mode in [TestMode.REGISTER, TestMode.FULL]:
            if not self.register():
                print(f"[{self.config.device_id}] Registration failed, exiting")
                return
        if self.config.test_mode in [TestMode.HEARTBEAT, TestMode.FULL]:
            self.heartbeat_thread = threading.Thread(
                target=self.heartbeat_loop, daemon=True
            )
            self.heartbeat_thread.start()
        if self.config.test_mode in [TestMode.STREAM, TestMode.FULL]:
            self.sse_thread = threading.Thread(target=self.connect_stream, daemon=True)
            self.sse_thread.start()
        if self.config.test_mode == TestMode.REGISTER:
            print(f"[{self.config.device_id}] Register-only mode complete")
            return
        try:
            while not self.stop_event.is_set():
                self.stop_event.wait(1)
        except KeyboardInterrupt:
            pass

    def stop(self):
        print(f"[{self.config.device_id}] Stopping mock ESP32...")
        self.stop_event.set()
        if self.heartbeat_thread and self.heartbeat_thread.is_alive():
            self.heartbeat_thread.join(timeout=2)
        if self.sse_thread and self.sse_thread.is_alive():
            self.sse_thread.join(timeout=2)
        print(f"[{self.config.device_id}] Mock ESP32 stopped")

    def get_status(self) -> dict:
        return {
            "device_id": self.config.device_id,
            "api_key": self.api_key[:20] + "..." if self.api_key else None,
            "is_connected": self.is_connected,
            "test_events_received": len(self.test_events_received),
        }


def main():
    parser = argparse.ArgumentParser(description="Mock ESP32 Device for Testing")
    parser.add_argument(
        "--device-id", default=os.getenv("MOCK_DEVICE_ID", "ESP32-A1B2C3")
    )
    parser.add_argument(
        "--server", default=os.getenv("MOCK_SERVER_URL", "http://app:5000")
    )
    parser.add_argument(
        "--factory-secret",
        default=os.getenv("MOCK_FACTORY_SECRET", "test_factory_secret_123"),
    )
    parser.add_argument(
        "--heartbeat-interval",
        type=int,
        default=int(os.getenv("MOCK_HEARTBEAT_INTERVAL", "30")),
    )
    parser.add_argument(
        "--mode",
        choices=["register", "heartbeat", "stream", "full"],
        default=os.getenv("MOCK_TEST_MODE", "full"),
    )
    parser.add_argument(
        "--no-auto-complete",
        action="store_true",
        help="Disable automatic test completion on test_started event",
    )
    parser.add_argument(
        "--data-points",
        type=int,
        default=int(os.getenv("MOCK_DATA_POINTS", "100")),
        help="Number of IMU data points per subtest",
    )
    args = parser.parse_args()

    device_id = args.device_id.upper()

    config = MockESP32Config(
        device_id=device_id,
        server_url=args.server,
        factory_secret=args.factory_secret,
        heartbeat_interval=args.heartbeat_interval,
        test_mode=TestMode(args.mode),
        auto_complete_tests=not args.no_auto_complete,
        tremor_data_points=args.data_points,
    )
    device = MockESP32(config)

    def signal_handler(sig, frame):
        device.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    device.start()


if __name__ == "__main__":
    main()
