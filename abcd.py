from flask import Flask, Response, jsonify
from picamera2 import Picamera2
import io
import time
import atexit
import signal
import sys
import threading
import random
import math
from sense_hat import SenseHat
from collections import deque
from datetime import datetime

app = Flask(__name__)

# Initialize    camera with proper cleanup
picam2 = None
sense = None
led_thread = None
fall_detection_thread = None
emergency_thread = None
environmental_thread = None

# Fall detection state
fall_detected = False
fall_timestamp = None
fall_history = deque(maxlen=10)  # Keep last 10 falls

# Emergency state
emergency_active = False
emergency_timestamp = None
emergency_history = deque(maxlen=10)  # Keep last 10 emergencies

# Assistance request state
assistance_request = None  # Current active request
assistance_timestamp = None
assistance_history = deque(maxlen=20)  # Keep last 20 requests

# Environmental monitoring
environmental_data = {
    'temperature': None,
    'humidity': None,
    'pressure': None,
    'last_update': None
}

def cleanup_camera():
    """Properly close camera and Sense HAT on shutdown"""
    global picam2, sense, led_thread, fall_detection_thread, emergency_thread, environmental_thread
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
    
    if fall_detection_thread is not None:
        try:
            fall_detection_thread.join(timeout=1)
            print("Fall detection thread stopped")
        except Exception as e:
            print(f"Error stopping fall detection thread: {e}")
    
    if emergency_thread is not None:
        try:
            emergency_thread.join(timeout=1)
            print("Emergency monitoring thread stopped")
        except Exception as e:
            print(f"Error stopping emergency thread: {e}")
    
    if environmental_thread is not None:
        try:
            environmental_thread.join(timeout=1)
            print("Environmental monitoring thread stopped")
        except Exception as e:
            print(f"Error stopping environmental thread: {e}")

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

def fall_alert_led():
    """Flash red LEDs for fall alert"""
    global sense
    if sense is None:
        return
    
    # Flash red 5 times
    for _ in range(5):
        sense.clear((255, 0, 0))  # Red
        time.sleep(0.2)
        sense.clear()
        time.sleep(0.2)

def emergency_alert_led():
    """Flash bright white LEDs for emergency alert"""
    global sense
    if sense is None:
        return
    
    # Flash white rapidly 10 times
    for _ in range(10):
        sense.clear((255, 255, 255))  # Bright white
        time.sleep(0.1)
        sense.clear()
        time.sleep(0.1)

def assistance_request_led(color):
    """Flash colored LEDs for assistance request"""
    global sense
    if sense is None:
        return
    
    # Flash colored light 5 times
    for _ in range(5):
        sense.clear(color)
        time.sleep(0.15)
        sense.clear()
        time.sleep(0.15)

