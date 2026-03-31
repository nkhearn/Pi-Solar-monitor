import requests
import time
import subprocess
import os
import signal
import json

def test_virtual_metrics_and_charts():
    base_url = "http://127.0.0.1:8000"

    # 1. Create a virtual metric
    print("Testing creation of virtual metric...")
    vm_payload = {
        "name": "test_vm",
        "formula": "pv_power * 2"
    }
    response = requests.post(f"{base_url}/api/virtual_metrics", json=vm_payload)
    print(f"Status: {response.status_code}, Body: {response.json()}")
    assert response.status_code == 200

    # 2. Check if it appears in /api/keys
    print("\nTesting if virtual metric appears in /api/keys...")
    response = requests.get(f"{base_url}/api/keys")
    keys = response.json()
    print(f"Keys: {keys}")
    assert "test_vm" in keys

    # 3. Test /api/data/test_vm/last
    # Note: This requires some data in the DB with 'pv_power' key.
    # If no data, it might return None, which is fine for connection test.
    print("\nTesting /api/data/test_vm/last...")
    response = requests.get(f"{base_url}/api/data/test_vm/last")
    print(f"Status: {response.status_code}, Data: {response.json()}")
    assert response.status_code == 200

    # 4. Save charts
    print("\nTesting saving charts...")
    charts_payload = [
        {"id": "c1", "title": "Chart 1", "metric": "test_vm", "type": "line", "range": "1h"}
    ]
    response = requests.post(f"{base_url}/api/charts", json=charts_payload)
    print(f"Status: {response.status_code}, Body: {response.json()}")
    assert response.status_code == 200

    # 5. Load charts
    print("\nTesting loading charts...")
    response = requests.get(f"{base_url}/api/charts")
    charts = response.json()
    print(f"Charts: {charts}")
    assert len(charts) == 1
    assert charts[0]["id"] == "c1"
    assert charts[0]["metric"] == "test_vm"

    # 6. Delete virtual metric
    print("\nTesting deletion of virtual metric...")
    response = requests.delete(f"{base_url}/api/virtual_metrics/test_vm")
    assert response.status_code == 200

    response = requests.get(f"{base_url}/api/keys")
    assert "test_vm" not in response.json()

if __name__ == "__main__":
    # Ensure DB is initialized
    subprocess.run(["python3", "init_db.py"])

    # Start the server
    process = subprocess.Popen(["uvicorn", "api:app", "--host", "127.0.0.1", "--port", "8000"])
    time.sleep(5) # Wait for server to start

    try:
        test_virtual_metrics_and_charts()
        print("\nAll integration tests passed!")
    except Exception as e:
        print(f"\nTests failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        process.terminate()
        process.wait()
