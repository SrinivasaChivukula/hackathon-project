from flask import Flask, Response
from picamera2 import Picamera2
import io
import time
import atexit
import signal
import sys
import threading
import random
from sense_hat import SenseHat

app = Flask(__name__)

# Initialize camera with proper cleanup
picam2 = None
sense = None
led_thread = None

def cleanup_camera():
    """Properly close camera and Sense HAT on shutdown"""
    global picam2, sense, led_thread
    if picam2 is not None:
        try:
            picam2.stop()
            picam2.close()
            print("Camera properly closed")
        except Exception as e:
            print(f"Error closing camera: {e}")
    
    if sense is not None:
        try:
            sense.clear()
            print("Sense HAT cleared")
        except Exception as e:
            print(f"Error clearing Sense HAT: {e}")
    
    if led_thread is not None:
        try:
            led_thread.join(timeout=1)
            print("LED thread stopped")
        except Exception as e:
            print(f"Error stopping LED thread: {e}")

def init_camera():
    """Initialize camera with error handling"""
    global picam2
    try:
        picam2 = Picamera2()
        # Use default configuration for best color accuracy
        config = picam2.create_preview_configuration()
        picam2.configure(config)
        picam2.start()
        print("Camera initialized successfully")
    except Exception as e:
        print(f"Error initializing camera: {e}")
        sys.exit(1)

def init_sense_hat():
    """Initialize Sense HAT for LED patterns"""
    global sense
    try:
        sense = SenseHat()
        sense.clear()
        print("Sense HAT initialized")
        return True
    except Exception as e:
        print(f"Error initializing Sense HAT: {e}")
        return False

def hsv_to_rgb(h, s, v):
    """Convert HSV to RGB (h: 0-360, s: 0-1, v: 0-1)"""
    import math
    h = h % 360  # Ensure h is in range
    h = h / 60.0  # Convert to 0-6 range
    i = int(h)
    f = h - i
    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))
    
    i = i % 6  # Ensure i is 0-5
    
    if i == 0:
        return (int(v * 255), int(t * 255), int(p * 255))
    elif i == 1:
        return (int(q * 255), int(v * 255), int(p * 255))
    elif i == 2:
        return (int(p * 255), int(v * 255), int(t * 255))
    elif i == 3:
        return (int(p * 255), int(q * 255), int(v * 255))
    elif i == 4:
        return (int(t * 255), int(p * 255), int(v * 255))
    else:
        return (int(v * 255), int(p * 255), int(q * 255))

def rainbow_wave():
    """Create a rainbow wave pattern"""
    import math
    offset = 0
    for _ in range(160):  # Run for about 8 seconds at 50ms per frame
        pixels = []
        for y in range(8):
            for x in range(8):
                # Create wave effect
                wave = math.sin((x + y) / 3.0 + offset) * 0.5 + 0.5
                hue = (offset * 50 + x * 20 + y * 20) % 360
                r, g, b = hsv_to_rgb(hue, 0.8, wave * 0.6 + 0.2)
                pixels.append((r, g, b))
        
        sense.set_pixels(pixels)
        offset += 0.1
        time.sleep(0.05)

def fire_pattern():
    """Create a fire-like pattern"""
    for _ in range(160):  # Run for about 8 seconds
        pixels = []
        for y in range(8):
            for x in range(8):
                # Fire effect - hotter at bottom, cooler at top
                base_intensity = random.randint(100, 255) * (8 - y) / 8
                r = int(min(255, base_intensity))
                g = int(max(0, base_intensity - 100))
                b = int(max(0, base_intensity - 200))
                pixels.append((r, g, b))
        
        sense.set_pixels(pixels)
        time.sleep(0.05)

def matrix_rain():
    """Create a Matrix-style rain effect"""
    import math
    rain_cols = [random.randint(0, 7) for _ in range(8)]
    rain_pos = [random.randint(0, 7) for _ in range(8)]
    
    for _ in range(160):  # Run for about 8 seconds
        pixels = [(0, 0, 0)] * 64
        
        for col_idx, col in enumerate(rain_cols):
            pos = rain_pos[col_idx]
            # Draw falling character with trail
            for trail in range(4):
                y = (pos - trail) % 8
                intensity = int(255 * (1 - trail * 0.3))
                pixels[y * 8 + col] = (0, intensity, 0)
            
            # Move rain down
            rain_pos[col_idx] = (rain_pos[col_idx] + 1) % 12
            
            # Occasionally start new rain column
            if random.random() < 0.05:
                rain_cols[col_idx] = random.randint(0, 7)
        
        sense.set_pixels(pixels)
        time.sleep(0.05)

def spiral_pattern():
    """Create a colorful spiral pattern"""
    import math
    offset = 0
    
    for _ in range(160):  # Run for about 8 seconds
        pixels = []
        for y in range(8):
            for x in range(8):
                # Calculate angle and distance from center
                dx = x - 3.5
                dy = y - 3.5
                angle = math.atan2(dy, dx)
                dist = math.sqrt(dx * dx + dy * dy)
                
                # Create spiral effect
                hue = ((angle * 57.3 + dist * 40 + offset * 50) % 360)
                brightness = 0.4 + 0.2 * math.sin(dist - offset)
                r, g, b = hsv_to_rgb(hue, 0.9, brightness)
                pixels.append((r, g, b))
        
        sense.set_pixels(pixels)
        offset += 0.06
        time.sleep(0.05)

def led_animation_worker():
    """LED animation worker thread"""
    global sense
    if sense is None:
        return
    
    patterns = [rainbow_wave, fire_pattern, matrix_rain, spiral_pattern]
    pattern_names = ["Rainbow Wave", "Fire", "Matrix Rain", "Spiral"]
    pattern_index = 0
    
    while True:
        try:
            pattern = patterns[pattern_index]
            pattern_name = pattern_names[pattern_index]
            
            print(f"🎨 Running LED pattern: {pattern_name}")
            
            # Each pattern runs for ~8 seconds internally
            pattern()
            
            # Move to next pattern
            pattern_index = (pattern_index + 1) % len(patterns)
            
            # Small pause between patterns
            time.sleep(0.2)
            
        except Exception as e:
            print(f"Error in LED animation: {e}")
            sense.clear()
            time.sleep(1)

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\nShutting down gracefully...")
    cleanup_camera()
    sys.exit(0)

# Register cleanup handlers
atexit.register(cleanup_camera)
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Initialize camera
init_camera()

# Initialize Sense HAT and start LED animations
if init_sense_hat():
    led_thread = threading.Thread(target=led_animation_worker, daemon=True)
    led_thread.start()
    print("🎨 LED animations started!")
else:
    print("⚠  Sense HAT not available - LED animations disabled")

def generate():
    while True:
        # Use Picamera2's built-in JPEG encoder for proper color handling
        stream = io.BytesIO()
        picam2.capture_file(stream, format='jpeg')
        stream.seek(0)
        frame_data = stream.read()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    return "<h1>PiCam3 MJPEG Stream</h1><img src='/video_feed' width='640' height='480'>"

if __name__ == '__main__':
    print("🎥 Starting PiCam3 MJPEG server with LED animations...")
    print("🎨 Sense HAT LED patterns will run automatically!")
    print("📡 Access the stream at: http://your-pi-ip:5000")
    app.run(host='0.0.0.0', port=5000, threaded=True)   