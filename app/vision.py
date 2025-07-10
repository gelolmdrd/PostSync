import cv2
import mediapipe as mp
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
import joblib

# Initialize MediaPipe Pose
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)

# Load Pretrained Model and Scaler
model = joblib.load('./models/svm.pkl')
scaler = joblib.load('./models/scaler.pkl')

# List of required landmarks
required_landmarks = [
    "nose", "left_eye_inner", "left_eye", "left_eye_outer",
    "right_eye_inner", "right_eye", "right_eye_outer",
    "left_ear", "right_ear", "mouth_left", "mouth_right",
    "left_shoulder", "right_shoulder"
]

# Column names for the keypoints
feature_names = [
    f"{landmark}_{axis}" for landmark in required_landmarks for axis in ['x', 'y', 'z']]

# Mapping of posture labels
labels = {
    0: "upright",
    1: "leaning_forward",
    2: "leaning_backward",
    3: "leaning_left",
    4: "leaning_right"
}


def get_posture():
    """Captures a single frame and predicts the sitting posture."""
    cap = cv2.VideoCapture(0)
    ret, frame = cap.read()
    cap.release()

    if not ret:
        return "No Camera Feed"

    # Flip frame horizontally for mirror effect
    frame = cv2.flip(frame, 1)

    # Convert to RGB
    image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Process with MediaPipe Pose
    results = pose.process(image)

    # Default prediction
    pred = "No Pose Detected"

    if results.pose_landmarks:
        landmarks = results.pose_landmarks.landmark

        # Extract required keypoints
        keypoints = []
        for landmark_name in required_landmarks:
            lm = getattr(mp_pose.PoseLandmark, landmark_name.upper())
            keypoints.extend(
                [landmarks[lm].x, landmarks[lm].y, landmarks[lm].z])

        # Convert to DataFrame
        keypoints_df = pd.DataFrame([keypoints], columns=feature_names)

        # Preprocess and Predict
        try:
            keypoints_scaled = scaler.transform(keypoints_df)
            pred_label = model.predict(keypoints_scaled)[0]
            pred = labels.get(pred_label, "Unknown Posture")
        except Exception as e:
            return f"Error: {e}"

    return pred
