#!/usr/bin/env python3
import requests
import json

def get_solar_predict():
    RATED_CAPACITY_W = 1300
    EFFICIENCY = 0.8
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
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if "hourly" not in data:
            return {"solar_error": "Invalid API response"}
        gti_values = data["hourly"]["global_tilted_irradiance"]
        total_wh = 0
        for gti in gti_values:
            if gti is not None:
                total_wh += gti / 1000 * RATED_CAPACITY_W * EFFICIENCY
        return {"solar_prediction": round(total_wh, 2)}
    except Exception as e:
        return {"solar_error": str(e)}

if __name__ == "__main__":
    print(json.dumps(get_solar_predict()))
