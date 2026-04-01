import sqlite3
import os

DB_PATH = "data/inverter_logs.db"

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS data_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT (STRFTIME('%Y-%m-%d %H:%M:%f', 'NOW')),
            data TEXT
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