def emergency_monitoring_worker():
    """Monitor joystick for emergency button presses and assistance requests"""
    global sense, emergency_active, emergency_timestamp, emergency_history
    global assistance_request, assistance_timestamp, assistance_history
    
    if sense is None:
        return
    
    print("🆘 Emergency & Assistance monitoring started!")
    
    # Define assistance request types
    assistance_types = {
        'up': {
            'name': 'General Help',
            'message': 'Patient needs general assistance',
            'color': (0, 255, 255),  # Cyan
            'icon': '🤝'
        },
        'down': {
            'name': 'Bathroom',
            'message': 'Patient needs bathroom assistance',
            'color': (255, 0, 255),  # Magenta
            'icon': '🚻'
        },
        'left': {
            'name': 'Food/Water',
            'message': 'Patient needs food or water',
            'color': (255, 165, 0),  # Orange
            'icon': '🍽️'
        },
        'right': {
            'name': 'Medication',
            'message': 'Patient needs medication',
            'color': (0, 255, 0),  # Green
            'icon': '💊'
        }
    }
    
    while True:
        try:
            # Get all joystick events
            events = sense.stick.get_events()
            
            for event in events:
                if event.action == 'pressed':
                    
                    # EMERGENCY: Middle button
                    if event.direction == 'middle':
                        emergency_active = True
                        emergency_timestamp = time.time()
                        
                        # Record emergency event
                        emergency_event = {
                            'timestamp': datetime.now().isoformat(),
                            'type': 'manual_button_press'
                        }
                        emergency_history.append(emergency_event)
                        
                        print(f"🆘 EMERGENCY BUTTON PRESSED!")
                        
                        # Flash LEDs to provide immediate feedback
                        emergency_alert_led()
                    
                    # ASSISTANCE REQUESTS: Directional buttons
                    elif event.direction in assistance_types:
                        request_info = assistance_types[event.direction]
                        
                        assistance_request = request_info['name']
                        assistance_timestamp = time.time()
                        
                        # Record assistance request
                        assistance_event = {
                            'timestamp': datetime.now().isoformat(),
                            'type': request_info['name'],
                            'message': request_info['message'],
                            'direction': event.direction
                        }
                        assistance_history.append(assistance_event)
                        
                        print(f"{request_info['icon']} {request_info['name'].upper()} REQUEST: {request_info['message']}")
                        
                        # Flash colored LEDs for feedback
                        assistance_request_led(request_info['color'])
            
            time.sleep(0.1)  # Check 10 times per second
            
        except Exception as e:
            print(f"Error in emergency monitoring: {e}")
            time.sleep(1)

def environmental_monitoring_worker():
    """Monitor environmental conditions"""
    global sense, environmental_data
    
    if sense is None:
        return
    
    print("🌡️ Environmental monitoring started!")
    
    while True:
        try:
            # Get temperature (in Celsius)
            temp_c = sense.get_temperature()
            
            # Get humidity (percentage)
            humidity = sense.get_humidity()
            
            # Get pressure (millibars)
            pressure = sense.get_pressure()
            
            # Update global environmental data
            environmental_data = {
                'temperature_c': round(temp_c, 1),
                'temperature_f': round((temp_c * 9/5) + 32, 1),
                'humidity': round(humidity, 1),
                'pressure': round(pressure, 1),
                'last_update': datetime.now().isoformat()
            }
            
            # Check for dangerous conditions
            temp_f = environmental_data['temperature_f']
            
            if temp_f > 85:
                print(f"⚠️ High temperature warning: {temp_f}°F")
            elif temp_f < 60:
                print(f"⚠️ Low temperature warning: {temp_f}°F")
            
            if humidity > 70:
                print(f"⚠️ High humidity warning: {humidity}%")
            elif humidity < 30:
                print(f"⚠️ Low humidity warning: {humidity}%")
            
            # Update every 30 seconds
            time.sleep(30)
            
        except Exception as e:
            print(f"Error in environmental monitoring: {e}")
            time.sleep(30)

def detect_fall():
    """
    Detect falls using accelerometer and gyroscope data
    
    Fall detection criteria:
    1. Sudden spike in total acceleration (free fall or impact)
    2. Large change in orientation (gyroscope)
    3. Sustained low acceleration after spike (person lying down)
    """
    global sense, fall_detected, fall_timestamp, fall_history
    
    if sense is None:
        return
    
    # Get current sensor readings
    accel = sense.get_accelerometer_raw()
    gyro = sense.get_gyroscope_raw()
    
    # Calculate total acceleration magnitude
    accel_magnitude = math.sqrt(
        accel['x']**2 + accel['y']**2 + accel['z']**2
    )
    
    # Calculate total rotation rate
    gyro_magnitude = math.sqrt(
        gyro['x']**2 + gyro['y']**2 + gyro['z']**2
    )
    
    # Fall detection thresholds (more sensitive for demo)
    FREEFALL_THRESHOLD = 0.6  # g (less than normal 1g indicates freefall)
    IMPACT_THRESHOLD = 2.0    # g (spike indicating impact) - lowered from 3.0
    GYRO_THRESHOLD = 150      # deg/s (rapid rotation) - lowered from 200
    
    # Detect freefall (sudden drop in acceleration)
    is_freefall = accel_magnitude < FREEFALL_THRESHOLD
    
    # Detect impact (sudden spike in acceleration)
    is_impact = accel_magnitude > IMPACT_THRESHOLD
    
    # Detect rapid rotation (tumbling)
    is_rotating = gyro_magnitude > GYRO_THRESHOLD
    
    # Fall detected if we see either:
    # 1. Impact + rotation (tumbling fall)
    # 2. Freefall (sudden drop)
    fall_condition = (is_impact and is_rotating) or is_freefall
    
    return fall_condition, accel_magnitude, gyro_magnitude

