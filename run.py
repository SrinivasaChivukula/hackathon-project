import cv2
from ultralytics import YOLO
import pygame
import time

# Setup audio
pygame.mixer.init()
alert_sound = pygame.mixer.Sound("alert.wav")

# Load model
model = YOLO('yolov8n.pt')  # pre-trained COCO

# Connect to Pi MJPEG stream
cap = cv2.VideoCapture("http://100.101.51.31:5000/video_feed")

# Load relevant classes from file
with open('relevant__classes', 'r') as f:
    relevant_classes = [line.strip() for line in f.readlines()]

# Timing variables
last_inference_time = 0
inference_interval = 5.0  # Run inference every 5 seconds

while True:
    ret, frame = cap.read()
    if not ret:
        continue

    current_time = time.time()
    
    # Only run inference every 5 seconds
    if current_time - last_inference_time >= inference_interval:
        results = model(frame)
        last_inference_time = current_time
        alert_triggered = False

        for box in results[0].boxes:
            cls_id = int(box.cls[0])
            cls_name = model.names[cls_id]
            if cls_name in relevant_classes:
                alert_triggered = True
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cv2.rectangle(frame, (x1,y1), (x2,y2), (0,255,0), 2)
            cv2.putText(frame, f"{cls_name}", (x1, y1-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 2)

        if alert_triggered:
            alert_sound.play()

    cv2.imshow("VisionAssist", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
pygame.quit()
