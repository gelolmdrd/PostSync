import requests
import time
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import tkinter as tk
from datetime import datetime
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.animation import FuncAnimation
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5.QtWidgets import QLabel
import tkinter as tk
import threading
from datetime import datetime
from collections import deque

# NodeMCU Server IP (Change this to your actual IP)
NODEMCU_IP = "http://192.168.43.57"
ENDPOINT = "/get_data"
ENDPOINT_TRIGGER = "/haptic"

HAPTIC_TRIGGER_INTERVAL = 0  # Seconds before another haptic trigger
HAPTIC_DETECTION_TIME = 30    # Posture must be incorrect for 10 sec before triggering
last_haptic_trigger_time = 0  # Stores last trigger time
incorrect_posture_start_time = None  # Start time for incorrect posture
haptic_active = True  # Track if haptic feedback is currently on
recording = False
latest_pressure_posture = "Unknown"
pressure_sensor_error_notified = False
posture_queue = deque(maxlen=5)  # Stores last 5 pressure postures
last_filtered_posture = None     # Tracks last filtered result
haptic_enabled = True  # Controlled by the UI toggle


SENSOR_LABELS = [
    "Sensor_1", "Sensor_2", "Sensor_3",
    "Sensor_4", "Sensor_5", "Sensor_6",
    "Sensor_7", "Sensor_8", "Sensor_9",
    "Sensor_10", "Sensor_11", "Sensor_12", "Sensor_13"
]

# Chair layout representation
chair_layout = np.array([
    [1,   0,   0,   0,   4],
    [2,   0,   8,   0,   5],
    [3,   0,   9,   0,   6],
    [7,   0,   0,   0,   10],
    [0,   11,  12,  13,  0]
])

# Thresholds
USER_DETECTION_THRESHOLD = 3.0

# Create Matplotlib figure for the heatmap
fig, ax = plt.subplots(figsize=(6, 6))
cbar = None  # Variable to hold the color bar reference

# Initialize heatmap with dummy values
dummy_matrix = np.full_like(chair_layout, np.nan, dtype=np.float64)
heatmap = sns.heatmap(dummy_matrix, annot=False, cmap="RdYlGn_r",
                      linewidths=1, linecolor="gray", cbar=True, ax=ax, vmin=0, vmax=10)
cbar = heatmap.collections[0].colorbar  # Store the color bar

# Embedding Matplotlib figure inside Tkinter
canvas = FigureCanvas(fig)  #Use PyQt-compatible canvas

# Label for detected posture

posture_label = QLabel("Detecting...")
posture_label.setStyleSheet("font-size: 14px; font-weight: bold; font-family: Arial;")

def apply_posture_filter(new_posture):
    """Apply a moving average (majority vote) filter to smooth posture."""
    posture_queue.append(new_posture)
    if len(posture_queue) == posture_queue.maxlen:
        return max(set(posture_queue), key=posture_queue.count)
    else:
        return new_posture  # Not enough data yet, return raw

def start_recording():
    """Starts collecting data and updating the application."""
    global recording
    recording = True

    def collect_data():
        while recording:
            update(None)  # Calls the update function to collect data
            time.sleep(0.5)  # Adjust sleep time to match data update rate

    data_thread = threading.Thread(target=collect_data, daemon=True)
    data_thread.start()

def stop_recording():
    """Stops collecting data."""
    global recording
    recording = False
    
def classify_posture(sensor_values, ui_callback=None):
    """Classifies posture based on sensor data and updates UI"""
    total_force = sum(sensor_values)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[INFO][{timestamp}] Raw Sensor Values: {sensor_values}")
    print(f"[INFO][{timestamp}] Total Force: {total_force:.2f}")
    
    if total_force < USER_DETECTION_THRESHOLD:
        posture = "No User Detected"
    else:
        percentages = [v / total_force * 100 for v in sensor_values]
        sensor_groups = {
            "left": [0, 1, 2, 6],
            "right": [3, 4, 5, 9],
            "forward": [0, 1, 2, 3, 4, 5],
            "back": [6, 9, 10, 11, 12]
        }
        
        # Calculate zone pressure distributions
        zone_distribution = {
            zone: sum(percentages[i] for i in indices)
            for zone, indices in sensor_groups.items()
        }

        # Log the zone distribution
        print("[INFO][{timestamp}] Zone Pressure Distribution:")
        for zone, pct in zone_distribution.items():
            print(f"{zone.capitalize()}: {pct:.2f}%")
        
        posture = "Correct Posture"  # Default to correct posture
        for indices in sensor_groups.values():
            if sum(percentages[i] for i in indices) > 55:
                posture = "Incorrect Posture"
                break

    # **Send update to app.py**
    if ui_callback:
        ui_callback(posture)

    global latest_pressure_posture
    latest_pressure_posture = posture

    return posture

