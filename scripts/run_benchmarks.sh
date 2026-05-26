#!/usr/bin/env bash
# ==============================================================================
# PD Server — Master Benchmark Runner
#
# Runs all benchmarks under production-matched resource limits (2 CPUs / 12 GB RAM).
# Results are saved to scripts/bench_results/ for thesis/report consumption.
#
# Usage:
#   bash scripts/run_benchmarks.sh              # Full suite
#   bash scripts/run_benchmarks.sh --ml-only    # ML inference only
#   bash scripts/run_benchmarks.sh --api-only   # API load test only
#
# Prerequisites:
#   - Docker + Docker Compose v2
#   - k6 (https://k6.io/docs/getting-started/installation/)
#     Linux:  sudo snap install k6
#     macOS:  brew install k6
#     Docker: docker pull grafana/k6
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
RESULTS_DIR="$SCRIPT_DIR/bench_results"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Resource limits matching production (Oracle VM.Standard.A1.Flex: 2 OCPUs, 12 GB)
BENCH_CPUS="${BENCH_CPUS:-2}"
BENCH_MEM="${BENCH_MEM:-12G}"
COMPOSE_DIR="$PROJECT_DIR/docker"

mkdir -p "$RESULTS_DIR"

# ── Helpers ──────────────────────────────────────────────────────────────────
info()  { echo -e "\033[36m[INFO]\033[0m $*"; }
ok()    { echo -e "\033[32m[OK]\033[0m   $*"; }
fail()  { echo -e "\033[31m[FAIL]\033[0m $*"; }
header() { echo -e "\n\033[1;33m$*\033[0m\n"; }

cleanup() {
    info "Stopping bench stack..."
    cd "$COMPOSE_DIR" 2>/dev/null || true
    docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.bench.yml down -v 2>/dev/null || true
    docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.bench.yml rm -f 2>/dev/null || true
}
trap cleanup EXIT

# ── Parse args ───────────────────────────────────────────────────────────────
RUN_ML=true
RUN_API=true
RUN_ESP32=true

for arg in "$@"; do
    case "$arg" in
        --ml-only) RUN_API=false; RUN_ESP32=false ;;
        --api-only) RUN_ML=false; RUN_ESP32=false ;;
        --esp32-only) RUN_ML=false; RUN_API=false ;;
        *) ;;
    esac
done

# ══════════════════════════════════════════════════════════════════════════════
# 0. Install k6 if missing
# ══════════════════════════════════════════════════════════════════════════════
if $RUN_API; then
    if ! command -v k6 &>/dev/null; then
        info "k6 not found. Installing via Docker..."
        alias k6='docker run --rm -i -v "$PWD":/scripts -w /scripts grafana/k6 run'
        # If docker isn't an option, suggest install
        if ! docker run --rm grafana/k6 --help &>/dev/null; then
            fail "Cannot run k6. Install it manually:"
            fail "  Linux: sudo snap install k6"
            fail "  macOS: brew install k6"
            fail "  Or run API benchmarks separately after installing k6"
            RUN_API=false
        fi
    else
        info "k6 found: $(k6 version 2>/dev/null || echo 'ok')"
    fi
fi

# ══════════════════════════════════════════════════════════════════════════════
# 1. ML Inference Benchmarks (standalone, runs on host)
# ══════════════════════════════════════════════════════════════════════════════
if $RUN_ML; then
    header "═══ 1. ML Inference Benchmarks ═══"

    cd "$PROJECT_DIR/ml/_FINAL_SCRIPTS"

    # Check if PyTorch is available
    if python3 -c "import torch; print(f'PyTorch {torch.__version__}')" 2>/dev/null; then
        info "Running ML inference benchmarks on host..." | true
        python3 bench_inference.py --runs 5 --output "$RESULTS_DIR/bench_ml_$TIMESTAMP.json"
        ok "ML benchmark complete"
    else
        info "PyTorch not on host. Building worker image in project root (needs context)..."

        cd "$PROJECT_DIR"
        ML_IMAGE="pd-server-ml-bench:latest"

        docker build -t "$ML_IMAGE" -f docker/Dockerfile.worker --target dev .
        ok "Image built: $ML_IMAGE"

        info "Running ML benchmarks with --cpus=$BENCH_CPUS --memory=$BENCH_MEM..."
        docker run --rm \
            --cpus="$BENCH_CPUS" --memory="$BENCH_MEM" \
            --user root \
            -v "$PROJECT_DIR/scripts/bench_results:/app/scripts/bench_results" \
            "$ML_IMAGE" bash -c "
                cd /app/ml/_FINAL_SCRIPTS && \
                pip install pycatch22 2>/dev/null; \
                python bench_inference.py --runs 5 --output /app/scripts/bench_results/bench_ml_$TIMESTAMP.json
            "
        ok "ML benchmark complete (Docker, ${BENCH_CPUS} CPUs / ${BENCH_MEM})"
    fi
