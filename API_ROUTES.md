# API Routes Documentation

## Authentication Routes (`/api/auth`)

### `POST /api/auth/register`

- **Description**: Register a new user account
- **Request Body**: JSON object containing `email` and `password`
- **Response**:
  - Success (201): JSON object with message, auth token, and user data
  - Error (400): Missing email or password
  - Error (409): Email already registered
- **Example Request**:

  ```json
  {
    "email": "user@example.com",
    "password": "password123"
  }
  ```

### `POST /api/auth/login`

- **Description**: Authenticate user and return auth token
- **Request Body**: JSON object containing `email` and `password`
- **Response**:
  - Success (200): JSON object with message, auth token, and user data
  - Error (400): Missing email or password
  - Error (401): Invalid email or password
- **Example Request**:

  ```json
  {
    "email": "user@example.com",
    "password": "password123"
  }
  ```

### `POST /api/auth/refresh`

- **Description**: Refresh access token using refresh token
- **Headers**: `Authorization: Bearer <token>`
- **Request Body**: JSON object containing `refresh_token`
- **Response**:
  - Success (200): New access token
  - Error (401): Invalid or expired refresh token

### `POST /api/auth/logout`

- **Description**: Logout and revoke refresh token
- **Headers**: `Authorization: Bearer <token>`
- **Request Body**: JSON object containing `refresh_token`
- **Response**:
  - Success (200): Logged out successfully
  - Error (401): Invalid refresh token

### `POST /api/auth/logout-all`

- **Description**: Logout from all devices
- **Headers**: `Authorization: Bearer <token>`
- **Response**:
  - Success (200): Logged out from all devices

### `GET /api/auth/sessions`

- **Description**: Get all active sessions for the user
- **Headers**: `Authorization: Bearer <token>`
- **Response**:
  - Success (200): List of active sessions with device info, IP, and expiry

## Test Routes (`/api/tests`)

### `POST /api/tests`

- **Description**: Create a new test session
- **Headers**: `Authorization: Bearer <token>`
- **Request Body**: JSON object
  - `test_type` (required): One of `tremor`, `drawing`, `voice`
  - `device` (optional): Override device source - one of `mobile`, `esp32`. If not provided, defaults to `esp32` for tremor tests and `mobile` for drawing/voice tests
  - `config` (optional): Configuration object for tremor tests (step_0 through step_10)
- **Response**:
  - Success (201): Created test session
  - Error (400): Invalid request data
  - Error (401): Invalid or missing token
- **Example Request (tremor with default device)**:

  ```json
  {
    "test_type": "tremor",
    "config": {
      "step_0": true,
      "step_1": true,
      "step_2": false,
      "step_10": true
    }
  }
  ```

- **Example Request (tremor with device override)**:

  ```json
  {
    "test_type": "tremor",
    "device": "mobile",
    "config": {
      "step_0": true,
      "step_1": true
    }
  }
  ```

- **Example Request (drawing/voice)**:

  ```json
  {
    "test_type": "drawing"
  }
  ```

- **Example Response**:

  ```json
  {
    "success": true,
    "data": {
      "id": 1,
      "user_id": 1,
      "test_type": "tremor",
      "status": "pending",
      "device_source": "esp32",
      "config": {
        "step_0": true,
        "step_1": true
      },
      "created_at": "2026-02-09T10:00:00Z",
      "completed_at": null,
      "ml_score": null,
      "inputs": []
    }
  }
  ```

### `GET /api/tests`

- **Description**: List user's tests with pagination and filters
- **Headers**: `Authorization: Bearer <token>`
- **Query Parameters**:
  - `test_type` (optional): Filter by `tremor`, `drawing`, or `voice`
  - `status` (optional): Filter by `pending`, `in_progress`, `completed`, `failed`
  - `page` (optional): Page number (default: 1)
  - `per_page` (optional): Items per page (default: 20, max: 100)
- **Response**:
  - Success (200): List of tests with pagination info
  - Error (401): Invalid or missing token