import threading

def set_haptic_enabled(state: bool):
    global haptic_enabled
    haptic_enabled = state

def check_and_trigger_haptic(sensor_values):
    """Triggers haptic feedback as a pulse when incorrect posture is detected."""
    global last_haptic_trigger_time, incorrect_posture_start_time, haptic_active, raw_posture, filtered_posture

    raw_posture = classify_posture(sensor_values)
    filtered_posture = apply_posture_filter(raw_posture)
    posture = filtered_posture  # Use this throughout below
    current_time = time.time()
    
    if not haptic_enabled:
        return  # Haptic feedback is currently disabled
    
    if posture == "Incorrect Posture":
        if incorrect_posture_start_time is None:
            incorrect_posture_start_time = current_time  # Start timer

        if current_time - incorrect_posture_start_time >= HAPTIC_DETECTION_TIME:
            if current_time - last_haptic_trigger_time >= HAPTIC_TRIGGER_INTERVAL:
                try:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    print(f"[{timestamp}]" "Triggering haptic feedback (1)")
                    requests.get(f"{NODEMCU_IP}{ENDPOINT_TRIGGER}?trigger=1")
                    haptic_active = True
                    last_haptic_trigger_time = current_time

                    # Turn off haptic after 100ms (0.1s) without blocking
                    def stop_haptic():
                        try:
                            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                            print(f"[{timestamp}]" "Turning off haptic feedback (0)")
                            requests.get(f"{NODEMCU_IP}{ENDPOINT_TRIGGER}?trigger=0")
                            haptic_active = False
                        except requests.RequestException as e:
                            print(f"Warning: Haptic stop request failed: {e}")

                    threading.Timer(0.1, stop_haptic).start()

                except requests.RequestException as e:
                    print(f"Warning: Haptic request failed: {e}")
    else:
        incorrect_posture_start_time = None  # Reset timer


def update_posture_in_app(posture, parent_widget=None):
    """Update posture in the UI."""
    from app import HomePage  #Import inside the function

    if parent_widget and isinstance(parent_widget, HomePage):
        parent_widget.update_pressure_posture(posture)
posture = "unknown"

def update(frame):
    """Update the heatmap and detect posture"""
    global chair_layout, cbar, heatmap, posture
    global pressure_sensor_error_notified  # Track if error was already 

    try:
        response = requests.get(f"{NODEMCU_IP}{ENDPOINT}", timeout=3)
        response.raise_for_status()  # Raise an error if response status is not 200

        sensor_values = list(map(float, response.text.strip().split(",")))
        if len(sensor_values) == len(SENSOR_LABELS):
            sensor_matrix = np.full_like(
                chair_layout, np.nan, dtype=np.float64)
            annot_matrix = np.full_like(chair_layout, "", dtype=object)

            # Assign values to correct sensor locations
            for i, sensor_index in enumerate(chair_layout.flatten()):
                if sensor_index > 0:
                    value = sensor_values[sensor_index - 1]
                    sensor_matrix[np.where(
                        chair_layout == sensor_index)] = value
                    annot_matrix[np.where(
                        chair_layout == sensor_index)] = f"{value:.1f}"

            # Remove previous heatmap and redraw with updated values
            ax.clear()
            ax.set_title("Real-Time Pressure Sensor Heatmap")

            heatmap = sns.heatmap(
                sensor_matrix, annot=annot_matrix, fmt="s", cmap="RdYlGn_r",
                linewidths=1, linecolor="gray", cbar=False, ax=ax, vmin=0, vmax=10
            )

            # Reuse existing color bar
            if cbar:
                cbar.update_normal(heatmap.collections[0])
            else:
                cbar = heatmap.collections[0].colorbar

            # Classify posture and update label
            posture = classify_posture(sensor_values)

            update_posture_in_app(posture)
            posture_label.setText(f"Detected: {posture}")  #Still updates local UI

            # Check for haptic feedback trigger
            check_and_trigger_haptic(sensor_values)

            canvas.draw()

            #Reset error notification if successful
            pressure_sensor_error_notified = False

    except requests.exceptions.RequestException as e:
        if not pressure_sensor_error_notified:
            print(f"Warning: Pressure sensor is not responding. Error: {e}")
            pressure_sensor_error_notified = True
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] Raw: {raw_posture} | Filtered: {filtered_posture}")

#Simple getter
def get_latest_pressure_posture():
    return latest_pressure_posture

# Animation for updating heatmap
ani = None  # Global variable

def setup_animation():
    global ani
    ani = FuncAnimation(fig, update, interval=500, cache_frame_data=False)

if __name__ == "__main__":  
    setup_animation()
    start_recording()  # Or your main function
    plt.show()  # Keep this if you need the heatmap to display

