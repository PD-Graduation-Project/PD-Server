import io
import secrets
import uuid
from typing import Dict, List, Optional, Tuple
from unittest.mock import MagicMock, patch

import pytest

from models.database import db
from models.test_models import ESP32Device
from models.user import User


@pytest.fixture(autouse=True)
def mock_ml_predictor_e2e():
    """
    Automatically mock all ML predictor functions for every E2E test.
    Prevents tests from loading PyTorch models and running real inference.
    Also mocks RQ queue to avoid enqueueing jobs in tests.
    """
    mock_job = MagicMock()
    mock_job.id = "test-job-id"

    mock_queue = MagicMock()
    mock_queue.enqueue.return_value = mock_job

    with (
        patch("ml.predictor.predict_drawing", return_value=0.5),
        patch("ml.predictor.predict_tremor", return_value=0.5),
        patch("ml.predictor.predict_voice", return_value=0.5),
        patch("ml.predictor.predict_questionnaire", return_value=0.5),
        patch("ml.overall_model.predict_overall", return_value=0.5),
        patch("routes.upload_routes.get_ml_queue", return_value=mock_queue),
        patch("routes.esp32_routes.connection_manager") as mock_esp32,
        patch("routes.mobile_routes.mobile_connection_manager") as mock_mobile,
    ):
        mock_esp32.add = MagicMock()
        mock_esp32.remove = MagicMock()
        mock_esp32.is_connected = MagicMock(return_value=True)
        mock_esp32.send_event = MagicMock(return_value=True)
        mock_mobile.add = MagicMock()
        mock_mobile.remove = MagicMock()
        mock_mobile.is_connected = MagicMock(return_value=True)
        mock_mobile.send_event = MagicMock(return_value=True)
        yield


# =============================================================================
# E2E Fixtures
# =============================================================================


@pytest.fixture(scope="function")
def e2e_app():
    """
    Create a fully configured test Flask application.
    Session-scoped for performance.
    """
    from app import create_app

    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "JWT_SECRET_KEY": "test-e2e-secret-key",
            "JWT_ALGORITHM": "HS256",
            "FACTORY_SECRET": "test_factory_secret",
        }
    )

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture(scope="function")
def e2e_client(e2e_app):
    """Create a test client for E2E tests."""
    return e2e_app.test_client()


@pytest.fixture(scope="function")
def e2e_db_session(e2e_app):
    """Create a clean database session for E2E tests."""
    with e2e_app.app_context():
        yield db.session
        db.session.rollback()


@pytest.fixture
def e2e_user(e2e_db_session):
    """
    Create a fully configured test user.
    User has email, password, and is committed to database.
    """
    email = f"e2e_test_{uuid.uuid4().hex[:8]}@example.com"
    user = User(email=email)
    user.set_password("testpassword123")  # Using consistent password
    e2e_db_session.add(user)
    e2e_db_session.commit()
    return user


@pytest.fixture
def e2e_user_with_tokens(e2e_client, e2e_user):
    """
    Create a user and return with valid access/refresh tokens.
    """
    response = e2e_client.post(
        "/api/auth/login",
        json={"email": e2e_user.email, "password": "e2e_test password"},
    )

    if response.status_code != 200:
        # User might not exist, register first
        response = e2e_client.post(
            "/api/auth/register",
            json={"email": e2e_user.email, "password": "e2e_test password"},
        )
        # Login again
        response = e2e_client.post(
            "/api/auth/login",
            json={"email": e2e_user.email, "password": "e2e_test password"},
        )

    data = response.get_json()
    return {
        "user": e2e_user,
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
    }


@pytest.fixture
def e2e_auth_headers(e2e_user_with_tokens):
    """Get authorization headers with valid access token."""
    return {
        "Authorization": f"Bearer {e2e_user_with_tokens['access_token']}",
        "Content-Type": "application/json",
    }


@pytest.fixture
def e2e_esp32_unregistered(e2e_app):
    """
    Create device_id and factory_key for an unregistered ESP32.
    Uses HMAC-generated factory key. No DB entry created.
    """
    from dataclasses import dataclass
    from typing import Optional

    from utils.factory_key import generate_factory_key

    # Generate a unique device ID
    device_id = f"ESP32-{uuid.uuid4().hex[:6].upper()}"
    factory_key = generate_factory_key(device_id)

    @dataclass
    class UnregisteredDevice:
        device_id: str
        factory_api_key: str
        api_key: Optional[str] = None

    return UnregisteredDevice(device_id=device_id, factory_api_key=factory_key)


