import sqlite3
import os

DB_PATH = "data/inverter_logs.db"

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create table if it doesn't exist (fresh install)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS data_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT (STRFTIME('%Y-%m-%d %H:%M:%f', 'NOW')),
            data TEXT
        )
    ''')

    # Migration for existing databases: check for generated columns and add if missing
    cursor.execute("PRAGMA table_info(data_points)")
    columns = [row[1] for row in cursor.fetchall()]

    migrations = [
        ("pv_voltage", "REAL GENERATED ALWAYS AS (json_extract(data, '$.pv_voltage')) VIRTUAL"),
        ("pv_power", "REAL GENERATED ALWAYS AS (json_extract(data, '$.pv_power')) VIRTUAL"),
        ("battery_voltage", "REAL GENERATED ALWAYS AS (json_extract(data, '$.battery_voltage')) VIRTUAL")
    ]

    for col_name, col_def in migrations:
        if col_name not in columns:
            print(f"Migrating: Adding column {col_name} to data_points")
            cursor.execute(f"ALTER TABLE data_points ADD COLUMN {col_name} {col_def}")

    # Index for faster time-range queries
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON data_points(timestamp)')
    # Indexes on frequently queried metrics to reduce disk I/O
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pv_voltage ON data_points(pv_voltage) WHERE pv_voltage IS NOT NULL')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pv_power ON data_points(pv_power) WHERE pv_power IS NOT NULL')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_battery_voltage ON data_points(battery_voltage) WHERE battery_voltage IS NOT NULL')

    # Table for virtual metrics
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS virtual_metrics (
            name TEXT PRIMARY KEY,
            formula TEXT NOT NULL
        )
    ''')

    # Table for dashboard configuration (charts)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dashboard_charts (
            id TEXT PRIMARY KEY,
            config TEXT NOT NULL
        )
    ''')

    # Table for metric configurations
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS metric_configs (
            key TEXT PRIMARY KEY,
            config TEXT NOT NULL
        )
    ''')

    # Enable Write-Ahead Logging for better concurrency and performance
    cursor.execute('PRAGMA journal_mode=WAL')

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
