import requests
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import csv
import os
import tkinter as tk
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

chair_layout = np.array([
    [1,   0,   0,   0,   4],
    [2,   0,   8,   0,   5],
    [3,   0,   9,   0,   6],
    [7,   0,   0,   0,   10],
    [0,   11,  12,  13,  0]
])

# Initialize GUI
root = tk.Tk()
root.title("Real-Time Pressure Sensor Heatmap")

# Create a Matplotlib figure for the heatmap
fig, ax = plt.subplots(figsize=(6, 6))

# Initialize heatmap with dummy values
dummy_matrix = np.full_like(chair_layout, np.nan, dtype=np.float64)
heatmap = sns.heatmap(dummy_matrix, annot=False, cmap="RdYlGn_r",
                      linewidths=1, linecolor="gray", cbar=True, ax=ax, vmin=0, vmax=10)

# Embedding Matplotlib figure inside Tkinter
canvas = FigureCanvasTkAgg(fig, master=root)
canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

# Recording state
is_recording = False
csv_filename = None
csv_file = None
csv_writer = None


def start_recording():
    """Start recording data to a single CSV file"""
    global is_recording, csv_filename, csv_file, csv_writer
    if not is_recording:
        csv_filename = "pressure_data.csv"  # Fixed filename
        file_exists = os.path.isfile(csv_filename)  # Check if file exists

        csv_file = open(csv_filename, mode='a', newline='')  # Open in append mode
        csv_writer = csv.writer(csv_file)

        if not file_exists:
            csv_writer.writerow(["Timestamp"] + SENSOR_LABELS)  # Write header only if file does not exist

        is_recording = True
        start_button.config(state=tk.DISABLED)
        stop_button.config(state=tk.NORMAL)
        print(f"Recording started: {csv_filename}")


def stop_recording():
    """Stop recording and close CSV file"""
    global is_recording, csv_file
    if is_recording:
        is_recording = False
        if csv_file:
            csv_file.close()  # Close the file properly
        start_button.config(state=tk.NORMAL)
        stop_button.config(state=tk.DISABLED)
        print("Recording stopped.")
    
def update(frame):
    """Update the heatmap and log data if recording is active"""
    global chair_layout, is_recording, csv_writer

    try:
        response = requests.get(f"{NODEMCU_IP}{ENDPOINT}", timeout=3)
        if response.status_code == 200:
            csv_data = response.text.strip()
            sensor_values = csv_data.split(",")

            if len(sensor_values) == len(SENSOR_LABELS):
                sensor_values = [float(v) for v in sensor_values]

                sensor_matrix = np.full_like(
                    chair_layout, np.nan, dtype=np.float64)
                annot_matrix = np.full_like(chair_layout, "", dtype=object)

                for i, sensor_index in enumerate(chair_layout.flatten()):
                    if sensor_index > 0:
                        value = sensor_values[sensor_index - 1]
                        sensor_matrix[np.where(
                            chair_layout == sensor_index)] = value
                        annot_matrix[np.where(
                            chair_layout == sensor_index)] = f"S{sensor_index}: {value:.1f}"

                # Update heatmap
                ax.clear()
                ax.set_title("Real-Time Pressure Sensor Heatmap")
                ax.set_xticks([])
                ax.set_yticks([])
                sns.heatmap(sensor_matrix, annot=annot_matrix, fmt="", cmap="RdYlGn_r",
                            linewidths=1, linecolor="gray", cbar=False, ax=ax, vmin=0, vmax=10)

                # Keep original color bar
                ax.collections[0].colorbar = heatmap.collections[0].colorbar

                # Save data if recording
                if is_recording:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    with open("pressure_data.csv", mode='a', newline='') as csv_file:
                        csv_writer = csv.writer(csv_file)
                        csv_writer.writerow([timestamp] + sensor_values)

        canvas.draw()  # Update Tkinter canvas

    except requests.RequestException as e:
        print(f"Warning: Request failed: {e}")

# Add Start and Stop buttons
button_frame = tk.Frame(root)
button_frame.pack(side=tk.BOTTOM, pady=10)

start_button = tk.Button(button_frame, text="Start Recording",
                         command=start_recording, fg="white", bg="green", font=("Arial", 12))
start_button.pack(side=tk.LEFT, padx=10)

stop_button = tk.Button(button_frame, text="Stop Recording", command=stop_recording,
                        fg="white", bg="red", font=("Arial", 12), state=tk.DISABLED)
stop_button.pack(side=tk.RIGHT, padx=10)


if __name__ == "__main__":
    ani = FuncAnimation(fig, update, interval=1000)
    root.mainloop()
