#!/bin/bash
# Start Flask + ngrok Tunnel

# Start Flask in background
python app.py &
FLASK_PID=$!
sleep 3

# Start ngrok tunnel
ngrok http 6969

# Cleanup when ngrok exits
kill $FLASK_PID 2>/dev/null
