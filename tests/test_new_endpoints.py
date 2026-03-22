import urllib.request
import urllib.parse
import json
import time
import subprocess
import os
import signal

def test_api():
    base_url = "http://127.0.0.1:8000"

    def get(path):
        url = f"{base_url}{path}"
        with urllib.request.urlopen(url) as response:
            return response.getcode(), json.loads(response.read().decode())

    # 1. Test /api/keys
    print("Testing /api/keys...")
    status, data = get("/api/keys")
    print(f"Status: {status}, Keys: {data}")
    assert status == 200
    assert "solar_prediction" in data

    # 2. Test /api/data/solar_prediction/last
    print("\nTesting /api/data/solar_prediction/last...")
    status, data = get("/api/data/solar_prediction/last")
    print(f"Status: {status}, Data: {data}")
    assert status == 200
    assert "value" in data

    # 3. Test /api/data/solar_prediction/history
    print("\nTesting /api/data/solar_prediction/history...")
    status, data = get("/api/data/solar_prediction/history?limit=5")
    print(f"Status: {status}, History: {data}")
    assert status == 200
    assert isinstance(data, list)

    # 4. Test /api/data/solar_prediction/history with relative time
    print("\nTesting /api/data/solar_prediction/history with start=1h...")
    status, data = get("/api/data/solar_prediction/history?start=1h")
    print(f"Status: {status}, History count: {len(data)}")
    assert status == 200

    # 5. Test /api/data/solar_prediction/stats
    print("\nTesting /api/data/solar_prediction/stats...")
    status, data = get("/api/data/solar_prediction/stats")
    print(f"Status: {status}, Stats: {data}")
    assert status == 200
    assert "avg" in data
    assert "max" in data

    # 6. Test original /api/history with relative time
    print("\nTesting original /api/history with start=today...")
    status, data = get("/api/history?start=today")
    print(f"Status: {status}, History count: {len(data)}")
    assert status == 200

    # 7. Test SQL Injection Resilience
    print("\nTesting SQL Injection resilience on /api/data/{key}/last...")
    # Malicious key that tries to close the json_extract and append something else
    malicious_key = urllib.parse.quote("foo') OR 1=1 --")
    status, data = get(f"/api/data/{malicious_key}/last")
    print(f"Status: {status}, Data: {data}")
    # Should not return data and definitely not crash
    assert status == 200
    assert data["value"] is None

if __name__ == "__main__":
    # Start the server
    process = subprocess.Popen(["uvicorn", "api:app", "--host", "127.0.0.1", "--port", "8000"])
    time.sleep(5) # Wait for server to start

    try:
        test_api()
        print("\nAll tests passed!")
    except Exception as e:
        print(f"\nTests failed: {e}")
    finally:
        process.terminate()
        process.wait()
