# ── Stage 1: Build ────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libev-dev \
    && rm -rf /var/lib/apt/lists/* \
    && adduser --disabled-password --gecos "" appuser

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# ── Stage 2: Production ───────────────────────────────────────────────────────
FROM python:3.11-slim AS prod
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/home/appuser/.local/bin:$PATH

# Only runtime libs — no gcc, no libpq-dev
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libev4 \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

RUN adduser --disabled-password --gecos "" appuser

RUN mkdir -p /app/logs /app/uploads && chown -R appuser:appuser /app

COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local
COPY --chown=appuser:appuser . .
COPY --chown=appuser:appuser docker/entrypoint.py /app/docker/entrypoint.py

USER appuser
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')"

CMD ["gunicorn", "--workers", "4", "--worker-class", "gevent", \
     "--bind", "0.0.0.0:5000", "--preload", "app:create_app()"]
