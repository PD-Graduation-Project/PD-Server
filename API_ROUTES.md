# API Routes Documentation

## Overview

| Client | Auth Method | Header |
|--------|-------------|--------|
| Mobile App | JWT Bearer token | `Authorization: Bearer <access_token>` |
| ESP32 Device | Production API key | `X-Device-API-Key: sk_live_...` |
| ESP32 (factory registration) | Factory HMAC key | `X-Device-API-Key: fk_...` |

**Base URL**: `https://<your-server>/`

---

## Authentication Routes `/api/auth`

> **Client**: Mobile App

---

### `POST /api/auth/register`

Register a new user account. Returns tokens immediately on success.

**Auth required**: No

**Request body**:

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `email` | string | Yes | Valid email format |
| `password` | string | Yes | Minimum 6 characters |

**Example request**:

```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Example response** `201`:

```json
{
  "message": "Success",
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "dGhpcyBpcyBhIHNlY3VyZSByYW5kb20gdG9rZW4...",
  "token_type": "Bearer",
  "expires_in": 900,
  "user": {
    "id": 1,
    "email": "user@example.com",
    "created_at": "2026-03-15T10:00:00",
    "age": null,
    "height": null,
    "weight": null,
    "gender": null,
    "pd_appearance_in_kinship": null,
    "pd_appearance_in_first_grade_kinship": null
  }
}
```

**Error responses**:

| Status | Body |
|--------|------|
| `400` | `{"error": "..."}` — validation failed |
| `409` | `{"error": "Email already registered"}` |

---

### `POST /api/auth/login`

Authenticate a user and receive access + refresh tokens.

**Auth required**: No

**Request body**:

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `email` | string | Yes | Valid email format |
| `password` | string | Yes | Minimum 6 characters |

**Example request**:

```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Example response** `200`:

```json
{
  "message": "Success",
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "dGhpcyBpcyBhIHNlY3VyZSByYW5kb20gdG9rZW4...",
  "token_type": "Bearer",
  "expires_in": 900,
  "user": {
    "id": 1,
    "email": "user@example.com",
    "created_at": "2026-03-15T10:00:00",
    "age": 35,
    "height": 175,
    "weight": 70,
    "gender": "male",
    "pd_appearance_in_kinship": false,
    "pd_appearance_in_first_grade_kinship": false
  }
}
```

**Error responses**:

| Status | Body |
|--------|------|
| `400` | `{"error": "..."}` — validation failed |
| `401` | `{"error": "Invalid credentials"}` |

---

### `POST /api/auth/refresh`

Exchange a valid refresh token for a new access token. The old refresh token remains valid until explicitly revoked.

**Auth required**: Yes (JWT — the current, possibly-expiring access token is still required in the header)

**Request body**:

| Field | Type | Required |
|-------|------|----------|
| `refresh_token` | string | Yes |

**Example request**:

```json
{
  "refresh_token": "dGhpcyBpcyBhIHNlY3VyZSByYW5kb20gdG9rZW4..."
}
```

