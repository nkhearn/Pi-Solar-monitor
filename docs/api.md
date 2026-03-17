# REST API Documentation

The Pi Solar Monitor provides a comprehensive REST API for accessing latest and historical data.

## Base URL
`http://<your-pi-ip>:8000`

---

## Global Endpoints

### Get Latest Record
Returns the most recent aggregated data point.

- **URL**: `/api/last`
- **Method**: `GET`
- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    {
        "timestamp": "2026-03-17 15:44:01.031",
        "data": {
            "inverter_error": "[Errno 2] No such file or directory: '/home/pi/.local/bin/mpp-solar'",
            "solar_prediction": 1523.08
        }
    }
    ```

### Get Historical Records
Returns a list of recent aggregated data points.

- **URL**: `/api/history`
- **Method**: `GET`
- **Query Parameters**:
    - `limit` (optional): Max number of records (default 100).
    - `start` (optional): ISO timestamp or relative time (e.g., `1h`, `today`).
    - `end` (optional): ISO timestamp or relative time.
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

### Get Available Keys
Returns a list of all unique data keys found in recent records.

- **URL**: `/api/keys`
- **Method**: `GET`
- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    [
        "ac_input_voltage",
        "battery_voltage",
        "solar_prediction",
        "water_in",
        "water_out"
    ]
    ```

---

## Data-Specific Endpoints

These endpoints focus on a single metric (key) within the data.

### Get Latest Value for Key
Returns the most recent value for a specific key.

- **URL**: `/api/data/{key}/last`
- **Method**: `GET`
- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    {
        "timestamp": "2026-03-17 15:45:01.080",
        "value": 1523.08
    }
    ```

### Get Historical Values for Key
Returns historical values for a key in a compact format suitable for charting.

- **URL**: `/api/data/{key}/history`
- **Method**: `GET`
- **Query Parameters**:
    - `limit` (optional): Default 100.
    - `start`, `end` (optional): ISO timestamp or relative time (`10s`, `5m`, `1h`, `7d`, `today`).
    - `gt`, `lt`, `eq` (optional): Value filters (Greater than, Less than, Equal to).
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

### Get Statistics for Key
Returns aggregate statistics for a key over a period.

- **URL**: `/api/data/{key}/stats`
- **Method**: `GET`
- **Query Parameters**:
    - `start`, `end` (optional): Time range.
    - `gt`, `lt`, `eq` (optional): Value filters.
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

## Time Filtering Format

The `start` and `end` parameters support:
- **ISO Timestamps**: `2023-10-27 10:00:00`
- **Relative Strings**:
    - `today`: Since midnight.
    - `[number][unit]`: Where unit is `s` (seconds), `m` (minutes), `h` (hours), or `d` (days). Example: `24h` for the last 24 hours.
