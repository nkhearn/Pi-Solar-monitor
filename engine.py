import os
import json
import subprocess
import sqlite3
import time
import asyncio
import re
from datetime import datetime, timezone
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

def sanitize_column_name(name):
    """
    Sanitizes a name for use as a SQL column name.
    """
    # Replace non-alphanumeric characters with underscores
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    # Ensure it doesn't start with a number
    if sanitized and sanitized[0].isdigit():
        sanitized = "_" + sanitized
    return sanitized.lower()

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

def should_run_collector(filename, current_time, directory_name):
    """
    Determines if a collector should run based on its filename and current time.
    """
    name_parts = filename.split('.')

    if directory_name == 'hourly':
        target_minute = 0
        for part in name_parts[1:-1]:
            if re.fullmatch(r'\d{2}', part):
                target_minute = int(part)
                break
        return current_time.minute == target_minute

    elif directory_name == 'daily':
        target_hour = 0
        target_minute = 0
        for part in name_parts[1:-1]:
            if re.fullmatch(r'\d{4}', part):
                target_hour = int(part[:2])
                target_minute = int(part[2:])
                break
        return current_time.hour == target_hour and current_time.minute == target_minute

    return True

async def collect_from_dirs(directories, timeout=55, current_time=None):
    """
    Iterates through specified directories and aggregates data from executables.
    """
    if current_time is None:
        current_time = datetime.now()

    aggregated_data = {}
    tasks = []
    for directory in directories:
        if not os.path.exists(directory):
            continue

        # Use the name of the directory (hourly, daily, etc.) for timing checks
        dir_name = os.path.basename(os.path.normpath(directory))

        for filename in sorted(os.listdir(directory)):
            filepath = os.path.join(directory, filename)
            if os.path.isfile(filepath) and os.access(filepath, os.X_OK):
                if should_run_collector(filename, current_time, dir_name):
                    tasks.append(run_collector(filepath, timeout))

    if tasks:
        results = await asyncio.gather(*tasks)
        for data in results:
            if data and isinstance(data, dict):
                aggregated_data.update(data)

    return aggregated_data

async def collect_all(current_time=None):
    """
    Aggregates data from all relevant collector directories based on the schedule.
    """
    if current_time is None:
        current_time = datetime.now()

    dirs_55s = [COLLECTORS_DIR, os.path.join(COLLECTORS_DIR, "minutely")]
    dirs_300s = [os.path.join(COLLECTORS_DIR, "hourly"), os.path.join(COLLECTORS_DIR, "daily")]

    tasks = [collect_from_dirs(dirs_55s, timeout=55, current_time=current_time)]
    tasks.append(collect_from_dirs(dirs_300s, timeout=300, current_time=current_time))

    results = await asyncio.gather(*tasks)

    aggregated_data = {}
    for data in results:
        aggregated_data.update(data)

    return aggregated_data

def save_to_db(data):
    """
    Saves the aggregated data to SQLite, adding columns as needed.
    """
    if not data:
        return

    # Sanitize and prepare data
    sanitized_data = {sanitize_column_name(k): v for k, v in data.items()}

    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA synchronous=NORMAL')
    cursor = conn.cursor()

    # Get current columns
    cursor.execute("PRAGMA table_info(data_points)")
    existing_columns = [row[1] for row in cursor.fetchall()]

    # Add missing columns
    for col in sanitized_data.keys():
        if col not in existing_columns:
            print(f"Adding new column: {col}")
            try:
                cursor.execute(f"ALTER TABLE data_points ADD COLUMN {col} REAL")
                existing_columns.append(col)
            except sqlite3.Error as e:
                print(f"Failed to add column {col}: {e}")

    # Build INSERT query
    columns = list(sanitized_data.keys())
    placeholders = ",".join(["?"] * len(columns))
    query = f"INSERT INTO data_points ({','.join(columns)}) VALUES ({placeholders})"

    try:
        cursor.execute(query, list(sanitized_data.values()))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error inserting data: {e}")
    finally:
        conn.close()

async def collect_now(current_time=None):
    """
    Performs a single collection cycle.
    """
    if current_time is None:
        now_utc = datetime.now(timezone.utc)
        current_time = datetime.now()
    else:
        if current_time.tzinfo is None:
            # Naive datetime is treated as local time, convert to UTC
            now_utc = current_time.astimezone(timezone.utc)
        else:
            now_utc = current_time.astimezone(timezone.utc)

    print(f"Collecting data at {now_utc} UTC")
    data = await collect_all(current_time=current_time)
    if data:
        db_task = asyncio.to_thread(save_to_db, data.copy())

        notify_tasks = []
        if api:
            notify_tasks.append(api.notify_new_data({
                "timestamp": now_utc.strftime('%Y-%m-%d %H:%M:%S'), # Second precision as requested
                "data": data.copy()
            }))
        else:
            print("Skipping websocket notification (api not available)")

        notify_tasks.append(send_to_macrodroid(data))
        await asyncio.gather(db_task, *notify_tasks)
        await condition_engine.engine.process_conditions(current_data=data)
        print(f"Data saved and broadcasted: {len(data)} keys")
    else:
        print("No data collected.")

async def collection_loop():
    """
    Main loop that runs every minute and schedules hourly/daily tasks.
    """
    print("Starting data collection engine...")

    now = datetime.now()
    run_hourly = (now.minute == 0)
    run_daily = (run_hourly and now.hour == 0)

    await collect_now(current_time=now)

    last_purge_hour = -1
    while True:
        now_ts = time.time()
        sleep_time = 60 - (now_ts % 60)
        if sleep_time < 1:
            sleep_time += 60
        await asyncio.sleep(sleep_time)

        now = datetime.now()
        run_hourly = (now.minute == 0)
        run_daily = (run_hourly and now.hour == 0)

        if now.hour != last_purge_hour:
            condition_engine.engine.purge_old_cooldowns()
            last_purge_hour = now.hour

        await collect_now(run_hourly=run_hourly, run_daily=run_daily, current_time=now)

if __name__ == "__main__":
    try:
        asyncio.run(collection_loop())
    except KeyboardInterrupt:
        print("Collection engine stopped.")
