import asyncio
import json
import httpx
import pytest
from api import app, notify_new_data, _latest_metrics_cache, invalidate_vm_cache
from engine import sanitize_column_name
import os

@pytest.mark.asyncio
async def test_cache_merging():
    import api
    api._latest_metrics_cache = {}
    invalidate_vm_cache()
    # Mock data payloads
    payload1 = {
        "timestamp": "2023-10-01 12:00:00",
        "data": {"minutely_metric": 10.5}
    }
    payload2 = {
        "timestamp": "2023-10-01 12:05:00",
        "data": {"hourly_metric": 100.0}
    }

    # We need to simulate the background tasks or call notify_new_data directly
    # notify_new_data is what updates the cache and broadcasts

    await notify_new_data(payload1)
    import api
    print(f"Cache after payload1: {api._latest_metrics_cache}")
    assert "minutely_metric" in api._latest_metrics_cache
    assert api._latest_metrics_cache["minutely_metric"]["value"] == 10.5

    await notify_new_data(payload2)
    assert "minutely_metric" in api._latest_metrics_cache
    assert "hourly_metric" in api._latest_metrics_cache
    assert api._latest_metrics_cache["minutely_metric"]["value"] == 10.5
    assert api._latest_metrics_cache["hourly_metric"]["value"] == 100.0
    assert api._latest_metrics_cache["hourly_metric"]["timestamp"] == "2023-10-01 12:05:00"

@pytest.mark.asyncio
async def test_api_last_merged():
    import api
    api._latest_metrics_cache = {}
    invalidate_vm_cache()
    await notify_new_data({
        "timestamp": "2023-10-01 12:00:00",
        "data": {"m1": 1}
    })
    await notify_new_data({
        "timestamp": "2023-10-01 12:01:00",
        "data": {"m2": 2}
    })

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/last")
        assert response.status_code == 200
        result = response.json()
        print(f"DEBUG api_last result: {result}")
        assert "m1" in result["data"]
        assert "m2" in result["data"]
        assert result["metric_timestamps"]["m1"] == "2023-10-01 12:00:00"
        assert result["metric_timestamps"]["m2"] == "2023-10-01 12:01:00"
        assert result["timestamp"] == "2023-10-01 12:01:00"

@pytest.mark.asyncio
async def test_cache_initialization_from_db():
    invalidate_vm_cache()
    # Manually insert data into DB
    import sqlite3
    from api import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM data_points")
    # Clean cache from previous tests that might have run in the same process
    import api
    api._latest_metrics_cache = {}
    cursor.execute("INSERT INTO data_points (timestamp, minutely_metric) VALUES ('2023-10-01 11:00:00', 5.5)")
    cursor.execute("INSERT INTO data_points (timestamp, hourly_metric) VALUES ('2023-10-01 10:00:00', 50.0)")
    conn.commit()
    conn.close()

    # Trigger cache initialization
    import api
    await api.ensure_cache_initialized()

    assert "minutely_metric" in api._latest_metrics_cache
    assert api._latest_metrics_cache["minutely_metric"]["value"] == 5.5
    assert api._latest_metrics_cache["minutely_metric"]["timestamp"] == "2023-10-01 11:00:00"
    assert "hourly_metric" in api._latest_metrics_cache
    assert api._latest_metrics_cache["hourly_metric"]["value"] == 50.0
    assert api._latest_metrics_cache["hourly_metric"]["timestamp"] == "2023-10-01 10:00:00"

if __name__ == "__main__":
    # To run this manually without pytest if needed
    async def run_tests():
        try:
            await test_cache_merging()
            print("test_cache_merging passed")
            await test_api_last_merged()
            print("test_api_last_merged passed")
            await test_cache_initialization_from_db()
            print("test_cache_initialization_from_db passed")
        except Exception as e:
            print(f"Tests failed: {e}")
            import traceback
            traceback.print_exc()

    asyncio.run(run_tests())