@pytest.fixture
def e2e_esp32_paired(e2e_db_session, e2e_user, e2e_app):
    """
    Create an ESP32 device that's already paired to a user.
    Uses HMAC-generated factory key.
    """
    from utils.factory_key import generate_factory_key

    device_id = f"ESP32-{uuid.uuid4().hex[:6].upper()}"
    factory_key = generate_factory_key(device_id)

    device = ESP32Device(
        device_id=device_id,
        user_id=e2e_user.id,
        factory_api_key=factory_key,
        api_key=f"sk_live_e2e_{secrets.token_hex(24)}",
        name="E2E Test Sensor",
        is_connected=False,
    )
    e2e_db_session.add(device)
    e2e_db_session.commit()
    return device


@pytest.fixture
def e2e_esp32_factory_headers(e2e_esp32_unregistered):
    """Headers for factory API key authentication."""
    return {
        "X-Device-API-Key": e2e_esp32_unregistered.factory_api_key,
        "Content-Type": "application/json",
    }


@pytest.fixture
def e2e_esp32_production_headers(e2e_esp32_paired):
    """Headers for production API key authentication."""
    return {
        "X-Device-API-Key": e2e_esp32_paired.api_key,
        "Content-Type": "application/json",
    }


# =============================================================================
# Test Data Generators
# =============================================================================


class E2ETestDataGenerator:
    """Generates realistic test data for E2E testing."""

    @staticmethod
    def generate_gyro_data(
        subtest: int, hand: str, samples: int = 100, sample_rate_hz: int = 100
    ) -> bytes:
        """
        Generate IMU data in the format expected by the ML model.

        Format: timestamp,ax,ay,az,gx,gy,gz (no header, 7 float columns)
        Matches the output of save_imu_data().
        """
        lines = []
        dt = 1.0 / sample_rate_hz

        for i in range(samples):
            timestamp = i * dt
            ax = ((i % 100) / 100.0) - 0.5 + (subtest * 0.01)
            ay = (((i + 33) % 100) / 100.0) - 0.5
            az = (((i + 66) % 100) / 100.0) - 0.5
            gx = ((i % 100) / 1000.0) - 0.05
            gy = (((i + 50) % 100) / 1000.0) - 0.05
            gz = (((i + 25) % 100) / 1000.0) - 0.05
            lines.append(
                f"{timestamp:.10f},{ax:.10f},{ay:.10f},{az:.10f},{gx:.10f},{gy:.10f},{gz:.10f}"
            )

        return "\n".join(lines).encode("utf-8")

    @staticmethod
    def generate_spiral_image(
        width: int = 500, height: int = 500, format: str = "PNG"
    ) -> bytes:
        """
        Generate a fake spiral image for testing.
        Returns PNG image bytes.
        """
        try:
            from PIL import Image, ImageDraw

            img = Image.new("RGB", (width, height), "white")
            draw = ImageDraw.Draw(img)

            # Draw a simple spiral
            center_x, center_y = width // 2, height // 2
            for i in range(100):
                radius = i * 2 + 10
                x = center_x + radius * (1 if i % 2 == 0 else -1)
                y = center_y + radius * (1 if i % 3 == 0 else -1)
                draw.ellipse(
                    [x - radius, y - radius, x + radius, y + radius],
                    outline="black",
                    width=2,
                )

            buffer = io.BytesIO()
            img.save(buffer, format=format)
            return buffer.getvalue()
        except ImportError:
            # Fallback if PIL not available
            return b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

    @staticmethod
    def generate_voice_sample(
        duration_ms: int = 3000,
        sample_rate: int = 44100,
        frequency: float = 440.0,
        format: str = "WAV",
    ) -> bytes:
        """
        Generate a fake voice sample for testing.
        Returns WAV audio bytes.
        """
        try:
            import struct
            import wave

            num_samples = int(sample_rate * duration_ms / 1000)
            amplitude = 16000

            buffer = io.BytesIO()
            with wave.open(buffer, "wb") as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 2 bytes per sample
                wav_file.setframerate(sample_rate)

                for i in range(num_samples):
                    value = int(amplitude * 0.5 * (1 + 0.3 * (i % 100) / 100.0))
                    wav_file.writeframes(struct.pack("<h", value))

            return buffer.getvalue()
        except ImportError:
            # Fallback - return fake WAV header
            return b"RIFF" + b"\x00" * 100

    @staticmethod
    def generate_test_config(num_steps=11, enabled_steps=None) -> Dict:
        """Generate a test configuration dictionary."""
        if enabled_steps is None:
            enabled_steps = list(range(num_steps))

        config = {}
        for i in range(num_steps):
            config[str(i)] = i in enabled_steps

        return config


