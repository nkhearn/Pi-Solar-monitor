import requests
import time

def test_sql_injection():
    base_url = "http://127.0.0.1:8000"

    print("Testing SQL Injection resilience on /api/data/{key}/last...")
    malicious_key = "foo') OR 1=1 --"
    response = requests.get(f"{base_url}/api/data/{malicious_key}/last")
    print(f"Status: {response.status_code}, Data: {response.json()}")
    assert response.status_code == 200
    assert response.json()["value"] is None

    print("\nTesting SQL Injection resilience on /api/data/{key}/stats...")
    response = requests.get(f"{base_url}/api/data/{malicious_key}/stats")
    print(f"Status: {response.status_code}, Stats: {response.json()}")
    assert response.status_code == 200
    assert response.json()["avg"] is None

if __name__ == "__main__":
    time.sleep(2)
    try:
        test_sql_injection()
        print("\nSQL Injection tests passed!")
    except Exception as e:
        print(f"\nSQL Injection tests failed: {e}")
