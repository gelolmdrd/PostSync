import sqlite3
import os
import pandas as pd
from datetime import datetime

# Create folders if they don't exist
db_folder = "data/db"
csv_folder = "data/exports"
os.makedirs(db_folder, exist_ok=True)
os.makedirs(csv_folder, exist_ok=True)

# File paths
db_path = os.path.join(db_folder, "posture_logs.db")
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
csv_path = os.path.join(csv_folder, f"PostSync_{timestamp}_posture_data.csv")

def initialize_database():
    """Create the database and table if they don't exist."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posture_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            posture TEXT
        )
    ''')
    conn.commit()
    conn.close()

db_path = "posture_data.db"

def save_posture(posture, timestamp=None):
    """Save a detected posture into the database with a precise timestamp."""
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Make sure the table exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS posture_logs (
            timestamp TEXT,
            posture TEXT
        )
    """)
    
    cursor.execute("INSERT INTO posture_logs (timestamp, posture) VALUES (?, ?)", (timestamp, posture))
    conn.commit()
    conn.close()
    #print(f"[DATABASE] Saved vision posture: {posture} at {timestamp}")

def export_to_csv():
    """Export posture data from the database to a CSV file."""
    if not os.path.exists(db_path):
        print("[ERROR] Database file not found. No data to export.")
        return
    
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM posture_logs", conn)
    conn.close()
    
    if df.empty:
        print("[INFO] No posture data found in the database.")
        return
    
    df.to_csv(csv_path, index=False)
    print(f"[SUCCESS] Posture data exported to {csv_path}")

# Initialize the database on module load
initialize_database()

if __name__ == "__main__":
    export_to_csv()
