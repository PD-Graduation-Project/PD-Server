# PD-Server TODO List

## Phase 1: Project Setup

- [ ] Initialize project repository
- [ ] Set up project structure (folders: `/api`, `/models`, `/utils`, `/db`)
- [x] Choose and configure web framework (Express.js/Flask/FastAPI)
- [ ] Set up environment variables (.env file)
- [ ] Configure CORS for mobile app communication
- [ ] Set up logging system

## Phase 2: Database

- [ ] Choose database (PostgreSQL/MongoDB/SQLite)
- [ ] Design database schema:
  - [ ] Users table (id, email, password_hash, created_at)
  - [ ] Tests table (id, user_id, type, status, created_at)
  - [ ] Results table (id, test_id, result_data, confidence_score)
- [ ] Set up database connection
- [ ] Create database migrations
- [ ] Write database helper functions (CRUD operations)

## Phase 3: Authentication System

- [ ] Install authentication dependencies (JWT/bcrypt)
- [ ] Create User model
- [ ] Implement `POST /api/auth/register`:
  - [ ] Validate email format
  - [ ] Hash password
  - [ ] Store user in database
  - [ ] Return JWT token
- [ ] Implement `POST /api/auth/login`:
  - [ ] Verify credentials
  - [ ] Generate JWT token
  - [ ] Return token and user info
- [ ] Create authentication middleware
- [ ] Add token verification to protected routes
- [ ] Test authentication flow

## Phase 4: File Upload Infrastructure

- [ ] Install file upload middleware (multer/similar)
- [ ] Configure file storage (local/cloud)
- [ ] Set file size limits:
  - [ ] Tremor files: TXT (max size TBD)
  - [ ] Drawing files: Images (max 10MB)
  - [ ] Speech files: MP3 (max 50MB)
- [ ] Add file type validation
- [ ] Create file cleanup utility (delete temp files)

## Phase 5: Drawing Test Endpoint

- [ ] Set up ML model for drawing analysis
- [ ] Create model loading function
- [ ] Implement `POST /api/test/drawing`:
  - [ ] Accept image upload
  - [ ] Validate file type and size
  - [ ] Save test record to database (status: processing)
  - [ ] Run drawing model
  - [ ] Store results in database
  - [ ] Return results to client
- [ ] Add error handling for model failures
- [ ] Test with sample images

## Phase 6: Voice Test Endpoint

- [ ] Set up ML model for voice analysis
- [ ] Create model loading function
- [ ] Implement `POST /api/test/speech`:
  - [ ] Accept audio file upload
  - [ ] Validate file type and size
  - [ ] Save test record to database (status: processing)
  - [ ] Run voice model
  - [ ] Store results in database
  - [ ] Return results to client
- [ ] Add error handling for model failures
- [ ] Test with sample audio files

## Phase 7: History & Results Retrieval

- [ ] Implement `GET /api/history`:
  - [ ] Get authenticated user ID
  - [ ] Query all tests for user
  - [ ] Return paginated list (consider pagination)
  - [ ] Include test type, date, status, summary
- [ ] Implement `GET /api/test/:id`:
  - [ ] Verify test belongs to authenticated user
  - [ ] Return detailed test results
  - [ ] Include confidence scores, raw data
- [ ] Add query filters (by date, by type)
- [ ] Test retrieval endpoints

## Phase 8: Tremor Asynchronous Flow

- [ ] Design notification strategy:
  - [ ] Research: WebSockets vs Push Notifications vs Polling
  - [ ] Choose implementation approach
- [ ] Set up ML model for tremor analysis
- [ ] Implement `POST /api/test/tremor`:
  - [ ] Accept multiple text files
  - [ ] Validate files
  - [ ] Save test record (status: processing)
  - [ ] Process files asynchronously (background job/queue)
  - [ ] Return test ID immediately
- [ ] Implement background job processor:
  - [ ] Run tremor model
  - [ ] Update test status in database
  - [ ] Trigger notification to mobile app
- [ ] Implement notification system:
  - [ ] Set up WebSocket/Push notification service
  - [ ] Send result notification to mobile app
- [ ] Test end-to-end tremor flow

## Phase 9: Testing & Validation

- [ ] Write unit tests for authentication
- [ ] Write unit tests for each test endpoint
- [ ] Write integration tests for complete flows
- [ ] Test file upload edge cases
- [ ] Test error scenarios (invalid files, model failures)
- [ ] Load test API endpoints
- [ ] Security audit (SQL injection, file upload vulnerabilities)

## Phase 10: Documentation & Deployment

- [ ] Write API documentation (Swagger/OpenAPI)
- [ ] Document environment variables
- [ ] Create setup instructions (README)
- [ ] Document model requirements and versions
- [ ] Set up CI/CD pipeline
- [ ] Choose deployment platform (AWS/GCP/Heroku)
- [ ] Configure production environment
- [ ] Set up monitoring and logging
- [ ] Deploy to production
- [ ] Test production deployment

## Optional Enhancements

- [ ] Add rate limiting to prevent abuse
- [ ] Implement result caching
- [ ] Add data export feature (PDF reports)
- [ ] Implement admin dashboard
- [ ] Add email notifications for test completion
- [ ] Set up automated model retraining pipeline
- [ ] Add analytics and usage tracking
