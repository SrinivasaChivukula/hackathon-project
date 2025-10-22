#!/bin/bash

# Vision Assistant Full-Stack Startup Script

echo "🚀 Starting Vision Assistant Full-Stack System..."
echo ""

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found. Please run installation first."
    exit 1
fi

# Check if Pi stream is accessible
echo "📡 Checking Pi stream connection..."
if curl -s --head --request GET http://100.101.51.31:5000/video_feed | grep "200 OK" > /dev/null; then 
    echo "✅ Pi stream is accessible"
else
    echo "⚠️  Warning: Pi stream may not be accessible"
    echo "   Make sure the Pi is running at http://100.101.51.31:5000/video_feed"
fi

echo ""
echo "Starting system components:"
echo "  - YOLO Object Detection"
echo "  - Flask API Server (port 5001)"
echo "  - SQLite Database Logger"
echo "  - Audio TTS & Voice Commands"
echo ""
echo "Dashboard will be available at: http://localhost:5001"
echo ""
echo "Controls:"
echo "  q - Quit"
echo "  c - Voice command mode"
echo "  s - Manual scene description"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Activate virtual environment and run
source .venv/bin/activate
python run.py

