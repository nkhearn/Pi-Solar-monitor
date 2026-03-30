import asyncio
import os
import json
import sqlite3
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
import api
import condition_engine

# Use the same DB path for consistency in tests
DB_PATH = "data/inverter_logs.db"
client = TestClient(api.app)

def setup_module(module):
    """Setup the test database with 70 minutes of data."""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE data_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT (STRFTIME('%Y-%m-%d %H:%M:%f', 'NOW')),
            data TEXT
        )
    ''')

    # Insert 70 data points, one per minute
    start_time = datetime.now() - timedelta(minutes=70)
    for i in range(71):
        timestamp = (start_time + timedelta(minutes=i)).strftime('%Y-%m-%d %H:%M:%f')
        # Use simple predictable values for testing stats
        # voltage: 200, 201, 202...
        data = {
            "voltage": 200 + i,
            "current": 10 + (i % 10),
            "power": (200 + i) * (10 + (i % 10)),
            "temperature": 20 + (i / 10.0),
            "humidity": 50
        }
        cursor.execute('INSERT INTO data_points (timestamp, data) VALUES (?, ?)', (timestamp, json.dumps(data)))

    conn.commit()
    conn.close()

def test_api_last():
    response = client.get("/api/last")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert data["data"]["voltage"] == 270 # 200 + 70

def test_api_keys():
    response = client.get("/api/keys")
    assert response.status_code == 200
    keys = response.json()
    assert "voltage" in keys
    assert "current" in keys
    assert "power" in keys
    assert "temperature" in keys
    assert "humidity" in keys

def test_api_data_last():
    response = client.get("/api/data/voltage/last")
    assert response.status_code == 200
    assert response.json()["value"] == 270

def test_api_stats_5m():
    # Last 5 minutes should have data points at index 66, 67, 68, 69, 70
    # Values for voltage: 266, 267, 268, 269, 270
    # Avg: 268
    # Sum: 1340
    # Count: 5
    response = client.get("/api/data/voltage/stats?start=5m")
    assert response.status_code == 200
    stats = response.json()
    assert stats["count"] == 5
    assert stats["avg"] == 268
    assert stats["sum"] == 1340
    assert stats["min"] == 266
    assert stats["max"] == 270

def test_api_stats_1h():
    # Last 60 minutes: 60 points
    # Values: 211 to 270
    # Avg: (211+270)/2 = 240.5
    # Count: 60
    response = client.get("/api/data/voltage/stats?start=1h")
    assert response.status_code == 200
    stats = response.json()
    assert stats["count"] == 60
    assert stats["avg"] == 240.5
    assert stats["min"] == 211
    assert stats["max"] == 270

@pytest.mark.asyncio
async def test_condition_engine():
    # Create a test condition file
    cond_content = """[conditions]
[and]
/api/data/voltage/last > 260
/api/data/voltage/stats/avg?start=1h > 240
[action]
touch /tmp/test_suite_triggered
[cooldown]
1s
"""
    with open('conditions/test_suite.cond', 'w') as f:
        f.write(cond_content)

    if os.path.exists('/tmp/test_suite_triggered'):
        os.remove('/tmp/test_suite_triggered')

    # Reset cooldowns
    condition_engine.engine.cooldowns = {}

    await condition_engine.engine.process_conditions()

    # Wait a bit for the subprocess to execute
    await asyncio.sleep(1)

    # Check if action triggered
    assert os.path.exists('/tmp/test_suite_triggered')
    os.remove('/tmp/test_suite_triggered')
    os.remove('conditions/test_suite.cond')
