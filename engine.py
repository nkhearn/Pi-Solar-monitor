import os
import json
import subprocess
import sqlite3
import time
import asyncio
import aiohttp
from datetime import datetime
import api  # Import our api module to notify websockets

DB_PATH = "data/inverter_logs.db"
COLLECTORS_DIR = "collectors"
MACRODROID_URL = "https://trigger.macrodroid.com/UUID/power"

async def send_to_macrodroid(payload_dict):
    """
    Asynchronously sends data to Macrodroid webhook.
    """
    headers = {'Content-Type': 'application/json'}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(MACRODROID_URL, json=payload_dict, headers=headers) as response:
                if response.status == 200:
                    print("Macrodroid Triggered Successfully")
                else:
                    text = await response.text()
                    print(f"Macrodroid Error: {response.status} - {text}")
    except Exception as e:
        print(f"Macrodroid Connection Error: {e}")

def run_collector(filepath):
    """
    Runs an executable and returns its JSON output.
    """
    try:
        result = subprocess.run([filepath], capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except Exception as e:
        print(f"Error running collector {filepath}: {e}")
        return None

def collect_all():
    """
    Iterates through all executables in the collectors directory and aggregates data.
    """
    aggregated_data = {}
    if not os.path.exists(COLLECTORS_DIR):
        return aggregated_data

    for filename in sorted(os.listdir(COLLECTORS_DIR)):
        filepath = os.path.join(COLLECTORS_DIR, filename)
        if os.path.isfile(filepath) and os.access(filepath, os.X_OK):
            data = run_collector(filepath)
            if data and isinstance(data, dict):
                aggregated_data.update(data)

    return aggregated_data

def save_to_db(data):
    """
    Saves the aggregated JSON data to SQLite.
    """
    if not data:
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO data_points (data) VALUES (?)', (json.dumps(data),))
    conn.commit()
    conn.close()

async def collect_now():
    """
    Performs a single collection cycle.
    """
    print(f"Collecting data at {datetime.now()}")
    data = collect_all()
    if data:
        save_to_db(data)
        # Notify websockets
        await api.notify_new_data({"timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%f'), "data": data})
        # Send to Macrodroid
        await send_to_macrodroid(data)
        print(f"Data saved and broadcasted: {len(data)} keys")
    else:
        print("No data collected.")

async def collection_loop():
    """
    Main loop that runs every minute.
    """
    print("Starting data collection engine...")
    # Perform an initial collection immediately
    await collect_now()

    while True:
        # Align with the next minute mark
        now = time.time()
        sleep_time = 60 - (now % 60)
        if sleep_time < 1: # avoid double execution if we are very close to the minute mark
            sleep_time += 60
        await asyncio.sleep(sleep_time)
        await collect_now()

if __name__ == "__main__":
    try:
        asyncio.run(collection_loop())
    except KeyboardInterrupt:
        print("Collection engine stopped.")
