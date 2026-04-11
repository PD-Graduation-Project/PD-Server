# PD-Server Docker Setup

This directory contains Docker configuration for the PD-Server application with all dependencies.

## Services

| Service | Description | Port |
|---------|-------------|------|
| nginx | Reverse proxy with SSL | 80, 443 |
| app | Flask API with gunicorn | 5000 (internal) |
| worker | RQ ML inference worker | - |
| postgres | PostgreSQL database | 5432 (internal) |
| redis | Redis queue | 6379 (internal) |
| mock_esp32 | Mock ESP32 device for testing | - (test only) |
| worker | Mock ML worker (no PyTorch) | - (test only) |

## Quick Start

1. **Copy environment file:**
   ```bash
   cp .env.example .env.docker
   ```

2. **Build and run:**
   ```bash
   cd docker
   docker-compose up --build
   ```

3. **Done!** Migrations run automatically on first startup.

Note: watchtower runs only in the `prod` compose profile.

## Production Auto-Deploy (GHCR + Watchtower)

Production uses pre-built images from GHCR instead of building on the server.

### How it works

1. Push to `main` triggers `.github/workflows/deploy.yml`
2. GitHub Actions builds and pushes:
   - `ghcr.io/<owner>/pd-server-app:latest`
   - `ghcr.io/<owner>/pd-server-worker:latest`
   - `ghcr.io/<owner>/pd-server-nginx:latest`
3. Deploy job SSHes into the server, pulls new images, and recreates services
4. Watchtower keeps polling GHCR and auto-restarts labeled services when newer images are published

### Required GitHub secrets

- `ORACLE_HOST`: Oracle VM host/IP
- `SSH_KEY`: private key for `ubuntu` user on server
- `GHCR_USERNAME`: GitHub username with read access to GHCR packages
- `GHCR_TOKEN`: GitHub token with at least `read:packages`

### Server prerequisites

Run once on the server as `ubuntu` user:

```bash
docker login ghcr.io
```

This creates `/home/ubuntu/.docker/config.json`, which is mounted into the `watchtower` container so it can authenticate when checking GHCR.

The deploy workflow starts compose with `--profile prod`, so watchtower is included only on server deployments.

### Notes

- `app`, `worker`, and `nginx` are labeled for watchtower updates
- Database and stateful services (`postgres`, `redis`, `minio`) are intentionally excluded from watchtower
- Local development still works with local builds/images by default

## Finding Your Server URL

### For Local Testing (Same Machine)

```bash
http://localhost:80
https://localhost:443   # Will show cert warning (self-signed)
```

### For Mobile App (Same Network)

Find your machine's local IP:

```bash
ip addr show | grep "inet " | awk '{print $2}' | cut -d/ -f1
```

Or on macOS:
```bash
ifconfig | grep "inet " | grep -v 127.0.0.1
```

Or on Windows (Command Prompt):
```cmd
ipconfig
```

Look for IPv4 Address (e.g., `192.168.1.100`)

### Your Team's URL

```
http://<your-ip>:80
```

Example: `http://192.168.0.106:80`

---

## Accessing the App

| URL | Description |
|-----|-------------|
| `http://localhost/health` | Health check |
| `http://localhost:80` | Main API (HTTP) |
| `https://localhost:443` | Main API (HTTPS, self-signed cert) |

---

## Common Commands

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# View logs for specific service
docker-compose logs -f app
docker-compose logs -f worker

# Stop all services (data is preserved)
docker-compose down

# Rebuild and start
docker-compose down
docker-compose up --build

# Restart a specific service
docker-compose restart app
```

---

## Database Migrations

Migrations run **automatically** on container startup. If you need to run manually:

```bash
docker-compose exec app flask db upgrade

