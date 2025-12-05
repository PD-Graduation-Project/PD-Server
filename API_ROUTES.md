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

## Test Routes (`/api/test`)

> **Note**: The tests blueprint is currently commented out in `app.py`, so these routes are not active. Uncomment the relevant lines in `app.py` to enable these routes.

### `POST /api/test/`
- **Description**: Create a new test record and return its ID
- **Headers**: `Authorization: Bearer <token>`
- **Response**:
  - Success (201): JSON object with message, test ID, and test data
  - Error (401): Invalid or missing token
- **Example Response**:
  ```json
  {
    "message": "Test started successfully",
    "test_id": 123,
    "test": { ... }
  }
  ```

### `POST /api/test/tremor`
- **Description**: Submit tremor test data (file upload)
- **Headers**: `Authorization: Bearer <token>`
- **Parameters**: `test_id` in query or form data
- **File Upload**: Requires tremor data file (txt, csv, or json)
- **Response**:
  - Success (200): JSON object with tremor score and ML results
  - Error (400): Missing test_id or invalid file
  - Error (401): Invalid or missing token
  - Error (404): Test not found

### `POST /api/test/drawing`
- **Description**: Submit drawing test data (file upload)
- **Headers**: `Authorization: Bearer <token>`
- **Parameters**: `test_id` in query or form data
- **File Upload**: Requires drawing file (png, jpg, or jpeg)
- **Response**:
  - Success (200): JSON object with drawing score and ML results
  - Error (400): Missing test_id or invalid file
  - Error (401): Invalid or missing token
  - Error (404): Test not found

### `POST /api/test/speech`
- **Description**: Submit speech test data (file upload)
- **Headers**: `Authorization: Bearer <token>`
- **Parameters**: `test_id` in query or form data
- **File Upload**: Requires audio file (mp3, wav, or m4a)
- **Response**:
  - Success (200): JSON object with speech score and ML results
  - Error (400): Missing test_id or invalid file
  - Error (401): Invalid or missing token
  - Error (404): Test not found

### `GET /api/test/<test_id>`
- **Description**: Get a specific test result by ID
- **Headers**: `Authorization: Bearer <token>`
- **Response**:
  - Success (200): JSON object with test data and progress
  - Error (401): Invalid or missing token
  - Error (404): Test not found

### `GET /api/test/current`
- **Description**: Get the user's current (incomplete) test
- **Headers**: `Authorization: Bearer <token>`
- **Response**:
  - Success (200): JSON object with current test data
  - Error (401): Invalid or missing token
  - Error (404): No current test found

### `GET /api/test/history`
- **Description**: Get all tests for the authenticated user with pagination
- **Headers**: `Authorization: Bearer <token>`
- **Query Parameters**:
  - `page`: Page number (default: 1)
  - `per_page`: Items per page (default: 10)
  - `completed`: Filter by completion status (true/false)
- **Response**: JSON object with tests list and pagination info

## Health Check Route

### `GET /health`
- **Description**: Check if the service is running
- **Response**:
  - Success (200): `{"status": "healthy", "service": "pd-server"}`

## Error Handlers
- **404**: Returns `{"error": "Not found"}`
- **500**: Returns `{"error": "Internal server error"}`

## Configuration
- JWT tokens expire after 7 days
- Maximum file upload size: 16MB
- Allowed file extensions:
  - Audio: mp3, wav, m4a
  - Images: png, jpg, jpeg, gif
  - Text: txt, csv, json

