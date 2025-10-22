import cv2
from ultralytics import YOLO
import pygame
import time
import pyttsx3
import threading
import logging
from datetime import datetime
from collections import defaultdict
import speech_recognition as sr
import requests
from data_logger import VisionDataLogger
from backend_api import set_current_frame, run_api_server

# Setup logging
logging.basicConfig(
    filename='vision_assist.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class VisionAssistant:
    def __init__(self):
        # Setup audio
        pygame.mixer.init()
        self.alert_sound = pygame.mixer.Sound("alert.wav")
        
        # Setup TTS
        self.tts_engine = pyttsx3.init()
        self.tts_engine.setProperty('rate', 175)  # Faster speed for less lag
        self.tts_engine.setProperty('volume', 0.9)
        self.tts_lock = threading.Lock()
        
        # Setup voice recognition
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        
        # Initialize data logger
        self.data_logger = VisionDataLogger()
        self.session_id = None
        
        # Load YOLO model
        self.model = YOLO('yolov8n.pt')
        
        # Connect to Pi MJPEG stream
        self.cap = cv2.VideoCapture("http://100.101.51.31:5000/video_feed")
        
        # Load relevant classes
        with open('relevant__classes', 'r') as f:
            self.relevant_classes = [line.strip() for line in f.readlines()]
        
        # Distance thresholds (based on bounding box height percentage)
        self.CRITICAL_DISTANCE = 0.6  # 60% of frame height
        self.WARNING_DISTANCE = 0.4   # 40% of frame height
        
        # Timing variables
        self.last_inference_time = 0
        self.inference_interval = 5.0
        self.last_alert_time = {}  # Per-object cooldown
        self.alert_cooldown = 5.0  # Don't repeat same alert within 5 seconds (reduce audio spam)
        
        # Fall detection monitoring
        self.last_fall_check = 0
        self.fall_check_interval = 2  # Check for falls every 2 seconds
        self.last_fall_alert_time = 0
        self.fall_alert_cooldown = 15  # Don't repeat fall warnings for 15 seconds
        
        # Assistance request monitoring
        self.last_assistance_check = 0
        self.assistance_check_interval = 2  # Check for assistance requests every 2 seconds
        self.last_assistance_alert_time = {}  # Track cooldown per request type
        self.assistance_alert_cooldown = 20  # Don't repeat same request for 20 seconds
        
        # Emergency monitoring
        self.last_emergency_check = 0
        self.emergency_check_interval = 2  # Check for emergency every 2 seconds
        self.last_emergency_alert_time = 0
        self.emergency_alert_cooldown = 20  # Don't repeat emergency for 20 seconds
        
        # Detection tracking
        self.current_detections = []
        self.scene_objects = defaultdict(int)
        self.last_boxes_to_draw = []  # Persist boxes between inference runs
        
        # Voice command flag
        self.listening_for_command = False
        
        logging.info("Vision Assistant initialized")
    
    def estimate_distance_category(self, box_height, frame_height):
        """Estimate distance category based on bounding box size"""
        height_ratio = box_height / frame_height
        
        if height_ratio > self.CRITICAL_DISTANCE:
            return "critical", height_ratio
        elif height_ratio > self.WARNING_DISTANCE:
            return "warning", height_ratio
        else:
            return "far", height_ratio
    
    def get_direction(self, box_center_x, frame_width):
        """Determine object direction relative to camera center"""
        center = frame_width / 2
        threshold = frame_width * 0.15  # 15% deadzone for "ahead"
        
        if abs(box_center_x - center) < threshold:
            return "ahead"
        elif box_center_x < center:
            return "on your left"
        else:
            return "on your right"
    
    def speak(self, text, priority=False):
        """Thread-safe TTS output"""
        def _speak():
            with self.tts_lock:
                logging.info(f"Speaking: {text}")
                self.tts_engine.say(text)
                self.tts_engine.runAndWait()
        
        thread = threading.Thread(target=_speak, daemon=True)
        thread.start()
        # Never block main thread, even for priority alerts
    
    def generate_proximity_alert(self, cls_name, distance_category, direction):
        """Generate natural language proximity alert"""
        distance_phrases = {
            "critical": "very close",
            "warning": "approaching",
            "far": "in the distance"
        }
        
        alert = f"{cls_name} {distance_phrases[distance_category]} {direction}"
        return alert
    
    def summarize_scene(self):
        """Generate a scene summary from current detections"""
        if not self.scene_objects:
            return "No objects detected in view"
        
        # Group by category
        people_count = self.scene_objects.get('person', 0)
        furniture = [obj for obj in self.scene_objects.keys() 
                    if obj in ['chair', 'couch', 'bed', 'dining table', 'bench']]
        vehicles = [obj for obj in self.scene_objects.keys() 
                   if obj in ['car', 'bus', 'truck', 'motorcycle', 'bicycle']]
        
        summary_parts = []
        
        if people_count > 0:
            summary_parts.append(f"{people_count} {'person' if people_count == 1 else 'people'}")
        
        if furniture:
            summary_parts.append(f"furniture detected: {', '.join(furniture[:3])}")
        
        if vehicles:
            summary_parts.append(f"vehicles: {', '.join(vehicles[:3])}")
        
        if len(summary_parts) == 0:
            other_objects = list(self.scene_objects.keys())[:3]
            summary_parts.append(f"Objects: {', '.join(other_objects)}")
        
        return "Scene: " + ". ".join(summary_parts)
    
    def listen_for_command(self):
        """Listen for voice commands"""
        try:
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                print("Listening for command...")
                audio = self.recognizer.listen(source, timeout=2, phrase_time_limit=3)
            
            command = self.recognizer.recognize_google(audio, language='en-US').lower()
            logging.info(f"Voice command received: {command}")
            return command
        except sr.WaitTimeoutError:
            return None
        except sr.UnknownValueError:
            return None
        except Exception as e:
            logging.error(f"Voice recognition error: {e}")
            return None
    
    def handle_voice_command(self, command):
        """Process voice commands"""
        if not command:
            return
        
        response = ""
        
        if "describe" in command or "what" in command or "scene" in command:
            summary = self.summarize_scene()
            self.speak(summary)
            response = summary
        elif "ahead" in command or "front" in command:
            ahead_objects = [d for d in self.current_detections 
                           if d['direction'] == "ahead"]
            if ahead_objects:
                closest = min(ahead_objects, key=lambda x: x['distance_score'])
                response = f"{closest['name']} {closest['distance']} ahead"
                self.speak(response)
            else:
                response = "Path ahead is clear"
                self.speak(response)
        elif "help" in command:
            response = "Say describe scene to hear what's around you, or what's ahead to check your path"
            self.speak(response)
        
        # Log voice command
        if self.session_id:
            self.data_logger.log_voice_command(self.session_id, command, response)
    
    def process_frame(self, frame):
        """Process a single frame and return annotated frame"""
        current_time = time.time()
        frame_height, frame_width = frame.shape[:2]
        
        # Run inference every 5 seconds
        if current_time - self.last_inference_time >= self.inference_interval:
            results = self.model(frame)
            self.last_inference_time = current_time
            
            # Reset scene tracking
            self.scene_objects.clear()
            self.current_detections = []
            self.last_boxes_to_draw = []  # Reset boxes
            
            proximity_alerts = []
            
            for box in results[0].boxes:
                cls_id = int(box.cls[0])
                cls_name = self.model.names[cls_id]
                
                # Track all objects for scene summary
                self.scene_objects[cls_name] += 1
                
                if cls_name in self.relevant_classes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    box_height = y2 - y1
                    box_center_x = (x1 + x2) / 2
                    
                    # Estimate distance and direction
                    distance_cat, distance_score = self.estimate_distance_category(
                        box_height, frame_height
                    )
                    direction = self.get_direction(box_center_x, frame_width)
                    
                    # Store detection
                    detection_data = {
                        'name': cls_name,
                        'distance': distance_cat,
                        'distance_score': distance_score,
                        'direction': direction,
                        'bbox': (x1, y1, x2, y2),
                        'confidence': float(box.conf[0]) if hasattr(box, 'conf') else 0.0
                    }
                    self.current_detections.append(detection_data)
                    
                    # Log detection to database
                    if self.session_id:
                        self.data_logger.log_detection(self.session_id, detection_data)
                    
                    # Store box info for drawing
                    color = (0, 0, 255) if distance_cat == "critical" else \
                           (0, 165, 255) if distance_cat == "warning" else (0, 255, 0)
                    
                    self.last_boxes_to_draw.append({
                        'bbox': (x1, y1, x2, y2),
                        'label': cls_name,
                        'color': color
                    })
                    
                    # Generate proximity alert for close objects
                    if distance_cat in ["critical", "warning"]:
                        alert_key = f"{cls_name}_{direction}"
                        last_alert = self.last_alert_time.get(alert_key, 0)
                        
                        if current_time - last_alert > self.alert_cooldown:
                            alert_text = self.generate_proximity_alert(
                                cls_name, distance_cat, direction
                            )
                            proximity_alerts.append((distance_cat, alert_text))
                            self.last_alert_time[alert_key] = current_time
                            
                            logging.info(f"Proximity alert: {alert_text}")
                            
                            # Log alert to database
                            if self.session_id:
                                self.data_logger.log_alert(
                                    self.session_id, cls_name, distance_cat, direction, alert_text
                                )
            
            # Speak proximity alerts (critical first, only 1 at a time)
            if proximity_alerts:
                proximity_alerts.sort(key=lambda x: 0 if x[0] == "critical" else 1)
                distance_cat, alert = proximity_alerts[0]  # Only speak the most critical one
                
                # Play alert sound only for critical
                if distance_cat == "critical":
                    self.alert_sound.play()
                
                # Speak the alert (non-blocking)
                self.speak(alert)
        
        # Draw all bounding boxes (persists between inference runs)
        for box_info in self.last_boxes_to_draw:
            x1, y1, x2, y2 = box_info['bbox']
            cv2.rectangle(frame, (x1, y1), (x2, y2), box_info['color'], 2)
            cv2.putText(frame, box_info['label'], (x1, y1-10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_info['color'], 2)
        
        return frame
    
    def check_fall_status(self):
        """Check if fall was detected on Pi and alert user"""
        current_time = time.time()
        
        # Only check every 2 seconds
        if current_time - self.last_fall_check < self.fall_check_interval:
            return
        
        self.last_fall_check = current_time
        
        try:
            # Query Pi for fall status
            response = requests.get('http://100.101.51.31:5000/api/fall_status', timeout=1)
            if response.status_code == 200:
                data = response.json()
                
                if data.get('fall_detected'):
                    # Check cooldown to avoid repeated warnings
                    if current_time - self.last_fall_alert_time > self.fall_alert_cooldown:
                        self.last_fall_alert_time = current_time
                        
                        # Voice alert
                        alert_message = "Warning! Fall detected! Patient may need assistance!"
                        self.speak(alert_message, priority=True)
                        
                        # Play critical alert sound
                        self.alert_sound.play()
                        
                        # Log to database as critical alert
                        if self.session_id:
                            self.data_logger.log_alert(
                                self.session_id,
                                'Fall Detection',
                                'critical',
                                'system',
                                alert_message
                            )
                        
                        logging.error(f"FALL DETECTED! {alert_message}")
        
        except Exception as e:
            # Silently fail - don't spam logs if Pi is unreachable
            pass
    
    def check_emergency_status(self):
        """Check if emergency button was pressed and alert user"""
        current_time = time.time()
        
        # Only check every 2 seconds
        if current_time - self.last_emergency_check < self.emergency_check_interval:
            return
        
        self.last_emergency_check = current_time
        
        try:
            # Query Pi for emergency status
            response = requests.get('http://100.101.51.31:5000/api/emergency_status', timeout=1)
            if response.status_code == 200:
                data = response.json()
                
                if data.get('emergency_active'):
                    # Check cooldown to avoid repeated warnings
                    if current_time - self.last_emergency_alert_time > self.emergency_alert_cooldown:
                        self.last_emergency_alert_time = current_time
                        
                        # Voice alert
                        alert_message = "EMERGENCY! Patient pressed emergency button! Immediate assistance required!"
                        self.speak(alert_message, priority=True)
                        
                        # Play critical alert sound
                        self.alert_sound.play()
                        
                        # Log to database as critical alert
                        if self.session_id:
                            self.data_logger.log_alert(
                                self.session_id,
                                'Emergency SOS',
                                'critical',
                                'emergency_button',
                                alert_message
                            )
                        
                        logging.error(f"EMERGENCY BUTTON PRESSED! {alert_message}")
        
        except Exception as e:
            # Silently fail - don't spam logs if Pi is unreachable
            pass
    
    def check_assistance_status(self):
        """Check if assistance was requested via joystick and alert user"""
        current_time = time.time()
        
        # Only check every 2 seconds
        if current_time - self.last_assistance_check < self.assistance_check_interval:
            return
        
        self.last_assistance_check = current_time
        
        try:
            # Query Pi for assistance status
            response = requests.get('http://100.101.51.31:5000/api/assistance_status', timeout=1)
            if response.status_code == 200:
                data = response.json()
                
                if data.get('assistance_active') and data.get('assistance_type'):
                    assistance_type = data['assistance_type']
                    
                    # Check cooldown to avoid repeated warnings for same request type
                    last_alert = self.last_assistance_alert_time.get(assistance_type, 0)
                    if current_time - last_alert > self.assistance_alert_cooldown:
                        self.last_assistance_alert_time[assistance_type] = current_time
                        
                        # Define voice messages for each assistance type
                        assistance_messages = {
                            'General Help': {
                                'message': 'Attention! Patient requesting general assistance!',
                                'priority': 'warning'
                            },
                            'Bathroom': {
                                'message': 'Alert! Patient needs bathroom assistance immediately!',
                                'priority': 'warning'
                            },
                            'Food/Water': {
                                'message': 'Patient is requesting food or water!',
                                'priority': 'warning'
                            },
                            'Medication': {
                                'message': 'Important! Patient needs medication!',
                                'priority': 'warning'
                            }
                        }
                        
                        request_info = assistance_messages.get(assistance_type, {
                            'message': f'Patient requesting {assistance_type}',
                            'priority': 'warning'
                        })
                        
                        # Voice alert
                        self.speak(request_info['message'], priority=True)
                        
                        # Play alert sound (less aggressive than emergency)
                        self.alert_sound.play()
                        
                        # Log to database
                        if self.session_id:
                            self.data_logger.log_alert(
                                self.session_id,
                                assistance_type,
                                request_info['priority'],
                                'assistance_request',
                                request_info['message']
                            )
                        
                        logging.warning(f"ASSISTANCE REQUEST: {assistance_type} - {request_info['message']}")
        
        except Exception as e:
            # Silently fail - don't spam logs if Pi is unreachable
            pass
    
    def run(self):
        """Main loop"""
        # Start session
        self.session_id = self.data_logger.start_session()
        logging.info(f"Started session #{self.session_id}")
        
        self.speak("Vision assistant started", priority=True)
        logging.info("Starting main loop")
        
        print("=" * 60)
        print("Vision Assistant Running")
        print("=" * 60)
        print()
        print("📹 View live video at: http://localhost:5001")
        print()
        print("Voice Commands (speak naturally):")
        print("  'Describe scene' - Get environment summary")
        print("  'What's ahead'   - Check path ahead")
        print()
        print("Press Ctrl+C to quit")
        print("=" * 60)
        
        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    logging.warning("Failed to read frame")
                    time.sleep(0.1)
                    continue
                
                # Process frame (inference happens here every 5 seconds)
                annotated_frame = self.process_frame(frame)
                
                # Check for fall detection (every 2 seconds)
                self.check_fall_status()
                
                # Check for emergency button (every 2 seconds)
                self.check_emergency_status()
                
                # Check for assistance requests (every 2 seconds)
                self.check_assistance_status()
                
                # Update frame for API streaming
                set_current_frame(annotated_frame)
                
                # Small delay to prevent CPU spinning
                time.sleep(0.05)  # ~20 FPS (smoother, less CPU)
        
        except KeyboardInterrupt:
            print("\nShutting down gracefully...")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        logging.info("Shutting down Vision Assistant")
        
        # End session
        if self.session_id:
            self.data_logger.end_session(self.session_id)
            logging.info(f"Ended session #{self.session_id}")
        
        self.speak("Vision assistant stopping", priority=True)
        self.cap.release()
        pygame.quit()

if __name__ == "__main__":
    # Start API server in background thread
    api_thread = threading.Thread(target=run_api_server, daemon=True)
    api_thread.start()
    logging.info("API server started on http://localhost:5001")
    
    # Give API server time to start
    time.sleep(1)
    
    # Start vision assistant
    assistant = VisionAssistant()
    assistant.run()

