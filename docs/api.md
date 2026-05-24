# 📡 REST API Documentation

The **Pi Solar Monitor** provides a comprehensive REST API for accessing live and historical data, managing virtual metrics, and configuring the dashboard.

## 🔗 Base URL
`http://<your-pi-ip>:8000`

---

## 🌍 Global Endpoints

### `GET` /api/last
Returns the most recent aggregated data point. This is a merged view containing the latest values for all physical and virtual metrics, along with their individual timestamps.

- **Example Request**:
  `GET /api/last`

- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    {
        "timestamp": "2023-10-27 15:44:01",
        "data": {
            "pv_input_power": 500.5,
            "battery_voltage": 52.4,
            "efficiency": 0.95
        },
        "metric_timestamps": {
            "pv_input_power": "2023-10-27 15:44:01",
            "battery_voltage": "2023-10-27 15:43:55",
            "efficiency": "2023-10-27 15:44:01"
        }
    }
    ```

---

### `GET` /api/history
Returns a list of recent system-wide data points.

- **Query Parameters**:
    - `limit` (optional): Max number of records (default 100).
    - `start` (optional): ISO timestamp (`2023-10-27 10:00:00`) or relative time (`1h`, `today`).
    - `end` (optional): ISO timestamp or relative time.

- **Example Request**:
  `GET /api/history?start=today&limit=5`

- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    [
        {
            "timestamp": "2023-10-27 15:44:01",
            "data": { "pv_input_power": 500.5, "battery_voltage": 52.4 }
        },
        {
            "timestamp": "2023-10-27 15:43:01",
            "data": { "pv_input_power": 490.2, "battery_voltage": 52.3 }
        }
    ]
    ```

---

### `GET` /api/keys
Returns an alphabetical list of all data keys currently in the database, including virtual metrics.

- **Example Request**:
  `GET /api/keys`

- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    [
        "battery_voltage",
        "efficiency",
        "pv_input_power",
        "solar_prediction",
        "water_temp"
    ]
    ```

---

## 📈 Data-Specific Endpoints

These endpoints focus on a single metric (key) and support both physical and virtual metrics.

### `GET` /api/data/{key}/last
Returns the most recent value and timestamp for a specific key.

- **Example Request**:
  `GET /api/data/pv_input_power/last`

- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    {
        "timestamp": "2023-10-27 15:45:01",
        "value": 500.5
    }
    ```

---

### `GET` /api/data/{key}/history
Returns historical values for a key in a compact format.

- **Query Parameters**:
    - `start` (optional): ISO timestamp or relative time (`10s`, `5m`, `1h`, `7d`, `today`).
    - `end` (optional): ISO timestamp or relative time.
    - `gt` (optional): Filter values greater than this number.
    - `lt` (optional): Filter values less than this number.
    - `eq` (optional): Filter values equal to this number.
    - `limit` (optional): Default 100.

- **Example Request (Relative Time)**:
  `GET /api/data/battery_voltage/history?start=1h&limit=10`

- **Example Request (Specific Date / Yesterday)**:
  `GET /api/data/pv_input_power/history?start=2023-10-26 00:00:00&end=2023-10-26 23:59:59`
  *(Note: To query for 'yesterday', provide the specific date range as shown above.)*

- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    [
        ["2023-10-27 15:45:01", 52.4],
        ["2023-10-27 15:44:01", 52.4],
        ["2023-10-27 15:43:01", 52.3]
    ]
    ```

---

### `GET` /api/data/{key}/stats
Returns summary statistics for a key over a period.

- **Query Parameters**:
    - `start`, `end`, `gt`, `lt`, `eq` (optional): Same as history endpoint.

- **Example Request**:
  `GET /api/data/pv_input_power/stats?start=today`

- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    {
        "avg": 450.2,
        "min": 0.0,
        "max": 1200.5,
        "sum": 324140.0,
        "count": 720
    }
    ```

---

### `GET` /api/data/{key}/stats/{stat_key}
Returns a single specific statistic.

