#!/bin/bash

# === Auto-start Flask + Ngrok ===
# Make sure your Python venv is active if you’re using one.

# Kill any existing Flask/Ngrok instances
pkill -f "flask" 2>/dev/null
pkill -f "ngrok" 2>/dev/null

# Start Flask in the background
echo "🚀 Starting Flask server..."
python3 app.py &
FLASK_PID=$!

# Wait a few seconds for Flask to start
sleep 4

# Start Ngrok tunnel on port 5002
echo "🌐 Starting Ngrok tunnel..."
ngrok http 5002 > /dev/null &
NGROK_PID=$!

# Wait a bit for Ngrok to initialize
sleep 6

# Fetch Ngrok public URL (v3-compatible)
NGROK_URL=$(curl -s http://127.0.0.1:4040/api/tunnels | grep -oE 'https://[^"]+ngrok-free.dev' | head -n1)

if [ -n "$NGROK_URL" ]; then
  echo ""
  echo "✅ Your chat app is LIVE!"
  echo "🌐 Public URL → $NGROK_URL"
  echo "📡 Share this with your friends to let them join!"
else
  echo "❌ Could not fetch Ngrok URL. Try waiting a few more seconds and re-run the script."
fi

# Keep both running until you stop manually
wait $FLASK_PID $NGROK_PID
