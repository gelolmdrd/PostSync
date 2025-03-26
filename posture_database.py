import sqlite3
import os
import pandas as pd
from datetime import datetime

db_path = "posture_logs.db"
csv_path = "posture_data.csv"

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

def save_posture(posture):
    """Save a detected posture into the database with a timestamp."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO posture_logs (timestamp, posture) VALUES (?, ?)", (timestamp, posture))
    conn.commit()
    conn.close()
    print(f"[DATABASE] Saved posture: {posture} at {timestamp}")

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
