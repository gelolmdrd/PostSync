import sys
import mediapipe as mp
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QTabWidget, QScrollArea, QFrame,
    QLabel, QPushButton, QTextEdit, QCheckBox, QStackedWidget, QSpacerItem, QSizePolicy
)
from PyQt5.QtGui import QPixmap, QIcon, QFont
from PyQt5.QtCore import Qt
from features import Features, PostureDetector
from datetime import datetime
from matplotlib.figure import Figure
from matplotlib.image import imread
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5.QtCore import QTimer
import numpy as np
import matplotlib.animation as animation
from scipy.ndimage import gaussian_filter
import threading
import requests
import data_collection # Import data_collection.py
import csv
import sqlite3
import posture_database
import traceback
from features import get_latest_vision_posture
from data_collection import get_latest_pressure_posture

def print_current_postures():
    print("Vision Posture:", get_latest_vision_posture())
    print("Pressure Posture:", get_latest_pressure_posture())
    print("Final Posture:", print_final_posture())

def get_final_posture_classification(vision_posture, pressure_posture):
    vision_posture = get_latest_vision_posture()
    pressure_posture = get_latest_pressure_posture()
    if vision_posture == "No Pose Detected" or pressure_posture == "No User Detected":
        return "No Person Detected"
    elif vision_posture == "Upright" and pressure_posture == "Correct Posture":
        return "Correct Posture"
    else:
        return "Incorrect Posture"

def print_final_posture():
    vision = get_latest_vision_posture()
    pressure = get_latest_pressure_posture()
    final_posture = get_final_posture_classification(vision, pressure)

    return final_posture

NODEMCU_IP = "http://192.168.43.57"  # Ensure this matches your NodeMCU IP
ENDPOINT = "/get_data"


class UIHelper:
    """Utility class for reusable UI components and styles."""
    @staticmethod
    def create_label(text, font_size=12, fixed_size=None, align=None):
        label = QLabel(text)
        font = QFont("Roboto", font_size)
        label.setFont(font)
        label.setStyleSheet(f"color: #F1F1F1; font-size: {font_size}px; margin: 0px; padding: 0px;")
        label.setContentsMargins(0, 0, 0, 0)  # No padding inside label
        # Set border using styleshee
        if fixed_size:
            label.setFixedSize(*fixed_size)
        if align:
            label.setAlignment(align)
        return label

    @staticmethod
    def create_button(text, width=170, height=36, callback=None):
        button = QPushButton(text)
        button.setStyleSheet(
            "background-color: white; color: black; padding: 5px; border-radius: 8px")
        button.setFixedSize(width, height)
        if callback:
            button.clicked.connect(callback)
        return button

    @staticmethod
    def update_toggle_icon(toggle, state):
        toggle.setIcon(
            QIcon("./assets/toggleOn.png" if state else "./assets/toggleOff.png"))


