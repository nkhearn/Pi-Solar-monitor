import pytest
import asyncio
from fastapi.testclient import TestClient
from api import app
import engine

client = TestClient(app)

def test_get_collectors():
    response = client.get("/api/collectors")
    assert response.status_code == 200
    data = response.json()
    assert "collectors" in data
    assert "non_minutely_keys" in data
    assert "metric_to_collector" in data

def test_trigger_collector():
    # Attempt triggering solar_prediction or solar_predict.py
    response = client.post("/api/collectors/trigger", json={"metric": "solar_prediction"})
    if response.status_code == 200:
        assert response.json()["status"] == "success"
        assert len(engine._manual_trigger_queue) > 0
    else:
        response2 = client.post("/api/collectors/trigger", json={"collector": "collectors/solar_predict.py"})
        assert response2.status_code == 200
        assert response2.json()["status"] == "success"
