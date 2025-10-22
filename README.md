# Vision Assist IoT System

AI-powered vision assistance for visually impaired patients with fall detection and emergency alerts.

## Hardware

- Raspberry Pi with Sense HAT and Pi Camera
- Laptop/PC for inference

## Features

- Real-time object detection with audio alerts
- Fall detection (accelerometer/gyroscope)
- Emergency SOS button (joystick middle)
- Assistance requests: General Help, Bathroom, Food/Water, Medication
- Voice alerts for all emergencies and requests
- Environmental monitoring (temp, humidity, pressure)
- Live dashboard with video feed
- Voice commands and scene summarization

## Setup

### Raspberry Pi

```bash
# Install dependencies
sudo apt-get update
sudo apt-get install -y python3-picamera2 python3-sense-hat

# Run the Pi script
python3 abcd.py
```

### Laptop/PC

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
sudo apt-get install portaudio19-dev python3-dev
pip install -r requirements.txt

# Update Pi IP in run.py and backend_api.py
# Change http://100.101.51.31:5000 to your Pi's IP

# Run the vision assistant
python run.py
```

## Configuration

Edit these files to match your Pi's IP address:

1. `run.py` - Line 45 and lines 370, 414
2. `backend_api.py` - Line 28

Replace `100.101.51.31` with your Pi's IP address.

## Usage

### Joystick Controls

- **Middle**: Emergency SOS
- **Up**: General Help
- **Down**: Bathroom
- **Left**: Food/Water  
- **Right**: Medication

### Voice Commands

Say naturally:
- "Describe scene"
- "What's ahead"

### Dashboard

Open browser: `http://localhost:5001`

View:
- Live video feed with object detection
- Recent alerts and statistics
- Environmental conditions
- Fall detection status
- Emergency and assistance requests

## Object Detection

Edit `relevant_classes.txt` to customize which objects trigger alerts.

## Architecture

```
Pi (abcd.py)
  ├─ Camera → MJPEG stream
  ├─ Sense HAT → Fall detection, emergency button, environment
  └─ Flask API → Status endpoints

Laptop (run.py)
  ├─ Fetch Pi stream → YOLOv8 inference
  ├─ TTS voice alerts
  ├─ Voice command recognition
  └─ Backend API (backend_api.py)
      └─ Dashboard (frontend/)
```

## API Endpoints

### Pi (port 5000)
- `/video_feed` - MJPEG stream
- `/api/fall_status` - Fall detection status
- `/api/emergency_status` - Emergency button status
- `/api/assistance_status` - Assistance request status
- `/api/environmental` - Temperature, humidity, pressure

### Backend (port 5001)
- `/api/video_feed` - Annotated video feed
- `/api/stats` - Detection statistics
- `/api/alerts` - Recent alerts
- All Pi endpoints proxied

## Database

SQLite database `vision_assist.db` stores:
- Sessions
- Object detections
- Alerts (falls, emergencies, assistance requests)
- Voice commands
- Scene summaries

## License

MIT
