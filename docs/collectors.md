# Data Collectors

The Pi Solar Monitor uses a modular collection system. This allows you to easily add new data sources without modifying the core engine.

## How it Works

1.  **Polling**: The `engine.py` runs every minute.
2.  **Execution**: It scans the `collectors/` directory for any file that has **execution permissions**.
3.  **Aggregation**: Each collector is executed. The engine expects a valid **JSON object** on `stdout`.
4.  **Merging**: All JSON objects are merged into a single dictionary.
5.  **Storage**: The aggregated dictionary is saved to the SQLite database with a timestamp.

---

## Existing Collectors

### 1. Inverter (`inverter.py`)
Queries a Voltronic-compatible inverter using the `mpp-solar` utility.
- **Requirement**: `mpp-solar` installed and inverter connected via USB (`/dev/hidraw0`).
- **Data**: AC voltage/frequency, Battery voltage/SOC, PV current, etc.

### 2. Solar Prediction (`solar_predict.py`)
Uses the Open-Meteo API to predict solar energy yield for the current day.
- **Method**: Fetches Global Tilted Irradiance (GTI) based on specified latitude, longitude, panel tilt, and azimuth.
- **Calculation**: Sums hourly GTI and scales by rated capacity and efficiency.

### 3. Temperatures (`temps.py`)
Reads DS18B20 temperature sensors connected via the 1-Wire interface.
- **Requirement**: 1-Wire enabled on Raspberry Pi.
- **Sensors**: Configured via a mapping of labels to unique sensor IDs found in `/sys/bus/w1/devices/`.

---

## Creating a Custom Collector

You can write a collector in any language (Python, Bash, C, etc.) as long as it outputs JSON.

### Python Example

```python
#!/usr/bin/env python3
import json
import random

# Your logic to read a sensor
def get_sensor_data():
    return {
        "outside_humidity": random.randint(40, 60)
    }

if __name__ == "__main__":
    # Output MUST be JSON to stdout
    print(json.dumps(get_sensor_data()))
```

### Bash Example

```bash
#!/bin/bash
cpu_temp=$(cat /sys/class/thermal/thermal_zone0/temp)
echo "{\"cpu_temperature\": $(($cpu_temp / 1000))}"
```

### Example: Analog Voltage Sensor (via ADC)

Here is an example of a Python collector that reads a voltage from an ADS1115 ADC:

```python
#!/usr/bin/env python3
import json
import sys

# Example using a library like Adafruit_ADS1x15
# (Ensure you install necessary libraries first)
try:
    # This is a mock example of reading an ADC
    # In a real scenario, you'd use: import Adafruit_ADS1x15

    voltage_reading = 12.65  # Replace with actual sensor reading logic

    data = {
        "battery_voltage": voltage_reading
    }

    print(json.dumps(data))
except Exception as e:
    # It's best to output nothing or handle errors silently to avoid
    # corrupting the aggregated JSON if the engine doesn't catch it.
    sys.exit(1)
```

**Steps to implement:**
1. Save the script in the `collectors/` directory (e.g., `collectors/voltage.py`).
2. Make it executable: `chmod +x collectors/voltage.py`.

### Deployment Steps

1.  Save your script in the `collectors/` directory.
2.  **Make it executable**: `chmod +x collectors/my_collector.py`.
3.  The engine will automatically pick it up on the next minute mark.

### Best Practices

- **Timeout**: Collectors should be fast. If a sensor might hang, implement a timeout within your script.
- **Error Handling**: If a collection fails, it is often better to output an empty object `{}` or a specific error key (e.g., `{"sensor_error": "Connection failed"}`) rather than exiting with an error, which might cause the engine to skip other collectors.
- **Unique Keys**: Ensure your JSON keys do not conflict with other collectors, as later collectors will overwrite values from earlier ones (sorted by filename).
- **Data**: AC voltage/frequency, Battery voltage/SOC, PV current, etc.

### 2. Solar Prediction (`solar_predict.py`)
Uses the Open-Meteo API to predict solar energy yield for the current day.
- **Method**: Fetches Global Tilted Irradiance (GTI) based on specified latitude, longitude, panel tilt, and azimuth.
- **Calculation**: Sums hourly GTI and scales by rated capacity and efficiency.

### 3. Temperatures (`temps.py`)
Reads DS18B20 temperature sensors connected via the 1-Wire interface.
- **Requirement**: 1-Wire enabled on Raspberry Pi.
- **Sensors**: Configured via a mapping of labels to unique sensor IDs found in `/sys/bus/w1/devices/`.

---

## Creating a Custom Collector

You can write a collector in any language (Python, Bash, C, etc.) as long as it outputs JSON.

### Python Example

```python
#!/usr/bin/env python3
import json
import random

# Your logic to read a sensor
def get_sensor_data():
    return {
        "outside_humidity": random.randint(40, 60)
    }

if __name__ == "__main__":
    # Output MUST be JSON to stdout
    print(json.dumps(get_sensor_data()))
```

### Bash Example

```bash
#!/bin/bash
cpu_temp=$(cat /sys/class/thermal/thermal_zone0/temp)
echo "{\"cpu_temperature\": $(($cpu_temp / 1000))}"
```

### Deployment Steps

1.  Save your script in the `collectors/` directory.
2.  **Make it executable**: `chmod +x collectors/my_collector.py`.
3.  The engine will automatically pick it up on the next minute mark.

### Best Practices

- **Timeout**: Collectors should be fast. If a sensor might hang, implement a timeout within your script.
- **Error Handling**: If a collection fails, it is often better to output an empty object `{}` or a specific error key (e.g., `{"sensor_error": "Connection failed"}`) rather than exiting with an error, which might cause the engine to skip other collectors.
- **Unique Keys**: Ensure your JSON keys do not conflict with other collectors, as later collectors will overwrite values from earlier ones (sorted by filename).
