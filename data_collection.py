import requests
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import tkinter as tk
import csv
from datetime import datetime
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.animation import FuncAnimation

# NodeMCU Server IP (Change this to your actual IP)
NODEMCU_IP = "http://192.168.121.112"
ENDPOINT = "/get_data"

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

# Threshold for detecting a user
USER_DETECTION_THRESHOLD = 1.0
UPRIGHT_HIP_THRESHOLD = 15.0  # Minimum percentage load for sensors 3 and 6

# Initialize GUI
root = tk.Tk()
root.title("Real-Time Pressure Sensor Heatmap")

# Create a Matplotlib figure for the heatmap
fig, ax = plt.subplots(figsize=(6, 6))
cbar = None  # Variable to hold the color bar reference

# Initialize heatmap with dummy values
dummy_matrix = np.full_like(chair_layout, np.nan, dtype=np.float64)
heatmap = sns.heatmap(dummy_matrix, annot=False, cmap="RdYlGn_r",
                      linewidths=1, linecolor="gray", cbar=True, ax=ax, vmin=0, vmax=10)
cbar = heatmap.collections[0].colorbar  # Store the color bar

# Embedding Matplotlib figure inside Tkinter
canvas = FigureCanvasTkAgg(fig, master=root)
canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

# Label for detected posture
posture_label = tk.Label(root, text="Detecting...", font=("Arial", 14, "bold"))
posture_label.pack(pady=10)

# Recording state
is_recording = False
csv_filename = None
csv_file = None
csv_writer = None


def classify_posture(sensor_values):
    """Classifies posture based on sensor data"""
    total_force = sum(sensor_values)
    if total_force < USER_DETECTION_THRESHOLD:
        return "No User Detected"

    percentages = [(v / total_force) * 100 for v in sensor_values]
    upright_sensors = [1, 2, 3, 4, 5, 6, 7, 10, 11, 12, 13]
    left_sensors = [1, 2, 3, 7]
    right_sensors = [4, 5, 6, 10]
    forward_sensors = [1, 2, 3, 4, 5, 6]
    back_sensors = [7, 10, 11, 12, 13]

    # New condition for detecting upright posture based on hip sensors (3 and 6)
    # if percentages[2] > UPRIGHT_HIP_THRESHOLD and percentages[5] > UPRIGHT_HIP_THRESHOLD:
    #     return "Correct Posture"
    # if sum(percentages[i-1] for i in upright_sensors) < 10:
    #     return "Correct Postures"
    if sum(percentages[i-1] for i in left_sensors) > 50:
        return "Incorrect Posture"
    elif sum(percentages[i-1] for i in right_sensors) > 50:
        return "Incorrect Posture"
    elif sum(percentages[i-1] for i in forward_sensors) > 50:
        return "Incorrect Posture"
    elif sum(percentages[i-1] for i in back_sensors) > 50:
        return "Incorrect Posture"

    return "Correct Posture"


def update(frame):
    """Update the heatmap and detect posture"""
    global chair_layout, cbar, is_recording, csv_writer, heatmap
    try:
        response = requests.get(f"{NODEMCU_IP}{ENDPOINT}", timeout=3)
        if response.status_code == 200:
            sensor_values = list(map(float, response.text.strip().split(",")))
            if len(sensor_values) == len(SENSOR_LABELS):
                sensor_matrix = np.full_like(
                    chair_layout, np.nan, dtype=np.float64)
                annot_matrix = np.full_like(chair_layout, "", dtype=object)

                # Assign values to the correct sensor locations in the matrix
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

                # Reuse the existing color bar (update instead of re-creating)
                if cbar:
                    cbar.update_normal(heatmap.collections[0])
                else:
                    cbar = heatmap.collections[0].colorbar

                # Classify posture
                posture = classify_posture(sensor_values)
                posture_label.config(text=f"Detected: {posture}")

                canvas.draw()
    except requests.RequestException as e:
        print(f"Warning: Request failed: {e}")


# Animation for updating heatmap
ani = FuncAnimation(fig, update, interval=1000)

# Run Tkinter main loop
root.mainloop()
