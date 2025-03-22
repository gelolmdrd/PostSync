import requests
import pandas as pd
import time
from datetime import datetime

# NodeMCU Server IP (Change this to your actual IP)
NODEMCU_IP = "http://192.168.198.112"  # Replace with your NodeMCU’s local IP
ENDPOINT = "/get_data"  # The API route that provides sensor data

# Sensor Labels (from your sensor image)
SENSOR_LABELS = [
    "Sensor_1", "Sensor_2", "Sensor_3",  # Left Leg Area
    "Sensor_4", "Sensor_5", "Sensor_6",  # Right Leg Area
    "Sensor_7", "Sensor_8", "Sensor_9",  # Hip Area
    "Sensor_10", "Sensor_11", "Sensor_12", "Sensor_13"
]

# Generate a timestamped filename
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
csv_filename = f"pressure_sensor_data_{timestamp}.csv"

# Data collection setup
data_list = []
start_time = time.time()
timeout = 3  # Start with a moderate timeout

print(f"Collecting data for 30 seconds... Saving to {csv_filename}")

while time.time() - start_time < 30:
    try:
        # Fetch data from NodeMCU
        response = requests.get(f"{NODEMCU_IP}{ENDPOINT}", timeout=timeout)

        if response.status_code == 200:
            csv_data = response.text.strip()  # Get raw CSV string
            sensor_values = csv_data.split(",")  # Split CSV string into list

            if len(sensor_values) == len(SENSOR_LABELS):  # Ensure correct number of sensors
                data_list.append([float(value)
                                 for value in sensor_values])  # Convert to float
                # Reduce timeout if response is fast
                timeout = max(2, timeout - 0.5)
        else:
            print(f"Warning: Received status code {response.status_code}")

    except requests.Timeout:
        print("Warning: NodeMCU response timed out. Retrying faster...")
        timeout = min(7, timeout + 1)  # Increase timeout to handle delays

    except requests.RequestException as e:
        print(f"Warning: Request failed: {e}")

# Save Data to CSV
df = pd.DataFrame(data_list, columns=SENSOR_LABELS)
df.to_csv(csv_filename, index=False)

print(f"Data saved to {csv_filename}")