- **Example Response**:

  ```json
  {
    "success": true,
    "data": {
      "tests": [
        {
          "id": 1,
          "user_id": 1,
          "test_type": "tremor",
          "status": "completed",
          "device_source": "esp32",
      "config": {"step_0": true},
      "created_at": "2026-02-09T10:00:00Z",
          "completed_at": "2026-02-09T10:00:30Z",
          "ml_score": 0.72,
          "inputs": []
        }
      ],
      "total": 1,
      "page": 1,
      "per_page": 20,
      "pages": 1
    }
  }
  ```

### `GET /api/tests/<test_id>`

- **Description**: Get a specific test session by ID
- **Headers**: `Authorization: Bearer <token>`
- **Response**:
  - Success (200): Test session data
  - Error (401): Invalid or missing token
  - Error (403): Forbidden (test belongs to another user)
  - Error (404): Test not found
- **Example Response**:

  ```json
  {
    "success": true,
    "data": {
      "id": 1,
      "user_id": 1,
      "test_type": "tremor",
      "status": "completed",
      "device_source": "esp32",
      "config": {"step_0": true, "step_1": true},
      "created_at": "2026-02-09T10:00:00Z",
      "completed_at": "2026-02-09T10:00:30Z",
      "ml_score": 0.72,
      "inputs": [
        {
          "id": 1,
          "input_type": "tremor_gyro",
          "file_path": "/uploads/tremor/1/1_0_l.txt",
          "mime_type": "text/plain",
          "file_size": 1024,
          "created_at": "2026-02-09T10:00:25Z",
          "expires_at": "2026-05-10T10:00:00Z"
        }
      ]
    }
  }
  ```

### `POST /api/tests/<test_id>/tremor`

- **Description**: Upload a gyro TXT file for a tremor test
- **Authentication**:
  - JWT Bearer token for mobile uploads
  - `X-Device-API-Key` header for ESP32 uploads
- **Request**: `multipart/form-data`
  - `file` (required): TXT file with gyro data
  - `subtest` (required): Subtest name (`0`, `1`, `2`, `3`, `4`, `5`, `6`, `7`, `8`, `9`, `10`)
  - `hand` (required): Hand (`l` for left, `r` for right)
- **Response**:
  - Success (200): File uploaded, TestInput created
  - Error (400): Missing file, invalid subtest, or invalid hand
  - Error (401): Unauthorized
  - Error (403): Forbidden (test belongs to another user)
- **Example Request**:

  ```
  POST /api/tests/1/tremor
  Content-Type: multipart/form-data

  --boundary
  Content-Disposition: form-data; name="file"; filename="data.txt"
  Content-Type: text/plain

  <gyro data>
  --boundary
  Content-Disposition: form-data; name="subtest"

  0
  --boundary
  Content-Disposition: form-data; name="hand"

  l
  --boundary--
  ```

- **Example Response**:

  ```json
  {
    "success": true,
    "data": {
      "id": 1,
      "input_type": "tremor_gyro",
      "subtest": "0",
      "hand": "l",
      "file_path": "/uploads/tremor/1/1_0_l.txt"
    }
  }
  ```

### `POST /api/tests/<test_id>/drawings`

- **Description**: Upload spiral drawing images for a drawing test
- **Headers**: `Authorization: Bearer <token>`
- **Request**: `multipart/form-data`
  - `spiral_left` (required): Left hand spiral image (PNG/JPG)
  - `spiral_right` (required): Right hand spiral image (PNG/JPG)
- **Response**:
  - Success (200): Both images uploaded
  - Error (400): Missing one or both images
  - Error (401): Unauthorized
- **Example Response**:

  ```json
  {
    "success": true,
    "data": {
      "inputs": [
        {
          "id": 10,
          "input_type": "drawing_spiral",
          "hand": "l",
          "file_path": "/uploads/drawing/2/spiral_left.png"
        },
        {
          "id": 11,
          "input_type": "drawing_spiral",
          "hand": "r",
          "file_path": "/uploads/drawing/2/spiral_right.png"
        }
      ]
    }
  }
  ```

