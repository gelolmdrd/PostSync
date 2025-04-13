import sys
import mediapipe as mp
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QDialog, QLabel, 
    QPushButton, QTextEdit, QCheckBox, QStackedWidget, QSpacerItem, QSizePolicy
)
from PyQt5.QtGui import QPixmap, QIcon, QFont
from PyQt5.QtCore import Qt
from features import Features, PostureDetector
from datetime import datetime
from matplotlib.figure import Figure
from matplotlib.image import imread
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5.QtCore import qInstallMessageHandler, QtMsgType
import numpy as np
import time
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from scipy.ndimage import gaussian_filter
import threading
import requests
import data_collection # Import data_collection.py
import csv
import sqlite3
import posture_database
from posture_database import export_to_csv
import traceback
from features import get_latest_vision_posture
from data_collection import get_latest_pressure_posture
from plyer import notification
from PyQt5.QtCore import QTimer

import ctypes
myappid = u"PostSync"  # Can be any unique string
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

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

icon_path = os.path.abspath("postsync_logo.ico")



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
        
class WelcomeScreen(QWidget):
    def __init__(self, stacked_widget):
        super().__init__()
        self.stacked_widget = stacked_widget
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        
        # Horizontal layout for "Welcome to" + logo
        title_layout = QHBoxLayout()
        title_layout.setAlignment(Qt.AlignCenter)

        welcome_label = UIHelper.create_label("Welcome to ", 48)
        
        logo_label = QLabel()
        logo_pixmap = QPixmap("./assets/PostSync Logo_scaled.png")
        # logo_pixmap = logo_pixmap.scaledToHeight(48, Qt.SmoothTransformation)  # Match text height
        logo_label.setPixmap(logo_pixmap)
        logo_label.setAlignment(Qt.AlignCenter)

        title_layout.addWidget(welcome_label)
        title_layout.addWidget(logo_label)

        layout.addLayout(title_layout)
        layout.addWidget(UIHelper.create_label("Before you start, please ensure that your workstation is set up like the example below:", 
                                            12), alignment=Qt.AlignCenter)

        infographic = QLabel()
        pixmap = QPixmap("./assets/workstation_setup.png")
        pixmap = pixmap.scaled(600, 350, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        infographic.setPixmap(pixmap)
        infographic.setAlignment(Qt.AlignCenter)
        
         # Apply rounded corners using stylesheet
        infographic.setStyleSheet("""
            border-radius: 12px;
            border: 1px solid #ccc;
            background-color: #ffffff;
            padding: 4px;
        """)
        
        layout.addWidget(infographic)
        
        self.understand_button = UIHelper.create_button("I Understand")
        self.understand_button.clicked.connect(self.proceed_to_main_app)
        layout.addWidget(self.understand_button, alignment=Qt.AlignCenter)

        self.setLayout(layout)

    def proceed_to_main_app(self):
        self.stacked_widget.setCurrentIndex(1)
        
class HomePage(QWidget):
    def __init__(self, stacked_widget, logs_page):
        super().__init__()
        self.stacked_widget = stacked_widget
        self.logs_page = logs_page   # Reference Logs page 
        self.last_notification = None

        self.vision_detector = PostureDetector()
        self.vision_detector.posture_updated.connect(self.update_posture_status)
        
        self.features = Features()
        self.detector = PostureDetector()  # Initialize PostureDetector
        self.detector.posture_updated.connect(self.update_posture_status)
        self.detector.notification_alert.connect(self.trigger_notification)
        self.vision_posture = "Unknown"  # Store the last detected vision posture
        self.pressure_posture = "Unknown"  # Store the last detected pressure posture
        self.last_notification_time = 0

        self.last_detected_posture = None
        self.posture_start_time = time.time()
        self.last_notification = None
        self.notifications_enabled = True  # Default: notifications on
        self.info_popup = None  # ✅ Initialize popup reference here

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
        plt.close('all')
        
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
        logo_pixmap = QPixmap("assets/PostSync Logo_scaled.png")
        if not logo_pixmap.isNull():
            logo_label.setPixmap(logo_pixmap)
        else:
            print("Failed to load logo image.")
        logo_label.setAlignment(Qt.AlignLeft)
        logo_label.setFixedSize(242, 65)
        left_layout.addWidget(logo_label)

        # Pressure Data
        left_layout.addWidget(UIHelper.create_label(
            "Cushion Activity", 14, (170, 16)))

        # Placeholder for displaying the heatmap of pressure data from the sensors
        self.pressure_layout = QVBoxLayout()
        self.pressure_canvas = FigureCanvas(Figure(figsize=(3, 3)))  # Matplotlib Figure
        self.pressure_canvas.setFixedSize(225, 225)  # Set fixed pixel size (width x height)
        self.pressure_layout.addWidget(self.pressure_canvas)
        left_layout.addLayout(self.pressure_layout)
        plt.close('all')


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
        
        # --- Info Button ---
        self.info_button = QPushButton(" Click here to see proper workstation setup")
        self.info_button.setIcon(QIcon("./assets/info.png"))
        # self.info_button.setFixedSize(None, 16)
        self.info_button.setStyleSheet("border: 2px; color: #B3B3B3")
        self.info_button.setCursor(Qt.PointingHandCursor)
        self.info_button.clicked.connect(self.show_info_popup)
        
        # Position info button top-right
        right_layout.addWidget(self.info_button, Qt.AlignRight)

        # Create QLabel to display the guidelines image
        self.guidelines_image = QLabel()
        guidlines_pixmap = QPixmap("./assets/guidelines.png")

        # Optional: scale the image to fit the QLabel size
        guidlines_pixmap = guidlines_pixmap.scaled(400, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.guidelines_image.setPixmap(guidlines_pixmap)
        self.guidelines_image.setFixedSize(420, 300)
        self.guidelines_image.setAlignment(Qt.AlignCenter)

        # Apply rounded corners using stylesheet
        self.guidelines_image.setStyleSheet("""
            border-radius: 12px;
            border: 1px solid #ccc;
            background-color: #ffffff;
            padding: 4px;
        """)

        right_layout.addWidget(self.guidelines_image)

        bottom_layout = self.create_bottom_controls()
        right_layout.addLayout(bottom_layout)
        return right_layout
    
    
    def show_info_popup(self):
        if self.info_popup is None:
            self.info_popup = QDialog(self)
            self.info_popup.setWindowTitle("Workspace Setup Guidelines")
            self.info_popup.setFixedSize(560, 315)
            self.info_popup.setModal(False)

            layout = QVBoxLayout()
                        
            infographic = QLabel()
            pixmap = QPixmap("./assets/workstation_setup.png")
            pixmap = pixmap.scaled(480, 270, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            infographic.setPixmap(pixmap)
            infographic.setAlignment(Qt.AlignCenter)
            
            # Apply rounded corners using stylesheet
            infographic.setStyleSheet("""
                border-radius: 12px;
                border: 1px solid #ccc;
                background-color: #ffffff;
                padding: 4px;
            """)
            
            layout.addWidget(infographic)
            self.info_popup.setLayout(layout)

        self.info_popup.show()
        self.info_popup.raise_()
        self.info_popup.activateWindow()

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
        self.haptic_toggle.stateChanged.connect(self.toggle_haptic_feedback)
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

    def log_message(self, message: str):
        if hasattr(self, "log_text"):
            self.log_text.append(message)
        else:
            print(f"[LOG]: {message}")  # Fallback for early-stage logging

    def go_to_logs(self):
        """Switch to the logs page when the Show Logs button is clicked."""
        self.stacked_widget.setCurrentWidget(self.stacked_widget.widget(2)) 

    def trigger_notification(self, message):
        """Send notification if message changed or enough time passed."""
        if not hasattr(self, "_last_notification"):
            self._last_notification = {"message": None, "time": 0}

        now = time.time()
        cooldown = 10  # seconds

        if (
            message != self._last_notification["message"]
            or now - self._last_notification["time"] > cooldown
        ):
            print(f"Notification sent: {message}")
            try:
                notification.notify(
                    title="Posture Alert",
                    message=message,
                    timeout=5
                )
                self._last_notification["message"] = message
                self._last_notification["time"] = now
            except Exception as e:
                print(f"Notification error: {e}")

    def check_final_posture_and_notify(self):
        if not self.notifications_enabled:
            return

        finalNotif = print_final_posture()
        current_time = time.time()

        good_posture = "Correct Posture"
        bad_postures = ["Incorrect Posture"]
        no_user = "No Person Detected"

        # If posture changed, reset timer
        if finalNotif != self.last_detected_posture:
            self.last_detected_posture = finalNotif
            self.posture_start_time = current_time

        # Calculate how long posture has been held
        posture_duration = current_time - self.posture_start_time
        time_since_last_notif = current_time - self.last_notification_time

        if finalNotif == good_posture and posture_duration >= 5 and (self.last_notification != "good" or time_since_last_notif >= 30):
            print("Good posture notification triggered!")
            self.trigger_notification("Good Posture! Keep It Up.")
            self.last_notification = "good"
            self.last_notification_time = current_time

        elif finalNotif in bad_postures and posture_duration >= 1 and time_since_last_notif >= 30:
            print("Bad posture notification triggered!")
            self.trigger_notification("Bad Posture! Fix your sitting position.")
            self.last_notification = "bad"
            self.last_notification_time = current_time

        elif finalNotif == no_user and posture_duration >= 1 and self.last_notification != "no user":
            print("No person detected notification triggered!")
            self.trigger_notification("No Person Detected on Chair.")
            self.last_notification = "no user"
            self.last_notification_time = current_time

    def toggle_notifications(self, state):
        """Enable or disable pop-up notifications based on user toggle."""
        self.notifications_enabled = state == Qt.Checked  # True if checked
        status = "enabled" if self.notifications_enabled else "disabled"
        print(f"Notifications {status}")
        self.logs_page.append_log(f"[SETTINGS]: Notifications {status}")

    def toggle_haptic_feedback(self, state):
        from data_collection import set_haptic_enabled
        enabled = state == Qt.Checked
        set_haptic_enabled(enabled)

        status = "enabled" if enabled else "disabled"
        print(f"Haptic feedback {status}")
        self.logs_page.append_log(f"[SETTINGS]: Haptic feedback {status}")

    def handler(mode, context, message):
        if "QPainter::begin" in message:
            return  # Suppress specific warnings
        print(message)

    qInstallMessageHandler(handler)

    def create_toggle_section(self, label_text):
        layout = QHBoxLayout()
        layout.addWidget(UIHelper.create_label(label_text, 12, (120, 24)))
        toggle = QCheckBox()
        toggle.setChecked(True)  #Set the default state to ON (checked)
        toggle.setIcon(QIcon("./assets/toggleOn.png"))  #Set the ON icon initially
        pixmap = QPixmap("./assets/toggleOn.png")  #Use ON icon to match the checked state
        if not pixmap.isNull():
            toggle.setIcon(QIcon(pixmap))
            size = pixmap.size()
            toggle.setIconSize(size)

        else:
            print("Failed to load toggleOff.png")
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

        self.check_final_posture_and_notify()

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
            self.vision_detector.start_detection()
            data_collection.start_recording()
            self.trigger_notification("Test notification from PostSync!")

            if self.heatmap is None:
                self.setup_pressure_heatmap()

            if self.ani is None:
                # Run animation update using PyQt's main event loop
                self.timer = QTimer()
                self.timer.timeout.connect(lambda: self.update_pressure_heatmap(None))
                self.timer.start(1000)  # Update every second

        else:
            self.detector.stop_detection()
            self.vision_detector.stop_detection()
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
                writer.writerow(["Time", "Posture"])  # CSV header
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
        self.save_button.setIcon(QIcon("./assets/Save.png"))
        self.save_button.clicked.connect(export_to_csv)
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
        self.parent().setCurrentIndex(1)  # Adjust based on your stacked widget index


        
class PostSyncApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon('./assets/logo.png'))
        self.setWindowTitle("PostSync App")
        self.setFixedSize(800, 560)
        self.setStyleSheet("background-color:#1E1E1E")
        self.setContentsMargins(36, 24, 36, 24)

        self.stacked_widget = QStackedWidget()
        
        self.welcome_screen = WelcomeScreen(self.stacked_widget)
        self.logs_page = LogsPage(self.stacked_widget)
        self.home_page = HomePage(self.stacked_widget, self.logs_page)

        self.stacked_widget.addWidget(self.welcome_screen) # WelcomeScreen (index 0)
        self.stacked_widget.addWidget(self.home_page)  # HomePage (index 1)
        self.stacked_widget.addWidget(self.logs_page)  # LogsPage (index 2) 
        
        self.setCentralWidget(self.stacked_widget)
    
    def closeEvent(self, event):
        """Export posture data to CSV when the application is closed."""
        print("Exporting posture data to CSV before closing the application...")  # Debugging
        print_current_postures()
        print_final_posture()
        #posture_database.export_to_csv()  # Export posture logs to CSV
        #print("CSV export complete.")  # Debugging confirmation
        event.accept()  # Ensures the application closes properly

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PostSyncApp()
    window.show()
    sys.exit(app.exec_())