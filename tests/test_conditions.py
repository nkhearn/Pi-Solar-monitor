import asyncio
import os
import json
import sqlite3
import pytest
from datetime import datetime
import api
import condition_engine

DB_PATH = "data/inverter_logs.db"

def setup_test_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS data_points')
    cursor.execute('''
        CREATE TABLE data_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT (STRFTIME('%Y-%m-%d %H:%M:%S.%f', 'NOW')),
            data TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS virtual_metrics (
            name TEXT PRIMARY KEY,
            formula TEXT NOT NULL
        )
    ''')

    # Insert some test data
    data = {"pv_voltage": 250, "battery_voltage": 52}
    cursor.execute('INSERT INTO data_points (data) VALUES (?)', (json.dumps(data),))

    # Insert older data for stats
    old_data = {"pv_voltage": 240}
    cursor.execute("INSERT INTO data_points (timestamp, data) VALUES (STRFTIME('%Y-%m-%d %H:%M:%S.%f', 'now', '-30 minutes'), ?)", (json.dumps(old_data),))

    conn.commit()
    conn.close()

@pytest.mark.asyncio
async def test_condition_evaluation():
    print("Setting up test database...")
    setup_test_db()

    print("Parsing condition file...")
    config = condition_engine.engine.parse_file('conditions/test_high_voltage.cond')
    print(f"Parsed config: {config}")

    print("Evaluating conditions...")
    # Clean up test log
    if os.path.exists('/tmp/condition_test.log'):
        os.remove('/tmp/condition_test.log')

    # Reset cooldowns
    condition_engine.engine.cooldowns = {}

    await condition_engine.engine.process_conditions()

    # Wait a bit for the async subprocess to finish
    await asyncio.sleep(1)

    assert os.path.exists('/tmp/condition_test.log')
    with open('/tmp/condition_test.log', 'r') as f:
        content = f.read().strip()
        print(f"Action result: {content}")
        assert "Action triggered: Voltage alert!" in content

if __name__ == "__main__":
    asyncio.run(test_condition_evaluation())