### `POST /api/tests/<test_id>/voice`

- **Description**: Upload a voice recording for a voice test
- **Headers**: `Authorization: Bearer <token>`
- **Request**: `multipart/form-data`
  - `audio` (required): Audio file (WAV/MP3/M4A)
- **Response**:
  - Success (200): Audio uploaded
  - Error (400): No audio file provided
  - Error (401): Unauthorized
- **Example Response**:

  ```json
  {
    "success": true,
    "data": {
      "id": 20,
      "input_type": "voice_recording",
      "file_path": "/uploads/voice/3/recording.wav"
    }
  }
  ```

### `POST /api/tests/<test_id>/complete`

- **Description**: Mark a test as completed (used by ESP32 after all gyro files uploaded)
- **Authentication**:
  - JWT Bearer token for mobile
  - `X-Device-API-Key` header for ESP32
- **Response**:
  - Success (200): Test completed
  - Error (400): Already completed or no uploads yet
  - Error (401): Unauthorized
- **Example Response**:

  ```json
  {
    "success": true,
    "data": {
      "message": "Test completed",
      "status": "completed",
      "uploaded_count": 20,
      "expected_count": 20,
      "missing": []
    }
  }
  ```

## ESP32 Device Routes (`/api/esp32-devices`)

### `POST /api/esp32-devices/pair`

- **Description**: Pair an ESP32 device to the current user account
- **Headers**: `Authorization: Bearer <token>`
- **Request Body**: JSON object
  - `device_id` (required): Device ID from sticker on ESP32 (e.g., `ESP32-001234`)
  - `name` (optional): User-friendly name for the device
- **Response**:
  - Success (200): Device paired successfully
  - Error (400): Missing device_id or invalid device
  - Error (401): Invalid or missing token
  - Error (404): Device not found in database
- **Example Request**:

  ```json
  {
    "device_id": "ESP32-001234",
    "name": "My Tremor Sensor"
  }
  ```

- **Example Response**:

  ```json
  {
    "success": true,
    "data": {
      "id": 1,
      "device_id": "ESP32-001234",
      "name": "My Tremor Sensor",
      "is_connected": false,
      "created_at": "2026-02-09T10:00:00Z"
    }
  }
  ```

### `GET /api/esp32-devices`

- **Description**: List all ESP32 devices paired to the current user's account
- **Headers**: `Authorization: Bearer <token>`
- **Response**:
  - Success (200): List of paired devices
  - Error (401): Invalid or missing token
- **Example Response**:

  ```json
  {
    "success": true,
    "data": [
      {
        "id": 1,
        "device_id": "ESP32-001234",
        "name": "My Tremor Sensor",
        "is_connected": true,
        "created_at": "2026-02-09T10:00:00Z"
      }
    ]
  }
  ```

### `DELETE /api/esp32-devices/<device_id>`

- **Description**: Unpair an ESP32 device from the current user's account
- **Headers**: `Authorization: Bearer <token>`
- **Response**:
  - Success (200): Device unpaired
  - Error (401): Invalid or missing token
  - Error (404): Device not found or not paired to this user
- **Example Response**:

  ```json
  {
    "success": true,
    "message": "Device unpaired successfully"
  }
  ```

## ESP32 Device Registration Routes (`/api/esp32`)

These routes are used by the ESP32 device itself, not by the mobile app.

### `POST /api/esp32/register`

- **Description**: Register ESP32 device and receive production API key
- **Headers**: `X-Device-API-Key: <factory_api_key>`
- **Request Body**: JSON object
  - `device_id` (required): Device ID (e.g., `ESP32-001234`)
- **Response**:
  - Success (200): Device registered, returns production API key
  - Error (401): Invalid factory API key
  - Error (400): Invalid request
- **Note**: Called automatically by ESP32 on first boot. Factory API key is pre-programmed in firmware and database.
- **Example Request**:

  ```json
  {
    "device_id": "ESP32-001234"
  }
  ```

