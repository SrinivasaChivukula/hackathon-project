# Vision Assistant for Vision-Impaired Patients

An IoT-based collision prevention and navigation assistance system using computer vision and audio feedback.

## Features

### ✅ Core Functionality
- **Real-time Object Detection** - YOLO-based detection of 24+ relevant object classes
- **Distance Estimation** - Calculates proximity based on object size in frame
- **Spatial Awareness** - Directional audio cues (left, right, ahead)
- **Collision Prevention** - Alerts for objects in critical proximity zones

### 🎤 Voice Interface
- **Voice Commands**:
  - "Describe scene" - Get a summary of current environment
  - "What's ahead" - Check for obstacles in path
  - "Help" - List available commands
- Press 'c' key for voice command mode

### 📊 Smart Detection
- **Proximity Zones**:
  - 🔴 Critical (60%+ of frame): Immediate danger, priority alerts
  - 🟠 Warning (40-60%): Approaching objects, advance warning
  - 🟢 Far (<40%): Background objects, tracked but no alert

- **Alert Cooldown**: 3-second cooldown per object to prevent alert spam
- **Inference Interval**: 5-second intervals to optimize performance

### 📝 Logging
- All detections and alerts logged to `vision_assist.log`
- Timestamps, object types, distances recorded
- Useful for caregiver monitoring and system debugging

## Hardware Setup

### Required Components
- Raspberry Pi with camera module (running Flask MJPEG stream)
- Laptop/PC for inference processing
- Speakers/headphones for audio feedback
- Microphone for voice commands

### Network Setup
- Pi streaming video at: `http://100.101.51.31:5000/video_feed`
- Both devices on same network

## Installation

### System Dependencies (Debian/Ubuntu)
```bash
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip libgl1 libglib2.0-0 ffmpeg
sudo apt-get install -y portaudio19-dev python3-pyaudio  # For voice recognition
sudo apt-get install -y espeak espeak-data libespeak-dev  # For TTS
```

### Python Environment
```bash
cd /home/richard/Desktop/yeah
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# For CPU-only (recommended for laptops)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# For CUDA GPU (if available)
# pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### Required Files
- `alert.wav` - Audio alert sound file
- `relevant__classes` - Text file with one object class per line
- `yolov8n.pt` - Downloaded automatically on first run

## Usage

```bash
source .venv/bin/activate
python run.py
```

### Controls
- **q** - Quit application
- **c** - Activate voice command mode
- **s** - Manual scene description

### Voice Commands
Speak clearly after pressing 'c':
- "Describe scene" / "What's around me"
- "What's ahead" / "What's in front"
- "Help"

## Architecture

```
┌─────────────┐       MJPEG Stream      ┌──────────────┐
│ Raspberry   │ ───────────────────────> │   Laptop     │
│ Pi Camera   │                          │  (Inference) │
└─────────────┘                          └──────────────┘
                                                │
                                                ├─> YOLO Detection
                                                ├─> Distance Estimation
                                                ├─> TTS Audio Output
                                                ├─> Voice Recognition
                                                └─> File Logging
```

## Hackathon Demo Tips

### Demo Scenarios
1. **Collision Prevention**: Walk toward objects, show critical alerts
2. **Navigation**: Demonstrate directional guidance (left/right/ahead)
3. **Voice Commands**: Show hands-free scene description
4. **Scene Understanding**: Multiple objects, prioritized alerts

### Key Talking Points
- **Real-time processing**: 5-second inference for efficiency
- **Offline capable**: No cloud dependency (except initial voice recognition)
- **Practical design**: Alert cooldowns prevent information overload
- **Accessibility focus**: Audio-first interface, simple controls
- **IoT integration**: Distributed processing (Pi + laptop)

## Relevant Object Classes
```
person, bicycle, car, motorcycle, bus, truck, boat,
traffic light, fire hydrant, stop sign, parking meter,
bench, chair, couch, potted plant, bed, dining table,
toilet, tv, microwave, oven, toaster, sink, refrigerator
```

## Future Enhancements
- [ ] Depth camera integration for accurate distance
- [ ] Path planning algorithms
- [ ] Web dashboard for caregiver monitoring
- [ ] Mobile app integration
- [ ] Haptic feedback vest/band
- [ ] Multi-camera 360° coverage
- [ ] Emergency contact auto-dial
- [ ] Indoor navigation/mapping

## Troubleshooting

### No audio output
- Check speaker/headphone connection
- Verify espeak is installed: `espeak "test"`

### Voice recognition not working
- Check microphone permissions
- Test microphone: `arecord -d 3 test.wav && aplay test.wav`
- Requires internet for Google Speech Recognition

### Camera connection fails
- Verify Pi stream is running: open `http://100.101.51.31:5000/video_feed` in browser
- Check network connectivity between devices

### Performance issues
- Reduce inference interval (change `inference_interval` in code)
- Use CPU-only torch installation
- Consider YOLOv8n (nano) instead of larger models

## License
MIT License - Hackathon Project

## Credits
- YOLOv8 by Ultralytics
- Built for accessibility and assistive technology