def fall_detection_worker():
    """Fall detection worker thread"""
    global sense, fall_detected, fall_timestamp, fall_history
    
    if sense is None:
        return
    
    print("🔍 Fall detection started!")
    
    # Calibration period
    print("Calibrating accelerometer (stay still for 2 seconds)...")
    time.sleep(2)
    
    fall_cooldown = 10  # seconds between fall detections
    consecutive_readings = 0
    required_consecutive = 2  # Require 2 consecutive readings to confirm fall (lowered from 3)
    
    while True:
        try:
            is_fall, accel_mag, gyro_mag = detect_fall()
            
            # Print sensor values every 2 seconds for debugging
            if int(time.time()) % 2 == 0:
                print(f"📊 Sensors: Accel={accel_mag:.2f}g, Gyro={gyro_mag:.1f}°/s")
            
            if is_fall:
                consecutive_readings += 1
                print(f"⚠️ Possible fall detected! Reading {consecutive_readings}/{required_consecutive}")
                
                # Require multiple consecutive readings to avoid false positives
                if consecutive_readings >= required_consecutive:
                    # Check cooldown to avoid duplicate detections
                    current_time = time.time()
                    if fall_timestamp is None or (current_time - fall_timestamp) > fall_cooldown:
                        fall_detected = True
                        fall_timestamp = current_time
                        
                        # Record fall event
                        fall_event = {
                            'timestamp': datetime.now().isoformat(),
                            'acceleration': accel_mag,
                            'rotation': gyro_mag
                        }
                        fall_history.append(fall_event)
                        
                        print(f"🚨 FALL DETECTED! Accel: {accel_mag:.2f}g, Gyro: {gyro_mag:.1f}°/s")
                        
                        # Flash LEDs to indicate fall
                        fall_alert_led()
                        
                        # Reset consecutive counter
                        consecutive_readings = 0
            else:
                # Reset consecutive counter if no fall detected
                consecutive_readings = max(0, consecutive_readings - 1)
            
            # Sample at 20 Hz
            time.sleep(0.05)
            
        except Exception as e:
            print(f"Error in fall detection: {e}")
            time.sleep(1)

def led_animation_worker():
    """LED animation worker thread"""
    global sense, fall_detected, emergency_active, assistance_request
    if sense is None:
        return
    
    patterns = [rainbow_wave, fire_pattern, matrix_rain, spiral_pattern]
    pattern_names = ["Rainbow Wave", "Fire", "Matrix Rain", "Spiral"]
    pattern_index = 0
    
    while True:
        try:
            # Check if emergency, fall, or assistance request was detected
            if fall_detected or emergency_active or assistance_request:
                time.sleep(1)  # Wait while alert is showing
                continue
            
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

# Initialize Sense HAT and start all monitoring threads
if init_sense_hat():
    led_thread = threading.Thread(target=led_animation_worker, daemon=True)
    led_thread.start()
    print("🎨 LED animations started!")
    
    fall_detection_thread = threading.Thread(target=fall_detection_worker, daemon=True)
    fall_detection_thread.start()
    print("🔍 Fall detection started!")
    
    emergency_thread = threading.Thread(target=emergency_monitoring_worker, daemon=True)
    emergency_thread.start()
    print("🆘 Emergency button monitoring started!")
    
    environmental_thread = threading.Thread(target=environmental_monitoring_worker, daemon=True)
    environmental_thread.start()
    print("🌡️ Environmental monitoring started!")