- **Example Response**:

  ```json
  {
    "success": true,
    "data": {
      "device_id": "ESP32-001234",
      "api_key": "sk_live_abc123def456..."
    }
  }
  ```

### `GET /api/esp32/stream`

- **Description**: Server-Sent Events stream for ESP32 devices to receive test_started events
- **Headers**: `X-Device-API-Key: <production_api_key>`
- **Response**: SSE stream (HTTP 200, connection kept open)
- **SSE Events**:
  - `test_started`: When mobile app starts a tremor test for this device's user
  - `heartbeat`: Periodic keep-alive event (every 30 seconds)
- **Example Event**:

  ```
  event: test_started
  data: {"test_id": 5, "test_type": "tremor", "config": {"step_0": true, "step_1": true}}
  ```

  ```
  event: heartbeat
  data: {"timestamp": "2026-02-09T10:00:00Z"}
  ```

### `POST /api/esp32/heartbeat`

- **Description**: Report ESP32 device is online (keep-alive)
- **Headers**: `X-Device-API-Key: <production_api_key>`
- **Response**:
  - Success (200): Heartbeat recorded
  - Error (401): Invalid API key
- **Example Response**:

  ```json
  {
    "success": true,
    "message": "Heartbeat received"
  }
  ```

## ESP32 Data Upload Routes (`/api/esp32/tests/<test_id>`)

**Note**: These routes are deprecated in favor of the standard `/api/tests/{id}/tremor` and `/api/tests/{id}/complete` routes. ESP32 can use either endpoint.

### `POST /api/esp32/tests/<test_id>/data` (Deprecated)

Use `/api/tests/{id}/tremor` instead.

### `POST /api/esp32/tests/<test_id>/complete` (Deprecated)

Use `/api/tests/{id}/complete` instead.

## ESP32 Authentication Flow

### Pairing Flow (User Action)

1. User sees sticker on ESP32: `Device ID: ESP32-001234`
2. User opens mobile app → "Pair Device"
3. User types: `ESP32-001234`
4. Optionally names: "My Sensor"
5. Server links device to user account
6. Done!

### ESP32 Registration Flow (Automatic)

1. ESP32 boots with factory API key pre-programmed
2. ESP32 calls `POST /api/esp32/register` with factory key
3. Server validates factory key, generates production API key
4. ESP32 stores production key in flash
5. ESP32 connects to `GET /api/esp32/stream`
6. ESP32 ready to receive test_started events

### Data Flow During Test

1. Mobile app creates tremor test: `POST /api/tests`
2. Server looks up user's paired ESP32 device
3. Server sends SSE event to ESP32: `test_started`
4. ESP32 collects gyro data, uploads via `POST /api/tests/{id}/tremor`
5. ESP32 calls `POST /api/tests/{id}/complete`
6. Mobile app polls `GET /api/tests/{id}` for results

## User Routes (`/api/user`)

### `GET /api/user`

- **Description**: Get current user's information
- **Headers**: `Authorization: Bearer <token>`
- **Response**:
  - Success (200): User demographics data
  - Error (401): Invalid or missing token
  - Error (404): User not found

### `PATCH /api/user`

- **Description**: Update user demographics
- **Headers**: `Authorization: Bearer <token>`
- **Request Body**: JSON object with fields to update
  - `age`, `height`, `weight`, `gender`
  - `pd_appearance_in_kinship`, `pd_appearance_in_first_grade_kinship`
  - `Q01` - `Q28`: Questionnaire responses (boolean)
- **Response**:
  - Success (200): Updated user data
  - Error (400): Validation failed
  - Error (401): Invalid or missing token

### `POST /api/user/reset`

- **Description**: Reset user data (demographics and questionnaire)
- **Headers**: `Authorization: Bearer <token>`
- **Response**:
  - Success (200): User data reset

### `DELETE /api/user`

