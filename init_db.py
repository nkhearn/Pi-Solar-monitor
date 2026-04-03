import sqlite3
import os

DB_PATH = "data/inverter_logs.db"

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check if we need to reinit due to schema change (presence of 'data' column)
    try:
        cursor.execute("PRAGMA table_info(data_points)")
        columns = [row[1] for row in cursor.fetchall()]
        if "data" in columns:
            print("Old schema detected. Dropping data_points table for reinitialization.")
            cursor.execute("DROP TABLE data_points")
            columns = []
    except sqlite3.OperationalError:
        # Table might not exist yet
        columns = []

    # Create table if it doesn't exist (fresh install or after drop)
    # Using second precision for timestamp as requested
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS data_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Index for faster time-range queries
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON data_points(timestamp)')

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