**Example response** `200`:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 900
}
```

**Error responses**:

| Status | Body |
|--------|------|
| `400` | `{"error": "..."}` — validation failed |
| `401` | `{"error": "Invalid or expired refresh token"}` |

---

### `POST /api/auth/logout`

Revoke a specific refresh token (logout from current device).

**Auth required**: Yes (JWT)

**Request body**:

| Field | Type | Required |
|-------|------|----------|
| `refresh_token` | string | Yes |

**Example request**:

```json
{
  "refresh_token": "dGhpcyBpcyBhIHNlY3VyZSByYW5kb20gdG9rZW4..."
}
```

**Example response** `200`:

```json
{
  "message": "Logged out successfully"
}
```

**Error responses**:

| Status | Body |
|--------|------|
| `400` | `{"error": "..."}` — validation failed |
| `401` | `{"error": "Invalid refresh token"}` |

---

### `POST /api/auth/logout-all`

Revoke all refresh tokens for the authenticated user (logout from every device).

**Auth required**: Yes (JWT)

**Request body**: None

**Example response** `200`:

```json
{
  "message": "Logged out from all devices"
}
```

---

### `GET /api/auth/sessions`

List all active (non-revoked, non-expired) sessions for the current user.

**Auth required**: Yes (JWT)

**Example response** `200`:

```json
{
  "sessions": [
    {
      "id": 1,
      "device_info": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0...)",
      "ip_address": "192.168.1.100",
      "created_at": "2026-03-15T10:00:00",
      "expires_at": "2026-04-14T10:00:00"
    },
    {
      "id": 2,
      "device_info": "MyApp/1.0 Android",
      "ip_address": "10.0.0.5",
      "created_at": "2026-03-14T08:30:00",
      "expires_at": "2026-04-13T08:30:00"
    }
  ]
}
```

---

## User Routes `/api/user`

> **Client**: Mobile App

---

### `GET /api/user/`

Get the current user's profile and demographic information.

**Auth required**: Yes (JWT)

**Example response** `200`:

```json
{
  "success": true,
  "data": {
    "id": 1,
    "age": 35,
    "height": 175,
    "weight": 70,
    "gender": "male",
    "pd_appearance_in_kinship": false,
    "pd_appearance_in_first_grade_kinship": false
  }
}
```

**Error responses**:

| Status | Body |
|--------|------|
| `401` | `{"error": "..."}` |
| `404` | `{"error": "User not found"}` |

---

### `PATCH /api/user/`

Update user demographic information. All fields are optional; only provided fields are updated.

**Auth required**: Yes (JWT)

**Request body**:

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `age` | integer | No | 0–100 |
| `height` | integer | No | 0–300 (cm) |
| `weight` | integer | No | 0–500 (kg) |
| `gender` | string | No | `"male"` or `"female"` |
| `pd_appearance_in_kinship` | boolean | No | |
| `pd_appearance_in_first_grade_kinship` | boolean | No | |

**Example request**:

```json
{
  "age": 42,
  "height": 180,
  "weight": 75,
  "gender": "male",
  "pd_appearance_in_kinship": true,
  "pd_appearance_in_first_grade_kinship": false
}
```

**Example response** `200`:

```json
{
  "success": true,
  "data": {
    "id": 1,
    "age": 42,
    "height": 180,
    "weight": 75,
    "gender": "male",
    "pd_appearance_in_kinship": true,
    "pd_appearance_in_first_grade_kinship": false
  }
}
```

**Error responses**:

| Status | Body |
|--------|------|
| `400` | `{"success": false, "error": "Validation failed", "message": "..."}` |
| `401` | `{"error": "..."}` |
| `404` | `{"error": "User not found"}` |

---

### `POST /api/user/reset`

Reset all demographic fields to `null`. Does **not** reset questionnaire responses or delete the account.

**Auth required**: Yes (JWT)

**Request body**: None

**Example response** `200`:

```json
{
  "success": true,
  "message": "User data reset"
}
```

**Fields reset**: `age`, `height`, `weight`, `gender`, `pd_appearance_in_kinship`, `pd_appearance_in_first_grade_kinship`

**Error responses**:

| Status | Body |
|--------|------|
| `401` | `{"error": "..."}` |
| `404` | `{"error": "User not found"}` |
| `500` | `{"success": false, "error": "..."}` |

---

### `DELETE /api/user/`

Permanently delete the current user account and all associated data.

**Auth required**: Yes (JWT)

**Request body**: None

**Example response** `200`:

```json
{
  "success": true,
  "message": "Account deleted"
}
```

**Error responses**:

| Status | Body |
|--------|------|
| `401` | `{"error": "..."}` |
| `404` | `{"error": "User not found"}` |
| `500` | `{"success": false, "error": "..."}` |

---

## Questionnaire Routes `/api/questionnaire`

> **Client**: Mobile App

Questions `Q01`–`Q28` are boolean fields on the user. Each represents a symptom or risk-factor question. All are `null` by default (unanswered).

---

### `GET /api/questionnaire/`

Get all 28 questionnaire responses for the current user.

**Auth required**: Yes (JWT)

**Example response** `200`:

```json
{
  "success": true,
  "data": {
    "Q01": true,
    "Q02": false,
    "Q03": null,
    "Q04": null,
    "Q05": true,
    "Q06": false,
    "Q07": null,
    "Q08": null,
    "Q09": true,
    "Q10": false,
    "Q11": null,
    "Q12": null,
    "Q13": true,
    "Q14": false,
    "Q15": null,
    "Q16": null,
    "Q17": true,
    "Q18": false,
    "Q19": null,
    "Q20": null,
    "Q21": true,
    "Q22": false,
    "Q23": null,
    "Q24": null,
    "Q25": true,
    "Q26": false,
    "Q27": null,
    "Q28": null
  }
}
```

**Error responses**:

| Status | Body |
|--------|------|
| `401` | `{"error": "..."}` |
| `404` | `{"error": "User not found"}` |

---

### `PATCH /api/questionnaire/`

Partially update questionnaire responses. Send only the questions you want to update. Values must be boolean (`true` / `false`) or `null` to clear.

**Auth required**: Yes (JWT)

**Request body**: Object where keys are `Q01`–`Q28` and values are `boolean` or `null`.

**Example request** (update a few questions):

```json
{
  "Q01": true,
  "Q05": false,
  "Q12": null
}
```

**Example response** `200`:

```json
{
  "success": true,
  "updated": ["Q01", "Q05", "Q12"]
}
```

**Error responses**:

| Status | Body |
|--------|------|
| `400` | `{"success": false, "error": "No valid fields provided"}` — no recognized question keys sent |
| `400` | `{"success": false, "error": "Q01 must be boolean"}` — non-boolean value |
| `401` | `{"error": "..."}` |
| `404` | `{"error": "User not found"}` |
| `500` | `{"success": false, "error": "..."}` |

---

## Test Group Routes `/api/groups`

> **Client**: Mobile App

A **test group** bundles one tremor, one drawing, and one voice `TestSession` into a single assessment session. The mobile app must create a group first, then create each of the three tests referencing the returned `group_id`.

**Group lifecycle**:
1. `POST /api/groups` → group created, `status = "pending"`
2. `POST /api/tests` (first test, any type) → group advances to `status = "in_progress"`
3. After all three tests are individually completed via `POST /api/tests/<id>/complete`, the server computes `overall_score` and sets `status = "completed"`

---

### `POST /api/groups`

Create a new test group. No request body required.

**Auth required**: Yes (JWT)

**Request body**: None (empty body or `{}`)

**Example response** `201`:

```json
{
  "success": true,
  "data": {
    "id": 3,
    "user_id": 1,
    "status": "pending",
    "overall_score": null,
    "created_at": "2026-03-15T10:00:00",
    "completed_at": null,
    "tests": []
  }
}
```

**Error responses**:

| Status | Body |
|--------|------|
| `401` | `{"error": "..."}` |

---

### `GET /api/groups`

List all test groups for the current user with optional status filter and pagination.

**Auth required**: Yes (JWT)

**Query parameters**:

| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| `status` | string | No | `"pending"`, `"in_progress"`, `"completed"` |
| `page` | integer | No | Default: `1`, min: `1` |
| `per_page` | integer | No | Default: `20`, min: `1`, max: `100` |

**Example request**:

```
GET /api/groups?status=completed&page=1&per_page=10
```

**Example response** `200`:

```json
{
  "success": true,
  "data": {
    "groups": [
      {
        "id": 3,
        "user_id": 1,
        "status": "completed",
        "overall_score": 0.68,
        "created_at": "2026-03-15T10:00:00",
        "completed_at": "2026-03-15T10:30:00",
        "tests": [
          {
            "id": 7,
            "user_id": 1,
            "group_id": 3,
            "test_type": "tremor",
            "status": "completed",
            "device_source": "esp32",
            "config": {"0": true, "1": true},
            "created_at": "2026-03-15T10:01:00",
            "completed_at": "2026-03-15T10:08:00",
            "ml_score": 0.72,
            "inputs": []
          },
          {
            "id": 8,
            "user_id": 1,
            "group_id": 3,
            "test_type": "drawing",
            "status": "completed",
            "device_source": "mobile",
            "config": {},
            "created_at": "2026-03-15T10:10:00",
            "completed_at": "2026-03-15T10:15:00",
            "ml_score": 0.60,
            "inputs": []
          },
          {
            "id": 9,
            "user_id": 1,
            "group_id": 3,
            "test_type": "voice",
            "status": "completed",
            "device_source": "mobile",
            "config": {},
            "created_at": "2026-03-15T10:20:00",
            "completed_at": "2026-03-15T10:25:00",
            "ml_score": 0.55,
            "inputs": []
          }
        ]
      }
    ],
    "total": 1,
    "page": 1,
    "per_page": 10,
    "pages": 1
  }
}
```

**Error responses**:

| Status | Body |
|--------|------|
| `400` | `{"success": false, "error": "..."}` — invalid query params |
| `401` | `{"error": "..."}` |

---

### `GET /api/groups/<group_id>`

Get a single group by ID, including all linked test sessions and their file inputs.

**Auth required**: Yes (JWT)

**URL parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `group_id` | integer | Group ID |

**Example request**:

```
GET /api/groups/3
```

**Example response** `200` (after all ML inference completes):

```json
{
  "success": true,
  "data": {
    "id": 3,
    "user_id": 1,
    "status": "completed",
    "overall_score": 0.68,
    "ml_status": "completed",
    "ml_job_id": null,
    "created_at": "2026-03-15T10:00:00",
    "completed_at": "2026-03-15T10:30:00",
    "tests": [
      {
        "id": 7,
        "user_id": 1,
        "group_id": 3,
        "test_type": "tremor",
        "status": "completed",
        "device_source": "esp32",
        "config": {"0": true, "1": true},
        "created_at": "2026-03-15T10:01:00",
        "completed_at": "2026-03-15T10:08:00",
        "ml_score": 0.72,
        "ml_status": "completed",
        "ml_job_id": null,
        "inputs": [
          {
            "id": 3,
            "input_type": "tremor_gyro",
            "file_path": "uploads/tremor/7/7_0_l.txt",
            "mime_type": "text/plain",
            "file_size": 2048,
            "created_at": "2026-03-15T10:05:00",
            "expires_at": "2026-06-13T10:05:00"
          }
        ]
      },
      {
        "id": 8,
        "user_id": 1,
        "group_id": 3,
        "test_type": "drawing",
        "status": "completed",
        "device_source": "mobile",
        "config": {},
        "created_at": "2026-03-15T10:10:00",
        "completed_at": "2026-03-15T10:15:00",
        "ml_score": 0.60,
        "ml_status": "completed",
        "ml_job_id": null,
        "inputs": []
      },
      {
        "id": 9,
        "user_id": 1,
        "group_id": 3,
        "test_type": "voice",
        "status": "completed",
        "device_source": "mobile",
        "config": {},
        "created_at": "2026-03-15T10:20:00",
        "completed_at": "2026-03-15T10:25:00",
        "ml_score": 0.55,
        "ml_status": "completed",
        "ml_job_id": null,
        "inputs": []
      }
    ]
  }
}
```

**Error responses**:

| Status | Body |
|--------|------|
| `401` | `{"error": "..."}` |
| `403` | `{"error": "Forbidden"}` |
| `404` | `{"error": "Group not found"}` |

---

## Test Routes `/api/tests`

> **Client**: Mobile App (create, list, get, drawings, voice) + ESP32 (tremor upload, complete)

---

### `POST /api/tests`

Create a new test session inside an existing group.

**Auth required**: Yes (JWT — Mobile App)

**Request body**:

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `group_id` | integer | Yes | Must be a group owned by the current user and not yet completed |
| `test_type` | string | Yes | `"tremor"`, `"drawing"`, or `"voice"` |
| `device` | string | No | `"mobile"` or `"esp32"`. Defaults to `"esp32"` for tremor, `"mobile"` for drawing/voice |
| `config` | object | No | For tremor tests: keys `"0"`–`"10"`, values `boolean`. Omitted keys default to `false` |

**Notes**:
- Each test type can appear **once** per group. A second attempt with the same `test_type` returns `409`.
- Adding the first test to a group advances the group from `"pending"` to `"in_progress"`.
- For tremor tests with ESP32, use `POST /api/tests/<id>/start` to notify the device to begin collecting data.

**Example request** — tremor test via ESP32:

```json
{
  "group_id": 3,
  "test_type": "tremor",
  "config": {
    "0": true,
    "1": true,
    "2": false,
    "5": true,
    "10": true
  }
}
```

**Example request** — tremor test via mobile (override):

```json
{
  "group_id": 3,
  "test_type": "tremor",
  "device": "mobile",
  "config": {
    "0": true,
    "1": true
  }
}
```

**Example request** — drawing test:

```json
{
  "group_id": 3,
  "test_type": "drawing"
}
```

**Example request** — voice test:

```json
{
  "group_id": 3,
  "test_type": "voice"
}
```

**Example response** `201`:

```json
{
  "success": true,
  "data": {
    "id": 7,
    "user_id": 1,
    "group_id": 3,
    "test_type": "tremor",
    "status": "pending",
    "device_source": "esp32",
    "config": {
      "0": true,
      "1": true,
      "5": true,
      "10": true
    },
    "created_at": "2026-03-15T10:00:00",
    "completed_at": null,
    "ml_score": null,
    "inputs": []
  }
}
```

**Error responses**:

| Status | Body |
|--------|------|
| `400` | `{"success": false, "error": "..."}` — validation failed |
| `401` | `{"error": "..."}` |
| `403` | `{"error": "Forbidden"}` — group belongs to another user |
| `404` | `{"error": "User not found"}` |
| `404` | `{"error": "Group not found"}` |
| `409` | `{"error": "Group is already completed"}` |
| `409` | `{"error": "A tremor test already exists in this group"}` |

---

### `GET /api/tests`

List all test sessions for the current user, with optional filtering and pagination.

**Auth required**: Yes (JWT — Mobile App)

**Query parameters**:

| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| `test_type` | string | No | `"tremor"`, `"drawing"`, or `"voice"` |
| `status` | string | No | `"pending"`, `"in_progress"`, `"completed"`, `"failed"` |
| `group_id` | integer | No | Filter by group |
| `page` | integer | No | Default: `1`, min: `1` |
| `per_page` | integer | No | Default: `20`, min: `1`, max: `100` |

**Example request**:

```
GET /api/tests?test_type=tremor&status=completed&page=1&per_page=10
```

**Example response** `200`:

```json
{
  "success": true,
  "data": {
    "tests": [
      {
        "id": 7,
        "user_id": 1,
        "test_type": "tremor",
        "status": "completed",
        "device_source": "esp32",
        "config": {"0": true, "1": true},
        "created_at": "2026-03-15T10:00:00",
        "completed_at": "2026-03-15T10:05:30",
        "ml_score": 0.72,
        "inputs": [
          {
            "id": 3,
            "input_type": "tremor_gyro",
            "file_path": "uploads/tremor/7/7_0_l.txt",
            "mime_type": "text/plain",
            "file_size": 2048,
            "created_at": "2026-03-15T10:02:00",
            "expires_at": "2026-06-13T10:02:00"
          }
        ]
      }
    ],
    "total": 1,
    "page": 1,
    "per_page": 10,
    "pages": 1
  }
}
```

**Error responses**:

| Status | Body |
|--------|------|
| `400` | `{"success": false, "error": "..."}` — invalid query params |
| `401` | `{"error": "..."}` |
| `404` | `{"error": "User not found"}` |

---

### `GET /api/tests/<test_id>`

Get a single test session by its database ID.

**Auth required**: Yes (JWT — Mobile App)

**URL parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `test_id` | integer | Test session ID |

**Example request**:

```
GET /api/tests/7
```

**Example response** `200` (while ML inference is processing):

```json
{
  "success": true,
  "data": {
    "id": 7,
    "user_id": 1,
    "group_id": 3,
    "test_type": "tremor",
    "status": "completed",
    "device_source": "esp32",
    "config": {"0": true, "1": true, "5": true},
    "created_at": "2026-03-15T10:00:00",
    "completed_at": "2026-03-15T10:05:30",
    "ml_score": null,
    "ml_status": "processing",
    "ml_job_id": "abc-123-def-456",
    "inputs": [
      {
        "id": 3,
        "input_type": "tremor_gyro",
        "file_path": "uploads/tremor/7/7_0_l.txt",
        "mime_type": "text/plain",
        "file_size": 2048,
        "created_at": "2026-03-15T10:02:00",
        "expires_at": "2026-06-13T10:02:00"
      }
    ]
  }
}
```

**Example response** `200` (after ML inference completes):

```json
{
  "success": true,
  "data": {
    "id": 7,
    "user_id": 1,
    "group_id": 3,
    "test_type": "tremor",
    "status": "completed",
    "device_source": "esp32",
    "config": {"0": true, "1": true, "5": true},
    "created_at": "2026-03-15T10:00:00",
    "completed_at": "2026-03-15T10:05:30",
    "ml_score": 0.72,
    "ml_status": "completed",
    "ml_job_id": null,
    "inputs": [
      {
        "id": 3,
        "input_type": "tremor_gyro",
        "file_path": "uploads/tremor/7/7_0_l.txt",
        "mime_type": "text/plain",
        "file_size": 2048,
        "created_at": "2026-03-15T10:02:00",
        "expires_at": "2026-06-13T10:02:00"
      }
    ]
  }
}
```

**Error responses**:

| Status | Body |
|--------|------|
| `401` | `{"error": "..."}` |
| `403` | `{"error": "Forbidden"}` |
| `404` | `{"error": "Test not found"}` |

---

### `POST /api/tests/<test_id>/tremor`

Upload IMU (gyroscope/accelerometer) data for one hand/subtest of a tremor test.

**Auth required**: JWT (Mobile App) **or** `X-Device-API-Key` (ESP32)

**URL parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `test_id` | integer | Must be a `tremor` type test owned by the authenticated user |

This endpoint accepts two content types:

---

#### Option A — JSON body (ESP32 recommended)

**Content-Type**: `application/json`

**Request body**:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `subtest_id` or `subtest` | string | Yes | `"0"` to `"10"` |
| `hand` | string | Yes | `"left"`, `"right"`, `"l"`, or `"r"` |
| `imu_data` | object | Yes | Object containing 6 arrays (see below) |
| `imu_data.ax` | float[] | Yes | Accelerometer X axis |
| `imu_data.ay` | float[] | Yes | Accelerometer Y axis |
| `imu_data.az` | float[] | Yes | Accelerometer Z axis |
| `imu_data.gx` | float[] | Yes | Gyroscope X axis |
| `imu_data.gy` | float[] | Yes | Gyroscope Y axis |
| `imu_data.gz` | float[] | Yes | Gyroscope Z axis |

All 6 arrays must be present. They should all be the same length.

**Example request**:

```json
{
  "subtest_id": "0",
  "hand": "left",
  "imu_data": {
    "ax": [0.12, 0.15, 0.11, 0.09],
    "ay": [0.05, 0.07, 0.06, 0.04],
    "az": [9.81, 9.80, 9.82, 9.79],
    "gx": [0.001, 0.002, 0.001, 0.003],
    "gy": [0.002, 0.001, 0.003, 0.001],
    "gz": [0.000, 0.001, 0.000, 0.002]
  }
}
```

The server saves this as a TXT file with the following CSV format:

```
const,ax,ay,az,gx,gy,gz
0,0.12,0.05,9.81,0.001,0.002,0.0
1,0.15,0.07,9.80,0.002,0.001,0.001
2,0.11,0.06,9.82,0.001,0.003,0.0
3,0.09,0.04,9.79,0.003,0.001,0.002
```

---

#### Option B — Multipart file upload (Mobile App)

**Content-Type**: `multipart/form-data`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `file` | file | Yes | `.txt` file with gyro data |
| `subtest` | string | Yes | `"0"` to `"10"` |
| `hand` | string | Yes | `"l"` or `"r"` |

---

**Example response** `200` (both options):

```json
{
  "success": true,
  "data": {
    "id": 3,
    "input_type": "tremor_gyro",
    "subtest": "0",
    "hand": "l",
    "file_path": "uploads/tremor/7/7_0_l.txt"
  }
}
```

**Error responses**:

| Status | Body |
|--------|------|
| `400` | `{"error": "subtest_id is required"}` |
| `400` | `{"error": "hand is required"}` |
| `400` | `{"error": "Invalid hand: must be 'left', 'right', 'l', or 'r'"}` |
| `400` | `{"error": "imu_data is required and must be an object"}` |
| `400` | `{"error": "imu_data missing keys: gx, gy"}` |
| `400` | `{"error": "imu_data.ax must be an array"}` |
| `400` | `{"error": "Invalid subtest: 11"}` |
| `400` | `{"error": "Subtest 0 is not enabled for this test"}` |
| `400` | `{"error": "Test is not a tremor test"}` |
| `401` | `{"error": "..."}` |
| `403` | `{"error": "Forbidden"}` |
| `404` | `{"error": "Test not found"}` |

---

### `POST /api/tests/<test_id>/drawings`

Upload spiral drawing images (both hands required in a single request) for a drawing test.

**Auth required**: Yes (JWT — Mobile App)

**Content-Type**: `multipart/form-data`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `spiral_left` | file | Yes | Left hand spiral image (PNG/JPG) |
| `spiral_right` | file | Yes | Right hand spiral image (PNG/JPG) |

**Example response** `200`:

```json
{
  "success": true,
  "data": {
    "inputs": [
      {
        "id": 10,
        "input_type": "drawing_spiral",
        "hand": "l",
        "file_path": "uploads/drawing/2/spiral_l.png"
      },
      {
        "id": 11,
        "input_type": "drawing_spiral",
        "hand": "r",
        "file_path": "uploads/drawing/2/spiral_r.jpg"
      }
    ]
  }
}
```

**Error responses**:

| Status | Body |
|--------|------|
| `400` | `{"error": "Both spiral_left and spiral_right files required"}` |
| `400` | `{"error": "Invalid file type for spiral_left. Only PNG/JPG allowed"}` |
| `400` | `{"error": "Test is not a drawing test"}` |
| `401` | `{"error": "..."}` |
| `403` | `{"error": "Forbidden"}` |
| `404` | `{"error": "Test not found"}` |

---

### `POST /api/tests/<test_id>/voice`

Upload a voice recording for a voice test.

**Auth required**: Yes (JWT — Mobile App)

**Content-Type**: `multipart/form-data`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `audio` | file | Yes | Audio file (WAV, MP3, or M4A) |

**Example response** `200`:

```json
{
  "success": true,
  "data": {
    "id": 20,
    "input_type": "voice_recording",
    "file_path": "uploads/voice/3/recording.wav"
  }
}
```

**Error responses**:

| Status | Body |
|--------|------|
| `400` | `{"error": "No audio file provided"}` |
| `400` | `{"error": "Invalid file type. Only WAV/MP3/M4A allowed"}` |
| `400` | `{"error": "Test is not a voice test"}` |
| `401` | `{"error": "..."}` |
| `403` | `{"error": "Forbidden"}` |
| `404` | `{"error": "Test not found"}` |

---

### `POST /api/tests/<test_id>/complete`

Mark a test as completed. The server validates that all required subtests have been uploaded, then enqueues an ML inference job (runs asynchronously).

**Auth required**: JWT (Mobile App) **or** `X-Device-API-Key` (ESP32)

**Request body**: None

**Validation**:

- `tremor`: Checks that a `{test_id}_{step}_{hand}.txt` file exists for every step enabled (`true`) in `config`, for both `l` and `r` hands.
- `drawing`: Requires exactly 2 uploaded inputs.
- `voice`: Requires exactly 1 uploaded input.

**Example response** `202`:

```json
{
  "success": true,
  "data": {
    "message": "Test completed",
    "status": "completed",
    "ml_status": "processing",
    "ml_job_id": "abc-123-def-456",
    "uploaded_count": 4,
    "expected_count": 4,
    "missing": []
  }
}
```

**Note**: The response returns immediately with `ml_status: "processing"`. The client should poll `GET /api/tests/<test_id>` to check when `ml_status` changes to `"completed"` (with `ml_score`) or `"failed"`.

**Example response** `202` — last test in the group to finish (group inference also async):

```json
{
  "success": true,
  "data": {
    "message": "Test completed",
    "status": "completed",
    "ml_status": "processing",
    "ml_job_id": "abc-123-def-456",
    "uploaded_count": 1,
    "expected_count": 1,
    "missing": []
  }
}
```

The `group_overall_score` is computed asynchronously after all three tests complete. Poll `GET /api/groups/<group_id>` to check when `ml_status` becomes `"completed"` with `overall_score`.

**Example error response** `400` (missing uploads):

```json
{
  "error": "Missing required subtest uploads",
  "missing": ["1_l", "1_r"],
  "expected_count": 4,
  "uploaded_count": 2
}
```

**Error responses**:

| Status | Body |
|--------|------|
| `400` | `{"error": "Test is already completed"}` |
| `400` | `{"error": "Test has no uploads yet"}` — status is still `"pending"` |
| `400` | `{"error": "Missing required subtest uploads", "missing": [...], ...}` |
| `401` | `{"error": "..."}` |
| `403` | `{"error": "Forbidden"}` |
| `404` | `{"error": "Test not found"}` |

---

### `POST /api/tests/<test_id>/reset`

Reset a test session by deleting all uploaded files and inputs, and setting the status back to pending. Also cancels any pending ML inference job.

**Auth required**: JWT (Mobile App) **or** `X-Device-API-Key` (ESP32)

**Request body**: (optional)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `config` | object | No | For tremor tests: keys `"0"`–`"10"`, values `boolean`. Updates the test configuration. |

**Notes**:
- Cannot reset a test if its group is already completed.
- For tremor tests with ESP32, use `POST /api/tests/<id>/start` to notify the device to begin collecting data after reset.

**Example request** (with new config):

```json
{
  "config": {
    "0": true,
    "1": true,
    "5": true
  }
}
```

**Example response** `200`:

```json
{
  "success": true,
  "data": {
    "message": "Test reset successfully",
    "status": "pending"
  }
}
```

**Error responses**:

| Status | Body |
|--------|------|
| `400` | `{"error": "config must be an object"}` |
| `400` | `{"error": "Invalid config key: ..."}` |
| `400` | `{"error": "Config value for ... must be boolean"}` |
| `400` | Test is not resetable (group is completed) |
| `401` | `{"error": "..."}` |
| `403` | `{"error": "Forbidden"}` |
| `404` | `{"error": "Test not found"}` |
| `409` | `{"error": "Cannot reset test in a completed group..."}` |

---

### `POST /api/tests/<test_id>/start`

Send a `test_started` event to the paired ESP32 device for a tremor test. Use this to notify the device to begin collecting data.

**Auth required**: JWT (Mobile App) **or** `X-Device-API-Key` (ESP32)

**Request body**: None

**Notes**:
- Only valid for tremor tests with `device_source = "esp32"`.
- Call this after creating a test or after resetting a test to notify the ESP32 to start collecting data.

**Example response** `200`:

```json
{
  "success": true,
  "data": {
    "message": "test_started event sent"
  }
}
```

**Example response** `503` (device not connected):

```json
{
  "error": "ESP32 device is not connected. Make sure the device is powered on and connected."
}
```

**Error responses**:

| Status | Body |
|--------|------|
| `400` | `{"error": "test_started event is only supported for tremor tests"}` |
| `400` | `{"error": "test_started event is only supported for ESP32 device tests"}` |
| `401` | `{"error": "..."}` |
| `403` | `{"error": "Forbidden"}` |
| `404` | `{"error": "Test not found"}` |
| `500` | `{"error": "Failed to send event to device"}` |

---

## ESP32 Device Pairing Routes `/api/esp32-devices`

> **Client**: Mobile App

These routes let the mobile app manage which ESP32 devices are linked to the user's account.

---

### `POST /api/esp32-devices/pair`

Pair an ESP32 device to the current user. The `device_id` is printed on a sticker on the device and entered by the user in the app.

**Auth required**: Yes (JWT)

**Request body**:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `device_id` | string | Yes | Format `ESP32-XXXXXX` (6 hex chars), case-insensitive |
| `name` | string | No | Friendly name; defaults to `device_id` if omitted |

**Example request**:

```json
{
  "device_id": "ESP32-AABBCC",
  "name": "My Wrist Sensor"
}
```

**Example response** `200` (newly paired):

```json
{
  "success": true,
  "data": {
    "id": 1,
    "device_id": "ESP32-AABBCC",
    "name": "My Wrist Sensor",
    "is_connected": false,
    "created_at": "2026-03-15T10:00:00"
  }
}
```

**Example response** `200` (already paired to this user):

```json
{
  "success": true,
  "data": {
    "id": 1,
    "device_id": "ESP32-AABBCC",
    "name": "My Wrist Sensor",
    "is_connected": true,
    "created_at": "2026-03-15T10:00:00"
  },
  "message": "Device is already paired to your account"
}
```

**Error responses**:

| Status | Body |
|--------|------|
| `400` | `{"error": "device_id is required"}` |
| `401` | `{"error": "..."}` |
| `404` | `{"error": "Device not found. Check the device ID and try again"}` |
| `409` | `{"error": "Device is already paired to another user"}` |

---

### `GET /api/esp32-devices`

List all ESP32 devices currently paired to the authenticated user.

**Auth required**: Yes (JWT)

**Example response** `200`:

```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "device_id": "ESP32-AABBCC",
      "name": "My Wrist Sensor",
      "is_connected": true,
      "last_seen_at": "2026-03-15T10:05:00",
      "created_at": "2026-03-15T10:00:00"
    },
    {
      "id": 2,
      "device_id": "ESP32-112233",
      "name": "Spare Device",
      "is_connected": false,
      "last_seen_at": "2026-03-14T09:00:00",
      "created_at": "2026-03-14T08:50:00"
    }
  ]
}
```

**Error responses**:

| Status | Body |
|--------|------|
| `401` | `{"error": "..."}` |

---

### `DELETE /api/esp32-devices/<device_id>`

Unpair an ESP32 device from the current user. The device's `user_id` and `name` are cleared; it can be re-paired by any user.

**Auth required**: Yes (JWT)

**URL parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `device_id` | string | The `device_id` string (e.g., `ESP32-AABBCC`) from the device sticker |

**Example request**:

```
DELETE /api/esp32-devices/ESP32-AABBCC
```

**Example response** `200`:

```json
{
  "success": true,
  "message": "Device unpaired successfully"
}
```

**Error responses**:

| Status | Body |
|--------|------|
| `401` | `{"error": "..."}` |
| `404` | `{"error": "Device not found"}` — device not found or not paired to this user |

---

## ESP32 Device Routes `/api/esp32`

> **Client**: ESP32 Device only

These routes are called directly by the ESP32 firmware. The mobile app never calls these.

---

### `POST /api/esp32/register`

One-time registration of an ESP32 device at the factory (or on first power-up). Verifies the factory HMAC key, creates the device record, and returns a permanent production API key.

**Auth required**: Factory key (`X-Device-API-Key: fk_...`)

**Headers**:

| Header | Value |
|--------|-------|
| `X-Device-API-Key` | `fk_<32-hex-chars>` — HMAC-SHA256 derived from `device_id` and `FACTORY_SECRET` |

**Request body**:

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `device_id` | string | Yes | Format `ESP32-XXXXXX` (uppercase 6 hex chars) |

**Example request**:

```json
{
  "device_id": "ESP32-AABBCC"
}
```

**Example response** `200` (first registration):

```json
{
  "success": true,
  "data": {
    "device_id": "ESP32-AABBCC",
    "api_key": "sk_live_Kx9mN2pQrT..."
  }
}
```

**Example response** `200` (re-registration, key unchanged):

```json
{
  "success": true,
  "data": {
    "device_id": "ESP32-AABBCC",
    "api_key": "sk_live_Kx9mN2pQrT..."
  }
}
```

**Error responses**:

| Status | Body |
|--------|------|
| `400` | `{"error": "device_id is required"}` |
| `400` | `{"error": "Invalid device_id format. Expected: ESP32-XXXXXX"}` |
| `401` | `{"error": "Invalid factory key"}` |

---

### `GET /api/esp32/stream`

Long-lived SSE (Server-Sent Events) connection. The ESP32 connects once and keeps this open to receive real-time commands. When the mobile app creates a tremor test with `device_source = "esp32"`, the server pushes a `test_started` event through this stream.

**Auth required**: Production key (`X-Device-API-Key: sk_live_...`)

**Device must be paired** to a user account before connecting.

**Response**: `text/event-stream` — connection stays open

**SSE events**:

| Event | When | Data |
|-------|------|------|
| `connected` | Immediately on connect | `{"device_id": "ESP32-AABBCC"}` |
| `test_started` | When mobile app starts a tremor test | `{"test_id": 7, "test_type": "tremor", "config": {"0": true, "1": true}}` |
| `heartbeat` | Every 30 seconds (keep-alive) | `{"timestamp": "2026-03-15T10:00:00"}` |

**Example SSE stream**:

```
event: connected
data: {"device_id": "ESP32-AABBCC"}

