Improvement Plan — PD-Server
============================

This document lists recommended improvements to make PD-Server production-ready and scalable. It includes concrete actions, which routes benefit from caching, why to add Nginx, and a description of shared services (Postgres, Redis, object storage, workers) and how they will be used.

Quick outcome
-------------

- Replace the Flask dev server with a production WSGI server (Gunicorn) behind Nginx.
- Add Redis for caching, rate-limiting, and as a broker for background tasks.
- Containerize the app (Docker → Docker Compose → Kubernetes) and move uploads to object storage (S3/MinIO).
- Offload heavy ML inference to background workers (Celery/RQ) with Redis broker.

Why do this?
------------

- Reliability: Gunicorn + Nginx handle connections and timeouts better than Flask's dev server.
- Performance: Nginx serves static files, compresses responses, and buffers slow clients.
- Cost and latency: Redis caching and ML worker offload reduce CPU usage and response times.
- Scalability: Containers + orchestration (k8s) enable horizontal scaling and automated rollouts.

Which routes should be cached
----------------------------

- `GET /api/tests` (list_tests)
  - Benefit: read-heavy, paginated, user-scoped listing. Cache per-user+query (include `user_id`, `page`, `per_page`, `test_type`, `status`).
  - Recommended TTL: 5–30s (short by default).

- `GET /api/tests/<id>` (get_test)
  - Benefit: repeated reads of the same test. Cache per test id + `user_id`.
  - Recommended TTL: 30s–5m. Invalidate on uploads/complete/update.

- `GET /api/user/` (get_user)
  - Benefit: user profile retrieval is cheap to cache; invalidate on PATCH/DELETE/RESET.
  - Recommended TTL: 10–60s.

- ML results / completed-test responses
  - Benefit: heavy CPU work. Cache ML outputs keyed by deterministic input hash (e.g., `ml:voice:<sha256(inputs)>`). TTL depends on whether outputs are deterministic — can be long or permanent.

- Static file GETs (uploads served as files)
  - Benefit: large files served directly by Nginx/CDN with long cache headers.

Cache key patterns (examples)
----------------------------

- `tests:list:{user_id}:page:{page}:per:{per_page}:type:{test_type}:status:{status}`
- `tests:item:{test_id}:user:{user_id}`
- `user:profile:{user_id}`
- `ml:predict:{model}:{input_sha256}`

Invalidation rules
------------------

- After `create_test` / `upload_*` / `complete_test`: invalidate `tests:list:{user_id}*` and `tests:item:{test_id}:user:{user_id}`.
- After `update_user` / `delete_user` / `reset_user_data`: invalidate `user:profile:{user_id}`.
- For ML cache: invalidate when inputs for a test change or user requests re-evaluation.

Why Nginx — concrete benefits for this repo
------------------------------------------

- TLS termination and certificate management (move TLS out of Flask dev server).
- Serve static/uploads directly (reduce load on Gunicorn workers).
- Buffering and slow-client protection so workers aren't blocked by slow uploads.
- Configurable timeouts and header forwarding (`X-Forwarded-For`, `X-Real-IP`) used by code (e.g., refresh token recording uses `request.remote_addr`).
- Rate-limiting (`limit_req`) and basic request filtering to protect endpoints (e.g., auth and ESP32 device endpoints).

Practical Nginx tuning notes
---------------------------

- `client_max_body_size` should match `Config.MAX_CONTENT_LENGTH` for uploads.
- `proxy_read_timeout` and `proxy_send_timeout` must be greater than Gunicorn worker timeouts for long ML tasks.
- `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;` so backend sees client IPs.
- Use `X-Accel-Redirect` / internal locations for secure file serving when returning protected files.

Shared services — what they are and how we use them
--------------------------------------------------

Postgres (primary)

- Role: primary transactional store for users, tests, refresh tokens, and results (`models/*.py`).
- Use cases: queries from endpoints like `list_tests`, `get_test`, `get_user` and writes from `create_test`, upload endpoints, `complete_test`.
- Scaling: single primary + read replicas for read-heavy workloads; use PgBouncer to pool connections from many app replicas.
- HA: managed DB (RDS/Cloud SQL) or Patroni; daily backups and WAL/PITR recommended.

Redis (cache, broker, ephemeral state)

