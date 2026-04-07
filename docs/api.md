# 📡 REST API Documentation

The **Pi Solar Monitor** provides a comprehensive REST API for accessing latest and historical data.

## 🔗 Base URL
`http://<your-pi-ip>:8000`

---

## 🌍 Global Endpoints

### `GET` /api/last
Returns the most recent aggregated data point, including any defined virtual metrics.

- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    {
        "timestamp": "2026-03-17 15:44:01.031",
        "data": {
            "pv_power": 500,
            "load": 200,
            "efficiency": 2.5
        }
    }
    ```

---

### `GET` /api/history
Returns a list of recent aggregated data points.

- **Query Parameters**:
    - `limit` (optional): Max number of records (default 100).
    - `start` (optional): ISO timestamp or relative time (e.g., `1h`, `today`).
    - `end` (optional): ISO timestamp or relative time.

- **Example**: `/api/history?start=2024-03-20%2010:00:00&end=2024-03-20%2012:00:00&limit=50`

- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    [
        {
            "timestamp": "2026-03-17 15:44:01.031",
            "data": { "solar_prediction": 1523.08, ... }
        },
        {
            "timestamp": "2026-03-17 15:43:41.152",
            "data": { "solar_prediction": 1523.08, ... }
        }
    ]
    ```

---

### `GET` /api/keys
Returns a list of all unique data keys found in recent records, plus all defined virtual metrics.

- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    [
        "ac_input_voltage",
        "battery_voltage",
        "solar_prediction",
        "efficiency",
        "water_in",
        "water_out"
    ]
    ```

---

## 📈 Data-Specific Endpoints

These endpoints focus on a single metric (key) within the data. They support both physical and virtual metrics.

### `GET` /api/data/{key}/last
Returns the most recent value for a specific key.

- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    {
        "timestamp": "2026-03-17 15:45:01.080",
        "value": 1523.08
    }
    ```

---

### `GET` /api/data/{key}/history
Returns historical values for a key in a compact format suitable for charting.

- **Query Parameters**:
    - `limit` (optional): Default 100.
    - `start`, `end` (optional): ISO timestamp or relative time (`10s`, `5m`, `1h`, `7d`, `today`).
    - `gt`, `lt`, `eq` (optional): Value filters (Greater than, Less than, Equal to).

- **Example**: `/api/data/pv_power/history?start=2024-03-20%2000:00:00&end=2024-03-20%2023:59:59`

- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    [
        ["2026-03-17 15:45:01.080", 1523.08],
        ["2026-03-17 15:44:01.031", 1523.08],
        ["2026-03-17 15:43:41.152", 1523.08]
    ]
    ```

---

### `GET` /api/data/{key}/stats
Returns aggregate statistics for a key over a period.

- **Query Parameters**:
    - `start`, `end` (optional): Time range.
    - `gt`, `lt`, `eq` (optional): Value filters.

- **Example**: `/api/data/battery_voltage/stats?start=2024-03-19%2012:00:00&end=2024-03-20%2012:00:00`

- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    {
        "avg": 1484.5020833333335,
        "min": 1463.9,
        "max": 1549.81,
        "sum": 35628.05,
        "count": 24
    }
    ```

---

### `GET` /api/data/{key}/stats/{stat_key}
Returns a single specific statistic for a key.

- **URL Parameters**:
    - `stat_key`: The statistic to return. Available: `avg`, `min`, `max`, `sum`, `count`.

- **Query Parameters**:
    - `start`, `end` (optional): Time range. Example: `24h` for the last 24 hours.
    - `gt`, `lt`, `eq` (optional): Value filters.

- **Examples**:
    - `/api/data/battery_voltage/stats/avg?start=24h`
    - `/api/data/pv_power/stats/sum?start=2024-03-20%2006:00:00&end=2024-03-20%2018:00:00`

- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    {
        "value": 12.5
    }
    ```

---

## 🧮 Virtual Metric Management Endpoints

### `GET` /api/virtual_metrics
Returns all defined virtual metrics and their formulas.

- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    [
        {"name": "efficiency", "formula": "pv_power / load"},
        {"name": "total_input", "formula": "pv_power + grid_power"}
    ]
    ```

---

### `POST` /api/virtual_metrics
Creates or updates a virtual metric.

- **Request Body**:
    ```json
    {
        "name": "efficiency",
        "formula": "pv_power / load"
    }
    ```

---

### `DELETE` /api/virtual_metrics/{name}
Deletes a virtual metric.

- **Success Response**:
  - **Code**: 200
  - **Content**: `{"status": "success"}`

---

## 📊 External Charts API

### `GET` /api/chart/data
Unified endpoint for external chart data access. Supports both historical trends and latest values.

- **Query Parameters**:
    - `type` (required): Chart type. Available: `line` (historical), `gauge` (latest).
    - `metric` (required): The data key to retrieve.
    - `period` (optional): Relative time range (e.g., `1h`, `24h`, `7d`, `today`). Only applicable for `type=line`.
    - `limit` (optional): Max number of records for historical data (default 100).

- **Success Response (type=gauge)**:
  - **Code**: 200
  - **Content**:
    ```json
    {
        "timestamp": "2026-03-17 15:45:01.080",
        "value": 1523.08
    }
    ```

- **Success Response (type=line)**:
  - **Code**: 200
  - **Content**:
    ```json
    [
        ["2026-03-17 15:45:01.080", 1523.08],
        ["2026-03-17 15:44:01.031", 1523.08]
    ]
    ```

---

## 📊 Dashboard Chart Endpoints

### `GET` /api/charts
Returns the persistent dashboard chart configuration.

- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    [
        {
            "id": "1710712345678",
            "title": "Solar Power",
            "metric": "pv_power",
            "type": "line",
            "range": "1h"
        }
    ]
    ```

---

### `POST` /api/charts
Saves the dashboard chart configuration. Overwrites existing configuration.

- **Request Body**:
    ```json
    [
        {
            "id": "1710712345678",
            "title": "Solar Power",
            "metric": "pv_power",
            "type": "line",
            "range": "1h"
        }
    ]
    ```

---

## ⏲️ Time Filtering Format

The `start` and `end` parameters support:
- **ISO Timestamps**: `2023-10-27 10:00:00`
- **Relative Strings**:
    - `today`: Since midnight.
    - `[number][unit]`: Where unit is `s` (seconds), `m` (minutes), `h` (hours), or `d` (days). Example: `24h` for the last 24 hours.
