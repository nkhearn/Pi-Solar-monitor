import requests
import time
import subprocess
import os
import signal

def test_api():
    base_url = "http://127.0.0.1:8000"

    # 1. Test /api/keys
    print("Testing /api/keys...")
    response = requests.get(f"{base_url}/api/keys")
    print(f"Status: {response.status_code}, Keys: {response.json()}")
    assert response.status_code == 200
    assert "solar_prediction" in response.json()

    # 2. Test /api/data/solar_prediction/last
    print("\nTesting /api/data/solar_prediction/last...")
    response = requests.get(f"{base_url}/api/data/solar_prediction/last")
    print(f"Status: {response.status_code}, Data: {response.json()}")
    assert response.status_code == 200
    assert "value" in response.json()

    # 3. Test /api/data/solar_prediction/history
    print("\nTesting /api/data/solar_prediction/history...")
    response = requests.get(f"{base_url}/api/data/solar_prediction/history?limit=5")
    print(f"Status: {response.status_code}, History: {response.json()}")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

    # 4. Test /api/data/solar_prediction/history with relative time
    print("\nTesting /api/data/solar_prediction/history with start=1h...")
    response = requests.get(f"{base_url}/api/data/solar_prediction/history?start=1h")
    print(f"Status: {response.status_code}, History count: {len(response.json())}")
    assert response.status_code == 200

    # 5. Test /api/data/solar_prediction/stats
    print("\nTesting /api/data/solar_prediction/stats...")
    response = requests.get(f"{base_url}/api/data/solar_prediction/stats")
    print(f"Status: {response.status_code}, Stats: {response.json()}")
    assert response.status_code == 200
    assert "avg" in response.json()
    assert "max" in response.json()

    # 6. Test original /api/history with relative time
    print("\nTesting original /api/history with start=today...")
    response = requests.get(f"{base_url}/api/history?start=today")
    print(f"Status: {response.status_code}, History count: {len(response.json())}")
    assert response.status_code == 200

    # 7. Test SQL Injection Resilience
    print("\nTesting SQL Injection resilience on /api/data/{key}/last...")
    # Malicious key that tries to close the json_extract and append something else
    malicious_key = "foo') OR 1=1 --"
    response = requests.get(f"{base_url}/api/data/{malicious_key}/last")
    print(f"Status: {response.status_code}, Data: {response.json()}")
    # Should not return data and definitely not crash
    assert response.status_code == 200
    assert response.json()["value"] is None

    # 8. Test /api/chart/data (gauge)
    print("\nTesting /api/chart/data?type=gauge&metric=solar_prediction...")
    response = requests.get(f"{base_url}/api/chart/data?type=gauge&metric=solar_prediction")
    print(f"Status: {response.status_code}, Data: {response.json()}")
    assert response.status_code == 200
    assert "value" in response.json()

    # 9. Test /api/chart/data (line)
    print("\nTesting /api/chart/data?type=line&metric=solar_prediction&period=1h...")
    response = requests.get(f"{base_url}/api/chart/data?type=line&metric=solar_prediction&period=1h")
    print(f"Status: {response.status_code}, History count: {len(response.json())}")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

    # 10. Test /api/chart/data with invalid type
    print("\nTesting /api/chart/data with invalid type...")
    response = requests.get(f"{base_url}/api/chart/data?type=invalid&metric=solar_prediction")
    print(f"Status: {response.status_code}, Detail: {response.json()}")
    assert response.status_code == 422 # Validation error for pattern mismatch

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
