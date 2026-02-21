#!/bin/bash
# Start Flask + Cloudflare Tunnel

python app.py &
FLASK_PID=$!
sleep 3
cloudflared tunnel --url http://localhost:5000
kill $FLASK_PID 2>/dev/null
