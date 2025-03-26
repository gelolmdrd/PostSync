import sys
import mediapipe as mp
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QTextEdit, QCheckBox, QStackedWidget, QSpacerItem, QSizePolicy
)
from PyQt5.QtGui import QPixmap, QIcon, QFont
from PyQt5.QtCore import Qt
from features import Features, PostureDetector
from datetime import datetime
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import numpy as np
import matplotlib.animation as animation
from scipy.ndimage import gaussian_filter
import requests
import data_collection  # Import data_collection.py
import csv
import sqlite3
import posture_database



NODEMCU_IP = "http://192.168.121.112"  # Ensure this matches your NodeMCU IP
ENDPOINT = "/get_data"


class UIHelper:
    """Utility class for reusable UI components and styles."""
    @staticmethod
    def create_label(text, font_size=12, fixed_size=None, align=None):
        label = QLabel(text)
        font = QFont("Roboto", font_size)
        label.setFont(font)
        label.setStyleSheet(f"color: #F1F1F1; font-size: {font_size}px;")
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
    def __init__(self, stacked_widget):
        super().__init__()
        self.features = Features()
        self.detector = PostureDetector()  # Initialize PostureDetector
        self.detector.posture_updated.connect(self.update_posture_status)
        self.detector.notification_alert.connect(self.show_notification)
        self.init_ui()
        self.setup_pressure_heatmap()

    def init_ui(self):
        main_layout = QHBoxLayout()
        left_layout = self.create_left_section()
        right_layout = self.create_right_section()
        main_layout.addLayout(left_layout)
        main_layout.addLayout(right_layout)
        self.setLayout(main_layout)

    def setup_pressure_heatmap(self):
        """Initialize the pressure heatmap using real-time data from sensors."""
        self.ax = self.pressure_canvas.figure.add_subplot(111)

        # Use the same 5x5 layout from data_collection.py for visualization
        self.chair_layout = np.array([
            [1,  0,  0,  0,  4],
            [2,  0,  8,  0,  5],
            [3,  0,  9,  0,  6],
            [7,  0,  0,  0, 10],
            [0, 11, 12, 13,  0]
        ])

        self.heatmap_data = np.full_like(self.chair_layout, np.nan, dtype=np.float64)  # Initialize as empty
        if not hasattr(self, 'heatmap') or self.heatmap is None:
            self.ax.clear()  # Clear any previous plot
            self.heatmap_data = np.full_like(self.chair_layout, np.nan, dtype=np.float64)
            self.heatmap = self.ax.imshow(self.heatmap_data, cmap="RdYlGn_r", interpolation="nearest", animated=True, vmin=0, vmax=10)

            self.ax.set_xticks([])
            self.ax.set_yticks([])

            self.ani = animation.FuncAnimation(self.pressure_canvas.figure, self.update_pressure_heatmap, interval=1000)
            self.pressure_canvas.figure.tight_layout()

        # Hide axis ticks for clean display
        self.ax.set_xticks([])
        self.ax.set_yticks([])

        # Start animation to update with real sensor data
        self.ani = animation.FuncAnimation(self.pressure_canvas.figure, self.update_pressure_heatmap, interval=1000)

        self.pressure_canvas.figure.tight_layout()

    def generate_sample_pressure_data(self):
        """Generate random pressure data with realistic sitting pressure distribution."""
        pressure = np.zeros((20, 20))  # Empty heatmap

        # Simulate higher pressure in seat and thigh regions
        sensor_positions = [(5, 5), (5, 14), (10, 5), (10, 14), (15, 5), (15, 14)]  # Sample sensor locations
        for x, y in sensor_positions:
            pressure[x, y] = np.random.uniform(0.5, 1.0)  # Random pressure at sensors

        # Smooth data to make it more natural
        pressure = gaussian_filter(pressure, sigma=3)

        return pressure

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
                    self.pressure_canvas.draw()
        except requests.RequestException as e:
            print(f"Warning: Failed to get sensor data: {e}")

    def create_left_section(self):
        left_layout = QVBoxLayout()

        # Logo
        logo_label = QLabel()
        logo_label.setPixmap(QPixmap("assets/PostSync Logo.png"))
        logo_label.setAlignment(Qt.AlignLeft)
        logo_label.setFixedSize(242, 65)
        left_layout.addWidget(logo_label)

        # Pressure Data
        left_layout.addWidget(UIHelper.create_label(
            "Pressure Data", 10, (200, 16)))

        # Placeholder for displaying the heatmap of pressure data from the sensors
        self.pressure_layout = QVBoxLayout()
        self.pressure_canvas = FigureCanvas(Figure(figsize=(3, 3)))  # Matplotlib Figure
        self.pressure_layout.addWidget(self.pressure_canvas)
        left_layout.addLayout(self.pressure_layout)


        # Current Posture
        left_layout.addWidget(UIHelper.create_label(
            "Current Posture", 10, (200, 30), Qt.AlignBottom))

        # Placeholder for displaying current posture status
        self.posture_status = UIHelper.create_label("", fixed_size=(200, 48))
        self.posture_status.setStyleSheet(
            "border: 1px solid #F1F1F1; border-radius: 8px; padding: 5px; color: white; font-weight: bold;")
        left_layout.addWidget(self.posture_status)

        return left_layout

    def create_right_section(self):
        right_layout = QVBoxLayout()
        right_layout.addWidget(UIHelper.create_label("Logs", 12, (40, 20)))

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet(
            "border-radius: 8px; background: #F1F1F1;padding: 5px")
        self.log_text.setFixedSize(400, 260)
        right_layout.addWidget(self.log_text)

        bottom_layout = self.create_bottom_controls()
        right_layout.addLayout(bottom_layout)
        return right_layout

    def create_bottom_controls(self):
        bottom_layout = QHBoxLayout()
        left_controls = QVBoxLayout()

        self.start_button = UIHelper.create_button("Start")
        self.start_button.clicked.connect(self.handle_start)
        left_controls.addWidget(UIHelper.create_label("Power", 12, (170, 16)))
        left_controls.addWidget(self.start_button)
        left_controls.addWidget(UIHelper.create_label("Info", 12, (170, 16)))
        left_controls.addWidget(UIHelper.create_button("Guidelines"))
        bottom_layout.addLayout(left_controls)

        # Add spacing before the alerts section
        bottom_layout.addSpacerItem(QSpacerItem(
            36, 36, QSizePolicy.Minimum, QSizePolicy.Fixed))

        bottom_layout.addLayout(self.create_alerts_section())

        return bottom_layout
    
    def create_alerts_section(self):
        alerts_layout = QVBoxLayout()
        alerts_layout.addWidget(UIHelper.create_label("Alerts", 12, (170, 16)))

        # Haptic Feedback Toggle
        haptic_layout = self.create_toggle_section("Haptic Feedback")
        self.haptic_toggle = haptic_layout[1]
        alerts_layout.addLayout(haptic_layout[0])

        # Notifications Toggle
        notif_layout = self.create_toggle_section("Notifications")
        self.notif_toggle = notif_layout[1]
        self.notif_toggle.stateChanged.connect(self.toggle_notifications)
        alerts_layout.addLayout(notif_layout[0])

        return alerts_layout
    
    def toggle_notifications(self, state):
        """Enable or disable pop-up notifications based on user toggle."""
        enabled = state == Qt.Checked  # Convert checkbox state to True/False
        self.detector.enable_notifications(enabled)
        
        status = "enabled" if enabled else "disabled"
        print(f"Notifications {status}")  # Debugging step
        self.log_text.append(f"[SETTINGS]: Notifications {status}")


    def show_notification(self, message):
        """Display notification alerts in the log."""
        self.log_text.append(f"[ALERT]: {message}")

    def create_toggle_section(self, label_text):
        layout = QHBoxLayout()
        layout.addWidget(UIHelper.create_label(label_text, 10, (120, 24)))
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
        self.posture_status.setText(posture)
        
        # Get current date and time
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Append log message with timestamp
        self.log_text.append(f"[{current_time}] Detected posture: {posture}")


    def toggle_start_button(self):
        is_start = self.start_button.text() == "Start"
        self.start_button.setText("Stop" if is_start else "Start")
        self.start_button.setStyleSheet(
            "background-color: #1B744D; color: #F1F1F1 ; padding: 5px; border-radius: 8px" if is_start else
            "background-color: #F1F1F1 ; color: black; padding: 5px; border-radius: 8px"
        )

    def handle_start(self):
        """Handles the Start/Stop button click."""
        self.toggle_start_button()
        
        if self.start_button.text() == "Stop":
            self.detector.start_detection()
            data_collection.start_recording()

            # Initialize heatmap only when "Start" is clicked
            if self.heatmap is None:
                self.setup_pressure_heatmap()
            
        else:
            self.detector.stop_detection()
            data_collection.stop_recording()

            # Hide heatmap when "Stop" is pressed
            if self.heatmap:
                self.ax.clear()
                self.heatmap = None
                self.pressure_canvas.draw()

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

class GuidelinesPage(QWidget):
    def __init__(self, stacked_widget):
        super().__init__()
        self.setLayout(QVBoxLayout())


class PostSyncApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon('./assets/logo.png'))
        self.setWindowTitle("PostSync App")
        self.setFixedSize(760, 480)
        self.setStyleSheet("background-color:#1E1E1E")
        self.setContentsMargins(36, 24, 36, 24)

        self.stacked_widget = QStackedWidget()
        self.stacked_widget.addWidget(HomePage(self.stacked_widget))
        self.stacked_widget.addWidget(GuidelinesPage(self.stacked_widget))

        self.setCentralWidget(self.stacked_widget)
    
    def closeEvent(self, event):
        """Export posture data to CSV when the application is closed."""
        print("Exporting posture data to CSV before closing the application...")  # Debugging
        posture_database.export_to_csv()  # Export posture logs to CSV
        print("CSV export complete.")  # Debugging confirmation
        event.accept()  # Ensures the application closes properly


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PostSyncApp()
    window.show()
    sys.exit(app.exec_())
