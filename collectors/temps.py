#!/usr/bin/env python3
import os
import json

TEMP_SENSORS = {
    'water_in': "28-00000ac879c7",
    'water_out': "28-00000ac8e16c"
}
W1_DEVICE_PATH = "/sys/bus/w1/devices/"

def get_temps():
    results = {}
    for label, s_id in TEMP_SENSORS.items():
        sensor_file = os.path.join(W1_DEVICE_PATH, s_id, "temperature")
        try:
            if os.path.exists(sensor_file):
                with open(sensor_file, "r") as f:
                    raw_temp = f.read().strip()
                    results[label] = round(float(raw_temp) / 1000.0, 2)
            # else: skip or add error
        except Exception:
            pass
    return results

if __name__ == "__main__":
    print(json.dumps(get_temps()))
