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

## Development Priority

1. Authentication system
2. Drawing and voice test endpoints (synchronous flow)
3. Database schema and storage
4. History retrieval
5. Tremor asynchronous flow (final phase)
