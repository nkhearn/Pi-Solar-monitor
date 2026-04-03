#!/usr/bin/env python3
import os
import sqlite3
import json
import subprocess
import mysql.connector
import struct
import datetime
import math
from pathlib import Path
import re

# Constants
SQLITE_DB_PATH = "data/inverter_logs.db"
DEFAULT_EMONCMS_PATH = "/var/opt/emoncms/"
TIME_WINDOW_SECONDS = 60

# --- Helper functions ---

def sanitize_column_name(name):
    """
    Sanitizes a name for use as a SQL column name.
    Matches engine.py and api.py implementation.
    """
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    if sanitized and sanitized[0].isdigit():
        sanitized = "_" + sanitized
    return sanitized.lower()

def init_sqlite_db():
    os.makedirs(os.path.dirname(SQLITE_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(SQLITE_DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS data_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON data_points(timestamp)')
    cursor.execute('PRAGMA journal_mode=WAL')
    conn.commit()
    return conn

def get_mysql_conn(host, user, password, database):
    return mysql.connector.connect(
        host=host,
        user=user,
        password=password,
        database=database
    )

def discover_collector_keys():
    print("\n--- Discovering data keys from collectors ---")
    keys = set()
    collectors_dir = Path("collectors")
    for script_path in collectors_dir.rglob("*.py"):
        print(f"Running collector: {script_path}...")
        try:
            result = subprocess.run(["python3", str(script_path)], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    keys.update(data.keys())
        except Exception as e:
            print(f"  Warning: Could not run {script_path}: {e}")

    # Allow manual entry
    while True:
        manual_key = input("Enter an additional data key (or press Enter to finish): ").strip()
        if not manual_key:
            break
        keys.add(manual_key)

    return sorted(list(keys))

def get_feeds_metadata(mysql_conn):
    cursor = mysql_conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name, tag, engine FROM feeds")
    feeds = cursor.fetchall()
    cursor.close()
    return feeds

def read_phpfina(feed_id, data_path, start_ts, end_ts):
    meta_path = Path(data_path) / f"phpfina/{feed_id}.meta"
    dat_file_path = Path(data_path) / f"phpfina/{feed_id}.dat"

    if not meta_path.exists() or not dat_file_path.exists():
        return []

    with open(meta_path, "rb") as f:
        f.seek(8) # Skip preamble
        interval = struct.unpack("I", f.read(4))[0]
        start_time = struct.unpack("I", f.read(4))[0]

    points = []
    with open(dat_file_path, "rb") as f:
        start_idx = max(0, int((start_ts - start_time) / interval))
        end_idx = int((end_ts - start_time) / interval)

        f.seek(start_idx * 4)
        for i in range(start_idx, end_idx + 1):
            val_bytes = f.read(4)
            if not val_bytes or len(val_bytes) < 4:
                break
            val = struct.unpack("f", val_bytes)[0]
            if not math.isnan(val):
                ts = start_time + (i * interval)
                points.append((ts, val))
    return points

def read_mysql_feed(mysql_conn, feed_id, start_ts, end_ts):
    cursor = mysql_conn.cursor()
    table_name = f"feed_{feed_id}"
    try:
        cursor.execute(f"SELECT time, value FROM {table_name} WHERE time >= %s AND time <= %s", (start_ts, end_ts))
        return cursor.fetchall()
    except mysql.connector.Error:
        return []
    finally:
        cursor.close()

def main():
    print("=== EmonCMS to SQLite Migration Utility ===")

    host = input("EmonCMS MySQL Host [localhost]: ") or "localhost"
    user = input("EmonCMS MySQL User: ")
    password = input("EmonCMS MySQL Password: ")
    database = input("EmonCMS MySQL Database [emoncms]: ") or "emoncms"

    try:
        mysql_conn = get_mysql_conn(host, user, password, database)
    except Exception as e:
        print(f"Error connecting to MySQL: {e}")
        return

    print("\n--- Date Range Selection ---")
    mode = input("Import (A)ll time or (D)ate range? [A/D]: ").upper()
    start_ts, end_ts = 0, int(datetime.datetime.now(datetime.timezone.utc).timestamp())

    if mode == 'D':
        start_date = input("Start date (YYYY-MM-DD): ")
        end_date = input("End date (YYYY-MM-DD): ")
        start_ts = int(datetime.datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).timestamp())
        end_ts = int(datetime.datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).timestamp())

    target_keys = discover_collector_keys()
    feeds = get_feeds_metadata(mysql_conn)

    print("\n--- Map EmonCMS Feeds to SQLite Keys ---")
    mapping = {}
    for feed in feeds:
        print(f"\nFeed ID: {feed['id']}, Name: {feed['name']}, Tag: {feed['tag']}")
        print(f"Available keys: {', '.join(target_keys)}")
        choice = input(f"Map '{feed['name']}' to which key? (leave blank to skip): ").strip()
        if choice in target_keys:
            mapping[feed['id']] = (sanitize_column_name(choice), feed['engine'])
        elif choice:
            sanitized = sanitize_column_name(choice)
            print(f"Warning: '{choice}' is not a discovered key, using sanitized version '{sanitized}'.")
            mapping[feed['id']] = (sanitized, feed['engine'])

    if not mapping:
        print("No mappings created. Exiting.")
        return

    sqlite_conn = init_sqlite_db()
    cursor = sqlite_conn.cursor()

    # Ensure all target columns exist
    cursor.execute("PRAGMA table_info(data_points)")
    existing_cols = [row[1] for row in cursor.fetchall()]
    for target_key, _ in mapping.values():
        if target_key not in existing_cols:
            print(f"Adding column {target_key}")
            cursor.execute(f"ALTER TABLE data_points ADD COLUMN {target_key} REAL")
            existing_cols.append(target_key)

    cursor.execute("SELECT count(*) FROM data_points")
    if cursor.fetchone()[0] > 0:
        action = input("\nSQLite database already contains data. (A)ppend or (C)lear? [A/C]: ").upper()
        if action == 'C':
            cursor.execute("DELETE FROM data_points")
            sqlite_conn.commit()
            print("Database cleared.")

    print("\n--- Extracting and Merging Data ---")

    data_path = DEFAULT_EMONCMS_PATH
    if any(m[1] == 6 for m in mapping.values()):
        if not os.path.exists(os.path.join(data_path, "phpfina")):
            print(f"Warning: EmonCMS data path '{data_path}/phpfina' not found.")
            data_path = input(f"Please enter correct base path (containing phpfina/): ")

    merged_data = {}

    for feed_id, (target_key, engine) in mapping.items():
        print(f"Fetching data for feed {feed_id} ({target_key})...")
        points = []
        if engine == 6:
            points = read_phpfina(feed_id, data_path, start_ts, end_ts)
        elif engine == 0:
            points = read_mysql_feed(mysql_conn, feed_id, start_ts, end_ts)

        for ts, val in points:
            rounded_ts = int(ts // TIME_WINDOW_SECONDS) * TIME_WINDOW_SECONDS
            if rounded_ts not in merged_data:
                merged_data[rounded_ts] = {}
            merged_data[rounded_ts][target_key] = val

    print(f"Merging complete. Inserting {len(merged_data)} entries into SQLite...")

    sorted_timestamps = sorted(merged_data.keys())
    for ts in sorted_timestamps:
        dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
        dt_str = dt.strftime('%Y-%m-%d %H:%M:%S') # Second precision

        row_data = merged_data[ts]
        cols = list(row_data.keys())
        placeholders = ",".join(["?"] * len(cols))

        query = f"INSERT INTO data_points (timestamp, {','.join(cols)}) VALUES (?, {placeholders})"
        cursor.execute(query, [dt_str] + list(row_data.values()))

    sqlite_conn.commit()
    sqlite_conn.close()
    mysql_conn.close()
    print("\nMigration completed successfully!")

if __name__ == "__main__":
    main()