- **URL Parameters**:
    - `stat_key`: `avg`, `min`, `max`, `sum`, or `count`.

- **Example Request**:
  `GET /api/data/battery_voltage/stats/avg?start=24h`

- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    {
        "value": 51.8
    }
    ```

---

## 📋 Daily Report Endpoint

### `GET` /api/daily_report
Returns calculated daily metrics for a specific date.

- **Query Parameters**:
    - `date` (required): Date in `YYYY-MM-DD` format.

- **Example Request**:
  `GET /api/daily_report?date=2023-10-26`

- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    {
        "date": "2023-10-26",
        "sample_count": 1440,
        "metrics": [
            {
                "title": "Total Solar Yield",
                "value": 12450.5,
                "unit": "Wh",
                "partial": false,
                "html_description": "Total energy generated by your solar panels today."
            },
            {
                "title": "Battery Efficiency",
                "value": 94.2,
                "unit": "%",
                "partial": false,
                "html_description": "How much energy you got back out of the battery compared to what you put in today."
            }
        ]
    }
    ```

---

## 📊 External Charts API

### `GET` /api/chart/data
A simplified endpoint for external integrations (e.g., custom widgets).

- **Query Parameters**:
    - `type` (required): `line` (for history) or `gauge` (for latest).
    - `metric` (required): The data key.
    - `period` (optional): Relative time (e.g., `1h`, `today`) for `line` charts.
    - `limit` (optional): Max records for `line` charts.

- **Example Request (Gauge)**:
  `GET /api/chart/data?type=gauge&metric=pv_input_power`

- **Success Response (Gauge)**:
  - **Code**: 200
  - **Content**:
    ```json
    {
        "timestamp": "2023-10-27 15:45:01",
        "value": 500.5
    }
    ```

- **Example Request (Line)**:
  `GET /api/chart/data?type=line&metric=pv_input_power&period=1h`

- **Success Response (Line)**:
  - **Code**: 200
  - **Content**:
    ```json
    [
        ["2023-10-27 15:45:01", 500.5],
        ["2023-10-27 15:44:01", 495.0]
    ]
    ```

---

## 🧮 Virtual Metrics

### `GET` /api/virtual_metrics
Lists all defined virtual metrics and their arithmetic formulas.

- **Example Request**:
  `GET /api/virtual_metrics`

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

- **Example Request**:
  `POST /api/virtual_metrics`
  **Body**:
  ```json
  {
      "name": "efficiency",
      "formula": "pv_power / load"
  }
  ```

- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    {
        "status": "success"
    }
    ```

---

### `DELETE` /api/virtual_metrics/{name}
Deletes a virtual metric.

- **Example Request**:
  `DELETE /api/virtual_metrics/efficiency`

- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    {
        "status": "success"
    }
    ```

---

## ⚙️ Configuration Endpoints

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
Saves the dashboard chart configuration.

- **Example Request**:
  `POST /api/charts`
  **Body**:
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

### `GET` /api/metric_configs
Returns customization settings for all metrics.

- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    {
        "pv_input_power": {
            "displayName": "Solar Production",
            "color": "#f1c40f",
            "hidden": false,
            "order": 1
        }
    }
    ```

---

### `POST` /api/metric_configs
Updates customization settings for one or more metrics.

- **Example Request**:
  `POST /api/metric_configs`
  **Body**:
  ```json
  {
      "pv_input_power": {
          "displayName": "Solar Production",
          "color": "#f1c40f",
          "hidden": false,
          "order": 1
      }
  }
  ```

---

## ⏲️ Time & Date Formats

### Relative Time
Used in `start`, `end`, and `period` parameters:
- `today`: Since 00:00:00 UTC.
- `[n][unit]`: `s` (seconds), `m` (minutes), `h` (hours), `d` (days). Example: `12h`, `30m`.

### Timestamps
Absolute timestamps should follow the internal format: `YYYY-MM-DD HH:MM:SS`.
Example: `2023-10-26 14:30:00`.

### Date Parameters
For the Daily Report, use `YYYY-MM-DD`.
Example: `2023-10-26`.