- **Description**: Delete user account
- **Headers**: `Authorization: Bearer <token>`
- **Response**:
  - Success (200): Account deleted

## Questionnaire Routes (`/api/questionnaire`)

### `GET /api/questionnaire`

- **Description**: Get all questionnaire responses
- **Headers**: `Authorization: Bearer <token>`
- **Response**:
  - Success (200): Object with Q01-Q28 responses

  ```json
  {
    "success": true,
    "data": {
      "Q01": true,
      "Q02": false,
      ...
    }
  }
  ```

### `PATCH /api/questionnaire`

- **Description**: Update questionnaire responses
- **Headers**: `Authorization: Bearer <token>`
- **Request Body**: Object with questions to update

  ```json
  {
    "Q01": true,
    "Q05": false
  }
  ```

- **Response**:
  - Success (200): Updated fields list
  - Error (400): Invalid data or no valid fields

## ESP32 SSE Stream Routes

### `GET /api/esp32/stream`

- **Description**: Server-Sent Events stream for ESP32 devices
- **Headers**: `X-Device-API-Key: <api_key>`
- **Response**: SSE stream for receiving `test_started` events
- **Example Event**:

  ```
  event: test_started
  data: {"test_id": 1, "test_type": "tremor", "config": {"step_0": true, "step_2": false}}
  ```

### `POST /api/esp32/tests/<test_id>/data`

- **Description**: Upload gyro data for a test session
- **Headers**: `X-Device-API-Key: <api_key>`
- **Request Body**: JSON object

  ```json
  {
    "gyro_data": [[x, y, z, timestamp], ...],
    "sample_rate_hz": 100,
    "duration_seconds": 30
  }
  ```

- **Response**:
  - Success (200): Data received
  - Error (401): Invalid API key

### `POST /api/esp32/tests/<test_id>/complete`

- **Description**: Signal test completion
- **Headers**: `X-Device-API-Key: <api_key>`
- **Response**:
  - Success (200): Test completed

### `POST /api/esp32/heartbeat`

- **Description**: Report ESP32 online status
- **Headers**: `X-Device-API-Key: <api_key>`
- **Response**:
  - Success (200): Heartbeat received

## Health Check Route

### `GET /health`

- **Description**: Check if the service is running
- **Response**:
  - Success (200): `{"status": "healthy"}`

## Error Handlers

- **400**: Returns `{"success": false, "error": "..."}`
- **401**: Returns `{"error": "..."}`
- **403**: Returns `{"error": "Forbidden"}`
- **404**: Returns `{"error": "Not found"}`
- **500**: Returns `{"error": "Internal server error"}`

## Configuration

- JWT access tokens expire after 15 minutes
- JWT refresh tokens expire after 30 days
- Maximum file upload size: 16MB
- Allowed file extensions:
  - Audio: mp3, wav, m4a
  - Images: png, jpg, jpeg, gif
  - Text: txt, csv, json
- Test data retention: 90 days (auto-delete)

## Tremor Test Configuration

Available tremor test steps (controlled via `config`):

| Step | Name | Default |
|------|------|---------|
| step_0 | Resting | true |
| step_1 | Resting with serial sevens | true |
| step_2 | Lift and extend arms | true |
| step_3 | Arms remain lifted | true |
| step_4 | Hold one kilogram weight | true |
| step_5 | Point index finger | true |
| step_6 | Drink from glass | true |
| step_7 | Cross and extend arms | true |
| step_8 | Touch index fingers together | true |
| step_9 | Tap nose with index finger | true |
| step_10 | Entrainment foot stomping | true |

## ESP32 Device ID Format

- Device IDs follow format: `ESP32-XXXXXX` (e.g., `ESP32-001234`)
- Printed on sticker on ESP32 device
- User types this ID in mobile app to pair device

## ESP32 vs Mobile

- ESP32 handles tremor test (sensor data)
- Mobile handles drawing + voice tests (user input)
- Different authentication (API key vs JWT)
- Separate route namespaces for clarity
