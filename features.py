import sys
import os
import cv2
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
import posture_database
import warnings

warnings.filterwarnings("ignore", category=UserWarning)

latest_vision_posture = "Unknown"

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
    
    def toggle_alert(self, toggle_state):
        """Handles alert toggles."""
        return "Enabled" if toggle_state else "Disabled"
    
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
        self.posture_queue = deque(maxlen=1)  # Stores last 5 postures for filtering

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

    
    def check_posture_duration(self, current_posture):
        """Tracks how long the user maintains a posture and triggers notifications."""
        #print(f"Current posture detected: {current_posture}")  # Debugging step

        good_posture = "Upright"
        bad_postures = {"Leaning Forward", "Leaning Backward", "Leaning Left", "Leaning Right"}

        # If posture changed, reset the timer
        if current_posture != self.last_posture:
            self.last_posture = current_posture
            self.posture_start_time = time.time()
            self.last_notification = None  # Reset notification tracker ✅
            print(f"New posture detected. Reset timer.")  # Debugging step

        elapsed_time = time.time() - self.posture_start_time
        print(f"Elapsed time: {elapsed_time:.2f} seconds")  # Debugging step

        # Send notification ONLY if it hasn't been sent yet
        if current_posture == good_posture and elapsed_time >= 4 and self.last_notification != "good":
            print("✅ Good posture notification triggered!")  # Debugging step
            self.send_notification("Good Posture! Keep It Up.")
            self.last_notification = "good"  # ✅ Prevent repeated alerts

        elif current_posture in bad_postures and elapsed_time >= 15 and self.last_notification != "bad":
            print("❌ Bad posture notification triggered!")  # Debugging step
            self.send_notification("Bad Posture! Fix your sitting position.")
            self.last_notification = "bad"  # ✅ Prevent repeated alerts


    def send_notification(self, message):
        """Sends a desktop notification if enabled."""
        print(f"Sending notification: {message}")  # Debugging step
        self.notification_alert.emit(message)  # Update UI log
        
        if self.notification_enabled:  # Only show pop-up if enabled
            print("Notification enabled, displaying popup...")  # Debugging step
            notification.notify(
                title="Posture Alert",
                message=message,
                timeout=5
            )
        else:
            print("Notification is disabled in UI.")  # Debugging step

    def apply_moving_average(self, new_posture):
        """Update queue and return the most frequent posture."""
        self.posture_queue.append(new_posture)  # Add new detection
        return max(set(self.posture_queue), key=self.posture_queue.count)  # Return most common posture


    def run_pose_detection(self):
        """Continuously capture frames and process posture detection."""
        global tracking_initialized
        global latest_vision_posture
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce latency

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
            results = pose.process(image)

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
            posture_database.save_posture(filtered_posture)  # Save to database

            # **Fix duplicate logging**
            current_time = time.strftime("%Y-%m-%d %H:%M:%S")  # Get timestamp
            if last_log_time != current_time:  # Ensure only 1 log per second
                last_log_time = current_time
                latest_vision_posture = filtered_posture
                self.posture_updated.emit(filtered_posture)  # Update UI log

            self.check_posture_duration(filtered_posture)  # Check duration

            time.sleep(0.1)  # Reduce delay for smoother updates

        cap.release()

def get_latest_vision_posture():
    return latest_vision_posture