# =============================================================================
# Simulator Classes
# =============================================================================


class ESP32Simulator:
    """
    Simulates ESP32 device behavior for E2E testing.

    Provides methods to:
    - Register device (first boot)
    - Connect to SSE stream
    - Upload tremor data
    - Complete tests
    - Send heartbeats
    """

    def __init__(self, client, device_id: str, api_key: str):
        self.client = client
        self.device_id = device_id
        self.api_key = api_key
        self.connected = False

    @classmethod
    def from_unregistered(cls, client, device: ESP32Device) -> "ESP32Simulator":
        """Create simulator from unregistered device fixture."""
        return cls(client, device.device_id, device.factory_api_key)

    @property
    def headers(self) -> Dict:
        """Get headers with current API key."""
        return {
            "X-Device-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

    def register(self) -> Tuple[bool, Optional[str]]:
        """
        Register device and get production API key.
        Returns (success, production_api_key).
        """
        response = self.client.post(
            "/api/esp32/register",
            json={"device_id": self.device_id},
            headers={
                "X-Device-API-Key": self.api_key,
                "Content-Type": "application/json",
            },
        )

        if response.status_code == 200:
            data = response.get_json()
            self.api_key = data["data"]["api_key"]
            return True, self.api_key

        return False, None

    def upload_tremor(
        self, test_id: int, subtest: str, hand: str, gyro_data: bytes
    ) -> bool:
        """Upload tremor data for a test."""
        response = self.client.post(
            f"/api/tests/{test_id}/tremor",
            data={
                "file": (io.BytesIO(gyro_data), f"subtest_{subtest}_{hand}.txt"),
                "subtest": subtest,
                "hand": hand,
            },
            headers={
                "X-Device-API-Key": self.api_key,
                "Content-Type": "multipart/form-data",
            },
        )

        return response.status_code == 200

    def complete_test(self, test_id: int) -> Tuple[bool, Optional[Dict]]:
        """Complete a test session."""
        response = self.client.post(
            f"/api/tests/{test_id}/complete", headers=self.headers
        )

        if response.status_code == 200:
            return True, response.get_json()
        return False, None


class MobileAppSimulator:
    """
    Simulates mobile app behavior for E2E testing.

    Provides methods to:
    - Register/login users
    - Pair ESP32 devices
    - Create and manage tests
    - Upload files
    - Poll for results
    """

    def __init__(self, client):
        self.client = client
        self.user_id = None
        self.access_token = None
        self.refresh_token = None

    @property
    def auth_headers(self) -> Dict:
        """Get authorization headers."""
        if not self.access_token:
            raise ValueError("Not authenticated. Call login() first.")
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def register(
        self,
        email: str,
        password: str,
        first_name: str = "Test",
        last_name: str = "User",
    ) -> Tuple[bool, Optional[Dict]]:
        """Register a new user."""
        response = self.client.post(
            "/api/auth/register",
            json={
                "email": email,
                "password": password,
                "first_name": first_name,
                "last_name": last_name,
            },
        )

        if response.status_code == 200:
            return True, response.get_json()
        return False, None

    def login(self, email: str, password: str) -> Tuple[bool, Optional[Dict]]:
        """Login and store tokens."""
        response = self.client.post(
            "/api/auth/login", json={"email": email, "password": password}
        )

        if response.status_code == 200:
            data = response.get_json()
            self.access_token = data["access_token"]
            self.refresh_token = data["refresh_token"]
            return True, data

        return False, None

    def pair_device(
        self, device_id: str, name: str = None
    ) -> Tuple[bool, Optional[Dict]]:
        """Pair an ESP32 device to the current user."""
        body = {"device_id": device_id}
        if name:
            body["name"] = name

        response = self.client.post(
            "/api/esp32-devices/pair", json=body, headers=self.auth_headers
        )

        if response.status_code == 200:
            return True, response.get_json()
        return False, None

    def list_devices(self) -> Tuple[bool, Optional[List[Dict]]]:
        """List user's paired devices."""
        response = self.client.get("/api/esp32-devices", headers=self.auth_headers)

        if response.status_code == 200:
            return True, response.get_json()["data"]
        return False, None

    def unpair_device(self, device_id: str) -> Tuple[bool, Optional[Dict]]:
        """Unpair a device."""
        response = self.client.delete(
            f"/api/esp32-devices/{device_id}", headers=self.auth_headers
        )

        if response.status_code == 200:
            return True, response.get_json()
        return False, None

    def create_group(self) -> Tuple[bool, Optional[int]]:
        """Create a new test group and return the group_id."""
        response = self.client.post("/api/groups", headers=self.auth_headers)
        if response.status_code == 201:
            return True, response.get_json()["data"]["id"]
        return False, None

    def create_test(
        self, test_type: str, config: Dict = None, group_id: int = None
    ) -> Tuple[bool, Optional[Dict]]:
        """Create a new test session. Auto-creates a group if group_id not provided."""
        if group_id is None:
            ok, group_id = self.create_group()
            if not ok:
                return False, None

        body: Dict = {"test_type": test_type, "group_id": group_id}
        if config:
            body["config"] = config  # type: ignore[assignment]

        response = self.client.post("/api/tests", json=body, headers=self.auth_headers)

        if response.status_code == 201:
            return True, response.get_json()["data"]
        return False, None

    def get_test(self, test_id: int) -> Tuple[bool, Optional[Dict]]:
        """Get test details."""
        response = self.client.get(f"/api/tests/{test_id}", headers=self.auth_headers)

        if response.status_code == 200:
            return True, response.get_json()["data"]
        return False, None

    def list_tests(
        self,
        test_type: str = None,
        status: str = None,
        limit: int = 10,
        offset: int = 0,
    ) -> Tuple[bool, Optional[List[Dict]]]:
        """List user's tests with optional filters."""
        params = []
        if test_type:
            params.append(f"test_type={test_type}")
        if status:
            params.append(f"status={status}")
        params.append(f"limit={limit}")
        params.append(f"offset={offset}")

        query = "&".join(params) if params else ""
        url = f"/api/tests?{query}" if query else "/api/tests"

        response = self.client.get(url, headers=self.auth_headers)

        if response.status_code == 200:
            return True, response.get_json()["data"]
        return False, None

    def poll_for_completion(
        self, test_id: int, max_polls: int = 30, interval_seconds: float = 0.5
    ) -> Tuple[bool, Optional[Dict]]:
        """Poll for test completion."""
        import time

        for _ in range(max_polls):
            success, data = self.get_test(test_id)
            if success and data["status"] in ["completed", "failed"]:
                return True, data
            time.sleep(interval_seconds)

        return False, None

    def upload_drawings(
        self, test_id: int, left_spiral: bytes, right_spiral: bytes
    ) -> Tuple[bool, Optional[Dict]]:
        """Upload spiral drawing images."""
        response = self.client.post(
            f"/api/tests/{test_id}/drawings",
            data={
                "spiral_left": (io.BytesIO(left_spiral), "left.png"),
                "spiral_right": (io.BytesIO(right_spiral), "right.png"),
            },
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "multipart/form-data",
            },
        )

        if response.status_code == 200:
            return True, response.get_json()
        return False, None

    def upload_voice(
        self, test_id: int, audio_data: bytes
    ) -> Tuple[bool, Optional[Dict]]:
        """Upload voice recording."""
        response = self.client.post(
            f"/api/tests/{test_id}/voice",
            data={
                "audio": (io.BytesIO(audio_data), "voice.wav"),
            },
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "multipart/form-data",
            },
        )

        if response.status_code == 200:
            return True, response.get_json()
        return False, None

    def complete_test(self, test_id: int) -> Tuple[bool, Optional[Dict]]:
        """Complete a test session."""
        response = self.client.post(
            f"/api/tests/{test_id}/complete", headers=self.auth_headers
        )

        if response.status_code == 200:
            return True, response.get_json()
        return False, None


# =============================================================================
# pytest Hooks
# =============================================================================


def pytest_collection_modifyitems(config, items):
    """
    Modify test collection for E2E tests.
    Add markers for slow tests.
    """
    for item in items:
        if "e2e" in str(item.fspath):
            if "complete" in str(item.name).lower() or "flow" in str(item.name).lower():
                item.add_marker(pytest.mark.slow)


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
