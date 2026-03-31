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
import condition_engine

DB_PATH = "data/inverter_logs.db"
COLLECTORS_DIR = "collectors"
# MACRODROID_URL = "https://trigger.macrodroid.com/UUID/power"
MACRODROID_URL = os.getenv("MACRODROID_URL")

async def send_to_macrodroid(payload_dict):
    """
    Asynchronously sends data to Macrodroid webhook using requests in a thread.
    """
    if not MACRODROID_URL:
        return

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
async def run_collector(filepath, timeout=55):
    """
    Runs an executable and returns its JSON output with a specified timeout.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            filepath,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
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
            print(f"Error: Collector {filepath} timed out after {timeout} seconds. Killing process.")
            try:
                proc.kill()
                await proc.wait()
            except Exception as e:
                print(f"Failed to kill process {filepath}: {e}")
            return None
    except Exception as e:
        print(f"Error running collector {filepath}: {e}")
        return None

async def collect_from_dirs(directories, timeout=55):
    """
    Iterates through specified directories and aggregates data from executables.
    """
    aggregated_data = {}
    tasks = []
    for directory in directories:
        if not os.path.exists(directory):
            continue
        for filename in sorted(os.listdir(directory)):
            filepath = os.path.join(directory, filename)
            if os.path.isfile(filepath) and os.access(filepath, os.X_OK):
                tasks.append(run_collector(filepath, timeout))

    if tasks:
        results = await asyncio.gather(*tasks)
        for data in results:
            if data and isinstance(data, dict):
                aggregated_data.update(data)

    return aggregated_data

async def collect_all(run_hourly=False, run_daily=False):
    """
    Aggregates data from all relevant collector directories based on the schedule.
    """
    # Minutely and root collectors (55s timeout)
    dirs_55s = [COLLECTORS_DIR, os.path.join(COLLECTORS_DIR, "minutely")]

    # Hourly and Daily collectors (300s timeout)
    dirs_300s = []
    if run_hourly:
        dirs_300s.append(os.path.join(COLLECTORS_DIR, "hourly"))
    if run_daily:
        dirs_300s.append(os.path.join(COLLECTORS_DIR, "daily"))

    tasks = [collect_from_dirs(dirs_55s, timeout=55)]
    if dirs_300s:
        tasks.append(collect_from_dirs(dirs_300s, timeout=300))

    results = await asyncio.gather(*tasks)

    aggregated_data = {}
    for data in results:
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

async def collect_now(run_hourly=False, run_daily=False):
    """
    Performs a single collection cycle.
    """
    print(f"Collecting data at {datetime.now()} (hourly={run_hourly}, daily={run_daily})")
    data = await collect_all(run_hourly=run_hourly, run_daily=run_daily)
    if data:
        # Pass copies of data to avoid race conditions and data leakage between tasks.
        # api.notify_new_data modifies its input dictionary to add virtual metrics.

        # Save to DB in a separate thread to avoid blocking the main event loop
        db_task = asyncio.to_thread(save_to_db, data.copy())

        # Prepare other notification tasks to run concurrently with the database write
        notify_tasks = []

        # Notify websockets
        if api:
            notify_tasks.append(api.notify_new_data({
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%f'),
                "data": data.copy()
            }))
        else:
            print("Skipping websocket notification (api not available)")

        # Send to Macrodroid
        notify_tasks.append(send_to_macrodroid(data.copy()))

        # Run database write and notifications concurrently
        await asyncio.gather(db_task, *notify_tasks)

        # Process conditional actions AFTER database write completes to avoid race conditions
        # (e.g. if conditions query the database for the data point we just saved)
        await condition_engine.engine.process_conditions()

        print(f"Data saved and broadcasted: {len(data)} keys")
    else:
        print("No data collected.")

async def collection_loop():
    """
    Main loop that runs every minute and schedules hourly/daily tasks.
    """
    print("Starting data collection engine...")

    # On startup, we determine if it's the top of the hour or midnight
    now = datetime.now()
    run_hourly = (now.minute == 0)
    run_daily = (run_hourly and now.hour == 0)

    # Perform an initial collection immediately
    await collect_now(run_hourly=run_hourly, run_daily=run_daily)

    # Track when we last purged old cooldowns
    last_purge_hour = -1

    while True:
        # Align with the next minute mark
        now_ts = time.time()
        sleep_time = 60 - (now_ts % 60)
        if sleep_time < 1: # avoid double execution if we are very close to the minute mark
            sleep_time += 60
        await asyncio.sleep(sleep_time)

        now = datetime.now()
        run_hourly = (now.minute == 0)
        run_daily = (run_hourly and now.hour == 0)

        # Purge old cooldown entries once per hour
        if now.hour != last_purge_hour:
            condition_engine.engine.purge_old_cooldowns()
            last_purge_hour = now.hour

        await collect_now(run_hourly=run_hourly, run_daily=run_daily)

if __name__ == "__main__":
    try:
        asyncio.run(collection_loop())
    except KeyboardInterrupt:
        print("Collection engine stopped.")