event: heartbeat
data: {"timestamp": "2026-03-15T10:00:30"}

event: test_started
data: {"test_id": 7, "test_type": "tremor", "config": {"0": true, "1": true, "5": true}}

event: heartbeat
data: {"timestamp": "2026-03-15T10:01:00"}
```

**Notes**:
- The device's `is_connected` is set to `true` on connect and `false` on disconnect.
- Only one active SSE connection per user is tracked at a time.
- Response headers include `Cache-Control: no-cache`, `X-Accel-Buffering: no` for proxy/Cloudflare compatibility.

**Error responses**:

| Status | Body |
|--------|------|
| `401` | `{"error": "..."}` — invalid or missing API key |
| `403` | `{"error": "..."}` — device not paired to any user |

---

### `POST /api/esp32/heartbeat`

Periodic keep-alive ping. Updates `is_connected = true` and `last_seen_at` timestamp. Should be sent regularly even when there is no active SSE connection.

**Auth required**: Production key (`X-Device-API-Key: sk_live_...`)

**Request body**: None

**Example response** `200`:

```json
{
  "success": true,
  "message": "Heartbeat received"
}
```

**Error responses**:

| Status | Body |
|--------|------|
| `401` | `{"error": "..."}` — invalid or missing API key |
| `403` | `{"error": "..."}` — device not paired to any user |

---

## Health Check

### `GET /health`

Simple liveness check.

**Auth required**: No

**Example response** `200`:

```json
{
  "status": "healthy"
}
```

---

## Authentication Summary

| Route | Client | Auth type | Header |
|-------|--------|-----------|--------|
| `POST /api/auth/register` | Mobile | None | — |
| `POST /api/auth/login` | Mobile | None | — |
| `POST /api/auth/refresh` | Mobile | JWT | `Authorization: Bearer <token>` |
| `POST /api/auth/logout` | Mobile | JWT | `Authorization: Bearer <token>` |
| `POST /api/auth/logout-all` | Mobile | JWT | `Authorization: Bearer <token>` |
| `GET /api/auth/sessions` | Mobile | JWT | `Authorization: Bearer <token>` |
| `GET /api/user/` | Mobile | JWT | `Authorization: Bearer <token>` |
| `PATCH /api/user/` | Mobile | JWT | `Authorization: Bearer <token>` |
| `POST /api/user/reset` | Mobile | JWT | `Authorization: Bearer <token>` |
| `DELETE /api/user/` | Mobile | JWT | `Authorization: Bearer <token>` |
| `GET /api/questionnaire/` | Mobile | JWT | `Authorization: Bearer <token>` |
| `PATCH /api/questionnaire/` | Mobile | JWT | `Authorization: Bearer <token>` |
| `POST /api/groups` | Mobile | JWT | `Authorization: Bearer <token>` |
| `GET /api/groups` | Mobile | JWT | `Authorization: Bearer <token>` |
| `GET /api/groups/<id>` | Mobile | JWT | `Authorization: Bearer <token>` |
| `POST /api/tests` | Mobile | JWT | `Authorization: Bearer <token>` |
| `GET /api/tests` | Mobile | JWT | `Authorization: Bearer <token>` |
| `GET /api/tests/<id>` | Mobile | JWT | `Authorization: Bearer <token>` |
| `POST /api/tests/<id>/tremor` | Mobile **or** ESP32 | JWT or Production key | `Authorization: Bearer <token>` or `X-Device-API-Key: sk_live_...` |
| `POST /api/tests/<id>/drawings` | Mobile | JWT | `Authorization: Bearer <token>` |
| `POST /api/tests/<id>/voice` | Mobile | JWT | `Authorization: Bearer <token>` |
| `POST /api/tests/<id>/complete` | Mobile **or** ESP32 | JWT or Production key | `Authorization: Bearer <token>` or `X-Device-API-Key: sk_live_...` |
| `POST /api/tests/<id>/reset` | Mobile **or** ESP32 | JWT or Production key | `Authorization: Bearer <token>` or `X-Device-API-Key: sk_live_...` |
| `POST /api/esp32-devices/pair` | Mobile | JWT | `Authorization: Bearer <token>` |
| `GET /api/esp32-devices` | Mobile | JWT | `Authorization: Bearer <token>` |
| `DELETE /api/esp32-devices/<device_id>` | Mobile | JWT | `Authorization: Bearer <token>` |
| `POST /api/esp32/register` | ESP32 | Factory key | `X-Device-API-Key: fk_...` |
| `GET /api/esp32/stream` | ESP32 | Production key | `X-Device-API-Key: sk_live_...` |
| `POST /api/esp32/heartbeat` | ESP32 | Production key | `X-Device-API-Key: sk_live_...` |
| `GET /health` | Any | None | — |

---

## Global Error Responses

| Status | Meaning | Body |
|--------|---------|------|
| `202` | Accepted (async processing started) | `{"success": true, "data": {...}}` |
| `400` | Bad request / validation error | `{"error": "..."}` or `{"success": false, "error": "..."}` |
| `401` | Unauthenticated | `{"error": "..."}` |
| `403` | Forbidden (wrong user) | `{"error": "Forbidden"}` |
| `404` | Not found | `{"error": "..."}` |
| `409` | Conflict | `{"error": "..."}` |
| `500` | Internal server error | `{"error": "Internal server error"}` or `{"success": false, "error": "..."}` |

---

## ML Inference Status Values

The `ml_status` field indicates the state of asynchronous ML inference:

| Value | Description |
|-------|-------------|
| `null` | Test not yet completed, or inference not started |
| `processing` | Inference job is queued or running |
| `completed` | Inference finished successfully — `ml_score` is available |
| `failed` | Inference failed — check server logs |

**Client polling workflow**:

1. Call `POST /api/tests/<test_id>/complete` → receive `202` with `ml_status: "processing"`
2. Poll `GET /api/tests/<test_id>` until `ml_status` is `"completed"` or `"failed"`
3. When all 3 tests in a group are complete, poll `GET /api/groups/<group_id>` for `ml_status: "completed"` with `overall_score`

---

## Token Lifetimes

| Token | Expiry |
|-------|--------|
| Access token (JWT) | 15 minutes (900 seconds) |
| Refresh token | 30 days |

---

## File Upload Limits

| Test type | Accepted formats | Max size |
|-----------|-----------------|----------|
| Tremor (file upload) | `.txt` | 16 MB |
| Drawing | `.png`, `.jpg`, `.jpeg` | 16 MB per file |
| Voice | `.wav`, `.mp3`, `.m4a` | 16 MB |

Test input files are retained for **90 days** then auto-deleted.

---

## Tremor Test Subtests

Subtests are controlled via the `config` object when creating a tremor test. Each enabled step (`true`) requires two uploads — left hand (`l`) and right hand (`r`).

| Step key | Description |
|----------|-------------|
| `"0"` | Resting |
| `"1"` | Resting with serial sevens |
| `"2"` | Lift and extend arms |
| `"3"` | Arms remain lifted |
| `"4"` | Hold one kilogram weight |
| `"5"` | Point index finger |
| `"6"` | Drink from glass |
| `"7"` | Cross and extend arms |
| `"8"` | Touch index fingers together |
| `"9"` | Tap nose with index finger |
| `"10"` | Entrainment foot stomping |

Steps not included in `config` default to disabled. The complete endpoint rejects the request if any enabled step is missing its uploads.

---

## ESP32 Device ID Format

- Format: `ESP32-XXXXXX` where `XXXXXX` is 6 uppercase hex characters
- Derived from the last 6 characters of the ESP32 MAC address
- Example: MAC `AA:BB:CC:DD:EE:FF` → device ID `ESP32-DDEEFF`
- Printed on a sticker on the physical device
- The user types this into the mobile app to pair

---

## ESP32 Factory Key Generation

Factory keys are generated during manufacturing using HMAC-SHA256 and a shared secret:

```
factory_key = "fk_" + HMAC-SHA256(device_id, FACTORY_SECRET)[:32]
```

**Usage**:

```bash
export FACTORY_SECRET="your_secret_here"
python scripts/generate_factory_key.py AA:BB:CC:DD:EE:FF
# device_id:   ESP32-DDEEFF
# factory_key: fk_a1b2c3d4e5f6...
```

**Environment variables**:

| Variable | Description | Required |
|----------|-------------|----------|
| `FACTORY_SECRET` | Shared secret for HMAC factory key generation | Yes (production) |
