import serial
import numpy as np
import keyboard
import time

# Connect to Arduino
ser = serial.Serial('COM6', 9600, timeout=1)  # Adjust COM port
last_vibration_time = 0  # To track vibration interval


def read_sensor_data():
    try:
        line = ser.readline().decode('utf-8').strip()
        if line:
            values = list(map(float, line.split(',')))
            if len(values) == 13:
                return np.array(values)
    except:
        pass
    return None


def detect_posture(sensor_values, threshold=0.2):
    """ Detect if posture is correct or incorrect based on pressure balance. """

    # Group pressure readings
    left_side_pressure = np.mean(
        sensor_values[[0, 1, 2, 6]])  # Sensors 1, 2, 3, 7
    right_side_pressure = np.mean(
        sensor_values[[3, 4, 5, 9]])  # Sensors 4, 5, 6, 10
    front_pressure = np.mean(sensor_values[[7, 8]])  # Sensors 8, 9
    back_pressure = np.mean(sensor_values[[10, 11, 12]])  # Sensors 11, 12, 13

    # Calculate differences
    side_diff = abs(left_side_pressure - right_side_pressure)
    front_back_diff = abs(front_pressure - back_pressure)

    # Check if balanced within threshold
    if side_diff <= threshold and front_back_diff <= threshold:
        return "Correct Posture"
    else:
        return "Incorrect Posture"


def activate_vibration():
    ser.write(b'1')  # Send '1' to Arduino to trigger vibration
    print("Haptic Feedback Activated for 2 seconds!")
    time.sleep(2)  # Vibration duration
    ser.write(b'0')  # Send '0' to stop vibration


# Continuously monitor posture
while True:
    # Exit loop when 'q' is pressed
    if keyboard.is_pressed('q'):
        print("Exiting program...")
        break

    sensor_data = read_sensor_data()
    if sensor_data is not None:
        posture_status = detect_posture(sensor_data)
        print(f"Posture Status: {posture_status}")

        # Trigger haptic feedback only when posture is incorrect
        current_time = time.time()
        if posture_status == "Incorrect Posture":
            if current_time - last_vibration_time >= 10:  # 10-second interval
                activate_vibration()
                last_vibration_time = current_time
