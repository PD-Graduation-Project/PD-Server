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
