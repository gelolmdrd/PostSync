import sys
import os
import cv2
import csv
import mediapipe as mp
import pandas as pd
import numpy as np
import joblib
import threading
import sqlite3
import time
from plyer import notification
from PyQt5.QtCore import pyqtSignal, QObject
from collections import deque
from datetime import datetime
import posture_database
import warnings

warnings.filterwarnings("ignore", category=UserWarning)

latest_vision_posture = "Unknown"
global bbox

# Load Machine Learning Model and Scaler
model = joblib.load(os.path.join(os.path.dirname(__file__), "models", "svm.pkl"))
scaler = joblib.load(os.path.join(os.path.dirname(__file__), "models", "scaler.pkl"))

last_log_time = None  # Store the last logged timestam

# Initialize MediaPipe Pose
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)
# Mapping of posture labels
labels = {
    0: "Upright",
    1: "Leaning Forward",
    2: "Leaning Backward",
    3: "Leaning Left",
    4: "Leaning Right"
}

# Required landmarks
required_landmarks = [
    "nose", "left_eye_inner", "left_eye", "left_eye_outer",
    "right_eye_inner", "right_eye", "right_eye_outer",
    "left_ear", "right_ear", "mouth_left", "mouth_right",
    "left_shoulder", "right_shoulder"
]

# Variables for single-subject tracking
subject_id = None
bbox = None  # Bounding box for the tracked subject
tracking_initialized = False

# Column names for keypoints
feature_names = [
    f"{landmark}_{axis}" for landmark in required_landmarks for axis in ['x', 'y', 'z']]

class Features:
    """Handles the application's backend logic."""
    
    def __init__(self):
        self.is_running = False
    
    def toggle_start(self):
        """Starts or stops the posture detection process."""
        self.is_running = not self.is_running
        return "Stop" if self.is_running else "Start"
    
    def log_message(self, message):
        """Handles log messages."""
        return f"[LOG]: {message}"
    
    def get_posture_status(self):
        """Placeholder for getting posture status from ML model."""
        return "Good Posture"  # Replace with actual model inference