fi

# ══════════════════════════════════════════════════════════════════════════════
# 2. Start the Stack (with resource limits)
# ══════════════════════════════════════════════════════════════════════════════
header "═══ Starting Docker stack with limits: ${BENCH_CPUS} CPUs / ${BENCH_MEM} RAM ═══"

cd "$COMPOSE_DIR"
export BENCH_CPUS BENCH_MEM

# Build app and worker images
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.bench.yml build app worker
ok "Images built"

# Start infrastructure first
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.bench.yml up -d \
    postgres redis minio
info "Waiting for infrastructure (postgres, redis, minio)..."
sleep 5
docker compose -f docker-compose.yml -f docker-compose.dev.yml ps

# Start app and worker
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.bench.yml up -d app worker

# Apply runtime resource limits (deploy.resources only works in swarm mode)
info "Applying resource limits to running containers..."
for svc in app worker; do
    cid=$(docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.bench.yml ps -q "$svc")
    if [ -n "$cid" ]; then
        docker update --cpus="$BENCH_CPUS" --memory="$BENCH_MEM" "$cid" 2>/dev/null || true
    fi
done
for svc in postgres redis minio; do
    cid=$(docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.bench.yml ps -q "$svc")
    if [ -n "$cid" ]; then
        docker update --cpus="0.5" --memory="512M" "$cid" 2>/dev/null || true
    fi
done
ok "Resource limits applied"

info "Waiting for stack to be ready (DB + Redis + storage)..."
SERVER_URL="http://localhost:5000"
timeout 120 bash -c '
    until curl -sf http://localhost:5000/ready > /dev/null 2>&1; do
        echo "  Waiting for app to be ready..."; sleep 5
    done
'
ok "Stack is ready at $SERVER_URL (DB, Redis, storage verified)"

# ══════════════════════════════════════════════════════════════════════════════
# 3. API Load Tests (k6)
# ══════════════════════════════════════════════════════════════════════════════
if $RUN_API; then
    header "═══ 2. API Load Tests (k6) ═══"

    cd "$PROJECT_DIR"

    for vus in 5 20 50; do
        info "Running k6 with ${vus} VUs..."
        k6 run -e BASE_URL="$SERVER_URL" -e VUS="$vus" \
            --summary-export "$RESULTS_DIR/bench_api_${vus}vu_$TIMESTAMP.json" \
            scripts/bench_api.js
        ok "k6 ${vus} VU test complete"
    done
fi

# ══════════════════════════════════════════════════════════════════════════════
# 4. ESP32 Concurrency Tests
# ══════════════════════════════════════════════════════════════════════════════
if $RUN_ESP32; then
    header "═══ 3. ESP32 Concurrency Tests ═══"

    cd "$PROJECT_DIR"

    for devices in 10 25 50 100; do
        info "Testing ${devices} concurrent ESP32 devices..."
        python3 scripts/bench_esp32_concurrency.py \
            --devices "$devices" \
            --server "$SERVER_URL" \
            --output "$RESULTS_DIR/bench_esp32_${devices}dev_$TIMESTAMP.json"
        ok "${devices} device test complete"
    done
fi

# ══════════════════════════════════════════════════════════════════════════════
# 5. Collect Resource Usage Snapshot
# ══════════════════════════════════════════════════════════════════════════════
header "═══ 4. Resource Usage Snapshot ═══"

docker stats --no-stream --format \
    "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}" \
    > "$RESULTS_DIR/bench_resources_$TIMESTAMP.txt"

cat "$RESULTS_DIR/bench_resources_$TIMESTAMP.txt"

# ══════════════════════════════════════════════════════════════════════════════
# DONE
# ══════════════════════════════════════════════════════════════════════════════
header "═══ ALL BENCHMARKS COMPLETE ═══"
echo "  Results: $RESULTS_DIR/"
ls -lh "$RESULTS_DIR/"

# Legacy "docker stats" format for final output
docker stats --no-stream 2>/dev/null || true
