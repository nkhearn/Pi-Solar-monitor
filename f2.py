#!/usr/bin/env python3
import os
import json
import requests
import subprocess
import time
import asyncio
import aiohttp
from datetime import datetime

# ================= CONFIGURATION =================
EMONCMS_URL = "http://127.0.0.1"  # No trailing slash
WRITE_API_KEY = "c304a3fb502903718d3da4e69d76b4b8"
NODE_NAME = "Inverter"
MACRODROID_URL = "https://trigger.macrodroid.com/UUID/power"
PYTHONANYWHERE_URL = "https://nhearn.eu.pythonanywhere.com/store/"

# Path for DS18B20 1-wire sensors
W1_DEVICE_PATH = "/sys/bus/w1/devices/"

# Sensor ID Map: { "Friendly Name": "Serial ID" }
TEMP_SENSORS = {
    'water_in': "28-00000ac879c7",
    'water_out': "28-00000ac8e16c"
}

# ================= DATA COLLECTION FUNCTIONS =================

def get_solar_predict():
    # --- Constants & Configuration ---
    # System: 1.3 kW (1300 W)
    RATED_CAPACITY_W = 1300
    STC_IRRADIANCE_WM2 = 1000 
    SCALING_FACTOR = RATED_CAPACITY_W / STC_IRRADIANCE_WM2 # 1.3
    EFFICIENCY = 0.8

    # Open-Meteo API URL for Eday, Orkney
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": 59.25,
        "longitude": -2.83,
        "hourly": "global_tilted_irradiance",
        "tilt": 12,
        "azimuth": 100,
        "forecast_days": 1
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        if "hourly" not in data:
            return {"error": "Invalid API response"}

        gti_values = data["hourly"]["global_tilted_irradiance"]

        total_wh = 0
        for gti in gti_values:
            if gti is not None:
                # Calculate Wh for this hour and add to total
                total_wh += gti / 1000 * RATED_CAPACITY_W * EFFICIENCY

        # Return as a single variable instead of a date-keyed dictionary
        return {"solar_prediction": round(total_wh, 2)}

    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


def get_inverter_data():
    """
    Executes the mpp-solar command and parses the JSON output.
    Filters out metadata and returns only relevant inverter metrics.
    Includes retry logic for robustness.
    """
    command = ["/home/pi/.local/bin/mpp-solar", "-p", "/dev/hidraw0", "-c", "QPIGS", "-o", "json"]
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            full_data = json.loads(result.stdout)
            
            # mpp-solar often includes metadata in the first few keys (e.g., 'command', 'unit')
            keys = list(full_data.keys())
            # Safety check before slicing
            if len(keys) > 2:
                return {k: full_data[k] for k in keys[2:]}
            return full_data

        except (subprocess.CalledProcessError, json.JSONDecodeError, Exception) as e:
            print(f"Inverter Error (Attempt {attempt + 1}/{max_retries}): {e}")
            time.sleep(2)
            
    return {}


def get_temps():
    """
    Reads DS18B20 temperature sensors directly from the 1-wire filesystem.
    Returns temperatures in Celsius.
    """
    results = {}
    
    for label, s_id in TEMP_SENSORS.items():
        sensor_file = os.path.join(W1_DEVICE_PATH, s_id, "temperature")
        try:
            if os.path.exists(sensor_file):
                with open(sensor_file, "r") as f:
                    raw_temp = f.read().strip()
                    # Convert millidegrees to degrees Celsius
                    results[label] = round(float(raw_temp) / 1000.0, 2)
            else:
                print(f"Warning: Sensor {label} ({s_id}) not found.")
        except Exception as e:
            print(f"Temp Sensor Error ({label}): {e}")
            
    return results


def get_meta_data():
    """
    Returns standard metadata like Unix timestamp for EmonCMS.
    """
    now = datetime.now()
    return {
        "time": time.time(), # EmonCMS prefers Unix timestamps for 'time' field
        "timestamp": int(now.timestamp()), # Integer timestamp as used in r1.py
        "local_date": int(now.strftime("%Y%m%d")),
        "local_time": int(now.strftime("%H%M%S"))
    }


# ================= COMMUNICATION =================

def send_to_emoncms(payload_dict):
    """
    Sends the aggregated data dictionary to the EmonCMS local/remote server.
    """
    if not payload_dict:
        print("No data to send.")
        return

    try:
        # Construct the request
        url = f"{EMONCMS_URL}/input/post"
        payload = {
            'node': NODE_NAME,
            'fulljson': json.dumps(payload_dict),
            'apikey': WRITE_API_KEY
        }
        
        response = requests.post(url, data=payload, timeout=10)
        
        # EmonCMS can return "ok" or a JSON success object
        is_success = response.text == "ok"
        if not is_success:
            try:
                is_success = response.json().get("success") is True
            except (ValueError, AttributeError):
                pass

        if is_success:
            print(f"Success: Sent {len(payload_dict)} data points.")
        else:
            print(f"EmonCMS Error: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"Connection Error: {e}")


async def send_to_macrodroid(payload_dict):
    """
    Asynchronously sends data to Macrodroid webhook.
    """
    headers = {'Content-Type': 'application/json'}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(MACRODROID_URL, json=payload_dict, headers=headers) as response:
                if response.status == 200:
                    print("Macrodroid Triggered Successfully")
                else:
                    text = await response.text()
                    print(f"Macrodroid Error: {response.status} - {text}")
    except Exception as e:
        print(f"Macrodroid Connection Error: {e}")


async def send_to_pythonanywhere(payload_dict):
    """
    Asynchronously sends data to PythonAnywhere.
    """
    headers = {'Content-Type': 'application/json'}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(PYTHONANYWHERE_URL, json=payload_dict, headers=headers) as response:
                if response.status == 200:
                    print("PythonAnywhere Upload Successful")
                else:
                    text = await response.text()
                    print(f"PythonAnywhere Error: {response.status} - {text}")
    except Exception as e:
        print(f"PythonAnywhere Connection Error: {e}")


async def broadcast_async_data(payload):
    """
    Orchestrates concurrent asynchronous uploads.
    """
    await asyncio.gather(
        send_to_macrodroid(payload),
        send_to_pythonanywhere(payload)
    )


# ================= MAIN RUNNER =================

def main():
    """
    Orchestrates the data collection and transmission.
    """
    print(f"--- Run Started: {datetime.now()} ---")
    
    # 1. Collect all data into a single flat dictionary
    final_payload = {}
    
    # List of collectors to iterate through
    collectors = [get_solar_predict, get_meta_data, get_inverter_data, get_temps]
    
    for collect_func in collectors:
        data = collect_func()
        if data:
            final_payload.update(data)

    # 2. Upload to EmonCMS and Remote Services
    if final_payload:
        # Send to EmonCMS (Synchronous)
        send_to_emoncms(final_payload)
        
        # Send to Async Services (Macrodroid, PythonAnywhere)
        try:
            asyncio.run(broadcast_async_data(final_payload))
        except Exception as e:
            print(f"Async Execution Error: {e}")
            
        # Debug: Print the payload to console
        print(json.dumps(final_payload, indent=2))
    else:
        print("Data collection failed, nothing to upload.")

if __name__ == "__main__":
    main()
