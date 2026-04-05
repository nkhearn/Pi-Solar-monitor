import requests
from typing import Optional, List, Dict, Any, Union

BASE_URL = "http://localhost:8000"

def get_available_metrics() -> List[str]:
    """
    Recommended first step: Retrieve a list of all available metric keys (both physical and virtual).
    This helps identify which data points can be queried.
    """
    response = requests.get(f"{BASE_URL}/api/keys")
    response.raise_for_status()
    return response.json()

def get_latest_system_data() -> Dict[str, Any]:
    """
    Retrieve the most recent aggregated data point for all metrics in the system.
    Returns:
        A dictionary containing the latest timestamp and the data values.
    """
    response = requests.get(f"{BASE_URL}/api/last")
    response.raise_for_status()
    return response.json()

def get_system_history(
    limit: int = 100,
    start: Optional[str] = None,
    end: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retrieve a list of recent aggregated data points for the entire system.
    Args:
        limit: Max number of records to return (default 100).
        start: ISO timestamp or relative time (e.g., '1h', 'today') to filter from.
        end: ISO timestamp or relative time to filter until.
    """
    params = {"limit": limit}
    if start: params["start"] = start
    if end: params["end"] = end
    response = requests.get(f"{BASE_URL}/api/history", params=params)
    response.raise_for_status()
    return response.json()

def get_latest_metric_value(metric_key: str) -> Dict[str, Any]:
    """
    Retrieve the most recent value for a specific metric.
    Args:
        metric_key: The name of the metric (e.g., 'battery_voltage').
    """
    response = requests.get(f"{BASE_URL}/api/data/{metric_key}/last")
    response.raise_for_status()
    return response.json()

def get_metric_history(
    metric_key: str,
    limit: int = 100,
    start: Optional[str] = None,
    end: Optional[str] = None,
    gt: Optional[float] = None,
    lt: Optional[float] = None,
    eq: Optional[float] = None
) -> List[List[Union[str, float]]]:
    """
    Retrieve historical values for a specific metric in a compact format [timestamp, value].
    Args:
        metric_key: The name of the metric.
        limit: Max number of records.
        start: Start time filter.
        end: End time filter.
        gt: Value must be Greater Than this.
        lt: Value must be Less Than this.
        eq: Value must be Equal To this.
    """
    params = {"limit": limit}
    if start: params["start"] = start
    if end: params["end"] = end
    if gt is not None: params["gt"] = gt
    if lt is not None: params["lt"] = lt
    if eq is not None: params["eq"] = eq

    response = requests.get(f"{BASE_URL}/api/data/{metric_key}/history", params=params)
    response.raise_for_status()
    return response.json()

def get_metric_stats(
    metric_key: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    gt: Optional[float] = None,
    lt: Optional[float] = None,
    eq: Optional[float] = None
) -> Dict[str, Any]:
    """
    Retrieve aggregate statistics (avg, min, max, sum, count) for a metric over a period.
    Args:
        metric_key: The name of the metric.
        start/end: Time range filters.
        gt/lt/eq: Value filters.
    """
    params = {}
    if start: params["start"] = start
    if end: params["end"] = end
    if gt is not None: params["gt"] = gt
    if lt is not None: params["lt"] = lt
    if eq is not None: params["eq"] = eq

    response = requests.get(f"{BASE_URL}/api/data/{metric_key}/stats", params=params)
    response.raise_for_status()
    return response.json()

def get_specific_metric_stat(
    metric_key: str,
    stat_key: str,
    start: Optional[str] = None,
    end: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieve a single specific statistic for a metric.
    Args:
        metric_key: The name of the metric.
        stat_key: One of 'avg', 'min', 'max', 'sum', 'count'.
        start/end: Time range filters.
    """
    params = {}
    if start: params["start"] = start
    if end: params["end"] = end

    response = requests.get(f"{BASE_URL}/api/data/{metric_key}/stats/{stat_key}", params=params)
    response.raise_for_status()
    return response.json()

def list_virtual_metrics() -> List[Dict[str, str]]:
    """
    List all defined virtual metrics and their calculation formulas.
    """
    response = requests.get(f"{BASE_URL}/api/virtual_metrics")
    response.raise_for_status()
    return response.json()

def create_or_update_virtual_metric(name: str, formula: str) -> Dict[str, str]:
    """
    Create a new virtual metric or update an existing one.
    Args:
        name: The name for the virtual metric.
        formula: The math formula (e.g., 'pv_power / load').
    """
    payload = {"name": name, "formula": formula}
    response = requests.post(f"{BASE_URL}/api/virtual_metrics", json=payload)
    response.raise_for_status()
    return response.json()

def delete_virtual_metric(name: str) -> Dict[str, str]:
    """
    Delete a virtual metric by name.
    Args:
        name: The name of the virtual metric to delete.
    """
    response = requests.delete(f"{BASE_URL}/api/virtual_metrics/{name}")
    response.raise_for_status()
    return response.json()

def get_chart_data(
    metric: str,
    chart_type: str = "line",
    period: Optional[str] = None,
    limit: int = 100
) -> Union[Dict[str, Any], List[Any]]:
    """
    Unified endpoint for retrieving chart data.
    Args:
        metric: Metric key.
        chart_type: 'line' for historical trends, 'gauge' for latest value.
        period: Time range (e.g., '24h', 'today') for 'line' charts.
        limit: Max records for 'line' charts.
    """
    params = {"type": chart_type, "metric": metric, "limit": limit}
    if period: params["period"] = period

    response = requests.get(f"{BASE_URL}/api/chart/data", params=params)
    response.raise_for_status()
    return response.json()

def get_dashboard_charts() -> List[Dict[str, Any]]:
    """Retrieve current dashboard chart configurations."""
    response = requests.get(f"{BASE_URL}/api/charts")
    response.raise_for_status()
    return response.json()

def save_dashboard_charts(charts: List[Dict[str, Any]]) -> Dict[str, str]:
    """Save dashboard chart configurations."""
    response = requests.post(f"{BASE_URL}/api/charts", json=charts)
    response.raise_for_status()
    return response.json()

def get_metric_ui_configs() -> Dict[str, Dict[str, Any]]:
    """Retrieve metric-level UI configurations (display names, colors, etc.)."""
    response = requests.get(f"{BASE_URL}/api/metric_configs")
    response.raise_for_status()
    return response.json()

def save_metric_ui_configs(configs: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
    """Save metric-level UI configurations."""
    response = requests.post(f"{BASE_URL}/api/metric_configs", json=configs)
    response.raise_for_status()
    return response.json()
