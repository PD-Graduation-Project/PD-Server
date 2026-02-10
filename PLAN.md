# PD-Server Implementation Plan

## Project Overview

Parkinson's Disease detection server with three test types:

- **Tremor**: Gyro data from ESP32 (MPU sensor)
- **Drawing (Spiral)**: Two images of spiral drawings
- **Voice**: Audio recording of sustained "Ahhh"

### Components

1. **Mobile App**: User interface for starting tests, uploading images/audio, viewing results
2. **Central Server**: API, authentication, ML model orchestration, data storage
3. **ESP32**: Embedded system for collecting gyro sensor data

---

## Communication Flow

### ESP32 Registration & Connection Flow

```
┌──────────┐                        ┌─────────────┐                        ┌─────────┐
│  ESP32   │                        │   Server    │                        │   App   │
└────┬─────┘                        └──────┬──────┘                        └────┬────┘
     │                                     │                                    │
     │  POST /api/esp32/register           │                                    │
     │  (factory_api_key)                  │                                    │
     │ ─────────────────────────────────►  │                                    │
     │                                     │                                    │
     │                                     │  Generate production_api_key       │
     │                                     │  Return: { device_id, api_key }    │
     │ ◄─────────────────────────────────  │                                    │
     │                                     │                                    │
     │  Store api_key in flash             │                                    │
     │                                     │                                    │
     │  GET /api/esp32/stream              │                                    │
     │  (production_api_key)               │                                    │
     │ ─────────────────────────────────►  │                                    │
     │                                     │                                    │
     │                                     │  SSE connection open               │
     │                                     │                                    │
     │                                     │                                    │
     │                                     │  POST /api/esp32-devices/pair      │
     │                                     │  (JWT auth, device_id typed)       │
     │                                     │ ◄────────────────────────────────  │
     │                                     │                                    │
     │                                     │  Link device.user_id = user        │
     │                                     │                                    │
     │                                     │                                    │
     │                                     │  POST /api/tests                   │
     │                                     │ ◄────────────────────────────────  │
     │                                     │{ test_type: "tremor", config:{...}}│
     │                                     │                                    │
     │                                     │  Find ESP32 with user_id           │
     │                                     │                                    │
     │  SSE event: test_started            │                                    │
     │ ◄────────────────────────────────   │                                    │
     │  { test_id, config }                │                                    │
     │                                     │                                    │
     │  Run test, collect gyro data        │                                    │
     │                                     │                                    │
     │  POST /api/tests/{id}/tremor        │                                    │
     │  (multiple files)                   │                                    │
     │ ─────────────────────────────────►  │                                    │
     │                                     │                                    │
     │  POST /api/tests/{id}/complete      │                                    │
     │ ─────────────────────────────────►  │                                    │
     │                                     │                                    │
     │                                     │  GET /api/tests/{id}               │
     │                                     │ ◄────────────────────────────────  │
     │                                     │  { status: "completed" }           │
```

### Gyro Data Upload Details

- **File Format**: Plain TXT files (not JSON)
- **Files per test**: 2-22 files (varies based on config)
- **Subtests**: 0, 1, 2, 3, 4, 5, 6, 7, 8, 9 (each with left/right hand = 2 files per subtest)
- **Filename**: `{test_id}_{subtest}_{l|r}.txt` (e.g., `1_1a_l.txt`, `1_1b_r.txt`)
- **Upload**: Single file per POST request
- **Client specifies**: subtest name (0-9) and hand (l or r)

### Key Flow Details

1. **App triggers test** → POST `/tests` with test configuration (which subtests to include)
2. **Server creates TestSession** (status: pending)
3. **Server emits SSE** → `test_started` event to the paired ESP32 (if tremor)
4. **ESP32 runs test** → collects gyro samples locally
5. **ESP32 uploads data** → POST `/tests/{id}/tremor` for each subtest/hand combo
6. **ESP32 signals completion** → POST `/tests/{id}/complete`
7. **Status tracking** → Each upload sets status to `in_progress`
8. **App polls for results** → GET `/tests/{id}` until completed

---

## Database Schema

### 1. TestSession

