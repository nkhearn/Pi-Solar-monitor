import asyncio
import os
import json
import sqlite3
import pytest
from datetime import datetime, timezone
import api
import condition_engine
from init_db import init_db

DB_PATH = "data/inverter_logs.db"

def setup_test_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Insert some test data
    now = datetime.now(timezone.utc)
    data = {"pv_voltage": 250, "battery_voltage": 52, "pv_power": 500}
    cursor.execute("INSERT INTO data_points (timestamp, data) VALUES (?, ?)",
                   (now.strftime('%Y-%m-%d %H:%M:%S.%f'), json.dumps(data)))

    # Insert older data for stats
    old_now = now.replace(minute=now.minute - 30 if now.minute >= 30 else 0)
    old_data = {"pv_voltage": 240, "battery_voltage": 51, "pv_power": 400}
    cursor.execute("INSERT INTO data_points (timestamp, data) VALUES (?, ?)",
                   (old_now.strftime('%Y-%m-%d %H:%M:%S.%f'), json.dumps(old_data)))

    conn.commit()
    conn.close()

@pytest.mark.asyncio
async def test_generated_columns_and_cache():
    setup_test_db()
    api._stats_cache = {} # Clear cache for test

    # Test last value retrieval using generated columns
    res = await api.get_data_last("pv_voltage")
    assert res["value"] == 250

    # Test stats retrieval using generated columns
    res_stats = await api.get_data_stats("pv_voltage", start="1h")
    assert res_stats["avg"] == 245.0
    assert res_stats["count"] == 2

    # Test cache
    api._stats_cache = {} # Clear cache for test
    # First call populates cache
    assert api._stats_cache == {}
    await api.get_data_stats("pv_voltage", start="1h")
    cache_key = ("pv_voltage", 'all', "1h", None, None, None, None)
    assert cache_key in api._stats_cache

    # Modify DB directly to see if cache is used
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE data_points SET data = json_set(data, '$.pv_voltage', 300)")
    conn.commit()
    conn.close()

    # Should still return cached value
    res_cached = await api.get_data_stats("pv_voltage", start="1h")
    assert res_cached["avg"] == 245.0

    # Test condition engine cache
    if os.path.exists('/tmp/condition_test.log'):
        os.remove('/tmp/condition_test.log')
    condition_engine.engine.cooldowns = {}

    # We'll mock evaluate_path to count calls
    original_evaluate_path = condition_engine.engine.evaluate_path
    call_count = 0
    async def mock_evaluate_path(path, current_data=None):
        nonlocal call_count
        call_count += 1
        return await original_evaluate_path(path, current_data)

    condition_engine.engine.evaluate_path = mock_evaluate_path

    # Remove other conditions to avoid interference
    os.rename('conditions/test_high_voltage.cond', 'conditions/test_high_voltage.cond.bak')

    # Create a condition that uses the same path twice
    with open('conditions/test_cache.cond', 'w') as f:
        f.write("[conditions]\n[or]\n/api/data/pv_voltage/last > 100\n/api/data/pv_voltage/last < 500\n[action]\necho 'cached' >> /tmp/condition_test.log\n")

    try:
        await condition_engine.engine.process_conditions()
    finally:
        os.rename('conditions/test_high_voltage.cond.bak', 'conditions/test_high_voltage.cond')

    # Wait for action
    await asyncio.sleep(1)

    # Check if action ran
    assert os.path.exists('/tmp/condition_test.log')

    # Should only have called evaluate_path once for /api/data/pv_voltage/last due to _current_eval_cache
    assert call_count == 1

    # Restore original
    condition_engine.engine.evaluate_path = original_evaluate_path
    os.remove('conditions/test_cache.cond')

if __name__ == "__main__":
    asyncio.run(test_generated_columns_and_cache())