class PostureDetector(QObject):
    """Handles posture detection and sends updates to the UI via signals."""
    posture_updated = pyqtSignal(str)
    notification_alert = pyqtSignal(str)  # Signal to update UI log
    notification_enabled = True  # NEW: Tracks whether notifications are on/off

    def __init__(self):
        super().__init__()
        self.is_running = False
        self.thread = None
        self.notification_enabled = False  # Default to enabled
        self.last_log_time = ""  # Track last logged second
        self.last_posture = None  # Track last detected posture
        self.posture_start_time = None  # Track when posture started
        self.last_notification = None  # Track last notification sent
        self.frame_counter = 0  # Tracks number of processed frames
        self.posture_queue = deque(maxlen=5)  # Stores last 5 postures for filtering

        self.screenshot_counts = {
            "Upright": 0,
            "Leaning Right": 0,
            "Leaning Left": 0,
            "Leaning Backward": 0,
            "Leaning Forward": 0,
            "No Pose Detected": 0
        }

        self.max_screenshots = 150  # Max screenshots per posture
        self.screenshot_dir = os.path.join(os.getcwd(), "screenshots")
        os.makedirs(self.screenshot_dir, exist_ok=True)

    def start_detection(self):
        """Start posture detection in a separate thread."""
        if not self.is_running:
            self.is_running = True
            self.thread = threading.Thread(target=self.run_pose_detection, daemon=True)
            self.thread.start()

    def stop_detection(self):
        """Stop the posture detection process."""
        self.is_running = False

    def enable_notifications(self, state):
        """Enable or disable pop-up notifications."""
        self.notification_enabled = state

    def apply_moving_average(self, new_posture):
        """Update queue and return the most frequent posture."""
        self.posture_queue.append(new_posture)  # Add new detection
        return max(set(self.posture_queue), key=self.posture_queue.count)  # Return most common posture


    def run_pose_detection(self):
        """Continuously capture frames and process posture detection."""
        global tracking_initialized, bbox
        global latest_vision_posture
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce latency
        print(f"Vision Posture: {latest_vision_posture}")

        global last_log_time  
        last_log_time = None  # Ensure it's initialized properly

        while self.is_running:
            ret, frame = cap.read()
            if not ret:
                continue

            frame = cv2.flip(frame, 1)  # Mirror effect for natural interaction
            image = frame.copy()
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = pose.process(rgb_image)

            pred = "No Pose Detected"

            if results.pose_landmarks:
                landmarks = results.pose_landmarks.landmark
                keypoints = []

                # Compute bounding box around the detected pose
                x_min = min(lm.x for lm in landmarks)
                y_min = min(lm.y for lm in landmarks)
                x_max = max(lm.x for lm in landmarks)
                y_max = max(lm.y for lm in landmarks)

                # Adjust the bounding box to include some extra space above the head
                y_min = max(0, y_min - 0.2)  # Shift the top boundary upwards by 20%

                new_bbox = (int(x_min * frame.shape[1]), int(y_min * frame.shape[0]),
                            int((x_max - x_min) * frame.shape[1]), int((y_max - y_min) * frame.shape[0]))

                if not tracking_initialized:
                    subject_id = 1  # Assign an ID to the first detected person
                    bbox = new_bbox
                    tracking_initialized = True
                else:
                    bbox = new_bbox  # Continuously update the bounding box to track movement

                # Ensure keypoints are extracted only from the tracked subject
                keypoints = []
                for landmark_name in required_landmarks:
                    lm = getattr(mp_pose.PoseLandmark, landmark_name.upper())
                    keypoints.extend(
                        [landmarks[lm].x, landmarks[lm].y, landmarks[lm].z])

                if keypoints:
                    keypoints = np.array(keypoints).reshape(1, -1)
                    keypoints_df = pd.DataFrame(keypoints, columns=feature_names)

                    try:
                        keypoints_scaled = scaler.transform(keypoints_df)
                        pred_label = model.predict(keypoints_scaled)[0]
                        pred_probs = model.predict_proba(keypoints_scaled)[0]
                        pred = labels.get(pred_label, "Unknown Posture")
                        prob = pred_probs[pred_label]
                    except Exception as e:
                        print(f"Error during prediction: {e}")

            # Apply filtering to stabilize posture classification
            filtered_posture = self.apply_moving_average(pred)

            # Initialize drawing utils
            mp_drawing = mp.solutions.drawing_utils

            # Draw pose landmarks on the image (only if landmarks exist)
            if results.pose_landmarks:
                mp_drawing.draw_landmarks(
                    image,
                    results.pose_landmarks,
                    mp.solutions.pose.POSE_CONNECTIONS,
                    mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=2),
                    mp_drawing.DrawingSpec(color=(255, 0, 0), thickness=2)
                )

            # Put the posture label as overlay text
            # cv2.putText(image, f"Posture: {filtered_posture}", (10, 30),
            #             cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2, cv2.LINE_AA)

            # Save the screenshot
            if filtered_posture in self.screenshot_counts and self.screenshot_counts[filtered_posture] < self.max_screenshots:
                posture_folder = os.path.join(self.screenshot_dir, filtered_posture.replace(" ", "_"))
                os.makedirs(posture_folder, exist_ok=True)

                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")[:-3]
                filename = f"{filtered_posture.replace(' ', '_')}_{timestamp}.jpg"
                filepath = os.path.join(posture_folder, filename)

                cv2.imwrite(filepath, image) 
                #print(f"Saved screenshot: {filepath}")
                self.screenshot_counts[filtered_posture] += 1

                
            latest_vision_posture = filtered_posture
            self.posture_updated.emit(filtered_posture)

            # Increment frame counter
            self.frame_counter += 1

            # Log to database every 5 frames (~2 times per second)
            if self.frame_counter % 5 == 0:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                posture_database.save_posture(filtered_posture, timestamp=timestamp)

            # Display prediction and probability
            if 'prob' in locals() and prob is not None:
                cv2.putText(image, f"Posture: {pred}", (50, 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2, cv2.LINE_AA)
            else:
                cv2.putText(image, f"Posture: {pred}", (50, 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2, cv2.LINE_AA)

            # Draw bounding box
            if bbox:
                x, y, w, h = bbox
                cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.putText(image, "", (x, y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA)

            # Draw landmarks
            mp.solutions.drawing_utils.draw_landmarks(
                image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

            # Show webcam feed
            cv2.imshow('Webcam Feed', image)

            # Exit if window was closed or 'q' was pressed
            if cv2.getWindowProperty('Webcam Feed', cv2.WND_PROP_VISIBLE) == 0:
                self.is_running = False
                break

            if cv2.waitKey(10) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()

def get_latest_vision_posture():
    return latest_vision_posture

def run():
    """Standalone execution entry point."""
    try:
        detector = PostureDetector()
        detector.is_running = True
        detector.run_pose_detection()
    except KeyboardInterrupt:
        print("\n[INFO] Stopping posture detection.")
        detector.is_running = False

if __name__ == "__main__":
    run()