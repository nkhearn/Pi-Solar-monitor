import os
import json
import subprocess
import sqlite3
import time
import asyncio
from datetime import datetime
try:
    import api  # Import our api module to notify websockets
except ImportError:
    api = None
import requests

DB_PATH = "data/inverter_logs.db"
COLLECTORS_DIR = "collectors"
MACRODROID_URL = "https://trigger.macrodroid.com/UUID/power"

async def send_to_macrodroid(payload_dict):
    """
    Asynchronously sends data to Macrodroid webhook using requests in a thread.
    """
    headers = {'Content-Type': 'application/json'}
    try:
        def do_post():
            return requests.post(MACRODROID_URL, json=payload_dict, headers=headers, timeout=10)

        response = await asyncio.to_thread(do_post)
        if response.status_code == 200:
            print("Macrodroid Triggered Successfully")
        else:
            print(f"Macrodroid Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Macrodroid Connection Error: {e}")
async def run_collector(filepath):
    """
    Runs an executable and returns its JSON output with a 55 second timeout.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            filepath,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=55)
            if proc.returncode == 0:
                try:
                    return json.loads(stdout.decode())
                except json.JSONDecodeError:
                    print(f"Error: Collector {filepath} returned invalid JSON.")
                    return None
            else:
                print(f"Error: Collector {filepath} exited with code {proc.returncode}")
                if stderr:
                    print(f"Stderr: {stderr.decode().strip()}")
                return None
        except asyncio.TimeoutError:
            print(f"Error: Collector {filepath} timed out after 55 seconds. Killing process.")
            try:
                proc.kill()
                await proc.wait()
            except Exception as e:
                print(f"Failed to kill process {filepath}: {e}")
            return None
    except Exception as e:
        print(f"Error running collector {filepath}: {e}")
        return None

async def collect_all():
    """
    Iterates through all executables in the collectors directory and aggregates data in parallel.
    """
    aggregated_data = {}
    if not os.path.exists(COLLECTORS_DIR):
        return aggregated_data

    tasks = []
    for filename in sorted(os.listdir(COLLECTORS_DIR)):
        filepath = os.path.join(COLLECTORS_DIR, filename)
        if os.path.isfile(filepath) and os.access(filepath, os.X_OK):
            tasks.append(run_collector(filepath))

    if tasks:
        results = await asyncio.gather(*tasks)
        for data in results:
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
    # Optimization: Set synchronous to NORMAL for faster writes.
    # WAL mode is already set at database creation.
    conn.execute('PRAGMA synchronous=NORMAL')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO data_points (data) VALUES (?)', (json.dumps(data),))
    conn.commit()
    conn.close()

async def collect_now():
    """
    Performs a single collection cycle.
    """
    print(f"Collecting data at {datetime.now()}")
    data = await collect_all()
    if data:
        # Save to DB in a separate thread to avoid blocking the main event loop
        await asyncio.to_thread(save_to_db, data)
        # Notify websockets
        if api:
            await api.notify_new_data({"timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%f'), "data": data})
        else:
            print("Skipping websocket notification (api not available)")
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