Main test record (one per test type).

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary Key (auto-increment) |
| user_id | FK | Link to User |
| test_type | String | `tremor`, `drawing`, `voice` |
| status | String | `pending`, `in_progress`, `completed`, `failed` |
| device_source | String | `esp32`, `mobile` |
| config | JSON | Test configuration (which subtests for tremor) |
| created_at | DateTime | Test session creation |
| completed_at | DateTime | Test completion timestamp |
| ml_score | Float | Final ML score (0.0 - 1.0) |

### 2. TestInput

Raw test files uploaded (images, audio, gyro data).

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary Key |
| test_session_id | FK | Link to TestSession |
| input_type | String | `tremor_gyro`, `drawing_spiral`, `voice_recording` |
| file_path | String | Storage path (local/S3) |
| original_filename | String | Original file name from upload |
| mime_type | String | MIME type (text/plain, image/png, audio/wav, etc.) |
| file_size | Integer | File size in bytes |
| created_at | DateTime | Upload timestamp |
| expires_at | DateTime | Auto-delete date (90 days from upload) |

### 3. ESP32Device

Pairs an ESP32 device to a user and stores an API key for authentication.

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary Key |
| device_id | String | Unique hardware identifier (provided on device) |
| user_id | FK | Owner user (null if not yet paired) |
| factory_api_key | String | Pre-programmed factory key (for initial registration) |
| api_key | String | Production API key (generated after first boot) |
| name | String | Optional user-friendly name |
| is_connected | Boolean | SSE connection status |
| last_seen_at | DateTime | Last heartbeat or SSE event timestamp |
| created_at | DateTime | Pairing timestamp |

---

## API Endpoints

### App Routes (JWT or API Key Authentication)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/tests` | Start a single test session (tremor/drawing/voice) |
| GET | `/tests` | List user's tests (with pagination and filters) |
| GET | `/tests/{id}` | Get test status and results |
| POST | `/tests/{id}/tremor` | Upload gyro TXT file (ESP32 via API key or mobile via JWT) |
| POST | `/tests/{id}/drawings` | Upload 2 spiral images (multipart/form-data) |
| POST | `/tests/{id}/voice` | Upload audio recording (multipart/form-data) |
| POST | `/tests/{id}/complete` | Signal test completion (ESP32 via API key or mobile via JWT) |

### ESP32 Device Management (JWT Authentication)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/esp32-devices/pair` | Pair ESP32 device to current user (provide device_id) |
| GET | `/esp32-devices` | List user's paired ESP32 devices |
| DELETE | `/esp32-devices/<id>` | Unpair device |

### ESP32 Device Registration (Factory API Key Authentication)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/esp32/register` | Register ESP32, get production API key |

### ESP32 Routes (Production API Key Authentication)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/esp32/stream` | SSE endpoint — ESP32 connects and listens for `test_started` events |
| POST | `/esp32/heartbeat` | Report ESP32 online status (keep-alive) |

### Request/Response Examples

#### POST /tests (Create Single Test Session)

**Request:**

```json
{
  "test_type": "tremor",
  "device": "esp32",
  "config": {
    "step_1a": true,
    "step_1b": true,
    "step_2": false,
    "step_3": true,
    "step_4": false,
    "step_5": true,
    "step_6": true,
    "step_7": true,
    "step_8": true,
    "step_9": true,
    "step_10": true
  }
}
```

