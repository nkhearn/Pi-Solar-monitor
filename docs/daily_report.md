# 📋 Daily Report

The Daily Report provides a summarized overview of your solar system's performance for a selected 24-hour period (00:00:00 to 23:59:59).

## 📊 Metrics Explained

### Total Solar Yield
- **What it is:** The total amount of energy produced by your solar panels throughout the day.
- **Simplistic Math:** It's the sum of all `pv_input_power` (in Watts) readings taken every minute, divided by 60 to convert Watt-minutes to Watt-hours (Wh).
- **Formula:** `Σ(pv_input_power) / 60`

### PV Power Clipping
- **What it is:** Solar energy lost because your panels were capable of producing more power than your inverter could handle at that moment.
- **Simplistic Math:** We look at your power data during the day and try to fit a "perfect" bell curve (Gaussian curve) to the points where you weren't clipping. The area between this theoretical curve and your actual power is the "missed" energy.
- **Status:**
    - **Normal:** Actual peak is close to the theoretical peak.
    - **Clipping Detected:** Actual peak is significantly lower than what the curve suggests was possible.

### Solar Self-Consumption
- **What it is:** The percentage of solar energy that was used directly by your home as it was being generated, rather than being stored in the battery.
- **Simplistic Math:** Total Solar Yield minus the energy that went into charging the battery, expressed as a percentage of the total solar yield.
- **Formula:** `((Total Solar Yield - Battery Charge Energy) / Total Solar Yield) * 100`

### Battery Efficiency
- **What it is:** A measure of how much energy you successfully retrieved from your battery compared to how much you put into it that day.
- **Simplistic Math:** Total energy discharged from the battery divided by total energy charged into the battery.
- **Formula:** `(Total Battery Discharge Energy / Total Battery Charge Energy) * 100`

### Solar Harvest Efficiency
- **What it is:** How well your actual solar production matched the forecast for that day.
- **Simplistic Math:** Your actual Total Solar Yield divided by the maximum predicted value from your solar forecast collector.
- **Formula:** `(Actual Yield / Predicted Yield) * 100`

### Peak Load Hour
- **What it is:** The specific hour during the day when your home's average electricity consumption was at its highest.
- **Simplistic Math:** We calculate the average `ac_output_active_power` for each of the 24 hours and identify the one with the highest average.

### Energy Source: AC Input
- **What it is:** The percentage of your total energy consumption that came from the grid or a generator (AC Input) rather than from solar or battery.
- **Simplistic Math:** Total AC Input energy divided by the sum of all energy sources (AC Input + Solar + Battery Discharge).
- **Formula:** `(AC Input Energy / (AC Input Energy + Solar Yield + Battery Discharge Energy)) * 100`

---
*Note: Some metrics may show "Partial Data" if there are fewer than 1300 data points (out of 1440 possible minutes) for the day.*
