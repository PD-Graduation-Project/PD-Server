# PD-Server Documentation

## Overview

A server application for Parkinson's Disease detection that processes tremor,
spiral drawing, and voice data through ML models
and manages user authentication and test history.

## Core Functionality

### 1. Authentication System

- User registration and login
- Session management
- Authorization for API endpoints

### 2. ML Model Processing

Processes three types of diagnostic tests:

- **Tremor Analysis**: Processes sensor data files
- **Drawing Analysis**: Evaluates motor control through drawing patterns
- **Voice Analysis**: Analyzes speech characteristics

### 3. Data Persistence

- Store test results in database
- Maintain user test history
- Link results to user accounts

### 4. Tremor Flow (Deferred Implementation)

Special handling for tremor data collection:

- Tremor module operates independently and uploads collected data
- Server processes files asynchronously
- Results pushed to mobile app (mechanism TBD)
- Requires bidirectional communication strategy

## Architecture Considerations

### Test Invocation Models

Implement a unified completion endpoint:

- Tests don't return immediate results
- Mobile app polls `GET /api/test/:id` after test completion
- Consistent pattern across all test types

## API Specification

### Authentication

```
POST /api/auth/register
POST /api/auth/login
```

### Test Submission

```
POST /api/test/tremor
Content-Type: multipart/form-data
Body: text files containing sensor data

POST /api/test/drawing
Content-Type: multipart/form-data
Body: image files

POST /api/test/speech
Content-Type: multipart/form-data
Body: audio files (mp3)
```

### Data Retrieval

```
GET /api/history
Returns: List of all tests for authenticated user

GET /api/test/:id
Returns: Detailed results for specific test
```

## App Sequence Diagram

```mermaid
sequenceDiagram
    participant Client as Client/Frontend
    participant App as Flask App
    participant Auth as Auth Routes
    participant Tests as Tests Routes
    participant DB as Database
    participant ML as ML Models
    participant Files as File System

    Note over Client,ML: 1. User Registration/Login Flow
    Client->>+Auth: POST /api/auth/register
    Auth->>+DB: Create user record
    DB-->>-Auth: Return user object
    Auth->>-Client: JWT Token + User Info

    Client->>+Auth: POST /api/auth/login
    Auth->>+DB: Validate credentials
    DB-->>-Auth: User object
    Auth->>-Client: JWT Token + User Info

    Note over Client,ML: 2. Starting a Test
    Client->>+Tests: POST /api/test/ (with JWT)
    Tests->>+DB: Create new test record
    DB-->>-Tests: Test object
    Tests->>-Client: Test ID + Test Object

    Note over Client,ML: 3. Submitting Tremor Test
    Client->>+Tests: POST /api/test/tremor (with JWT + file)
    Tests->>+Files: Save uploaded file
    Files-->>-Tests: File path
    Tests->>+ML: Process tremor file
    ML-->>-Tests: Analysis results
    Tests->>+DB: Update tremor_score
    DB-->>-Tests: Updated test object
    Tests->>-Client: Success response + ML results

    Note over Client,ML: 4. Submitting Drawing Test
    Client->>+Tests: POST /api/test/drawing (with JWT + file)
    Tests->>+Files: Save uploaded file
    Files-->>-Tests: File path
    Tests->>+ML: Process drawing file
    ML-->>-Tests: Analysis results
    Tests->>+DB: Update drawing_score
    DB-->>-Tests: Updated test object
    Tests->>-Client: Success response + ML results

    Note over Client,ML: 5. Submitting Speech Test
    Client->>+Tests: POST /api/test/speech (with JWT + file)
    Tests->>+Files: Save uploaded file
    Files-->>-Tests: File path
    Tests->>+ML: Process speech file
    ML-->>-Tests: Analysis results
    Tests->>+DB: Update speech_score
    DB-->>-Tests: Updated test object
    Tests->>-Client: Success response + ML results

    Note over Client,ML: 6. Retrieving Test Results
    Client->>+Tests: GET /api/test/{test_id} (with JWT)
    Tests->>+DB: Retrieve test record
    DB-->>-Tests: Test object
    Tests->>-Client: Test result with scores and progress
```

## Utility Scripts

Scripts are located in the `scripts/` directory.

### Clear Test Data

Delete all test data (TestGroups, TestSessions, TestInputs):

```bash
# Clear database only
python scripts/clear_test_data.py

# Clear database AND uploads folder
python scripts/clear_test_data.py --all
```

**Docker:**

```bash
docker compose exec app python scripts/clear_test_data.py
docker compose exec app python scripts/clear_test_data.py --all
```

### Cleanup Expired Inputs

Delete expired test inputs and their associated files:

```bash
# Preview what would be deleted (dry run)
python scripts/cleanup_expired_inputs.py

# Actually delete expired inputs
python scripts/cleanup_expired_inputs.py --run
```

**Docker:**

```bash
docker compose exec app python scripts/cleanup_expired_inputs.py
docker compose exec app python scripts/cleanup_expired_inputs.py --run
```

### Generate Factory Key

Generate factory API keys for ESP32 device provisioning:

```bash
python scripts/generate_factory_key.py <mac_address>

# Example
python scripts/generate_factory_key.py AA:BB:CC:DD:EE:FF
```

**Docker:**

```bash
docker compose exec app python scripts/generate_factory_key.py AA:BB:CC:DD:EE:FF
```