**Response (201 Created):**

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
      "step_1a": true,
      "step_1b": true
    },
    "created_at": "2026-02-09T10:00:00Z",
    "completed_at": null,
    "ml_score": null,
    "inputs": []
  }
}
```

#### POST /tests/{id}/tremor (Upload Gyro TXT File)

**Request:** multipart/form-data

| Field | Type | Description |
|-------|------|-------------|
| file | File | TXT file with gyro data |
| subtest | String | Subtest name: "1a", "1b", "2", "3", "4", "5", "6", "7", "8", "9" |
| hand | String | "l" for left, "r" for right |

**Filename:** Server generates `{test_id}_{subtest}_{hand}.txt` (e.g., `1_1a_l.txt`)

**Response (200 OK):**

```json
{
  "success": true,
  "data": {
    "id": 1,
    "input_type": "tremor_gyro",
    "subtest": "1a",
    "hand": "l",
    "file_path": "/uploads/tremor/1/1_1a_l.txt"
  }
}
```

#### POST /tests/{id}/drawings (Upload Spiral Images)

**Request:** multipart/form-data with 2 images

| Field | Type | Description |
|-------|------|-------------|
| spiral_left | File | Left hand spiral image (png/jpg) |
| spiral_right | File | Right hand spiral image (png/jpg) |

**Response (200 OK):**

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

#### POST /tests/{id}/voice (Upload Audio Recording)

**Request:** multipart/form-data with audio file

| Field | Type | Description |
|-------|------|-------------|
| audio | File | Audio recording (wav/mp3/m4a) |

**Response (200 OK):**

```json
{
  "success": true,
  "data": {
    "id": 20,
    "input_type": "voice_recording",
    "file_path": "/uploads/voice/3/recording.wav",
    "duration_seconds": 5
  }
}
```

#### SSE: GET /esp32/stream (ESP32 connects)

ESP32 devices establish a persistent SSE connection to `/esp32/stream` (authenticated with an API key via `X-Device-API-Key` header). When the server creates a tremor test for a device, it sends a `test_started` event with the test ID and configuration.

**SSE event example:**

```
event: test_started
data: {"test_id": 1, "test_type": "tremor", "config": {"step_1a": true, "step_1b": true, "step_2": false}}
```

#### POST /esp32/heartbeat (ESP32 Heartbeat)

**Headers:** `X-Device-API-Key: {api_key}`

**Response (200 OK):**

```json
{
  "success": true,
  "message": "Heartbeat received"
}
```

---

## Storage Strategy

### File Storage

- **Local filesystem** for simplicity (can migrate to S3 later)
- **Path structure**:
  - Tremor: `uploads/tremor/{test_id}/{test_id}_{subtest}_{hand}.txt`
  - Drawing: `uploads/drawing/{test_id}/spiral_{hand}.{ext}`
  - Voice: `uploads/voice/{test_id}/recording.{ext}`

### Gyro Data File Structure

```
uploads/tremor/1/
├── 1_1a_l.txt    # Subtest 1a, left hand
├── 1_1a_r.txt    # Subtest 1a, right hand
├── 1_1b_l.txt    # Subtest 1b, left hand
├── 1_1b_r.txt    # Subtest 1b, right hand
├── 1_2_l.txt     # Subtest 2, left hand
├── 1_2_r.txt     # Subtest 2, right hand
├── ...
└── 1_9_l.txt     # Subtest 9, left hand
    1_9_r.txt     # Subtest 9, right hand
```

### Data Retention

| Data Type | Retention Period | Auto-Delete |
|-----------|-----------------|-------------|
| Spiral images | 90 days | Yes |
| Voice audio | 90 days | Yes |
| Gyro data | 90 days | Yes |
| ML metrics | 1 year | No |
| Test results | Indefinite | No |
| Demographics snapshots | Indefinite | No |

### Auto-Delete Job

- Scheduled task (e.g., daily at midnight)
- Deletes TestInput records where `expires_at < NOW()`
- Physically removes files from filesystem

---

## Implementation Phases

### Phase 1: Database Models

- [x] Create models: TestSession, TestInput, ESP32Device
- [x] Write Alembic migration
- [x] Create indexes for efficient queries

### Phase 2: ESP32 Routes & SSE

- [x] `/esp32/register` - ESP32 registration endpoint (factory key → production key)
- [x] `/esp32/stream` - SSE endpoint for devices to receive `test_started` events
- [x] `/esp32/heartbeat` - Heartbeat endpoint (updates is_connected, last_seen_at)
- [x] API key authentication middleware for ESP32 routes
- [x] Device-to-user lookup when SSE connection established
- [x] `/esp32-devices/pair` - User pairing endpoint (user types device_id)
- [x] `/esp32-devices` - List user's paired devices
- [x] `/esp32-devices/<id>` - Unpair device

### Phase 3: App Routes - Test Session Management

- [x] `POST /tests` - Create a single TestSession for the requested test
- [x] `GET /tests` - List user's tests with pagination and filters
- [x] `GET /tests/{id}` - Get single test with ML results

### Phase 4: App Routes - File Uploads

- [x] `POST /tests/{id}/tremor` - Upload gyro TXT file with subtest/hand
- [x] `POST /tests/{id}/drawings` - Handle 2 image uploads (spiral_left, spiral_right)
- [x] `POST /tests/{id}/voice` - Handle audio upload
- [x] Create TestInput records with expires_at
- [x] Validate file types and sizes

### Phase 5: Storage & Maintenance

- [ ] File upload utility with path generation
- [ ] Auto-delete job for expired TestInputs
- [ ] Storage cleanup script

### Phase 6: Testing & Documentation

- [ ] Write unit tests for new routes
- [ ] Update Bruno API collection with new endpoints
- [ ] Update OpenAPI spec

---

## Notes

### Test Status Flow

```
pending → in_progress → completed
                     → failed
