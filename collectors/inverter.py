#!/usr/bin/env python3
import subprocess
import json
import time

def get_inverter_data():
    command = ["/home/pi/.local/bin/mpp-solar", "-p", "/dev/hidraw0", "-c", "QPIGS", "-o", "json"]
    try:
        # On actual hardware, we might need retries. Here we'll do one attempt for simplicity.
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=15)
        full_data = json.loads(result.stdout)
        keys = list(full_data.keys())
        if len(keys) > 2:
            return {k: full_data[k] for k in keys[2:]}
        return full_data
    except Exception as e:
        return {"inverter_error": str(e)}

if __name__ == "__main__":
    print(json.dumps(get_inverter_data()))
