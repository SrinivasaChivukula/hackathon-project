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
        self.tts_engine.setProperty('rate', 150)  # Speed
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
        self.alert_cooldown = 3.0  # Don't repeat same alert within 3 seconds
        
        # Detection tracking
        self.current_detections = []
        self.scene_objects = defaultdict(int)
        
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
        
        thread = threading.Thread(target=_speak)
        thread.daemon = True
        thread.start()
        
        if priority:
            thread.join()  # Wait for critical alerts
    
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
                    
                    # Draw bounding box
                    color = (0, 0, 255) if distance_cat == "critical" else \
                           (0, 165, 255) if distance_cat == "warning" else (0, 255, 0)
                    
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(frame, f"{cls_name}", (x1, y1-10),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                    
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
            
            # Speak proximity alerts (critical first)
            proximity_alerts.sort(key=lambda x: 0 if x[0] == "critical" else 1)
            for distance_cat, alert in proximity_alerts[:2]:  # Max 2 alerts at once
                self.alert_sound.play()
                self.speak(alert, priority=(distance_cat == "critical"))
        
        return frame
    
    def run(self):
        """Main loop"""
        # Start session
        self.session_id = self.data_logger.start_session()
        logging.info(f"Started session #{self.session_id}")
        
        self.speak("Vision assistant started", priority=True)
        logging.info("Starting main loop")
        
        print("Vision Assistant Running")
        print("Commands: 'Describe scene', 'What's ahead'")
        print("Press 'q' to quit, 'c' to give voice command, 's' for scene description")
        print(f"Dashboard available at: http://localhost:5001")
        
        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    logging.warning("Failed to read frame")
                    continue
                
                # Process frame
                annotated_frame = self.process_frame(frame)
                
                # Update frame for API streaming
                set_current_frame(annotated_frame)
                
                # Display
                cv2.imshow("VisionAssist", annotated_frame)
                
                # Handle keyboard input
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('c'):
                    command = self.listen_for_command()
                    self.handle_voice_command(command)
                elif key == ord('s'):
                    # Manual scene description
                    summary = self.summarize_scene()
                    self.speak(summary)
                    if self.session_id:
                        self.data_logger.log_scene_summary(
                            self.session_id, summary, len(self.scene_objects)
                        )
        
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
        cv2.destroyAllWindows()
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