```

**Status transitions:**

- `pending` → `in_progress`: First file uploaded (tremor/drawing/voice)
- `in_progress` → `completed`: All required files uploaded + `/complete` called (tremor)
- `in_progress` → `completed`: Files uploaded (drawing/voice)
- `in_progress` → `failed`: Missing required files when `/complete` called (tremor)

### Tremor Test Completion Logic

1. Client uploads gyro files one at a time via POST `/tests/{id}/tremor`
2. Each upload creates a TestInput record
3. Client calls POST `/tests/{id}/complete` when done
4. Server validates: all configured subtests have both left/right files uploaded
5. If valid: status → `completed`
6. If missing files: status → `failed` with list of missing subtests

### Each TestSession Independent

- If user requests tremor + drawing + voice, three separate TestSession records are created
- Each tracks its own status, inputs, and results
- Allows partial completion and retry

### Config for Tremor Tests

When creating a tremor test, the mobile app specifies which subtests to include:

```json
{
  "test_type": "tremor",
  "device": "esp32",
  "config": {
    "step_1a": true,
    "step_1b": true,
    "step_2": false,  // Skip this subtest
    "step_3": true,
    ...
  }
}
```

**Subtest names:**

| Key | Name | Default |
|-----|------|---------|
| step_1a | Resting eyes closed | true |
| step_1b | Resting with serial sevens | true |
| step_2 | Lift and extend arms | true |
| step_3 | Arms remain lifted | true |
| step_4 | Hold one kilogram weight | true |
| step_5 | Point index finger | true |
| step_6 | Drink from glass | true |
| step_7 | Cross and extend arms | true |
| step_8 | Touch index fingers together | true |
| step_9 | Tap nose with index finger | true |
| step_10 | Entrainment foot stomping | true |

### ESP32 vs Mobile

- ESP32 handles tremor test (sensor data)
- Mobile handles drawing + voice tests (user input)
- Different authentication (API key vs JWT)
- Separate route namespaces for clarity

### ESP32 Pairing Flow

**Database (Pre-loaded at Factory):**

| device_id | factory_api_key | user_id | production_api_key |
|-----------|-----------------|---------|-------------------|
| ESP32-001234 | factory_esp32_a1b2c3... | NULL | NULL |

**ESP32 Firmware (Pre-programmed):**

```cpp
#define DEVICE_ID "ESP32-001234"
#define FACTORY_API_KEY "factory_esp32_a1b2c3d4e5"
```

**User Pairing (User types only device_id):**

1. User sees sticker: `ESP32-001234`
2. User types in mobile app: `ESP32-001234`
3. Server links device to user account
4. Done!

**ESP32 Registration (Automatic on first boot):**

1. ESP32 calls `POST /api/esp32/register` with factory key
2. Server validates, generates production key
3. ESP32 stores production key in flash
4. ESP32 connects to SSE stream

### ESP32 Data Upload

ESP32 can use either:

- `/api/tests/{id}/tremor` (multipart form-data with file, subtest, hand)

Both require `X-Device-API-Key` header with production API key.

---

## Future Enhancements (Out of Scope)

1. **Real-time updates**: WebSocket for live test status
2. **S3 storage**: Migrate from local filesystem
3. **ML model integration**: Actual ML inference endpoints
4. **Questionnaire snapshot**: Store Q01-Q28 per test
5. **Test scheduling**: Queue tests for future execution
6. **Multi-user ESP32**: ESP32 serves multiple users
