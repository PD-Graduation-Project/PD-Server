#!/bin/sh
set -e

mkdir -p /home/workeruser/.cache/gdown

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

exec rq worker ml
