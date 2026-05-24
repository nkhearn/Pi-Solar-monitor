# 📋 Daily Report

The Daily Report provides a summarized overview of your solar system's performance for a selected 24-hour period (00:00:00 to 23:59:59).

Access it by clicking the 📋 icon in the main dashboard header.

## 📊 Metrics Explained

### Total Solar Yield
- **What it is:** The total amount of energy produced by your solar panels throughout the day.
- **Math:** Sum of all `pv_input_power` (Watts) readings, divided by 60 to convert to Watt-hours (Wh).

### Missed Solar Potential
- **What it is:** Estimated solar energy lost because it exceeded your inverter's capacity (clipping).
- **Math:** We fit a Gaussian (bell) curve to your actual power data to predict what the "perfect" curve would have been without clipping. The difference between this theoretical curve and your actual production is the missed potential.
- **Status:**
    - **Normal:** Actual peak matches or is close to the theoretical peak.
    - **Clipping Detected:** Actual peak is significantly flattened compared to the theoretical curve.

### Unstored Solar Usage
- **What it is:** The percentage of solar energy consumed directly by your home as it was generated, rather than being stored in the battery.
- **Math:** `((Total Solar Yield - Battery Charge Energy) / Total Solar Yield) * 100`

### Battery Efficiency
- **What it is:** How much energy you retrieved from the battery compared to what was put in that day.
- **Math:** `(Total Battery Discharge Energy / Total Battery Charge Energy) * 100`

### Solar Harvest Efficiency
- **What it is:** How well your actual solar production matched the forecast for that day.
- **Math:** `(Actual Yield / Max Predicted Yield) * 100`

### Peak Load Hour
- **What it is:** The hour during the day with the highest average electricity consumption.
- **Math:** The average `ac_output_active_power` is calculated for each of the 24 hours to find the peak.

### Energy Source: AC Input
- **What it is:** The percentage of your total daily energy consumption that came from the grid or a generator (AC Input).
- **Math:** `(AC Input Energy / (AC Input Energy + Solar Yield + Battery Discharge Energy)) * 100`

---

## ⚠️ Data Accuracy

### Partial Data Warning
A **"Partial Data"** badge will appear on metric cards if the system detects fewer than 1300 data points for the day (a full day should have 1440 minutely samples). This often happens if the Pi was powered off or if there were communication issues with the inverter during the day.

### Data Handling
The system handles non-numeric data (e.g., error strings like "Invalid response CRCs") by defaulting those specific samples to `0.0`, ensuring the daily calculations can still complete without crashing.

---

## 👩‍💻 Developer Guide: Customizing Metrics

You can add, remove, or modify metrics by editing the `generate_report_data` function in `daily_report.py`.

### 🛠️ Metric Data Schema
Each metric is a Python dictionary with the following keys:
- `title`: (Required) The name displayed on the card.
- `value`: (Required) The numerical or string value.
- `unit`: (Optional) Units string (e.g., 'Wh', '%').
- `html_description`: (Required) The explanation shown when the card is expanded.
- `description`: (Optional) Small sub-text shown below the value.
- `status`: (Optional) Accent text (e.g., 'Normal', 'High').
- `partial`: (Boolean) Triggers the 'Partial Data' warning badge.
- `error`: (Optional) Displays an error message instead of the value.

### ➕ Adding a New Metric
1.  **Retrieve Data**: Use the `get_clean_series(key)` helper to get a NumPy array of data for any database key or virtual metric.
2.  **Calculate**: Perform your calculations using NumPy or standard Python.
3.  **Append**: Add your metric dictionary to the `results` list.

**Example:**
```python
# 1. Get data for 'water_temp'
temps = get_clean_series('water_temp')

# 2. Calculate average
avg_temp = np.mean(temps) if len(temps) > 0 else 0

# 3. Append to results
results.append({
    "title": "Avg Water Temp",
    "value": round(avg_temp, 1),
    "unit": "°C",
    "partial": is_partial,
    "html_description": "The average temperature of the water tank today."
})
```

### ❌ Removing or Editing Metrics
- **To remove**: Simply comment out or delete the `results.append(...)` block for that metric.
- **To edit**: Modify the logic or dictionary values within the existing blocks in `daily_report.py`.

### ⚠️ Important: JSON Serialization
The API converts all results to JSON. Since NumPy types (like `np.float64`) are not JSON-serializable by default, the system automatically runs `.item()` on all numeric values before returning. If you add complex nested structures, ensure they contain only native Python types.
