import cv2
import mediapipe as mp
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
import joblib

# Initialize MediaPipe Pose
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)
mp_drawing = mp.solutions.drawing_utils

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

# Column names for keypoints
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

# Variables for single-subject tracking
subject_id = None
bbox = None  # Bounding box for the tracked subject
tracking_initialized = False

# Start Webcam
cap = cv2.VideoCapture(0)
print("Press 'q' to quit the webcam feed.")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        print("Camera feed unavailable!")
        break

    frame = cv2.flip(frame, 1)
    image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    image.flags.writeable = False
    results = pose.process(image)
    image.flags.writeable = True
    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

    pred = "No Pose Detected"
    prob = None
    new_bbox = None

    if results.pose_landmarks:
        landmarks = results.pose_landmarks.landmark

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

    # Display prediction and probability
    if prob is not None:
        cv2.putText(image, f"Posture: {pred} ({prob*100:.2f}%)", (50, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2, cv2.LINE_AA)
    else:
        cv2.putText(image, f"Posture: {pred}", (50, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2, cv2.LINE_AA)

    # Draw bounding box around tracked subject
    if bbox:
        x, y, w, h = bbox
        cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.putText(image, "Tracking", (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA)

    mp_drawing.draw_landmarks(
        image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)
    cv2.imshow('Webcam Feed', image)

    if cv2.waitKey(10) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