else:
    print("⚠  Sense HAT not available - all monitoring features disabled")

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

@app.route('/api/fall_status')
def fall_status():
    """Get current fall detection status"""
    global fall_detected, fall_timestamp, fall_history
    return jsonify({
        'fall_detected': fall_detected,
        'last_fall_timestamp': fall_timestamp,
        'fall_history': list(fall_history)
    })

@app.route('/api/fall_acknowledge')
def fall_acknowledge():
    """Acknowledge a fall alert (resets the flag)"""
    global fall_detected, fall_timestamp
    fall_detected = False
    return jsonify({
        'status': 'acknowledged',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/sensor_data')
def sensor_data():
    """Get current sensor readings"""
    global sense
    if sense is None:
        return jsonify({'error': 'Sense HAT not available'}), 503
    
    try:
        accel = sense.get_accelerometer_raw()
        gyro = sense.get_gyroscope_raw()
        orientation = sense.get_orientation()
        
        return jsonify({
            'acceleration': accel,
            'gyroscope': gyro,
            'orientation': orientation,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/emergency_status')
def get_emergency_status():
    """Get emergency button status"""
    global emergency_active, emergency_timestamp, emergency_history
    return jsonify({
        'emergency_active': emergency_active,
        'last_emergency_timestamp': emergency_timestamp,
        'emergency_history': list(emergency_history)
    })

@app.route('/api/emergency_acknowledge')
def acknowledge_emergency():
    """Acknowledge emergency alert"""
    global emergency_active, emergency_timestamp
    emergency_active = False
    return jsonify({
        'status': 'acknowledged',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/environmental')
def get_environmental():
    """Get environmental sensor data"""
    global environmental_data
    return jsonify(environmental_data)

@app.route('/api/assistance_status')
def get_assistance_status():
    """Get assistance request status"""
    global assistance_request, assistance_timestamp, assistance_history
    return jsonify({
        'assistance_active': assistance_request is not None,
        'assistance_type': assistance_request,
        'last_assistance_timestamp': assistance_timestamp,
        'assistance_history': list(assistance_history)
    })

@app.route('/api/assistance_acknowledge')
def acknowledge_assistance():
    """Acknowledge assistance request"""
    global assistance_request, assistance_timestamp
    assistance_request = None
    return jsonify({
        'status': 'acknowledged',
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    print("=" * 60)
    print("🎥 Starting PiCam3 MJPEG server...")
    print("🎨 Sense HAT LED patterns running")
    print("🔍 Fall detection active")
    print("🆘 Emergency button active (press joystick middle)")
    print("🌡️ Environmental monitoring active")
    print("=" * 60)
    print()
    print("API Endpoints:")
    print("  📹 /video_feed - MJPEG stream")
    print("  🚨 /api/fall_status - Get fall detection status")
    print("  ✅ /api/fall_acknowledge - Acknowledge fall alert")
    print("  🆘 /api/emergency_status - Get emergency button status")
    print("  ✅ /api/emergency_acknowledge - Acknowledge emergency")
    print("  🤝 /api/assistance_status - Get assistance request status")
    print("  ✅ /api/assistance_acknowledge - Acknowledge assistance")
    print("  🌡️ /api/environmental - Get environmental data")
    print("  📊 /api/sensor_data - Get current sensor readings")
    print()
    print("Joystick Controls:")
    print("  🔴 MIDDLE - Emergency SOS")
    print("  ⬆️  UP    - General Help")
    print("  ⬇️  DOWN  - Bathroom")
    print("  ⬅️  LEFT  - Food/Water")
    print("  ➡️  RIGHT - Medication")
    print()
    print("📡 Access at: http://your-pi-ip:5000")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, threaded=True)   