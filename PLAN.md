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

### SSE-based ESP32 Notification (Recommended)

Instead of polling, the server maintains a Server-Sent Events (SSE) stream that ESP32 devices connect to. When the app starts a tremor test, the server emits a `test_started` SSE event to the appropriate ESP32 device. The ESP32 then performs the test and uploads data via REST POST endpoints.

```
┌─────────┐                        ┌─────────┐                        ┌─────────┐
│   App   │                        │ Server  │                        │  ESP32  │
└────┬────┘                        └────┬────┘                        └────┬────┘
     │                                  │                                  │
     │  POST /tests                     │       GET /esp32/stream          │
     │  {test_type: "tremor",         │  ◄──────────────────────────────  │
     │   config: {...}}                 │       (persistent connection)     │
     │ ──────────────────────────────►  │                                  │
     │                                  │                                  │
     │                                  │  SSE event: test_started         │
     │                                  │  {test_id, test_type, config}    │
     │                                  │ ──────────────────────────────►  │
     │                                  │                                  │
     │                                  │  POST /esp32/tests/{id}/data     │
     │                                  │ ◄──────────────────────────────  │
     │                                  │  {gyro_data: [...]}              │
     │                                  │                                  │
     │                                  │  POST /esp32/tests/{id}/complete │
     │                                  │ ◄──────────────────────────────  │
     │  GET /tests/{id}                 │                                  │
     │ ◄──────────────────────────────  │                                  │
     │  {status: completed, score: 0.7} │                                  │
     │                                  │                                  │
```

### Key Flow Details

1. **App triggers test** → POST `/tests` with single-test configuration
2. **Server creates TestSession** (status: pending)
3. **Server emits SSE** → `test_started` event to the paired ESP32 (if tremor)
4. **ESP32 runs test** → collects gyro samples locally
5. **ESP32 uploads data** → POST `/esp32/tests/{id}/data`
6. **ESP32 signals completion** → POST `/esp32/tests/{id}/complete`
7. **App polls for results** → GET `/tests/{id}` until completed

---

## Database Schema

### 1. TestSession

Main test record (one per test type).

| Column | Type | Description |
|--------|------|-------------|
| id | UUID/Integer | Primary Key |
| user_id | FK | Link to User |
| test_type | Enum | `tremor`, `drawing`, `voice` |
| status | Enum | `pending`, `in_progress`, `completed`, `failed` |
| device_source | String | `esp32`, `mobile` |
| created_at | DateTime | Test session creation |
| completed_at | DateTime | Test completion timestamp |
| ml_score | Float | Final ML score (0.0 - 1.0) |

### 2. TestInput

Raw test files uploaded (images, audio, gyro data).

| Column | Type | Description |
|--------|------|-------------|
| id | UUID/Integer | Primary Key |
| test_session_id | FK | Link to TestSession |
| input_type | Enum | `spiral_image_1`, `spiral_image_2`, `voice_audio`, `tremor_gyro` |
| file_path | String | Storage path (local/S3) |
| original_filename | String | Original file name from upload |
| mime_type | String | MIME type (image/png, audio/wav, etc.) |
| file_size | Integer | File size in bytes |
| created_at | DateTime | Upload timestamp |
| expires_at | DateTime | Auto-delete date (90 days from upload) |

### 3. ESP32Device (new)

Pairs an ESP32 device to a user and stores an API key for authentication.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID/Integer | Primary Key |
| device_id | String | Unique hardware identifier (provided on device) |
| user_id | FK | Owner user |
| api_key | String | Device API key (showed once at pairing) |
| name | String | Optional user-friendly name |
| is_connected | Boolean | SSE connection status |
| last_seen_at | DateTime | Last heartbeat or SSE event timestamp |
| created_at | DateTime | Pairing timestamp |

### Notes on Removed Tables

- `MLMetrics` table removed — detailed metrics can be added later if needed, currently `ml_score` on `TestSession` suffices.
- `TestDemographicsSnapshot` removed — the `User` demographics are used; if historical snapshots become necessary we can add this model later.
---

## API Endpoints

### App Routes (JWT Authentication)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/tests` | Start a single test session (tremor/drawing/voice) |
| GET | `/tests` | List user's tests (with pagination and filters) |
| GET | `/tests/{id}` | Get test status and results |
| POST | `/tests/{id}/drawings` | Upload 2 spiral images (multipart/form-data) |
| POST | `/tests/{id}/voice` | Upload audio recording (multipart/form-data) |

### ESP32 Device Management (JWT Auth)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/esp32-devices` | Pair an ESP32 device to the current user (provide `device_id`) |
| GET | `/esp32-devices` | List user's paired ESP32 devices |
| DELETE | `/esp32-devices/{id}` | Unpair device |