- Role: in-memory caching for responses, rate-limiter counters, broker/result backend for Celery/RQ, and ephemeral coordination (pub/sub for ESP32 events).
- Use cases in this project:
  - Response cache: `list_tests`, `get_test`, `get_user`.
  - ML input caching: `ml:predict:{model}:{input_hash}` to avoid re-running inference.
  - Pub/sub or shared state for `utils/esp32_connection_manager.py` so many API replicas can notify the correct device.
  - Rate limiting for sensitive endpoints.
- Scaling: single instance for development; managed or clustered Redis for production.

Object Storage (S3 / MinIO)

- Role: store uploads (drawings, voice, tremor files) and serve them via CDN or Nginx.
- Why: removes local disk dependency (current `UPLOAD_FOLDER = "uploads"`) so app replicas are stateless.
- Use cases: `utils/storage.py` should be updated to put files in S3 and return signed URLs or public URLs behind CDN.
- Security: use pre-signed URLs for private content; use lifecycle rules to expire old uploads.

Background workers + Broker

- Role: run heavy ML inference (`ml/*.py`) asynchronously. Keep API latency low by queuing work and returning job ids.
- Stack: Celery (or RQ) + Redis (or RabbitMQ) as broker. Workers can be CPU/GPU optimized and scaled independently.
- Flow: upload endpoints enqueue a job → worker processes inputs and writes `ml_score`/result to DB or object storage → API can poll job status or receive push notification.

Load balancer / Ingress

- Role: global traffic management, TLS, rate-limiting, and ingress routing (Nginx or a cloud LB + ingress controller on k8s).

Observability & ops
-------------------

- Health checks: `GET /health` already exists; add readiness/liveness probes.
- Metrics: expose Prometheus metrics or use an exporter; instrument request duration, queue lengths, ML latencies.
- Logging: structured JSON logs to stdout for aggregator (ELK, Loki).
- Error tracking: integrate Sentry for exceptions and traces.

Security & secrets
------------------

- Keep secrets out of repo: use Vault / cloud secrets manager / k8s Secrets.
- Always terminate TLS at Nginx or a managed LB.
- Set secure cookie flags if cookies are used; ensure JWT secrets are rotated and stored securely.

Staged actionable plan (recommended order)
-----------------------------------------

1. Quick production baseline (low risk)
   - Switch to Gunicorn (replace running `app.run(...)` locally with `gunicorn "app:create_app()" -b 0.0.0.0:5000 --workers 3`).
   - Add minimal Nginx config to proxy to Gunicorn and serve `uploads/` locally for dev.
   - Add `client_max_body_size` and header forwarding.

2. Add Redis + caching
   - Deploy Redis (local or managed).
   - Implement a small Redis-backed cache decorator and invalidate cache in: `create_test`, upload endpoints, `complete_test`, `update_user`.
   - Add a simple rate-limiter middleware using Redis.

3. Move uploads to object storage (S3/MinIO)
   - Update `utils/storage.py` and `config.py` to use S3 credentials.
   - Serve files via CDN or Nginx with cache headers.

4. Background workers for ML
   - Add Celery + Redis (broker & result backend) or RQ.
   - Convert `complete_test` ML calls to enqueue jobs; return job id or run synchronously when configured.
   - Persist ML results to DB and invalidate caches as needed.

5. Containerize and orchestrate
   - Add `Dockerfile`, `.dockerignore`, and `docker-compose.yml` for local dev (web, postgres, redis, nginx, minio).
   - Prepare k8s manifests (Deployment, Service, HPA, Ingress, StatefulSet for Postgres if needed).

6. Observability, security, and hardening
   - Add metrics and logging, Sentry, automated backups, secrets management, CI/CD with rolling deploys.

Example commands & snippets
-------------------------

- Run with Gunicorn (local test):

```
gunicorn "app:create_app()" -b 0.0.0.0:5000 --workers 3 --worker-class gthread
```

- Example cache key for `list_tests`:

```
tests:list:42:page:1:per:20:type:drawing:status:completed
```

Next steps
---------------------------------

1) Create a production-ready `Dockerfile` + `gunicorn` command and a minimal `nginx.conf` tuned for uploads (recommended first).
2) Implement a Redis caching decorator and add cache invalidation calls in the appropriate routes.
3) Add Docker Compose (web + postgres + redis + minio + nginx) for local testing.

Pick a number (1, 2, or 3) and I will start implementing it.

References in repo
------------------

- App entry: `app.py`
- Upload handling & ML call sites: `routes/upload_routes.py`
- Test listing & detail: `routes/test_routes.py`
- User profile endpoints: `routes/user_routes.py`
- Storage helper: `utils/storage.py`
- ESP32 connection manager: `utils/esp32_connection_manager.py`
