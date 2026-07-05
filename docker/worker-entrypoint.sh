#!/bin/sh
set -e

mkdir -p /home/workeruser/.cache/gdown /app/logs

cd /app/ml/_FINAL_SCRIPTS

if [ -z "$(ls -A weights/*.pth 2>/dev/null)" ]; then
    echo 'Downloading model weights...'
    gdown "$GDRIVE_WEIGHTS_ID" --folder -O weights || { echo 'gdown failed'; exit 1; }
    echo 'Download complete:'
    ls -la weights/
else
    echo 'Weights already present, skipping download.'
    ls -la weights/
fi

cd /app

echo 'Starting Prometheus metrics endpoint on port 6001...'
python -m ml.worker_metrics &
METRICS_PID=$!
echo "Metrics server PID: $METRICS_PID"

echo 'Starting RQ worker...'
exec rq worker ml