class HomePage(QWidget):
    def __init__(self, stacked_widget, logs_page):
        super().__init__()
        self.stacked_widget = stacked_widget
        self.logs_page = logs_page   # Reference Logs page 

        self.features = Features()
        self.detector = PostureDetector()  # Initialize PostureDetector
        self.detector.posture_updated.connect(self.update_posture_status)
        self.detector.notification_alert.connect(self.show_notification)
        self.vision_posture = "Unknown"  # Store the last detected vision posture
        self.pressure_posture = "Unknown"  # Store the last detected pressure posture
        self.init_ui()
        self.setup_pressure_heatmap()

    def init_ui(self):
        main_layout = QHBoxLayout()
        main_layout.setSpacing(45)
        left_layout = self.create_left_section()
        right_layout = self.create_right_section()
        main_layout.addLayout(left_layout)
        main_layout.addLayout(right_layout)
        self.setLayout(main_layout)

    def setup_pressure_heatmap(self):
        """Initialize the pressure heatmap but do NOT start animation until Start is clicked."""
        self.ax = self.pressure_canvas.figure.add_subplot(111)
        # ✅ Do NOT start animation automatically
        self.ani = None

        self.chair_layout = np.array([
            [1,  0,  0,  0,  4],
            [2,  0,  8,  0,  5],
            [3,  0,  9,  0,  6],
            [7,  0,  0,  0, 10],
            [0, 11, 12, 13,  0]
        ])

        self.heatmap_data = np.full_like(self.chair_layout, np.nan, dtype=np.float64)

        if not hasattr(self, 'heatmap') or self.heatmap is None:
            self.ax.clear()
            self.heatmap = self.ax.imshow(self.heatmap_data, cmap="RdYlGn_r", interpolation="nearest", animated=True, vmin=0, vmax=10)

            self.ax.set_xticks([])
            self.ax.set_yticks([])  

        self.pressure_canvas.figure.tight_layout()
        
    def run_data_collection():
        """Start data collection as a background process."""
        data_collection.start_recording()  # Ensure this function starts the haptic feedback loop

    def update_pressure_heatmap(self, frame):
        """Fetch real sensor data and update the heatmap."""
        try:
            response = requests.get(f"{NODEMCU_IP}{ENDPOINT}", timeout=3)
            if response.status_code == 200:
                csv_data = response.text.strip()
                sensor_values = [float(v) for v in csv_data.split(",")]

                if len(sensor_values) == 13:
                    sensor_matrix = np.full_like(self.chair_layout, np.nan, dtype=np.float64)
                    
                    for i, sensor_index in enumerate(self.chair_layout.flatten()):
                        if sensor_index > 0:
                            sensor_matrix[np.where(self.chair_layout == sensor_index)] = sensor_values[sensor_index - 1]

                    self.heatmap.set_data(sensor_matrix)
                    self.pressure_canvas.figure.canvas.draw_idle()

        except requests.RequestException as e:
            print(f"Warning: Failed to get sensor data: {e}")

    def create_left_section(self):
        left_layout = QVBoxLayout()
        left_layout.setSpacing(0)
        left_layout.setContentsMargins (0, 0, 0, 0)

        # Logo
        logo_label = QLabel()
        logo_label.setPixmap(QPixmap("assets/PostSync Logo_scaled.png"))
        logo_label.setAlignment(Qt.AlignLeft)
        logo_label.setFixedSize(242, 65)
        left_layout.addWidget(logo_label)

        # Pressure Data
        left_layout.addWidget(UIHelper.create_label(
            "Pressure Data", 14, (170, 16)))

        # Placeholder for displaying the heatmap of pressure data from the sensors
        self.pressure_layout = QVBoxLayout()
        self.pressure_canvas = FigureCanvas(Figure(figsize=(3, 3)))  # Matplotlib Figure
        self.pressure_canvas.setFixedSize(225, 225)  # Set fixed pixel size (width x height)
        self.pressure_layout.addWidget(self.pressure_canvas)
        left_layout.addLayout(self.pressure_layout)

        # Current Posture
        left_layout.addWidget(UIHelper.create_label(
            "Current Posture", 14, (170, 16)))
        
        # Placeholder for displaying current posture status
        self.posture_status = UIHelper.create_label("", fixed_size=(200, 48))
        self.posture_status.setStyleSheet(
            "border: 1px solid #F1F1F1; border-radius: 8px; padding: 5px; color: white; font-weight: bold;")
        left_layout.addWidget(self.posture_status)

        return left_layout

    def create_right_section(self):
        right_layout = QVBoxLayout()
        right_layout.setSpacing(0)
        right_layout.setContentsMargins (0, 0, 0, 0)

        # Create QLabel to display the guidelines image
        self.guidelines_image = QLabel()
        pixmap = QPixmap("./assets/guidelines.png")

        # Optional: scale the image to fit the QLabel size
        pixmap = pixmap.scaled(400, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.guidelines_image.setPixmap(pixmap)
        self.guidelines_image.setFixedSize(420, 300)
        self.guidelines_image.setAlignment(Qt.AlignCenter)

        # Apply rounded corners using stylesheet
        self.guidelines_image.setStyleSheet("""
            border-radius: 12px;
            border: 1px solid #ccc;
            background-color: #f8f8f8;
            padding: 4px;
        """)

        right_layout.addWidget(self.guidelines_image)

        bottom_layout = self.create_bottom_controls()
        right_layout.addLayout(bottom_layout)
        return right_layout

    def create_bottom_controls(self):
        bottom_layout = QHBoxLayout()
        
        # Create controls section
        controls_section = QVBoxLayout()
                
        controls_section.addWidget(UIHelper.create_label("Power", 12, (170, 16)))
        self.start_button = UIHelper.create_button("Start")
        self.start_button.clicked.connect(self.handle_start)
        controls_section.addWidget(self.start_button)
        controls_section.addWidget(UIHelper.create_label("Logs", 12, (170, 16)))
        self.logs_button = UIHelper.create_button("Show Logs", callback=self.go_to_logs)
        controls_section.addWidget(self.logs_button)
        
        # Add controls section to bottom layout
        bottom_layout.addLayout(controls_section)

        # Add spacing before the alerts section
        bottom_layout.addSpacerItem(QSpacerItem(
            48, 48, QSizePolicy.Minimum, QSizePolicy.Fixed))
        
        # Create alerts section
        alerts_section = QVBoxLayout()
        
        alerts_section.addWidget(UIHelper.create_label("Alerts", 14, (170, 16)))

        # Haptic Feedback Toggle
        haptic_layout = self.create_toggle_section("Haptic Feedback")
        self.haptic_toggle = haptic_layout[1]
        alerts_section.addLayout(haptic_layout[0])

        # Notifications Toggle
        notif_layout = self.create_toggle_section("Notifications")
        self.notif_toggle = notif_layout[1]
        self.notif_toggle.stateChanged.connect(self.toggle_notifications)
        alerts_section.addLayout(notif_layout[0])
        
        # Add alerts section to bottoms layout
        bottom_layout.addLayout(alerts_section)

        return bottom_layout
    
    def show_logs(self):
        self.logs_page = LogsPage(self)
        self.setCentralWidget(self.logs_page)

    def go_to_logs(self):
        """Switch to the logs page when the Show Logs button is clicked."""
        self.stacked_widget.setCurrentWidget(self.stacked_widget.widget(1)) 
    
    def toggle_notifications(self, state):
        """Enable or disable pop-up notifications based on user toggle."""
        enabled = state == Qt.Checked  # Convert checkbox state to True/False
        self.detector.enable_notifications(enabled)
        
        status = "enabled" if enabled else "disabled"
        print(f"Notifications {status}")  # Debugging step
        self.logs_page.append_log(f"[SETTINGS]: Notifications {status}")


    def show_notification(self, message):
        """Display notification alerts in the log."""
        self.logs_page.append_log(f"[ALERT]: {message}")

    def create_toggle_section(self, label_text):
        layout = QHBoxLayout()
        layout.addWidget(UIHelper.create_label(label_text, 12, (120, 24)))
        toggle = QCheckBox()
        toggle.setIcon(QIcon("./assets/toggleOff.png"))
        toggle.setIconSize(QPixmap("./assets/toggleOff.png").size())
        toggle.setStyleSheet(
            "QCheckBox::indicator { width: 0px; height: 0px; }")
        toggle.stateChanged.connect(
            lambda state: UIHelper.update_toggle_icon(toggle, state))
        layout.addWidget(toggle)
        return layout, toggle
    
    def update_posture_status(self, posture):
        """Update the UI with the detected posture and log it with a timestamp."""
        self.posture_status.setText(print_final_posture())

        # Get current date and time
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
        # Append log message with timestamp
        self.logs_page.append_log(f"[{current_time}] Detected posture: {posture}")

    def log_posture(self, source, posture):
        """Append original posture readings to the logs."""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.logs_page.append_log(f"[{current_time}] {source} detected: {posture}")  # Keep detailed log

    def toggle_start_button(self):
        is_start = self.start_button.text() == "Start"
        self.start_button.setText("Stop" if is_start else "Start")
        self.start_button.setStyleSheet(
            "background-color: #1B744D; color: #F1F1F1 ; padding: 5px; border-radius: 8px" if is_start else
            "background-color: #F1F1F1 ; color: black; padding: 5px; border-radius: 8px"
        )

    def handle_start(self):
        self.toggle_start_button()

        if self.start_button.text() == "Stop":
            self.detector.start_detection()
            data_collection.start_recording()

            if self.heatmap is None:
                self.setup_pressure_heatmap()

            if self.ani is None:
                # Run animation update using PyQt's main event loop
                self.timer = QTimer()
                self.timer.timeout.connect(lambda: self.update_pressure_heatmap(None))
                self.timer.start(1000)  # Update every second

        else:
            self.detector.stop_detection()
            data_collection.stop_recording()
            if hasattr(self, 'timer'):
                self.timer.stop()  # Stop the timer when stopping

    def export_posture_data_to_csv():
        """Export posture data from the database to a CSV file."""
        conn = sqlite3.connect("posture_data.db")
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM posture_logs")  # Fetch all posture records
        data = cursor.fetchall()

        if data:
            with open("posture_data.csv", mode="w", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(["Time", "Posture", "Duration"])  # CSV header
                writer.writerows(data)  # Write database records

        conn.close()
        
class LogsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)  # Main layout for the page
                
        # ✅ Create top layout for Label and Save Button
        top_layout = QHBoxLayout()
        
        top_layout.addWidget(UIHelper.create_label("Logs", 14, (40, 20)))
        top_layout.addStretch(1)  # Push everything else to the right
        
        # Create a save button
        self.save_button = UIHelper.create_button("save")
        top_layout.addWidget(self.save_button)
        
        main_layout.addLayout(top_layout)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet(
            "border-radius: 8px; background: #F1F1F1;padding: 5px")
        self.log_text.setFixedSize(710, 360)
        
        main_layout.addWidget(self.log_text)  # Left align button
        
        # ✅ Back Button (Lower Left)
        self.back_button = UIHelper.create_button("back")
        self.back_button.clicked.connect(self.go_back)
        
        # ✅ Create bottom layout for Back Button
        bottom_layout = QHBoxLayout()
        bottom_layout.addWidget(self.back_button)  # Left align button
        bottom_layout.addStretch(1)  # Push everything else to the right

        # ✅ Add widgets to the main layout
        main_layout.addLayout(bottom_layout)  # Back button at the bottom left

        self.setLayout(main_layout)
    
    def append_log(self, message):
        self.log_text.append(message)

    def go_back(self):
        """Go back to the main detection page."""
        self.parent().setCurrentIndex(0)  # Adjust based on your stacked widget index

class PostSyncApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon('./assets/logo.png'))
        self.setWindowTitle("PostSync App")
        self.setFixedSize(800, 560)
        self.setStyleSheet("background-color:#1E1E1E")
        self.setContentsMargins(36, 24, 36, 24)

        self.stacked_widget = QStackedWidget()

        self.logs_page = LogsPage(self.stacked_widget)
        self.home_page = HomePage(self.stacked_widget, self.logs_page)

        self.stacked_widget.addWidget(self.home_page)  # HomePage (index 0)
        self.stacked_widget.addWidget(self.logs_page)  # LogsPage (index 1) 
        
        self.setCentralWidget(self.stacked_widget)
    
    def closeEvent(self, event):
        """Export posture data to CSV when the application is closed."""
        print("Exporting posture data to CSV before closing the application...")  # Debugging
        print_current_postures()
        print_final_posture()
        posture_database.export_to_csv()  # Export posture logs to CSV
        print("CSV export complete.")  # Debugging confirmation
        event.accept()  # Ensures the application closes properly


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PostSyncApp()
    window.show()
    sys.exit(app.exec_())