# Create new migration
docker-compose exec app flask db migrate -m "your message"
```

---

## Troubleshooting

## Log Retention and Disk Safety

- App daily logs are stored in the `app_logs` volume and auto-pruned by day.
- Configure retention with `LOG_FILE_RETENTION_DAYS` (default `7`) in `docker/.env.docker`.
- Health/readiness/metrics request logs are skipped by default via `LOG_SILENT_PATHS`.
- Nginx access logging is reduced to 4xx/5xx events to control storage growth.
- Nginx access logs are ingested by Promtail, but high-cardinality labels are avoided to keep Loki stable.
- Fail2ban log (`/var/log/fail2ban.log`) is ingested into Loki as `service=fail2ban` for security visibility.
- Docker container stdout/stderr logs are capped with `max-size=10m` and `max-file=3`.
- Loki retention is set in `docker/loki-config.yml` (`retention_period: 168h`, i.e. 7 days).

### Database not connecting?
Make sure PostgreSQL container is healthy:
```bash
docker-compose ps
```

### View database:
```bash
docker-compose exec postgres psql -U pduser -d pdserver
```

### View Redis:
```bash
docker-compose exec redis redis-cli
```

---

## Volumes

- `postgres_data` - PostgreSQL data (persists between restarts)
- `redis_data` - Redis data (persists between restarts)
- `uploads` - Shared uploads folder (test files, images, audio)

**Note:** Using `docker-compose down -v` or `docker-compose down --volumes` will DELETE all data!

---

## SSL Certificates

The nginx container generates a self-signed certificate on build (CN=localhost).

For production, replace:
- `/etc/nginx/ssl/server.crt`
- `/etc/nginx/ssl/server.key`

With proper certificates from Let's Encrypt or your CA.

---

## ML Model Weights

The ML worker container expects model weights in `ml/_FINAL_SCRIPTS/weights/`.

If weights are not in the container, either:
1. Mount the weights folder in docker-compose.yml
2. Download during build (add gdown to Dockerfile.worker)

---

## Scaling

To run multiple workers:
```bash
docker-compose up -d --scale worker=2
```

---

## Mock ESP32 Testing

The `mock_esp32` service simulates an ESP32 device for integration testing. It:

1. Registers with factory key
2. Sends heartbeats
3. Connects to SSE stream
4. Automatically uploads tremor data and completes tests on `test_started` events

### Running Tests with Mock ESP32

```bash
# Run test stack with mock ESP32
docker-compose -f docker-compose.test.yml up --build

# View mock ESP32 logs
docker-compose -f docker-compose.test.yml logs -f mock_esp32
```

### Mock ESP32 Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `MOCK_DEVICE_ID` | `ESP32-MOCK01` | Device ID (format: ESP32-XXXXXX) |
| `MOCK_SERVER_URL` | `http://app:5000` | Server URL |
| `MOCK_FACTORY_SECRET` | `test_factory_secret_123` | Factory secret for HMAC |
| `MOCK_HEARTBEAT_INTERVAL` | `30` | Heartbeat interval (seconds) |
| `MOCK_TEST_MODE` | `full` | Mode: `register`, `heartbeat`, `stream`, `full` |
| `MOCK_DATA_POINTS` | `100` | IMU data points per subtest |

---

## Global Rate Limiting

All routes are rate-limited globally before route matching, including unknown paths that return `404`.

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RATE_LIMIT_ENABLED` | `true` | Enable/disable global rate limiter |
| `RATE_LIMIT_REQUESTS` | `120` | Max requests per IP in the window |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Rate-limit window size in seconds |
| `RATE_LIMIT_EXEMPT_PATHS` | `/health,/ready,/metrics` | Comma-separated paths excluded from limiting |

When a request is limited, API returns `429` and includes the detected client IP in the response body.

### Test Modes

| Mode | Description |
|------|-------------|
| `register` | Register device only, then exit |
| `heartbeat` | Register + send periodic heartbeats |
| `stream` | Register + connect to SSE stream |
| `full` | Register + heartbeat + stream (default) |

### Manual Testing

```bash
# Run mock ESP32 with custom settings
docker run --rm -it \
  -e MOCK_DEVICE_ID=ESP32-TEST01 \
  -e MOCK_SERVER_URL=http://host.docker.internal:5000 \
  -e MOCK_FACTORY_SECRET=your_secret \
  --network host \
  $(docker build -q -f Dockerfile.mock_esp32 .) \
  --mode full
```