### ESP32 Routes (API Key Authentication)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/esp32/stream` | SSE endpoint — ESP32 connects and listens for `test_started` events |
| POST | `/esp32/tests/{id}/data` | Upload gyro data for a test session |
| POST | `/esp32/tests/{id}/complete` | Signal test completion |
| POST | `/esp32/heartbeat` | Report ESP32 online status |

### Request/Response Examples

#### POST /tests (Create Single Test Session)

**Request:**

```json
{
  "test_type": "tremor",
  "config": {
    "duration_seconds": 30,
    "sample_rate_hz": 100
  }
}
```

**Response (201 Created):**

```json
{
  "id": 1,
  "test_type": "tremor",
  "status": "pending",
  "created_at": "2026-02-09T10:00:00Z"
}
```
#### GET /tests/{id} (Get Test Status)

**Response (200 OK):**

```json
{
  "id": 1,
  "test_type": "tremor",
  "status": "completed",
  "ml_score": 0.72,
  "completed_at": "2026-02-06T10:30:00Z"
}
```
#### POST /tests/{id}/drawings (Upload Spiral Images)

**Request:** multipart/form-data with 2 images

**Response (200 OK):**

```json
{
  "message": "Images uploaded",
  "test_id": 2,
  "status": "in_progress"
}
```

#### SSE: GET /esp32/stream (ESP32 connects)

ESP32 devices establish a persistent SSE connection to `/esp32/stream` (authenticated with an API key). When the server creates a tremor test for a device, it sends a `test_started` event with the test ID and configuration.

**SSE event example:**

```
event: test_started
data: {"test_id": 1, "test_type": "tremor", "config": {"duration_seconds": 30, "sample_rate_hz": 100}}
```

#### POST /esp32/tests/{id}/data (ESP32 Upload)

**Request:**

```json
{
  "gyro_data": [[x, y, z, timestamp], ...],
  "sample_rate_hz": 100,
  "duration_seconds": 30
}
```

**Response (200 OK):**

```json
{
  "message": "Gyro data received",
  "test_id": 1,
  "status": "processing"
}
```

#### POST /esp32/tests/{id}/complete (ESP32 Complete)

**Request:**

```json
{
  "status": "completed"
}
```

**Response (200 OK):**

```json
{
  "message": "Test completed",
  "test_id": 1,
  "status": "completed"
}
```

---

## Storage Strategy

### File Storage

- **Local filesystem** for simplicity (can migrate to S3 later)
- Path structure: `uploads/{test_type}/{test_id}/{input_type}_{timestamp}.{ext}`

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

- [ ] Create models: TestSession, TestInput, ESP32Device
- [ ] Write Alembic migration
- [ ] Create indexes for efficient queries

### Phase 2: ESP32 Routes & SSE

- [ ] `/esp32/stream` - SSE endpoint for devices to receive `test_started` events
- [ ] `/esp32/tests/{id}/data` - Handle gyro JSON upload, create TestInput record
- [ ] `/esp32/tests/{id}/complete` - Update TestSession status
- [ ] `/esp32/heartbeat` - Heartbeat endpoint
- [ ] Add API key authentication middleware for ESP32 routes

### Phase 3: App Routes - Test Session Management

- [ ] `POST /tests` - Create a single TestSession for the requested test
- [ ] `GET /tests` - List user's tests with pagination and filters (e.g., ?status=completed)
- [ ] `GET /tests/{id}` - Get single test with ML results

### Phase 4: App Routes - File Uploads

- [ ] `POST /tests/{id}/drawings` - Handle 2 image uploads
- [ ] `POST /tests/{id}/voice` - Handle audio upload
- [ ] Create TestInput records with expires_at
- [ ] Validate file types and sizes

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

### Each TestSession Independent

- If user requests tremor + drawing + voice, three separate TestSession records are created
- Each tracks its own status, inputs, and results
- Allows partial completion and retry

### Demographics Snapshot

- Saved once per test session (shared across all test types in the session)
- Preserves historical accuracy for trend analysis

### ESP32 vs Mobile

- ESP32 handles tremor test (sensor data)
- Mobile handles drawing + voice tests (user input)
- Different authentication (API key vs JWT)
- Separate route namespaces for clarity

---

## Future Enhancements (Out of Scope)

1. **Real-time updates**: WebSocket for live test status
2. **S3 storage**: Migrate from local filesystem
3. **ML model integration**: Actual ML inference endpoints
4. **Questionnaire snapshot**: Store Q01-Q28 per test
5. **Test scheduling**: Queue tests for future execution
6. **Multi-user ESP32**: ESP32 serves multiple users

## Improvements

instead of exposing a http route for the esp to pool we introduce an SSE
to the esp32 to know when the test starts (i should send the selected tests json from the app)
