import requests
from typing import List, Optional, Dict, Any

BASE_URL = "http://localhost:8000"

def get_available_metrics() -> List[str]:
    """
    Retrieves a list of all unique data keys available in the system, including virtual metrics.
    Recommended to run this initially to identify valid metrics for other queries.
    """
    response = requests.get(f"{BASE_URL}/api/keys")
    response.raise_for_status()
    return response.json()

def get_latest_data() -> Dict[str, Any]:
    """
    Returns the most recent aggregated data point, including timestamps and values for all metrics.
    """
    response = requests.get(f"{BASE_URL}/api/last")
    response.raise_for_status()
    return response.json()

def get_metric_last_value(metric_key: str) -> Dict[str, Any]:
    """
    Returns the most recent value and timestamp for a specific metric key.
    """
    response = requests.get(f"{BASE_URL}/api/data/{metric_key}/last")
    response.raise_for_status()
    return response.json()

def get_metric_history(
    metric_key: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    limit: int = 100
) -> List[List[Any]]:
    """
    Returns historical values for a specific metric key in a compact [timestamp, value] format.
    'start' and 'end' can be ISO timestamps or relative strings (e.g., 'today', '1h', '24h').
    """
    params = {"limit": limit}
    if start: params["start"] = start
    if end: params["end"] = end
    response = requests.get(f"{BASE_URL}/api/data/{metric_key}/history", params=params)
    response.raise_for_status()
    return response.json()

def get_metric_statistics(
    metric_key: str,
    start: Optional[str] = None,
    end: Optional[str] = None
) -> Dict[str, Any]:
    """
    Returns aggregate statistics (avg, min, max, sum, count) for a metric key over a period.
    """
    params = {}
    if start: params["start"] = start
    if end: params["end"] = end
    response = requests.get(f"{BASE_URL}/api/data/{metric_key}/stats", params=params)
    response.raise_for_status()
    return response.json()

def get_metric_specific_stat(
    metric_key: str,
    stat_key: str,
    start: Optional[str] = None,
    end: Optional[str] = None
) -> Dict[str, Any]:
    """
    Returns a single specific statistic (avg, min, max, sum, or count) for a metric key.
    """
    params = {}
    if start: params["start"] = start
    if end: params["end"] = end
    response = requests.get(f"{BASE_URL}/api/data/{metric_key}/stats/{stat_key}", params=params)
    response.raise_for_status()
    return response.json()

def list_virtual_metrics() -> List[Dict[str, str]]:
    """
    Returns all defined virtual metrics and their arithmetic formulas.
    """
    response = requests.get(f"{BASE_URL}/api/virtual_metrics")
    response.raise_for_status()
    return response.json()

def get_system_history(
    start: Optional[str] = None,
    end: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Returns a list of recent aggregated data points for the entire system.
    Each point includes a timestamp and a data object with all available metrics.
    """
    params = {"limit": limit}
    if start: params["start"] = start
    if end: params["end"] = end
    response = requests.get(f"{BASE_URL}/api/history", params=params)
    response.raise_for_status()
    return response.json()

if __name__ == "__main__":
    # Example usage
    try:
        print("Available metrics:", get_available_metrics())
        print("Latest data:", get_latest_data())
    except Exception as e:
        print(f"Error connecting to Pi Solar API: {e}")
