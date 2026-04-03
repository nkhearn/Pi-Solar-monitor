import asyncio
import json
from api import app
from fastapi.testclient import TestClient
import sqlite3
import os
from engine import save_to_db

# Ensure we use the test database
DB_PATH = "data/inverter_logs.db"

client = TestClient(app)

def setup_module():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    from init_db import init_db
    init_db()

def test_api_with_new_schema():
    # 1. Insert some data via engine
    data1 = {"pv_voltage": 120.5, "battery_voltage": 13.2}
    save_to_db(data1)

    # 2. Test /api/keys
    response = client.get("/api/keys")
    assert response.status_code == 200
    keys = response.json()
    assert "pv_voltage" in keys
    assert "battery_voltage" in keys

    # 3. Test /api/last
    response = client.get("/api/last")
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["data"]["pv_voltage"] == 120.5
    assert res_data["data"]["battery_voltage"] == 13.2

    # 4. Test /api/data/{key}/last
    response = client.get("/api/data/pv_voltage/last")
    assert response.status_code == 200
    assert response.json()["value"] == 120.5

    # 5. Test /api/data/{key}/history
    response = client.get("/api/data/pv_voltage/history")
    assert response.status_code == 200
    history = response.json()
    assert len(history) == 1
    assert history[0][1] == 120.5

    # 6. Test virtual metrics
    client.post("/api/virtual_metrics", json={"name": "power", "formula": "pv_voltage * 2"})
    response = client.get("/api/last")
    assert response.json()["data"]["power"] == 241.0

    response = client.get("/api/data/power/last")
    assert response.json()["value"] == 241.0

    # 7. Test stats
    response = client.get("/api/data/pv_voltage/stats")
    assert response.json()["avg"] == 120.5
    assert response.json()["count"] == 1

if __name__ == "__main__":
    setup_module()
    test_api_with_new_schema()
    print("API tests passed!")
